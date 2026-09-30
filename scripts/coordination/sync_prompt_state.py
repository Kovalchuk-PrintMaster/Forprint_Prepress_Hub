#!/usr/bin/env python3
"""ForPrint Prepress Hub module-owned Blueprint prompt intake.

Adapted from the proven ForPrint Logistics Service prompt-state automation
(`scripts/coordination/sync_prompt_state.py`) after the 2026-09-28 precedent audit.

Boundary:
- Blueprint is read-only.
- Writes are restricted to the current Prepress repository.
- This script does not stage, commit, push, release, or mutate Blueprint.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

MODULE_ID = "forprint_prepress_hub"
STRICT_BLUEPRINT_MARKER = "SYSTEM_BLUEPRINT_ACCESS_FROM_PREPRESS=READ_ONLY_STRICT"

READY_BLUEPRINT_STATUSES = {
    "ready_for_module_pull",
    "in_progress",
    "returned_for_fix",
}

TERMINAL_LOCAL_STATUSES = {
    "completed_in_module",
    "accepted_by_blueprint",
    "superseded",
}


@dataclass(frozen=True, slots=True)
class PromptSyncResult:
    active_prompt_id: str | None
    active_prompt_title: str | None
    received_files: tuple[str, ...]
    archived_files: tuple[str, ...]


def load_mapping(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def yaml_text(data: dict[str, Any]) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)


def write_text_if_changed(path: Path, content: str) -> bool:
    normalized = content.rstrip() + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == normalized:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(normalized, encoding="utf-8")
    return True


def write_yaml_if_changed(path: Path, data: dict[str, Any]) -> bool:
    return write_text_if_changed(path, yaml_text(data))


def copy_if_changed(source: Path, target: Path) -> bool:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and source.read_bytes() == target.read_bytes():
        return False
    shutil.copyfile(source, target)
    return True


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative_path(path: Path, project_root: Path) -> str:
    return path.resolve().relative_to(project_root.resolve()).as_posix()


def ensure_write_under_module(path: Path, project_root: Path) -> None:
    try:
        path.resolve().relative_to(project_root.resolve())
    except ValueError as exc:
        raise ValueError(f"Write target escapes Prepress module root: {path}") from exc


def sorted_queue(blueprint_index: dict[str, Any]) -> list[dict[str, Any]]:
    queue = blueprint_index.get("prompt_queue")
    if not isinstance(queue, list):
        raise ValueError("Blueprint prompt index must contain prompt_queue list")
    records = [record for record in queue if isinstance(record, dict)]
    return sorted(records, key=lambda record: int(record.get("sequence", 0)))


def execution_status(record: dict[str, Any]) -> str:
    execution = record.get("module_execution")
    if not isinstance(execution, dict):
        return "planned"
    return str(execution.get("status", "planned"))


def review_status(record: dict[str, Any]) -> str:
    review = record.get("blueprint_review")
    if not isinstance(review, dict):
        return "not_started"
    return str(review.get("status", "not_started"))


def record_file(record: dict[str, Any], blueprint_module_dir: Path) -> Path:
    value = record.get("file")
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Prompt {record.get('prompt_id')} has no file")

    base = blueprint_module_dir.resolve()
    path = (blueprint_module_dir / value).resolve()
    try:
        path.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"Blueprint prompt file escapes module queue: {value}") from exc

    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def normalize_local_index(
    local_index: dict[str, Any],
    module_id: str,
) -> dict[str, Any]:
    if local_index.get("module_id") != module_id:
        raise ValueError(f"Local prompt index module_id does not match {module_id}")

    schema = local_index.get("schema_version")

    if schema == "module_prompt_index_v0_1":
        prompts = local_index.get("prompts")
        if prompts is None:
            local_index["prompts"] = []
        elif not isinstance(prompts, list):
            raise ValueError("Local prompt index prompts must be a list")
        local_index.setdefault("active_prompt_id", None)
        return local_index

    if schema == "forprint_prompt_index_v0_1":
        if local_index.get("status") != "bootstrap_empty":
            raise ValueError("Unsupported legacy Prepress prompt index state")

        for key in ("received", "active", "archived"):
            value = local_index.get(key, [])
            if value not in (None, []):
                raise ValueError(
                    f"Legacy Prepress prompt index {key} must be empty before migration"
                )

        return {
            "schema_version": "module_prompt_index_v0_1",
            "module_id": module_id,
            "prompts": [],
            "active_prompt_id": None,
        }

    raise ValueError(f"Unsupported local prompt index schema: {schema}")


def existing_prompt_map(
    local_index: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    prompts = local_index.get("prompts", [])
    if not isinstance(prompts, list):
        raise ValueError("Local prompt index prompts must be a list")

    result: dict[str, dict[str, Any]] = {}
    for prompt in prompts:
        if not isinstance(prompt, dict):
            continue
        prompt_id = prompt.get("prompt_id")
        if isinstance(prompt_id, str):
            result[prompt_id] = dict(prompt)
    return result


def choose_active_prompt(
    records: list[dict[str, Any]],
    existing: dict[str, dict[str, Any]],
    requested_prompt_id: str | None,
) -> dict[str, Any] | None:
    by_id = {
        str(record["prompt_id"]): record
        for record in records
        if "prompt_id" in record
    }

    if requested_prompt_id:
        record = by_id.get(requested_prompt_id)

        if record is None:
            raise ValueError(
                f"Requested prompt is not present in Blueprint queue: "
                f"{requested_prompt_id}"
            )

        if (
            execution_status(record) == "completed_by_module"
            or review_status(record) == "accepted_by_blueprint"
        ):
            return None

        if execution_status(record) not in READY_BLUEPRINT_STATUSES:
            raise ValueError(
                f"Requested prompt is not consumable: "
                f"{requested_prompt_id}={execution_status(record)}"
            )

        return record

    current_active = [
        prompt_id
        for prompt_id, prompt in existing.items()
        if prompt.get("status") == "active"
    ]

    if len(current_active) > 1:
        raise ValueError(
            "Local prompt index contains multiple active prompts"
        )

    if current_active:
        active_id = current_active[0]
        record = by_id.get(active_id)

        if record is not None:
            if (
                execution_status(record) in READY_BLUEPRINT_STATUSES
                and review_status(record) != "accepted_by_blueprint"
            ):
                return record

    for record in records:
        prompt_id = str(record.get("prompt_id", ""))
        local_status = existing.get(
            prompt_id,
            {},
        ).get("status")

        if local_status in TERMINAL_LOCAL_STATUSES:
            continue

        if (
            execution_status(record) in READY_BLUEPRINT_STATUSES
            and review_status(record) != "accepted_by_blueprint"
        ):
            return record

    return None

def received_date(source_file: Path) -> str:
    prefix = source_file.name[:10]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", prefix):
        return prefix
    return datetime.now(ZoneInfo("Europe/Kyiv")).date().isoformat()


def build_local_entry(
    *,
    record: dict[str, Any],
    existing: dict[str, Any],
    source_file: Path,
    received_file: Path,
    active_file: Path,
    archived_file: Path,
    project_root: Path,
    module_id: str,
    active_prompt_id: str | None,
) -> dict[str, Any]:
    entry = dict(existing)

    execution = record.get("module_execution")
    review = record.get("blueprint_review")

    execution = (
        execution
        if isinstance(execution, dict)
        else {}
    )
    review = (
        review
        if isinstance(review, dict)
        else {}
    )

    prompt_id = str(record["prompt_id"])

    if prompt_id == active_prompt_id:
        local_status = "active"
    elif entry.get("status") in TERMINAL_LOCAL_STATUSES:
        local_status = str(entry["status"])
    elif execution_status(record) == "completed_by_module":
        local_status = "completed_in_module"
    elif review_status(record) == "accepted_by_blueprint":
        local_status = "accepted_by_blueprint"
    elif execution_status(record) in READY_BLUEPRINT_STATUSES:
        local_status = "received"
    else:
        local_status = execution_status(record)

    completion_report = (
        execution.get("completion_report")
        or entry.get("completion_report")
    )
    completion_commit = (
        execution.get("completion_commit")
        or entry.get("completion_commit")
    )

    entry.update(
        {
            "prompt_id": prompt_id,
            "sequence": int(record.get("sequence", 0)),
            "title": str(record.get("title", "")),
            "phase": str(record.get("phase", "")),
            "priority": str(record.get("priority", "normal")),
            "source": "forprint_system_blueprint",
            "source_file": (
                f"coordination/outgoing_prompts/"
                f"{module_id}/{record['file']}"
            ),
            "file": relative_path(
                received_file,
                project_root,
            ),
            "status": local_status,
            "received_at": entry.get(
                "received_at",
                received_date(source_file),
            ),
            "module_execution_status": execution_status(record),
            "blueprint_review_status": review_status(record),
            "completion_report": completion_report,
            "completion_commit": completion_commit,
            "blueprint_acceptance_commit": review.get(
                "acceptance_commit"
            ),
            "blueprint_accepted_at": review.get(
                "accepted_at"
            ),
        }
    )

    if active_file.is_file():
        entry["active_file"] = relative_path(
            active_file,
            project_root,
        )
    else:
        entry.pop("active_file", None)

    if archived_file.is_file():
        entry["archived_file"] = relative_path(
            archived_file,
            project_root,
        )
    else:
        entry.pop("archived_file", None)

    return entry

def render_prompt_status_section(
    *,
    record: dict[str, Any],
    received_file: Path,
    active_file: Path,
    project_root: Path,
) -> str:
    return f"""<!-- BEGIN ACTIVE_BLUEPRINT_PROMPT -->
## Active Blueprint prompt

- Prompt ID: `{record['prompt_id']}`
- Title: {record.get('title', '')}
- Phase: `{record.get('phase', '')}`
- Priority: `{record.get('priority', '')}`
- Blueprint queue status: `{execution_status(record)}`
- Received copy: `{relative_path(received_file, project_root)}`
- Active copy: `{relative_path(active_file, project_root)}`

Formal module prompt intake is synchronized. Verified module-side implementation state is tracked in the current status surfaces and is not reset by prompt synchronization.

`SYSTEM_BLUEPRINT_ACCESS_FROM_PREPRESS=READ_ONLY_STRICT`

System Blueprint remains strictly read-only from Prepress Hub. Any Blueprint-owned
change must be requested through module-owned evidence/handoff and executed from
the Blueprint context.
<!-- END ACTIVE_BLUEPRINT_PROMPT -->"""


def update_status_surfaces(
    *,
    status_yaml_path: Path,
    status_markdown_path: Path,
    record: dict[str, Any],
    received_file: Path,
    active_file: Path,
    project_root: Path,
) -> None:
    status = load_mapping(status_yaml_path)

    if status.get("module_id") != MODULE_ID:
        raise ValueError("Current status belongs to a different module")
    if status.get("production_write_enabled") is not False:
        raise ValueError("Prepress production_write_enabled must remain false")
    if status.get("graphic_design_lab_runtime_initialized") is not False:
        raise ValueError("Graphic Design Lab runtime must remain uninitialized")

    status["source_prompt_id"] = str(record["prompt_id"])
    existing_intake = status.get("prompt_intake")
    status["prompt_intake"] = {
        "status": "active",
        "source": "forprint_system_blueprint",
        "active_prompt_id": str(record["prompt_id"]),
        "blueprint_queue_status": execution_status(record),
        "received_file": relative_path(received_file, project_root),
        "active_file": relative_path(active_file, project_root),
        "implementation_started": (
            existing_intake.get("implementation_started", False)
            if isinstance(existing_intake, dict)
            else False
        ),
        "blueprint_access": "READ_ONLY_STRICT",
    }

    if isinstance(existing_intake, dict):
        for key in (
            "implementation_status",
            "implementation_commits",
            "next_contour_activated",
            "completion_report",
            "completion_commit",
            "completion_state",
        ):
            if key in existing_intake:
                status["prompt_intake"][key] = existing_intake[key]

    write_yaml_if_changed(status_yaml_path, status)

    current_md = status_markdown_path.read_text(encoding="utf-8")
    start = "<!-- BEGIN ACTIVE_BLUEPRINT_PROMPT -->"
    end = "<!-- END ACTIVE_BLUEPRINT_PROMPT -->"
    section = render_prompt_status_section(
        record=record,
        received_file=received_file,
        active_file=active_file,
        project_root=project_root,
    )

    if start in current_md or end in current_md:
        if current_md.count(start) != 1 or current_md.count(end) != 1:
            raise ValueError("Malformed active prompt section in current_status.md")
        before, tail = current_md.split(start, 1)
        _, after = tail.split(end, 1)
        merged = before.rstrip() + "\n\n" + section + after
    else:
        merged = current_md.rstrip() + "\n\n" + section + "\n"

    write_text_if_changed(status_markdown_path, merged)



def update_terminal_status_surfaces(
    *,
    status_yaml_path: Path,
    status_markdown_path: Path,
    record: dict[str, Any],
    archived_file: Path,
    project_root: Path,
) -> None:
    status = load_mapping(status_yaml_path)

    if status.get("module_id") != MODULE_ID:
        raise ValueError(
            "Current status belongs to a different module"
        )

    if status.get("production_write_enabled") is not False:
        raise ValueError(
            "Prepress production_write_enabled must remain false"
        )

    if (
        status.get("graphic_design_lab_runtime_initialized")
        is not False
    ):
        raise ValueError(
            "Graphic Design Lab runtime must remain uninitialized"
        )

    prompt_id = str(record["prompt_id"])

    status["status"] = "completed_in_module"
    status["source_prompt_id"] = prompt_id
    status["current_focus"] = (
        "gdl_guided_intake_creator_handoff_foundation_accepted"
    )
    status["next_expected_focus"] = (
        "separately_authorized_next_gdl_contour"
    )

    prompt_progress = status.get("prompt_progress")

    if not isinstance(prompt_progress, dict):
        prompt_progress = {}

    prompt_progress.update(
        {
            "intake": "completed",
            "implementation": "completed",
            "tests": "passed",
            "completion": "completed",
        }
    )

    status["prompt_progress"] = prompt_progress

    current_step = status.get("current_step")

    if not isinstance(current_step, dict):
        current_step = {}

    current_step.update(
        {
            "id": prompt_id,
            "status": "completed",
            "next_action": (
                "await_separately_authorized_next_gdl_contour"
            ),
        }
    )

    status["current_step"] = current_step

    intake = status.get("prompt_intake")

    if not isinstance(intake, dict):
        intake = {}

    intake["status"] = "completed_in_module"
    intake["source"] = "forprint_system_blueprint"
    intake["blueprint_queue_status"] = execution_status(record)
    intake["blueprint_review_status"] = review_status(record)
    intake["archived_file"] = relative_path(
        archived_file,
        project_root,
    )
    intake["completion_state"] = "ACCEPTED_BY_BLUEPRINT"
    intake["next_contour_activated"] = False
    intake["blueprint_access"] = "READ_ONLY_STRICT"

    review = record.get("blueprint_review")
    review = review if isinstance(review, dict) else {}

    intake["blueprint_acceptance_commit"] = review.get(
        "acceptance_commit"
    )
    intake["blueprint_accepted_at"] = review.get(
        "accepted_at"
    )

    intake.pop("active_prompt_id", None)
    intake.pop("active_file", None)

    status["prompt_intake"] = intake

    latest = status.get(
        "latest_gdl_intake_handoff_foundation"
    )

    if isinstance(latest, dict):
        latest["blueprint_acceptance"] = (
            "ACCEPTED_BOUNDED_FOUNDATION"
        )
        latest["next_contour_activated"] = False

    write_yaml_if_changed(
        status_yaml_path,
        status,
    )

    current_md = status_markdown_path.read_text(
        encoding="utf-8"
    )

    begin = "<!-- BEGIN ACTIVE_BLUEPRINT_PROMPT -->"
    end = "<!-- END ACTIVE_BLUEPRINT_PROMPT -->"

    if current_md.count(begin) != 1:
        raise ValueError(
            "Expected exactly one prompt section begin marker"
        )

    if current_md.count(end) != 1:
        raise ValueError(
            "Expected exactly one prompt section end marker"
        )

    before, tail = current_md.split(begin, 1)
    _, after = tail.split(end, 1)

    accepted_at = review.get("accepted_at")

    section = f"""<!-- BEGIN ACTIVE_BLUEPRINT_PROMPT -->
## Completed Blueprint prompt

- Prompt ID: `{prompt_id}`
- Module execution: `{execution_status(record)}`
- Blueprint review: `{review_status(record)}`
- Blueprint accepted at: `{accepted_at}`
- Protocol acceptance commit: `{review.get('acceptance_commit')}`
- Local prompt state: `completed_in_module`
- Archived copy: `{relative_path(archived_file, project_root)}`
- Next contour activated: `false`

The bounded GDL Guided Intake / Creator Handoff foundation
is canonically accepted by System Blueprint.

This acceptance does not activate a subsequent GDL contour.

`SYSTEM_BLUEPRINT_ACCESS_FROM_PREPRESS=READ_ONLY_STRICT`
<!-- END ACTIVE_BLUEPRINT_PROMPT -->"""

    merged = (
        before.rstrip()
        + "\n\n"
        + section
        + after
    )

    merged = merged.replace(
        "## Local completion ready for Blueprint review",
        "## Local completion accepted by Blueprint",
    )

    merged = merged.replace(
        "- Blueprint review: pending",
        "- Blueprint review: accepted_by_blueprint",
    )

    stale = (
        "The local prompt remains visible as the current "
        "synchronized Blueprint prompt\n"
        "until Blueprint-side review changes authoritative "
        "queue/review state.\n"
        "Prepress does not mutate that Blueprint state directly."
    )

    replacement = (
        "The completed prompt is archived in the module-local "
        "prompt lifecycle.\n"
        "No next GDL contour is activated by this acceptance."
    )

    merged = merged.replace(
        stale,
        replacement,
    )

    write_text_if_changed(
        status_markdown_path,
        merged,
    )

    questions_path = status_yaml_path.with_name(
        "next_questions_for_blueprint.md"
    )

    if questions_path.is_file():
        questions = questions_path.read_text(
            encoding="utf-8"
        )

        marker = (
            "## GDL intake/handoff completion review request"
        )

        if marker in questions:
            prefix = questions.split(
                marker,
                1,
            )[0].rstrip()

            questions = (
                prefix
                + "\n\n"
                + "## GDL intake/handoff acceptance recorded\n\n"
                + "The bounded Guided Intake / Creator Handoff "
                + "foundation has been accepted by System Blueprint.\n\n"
                + "There is no remaining Blueprint review request "
                + "for this contour.\n\n"
                + "Any subsequent GDL execution contour requires "
                + "separate Human Owner / Blueprint authorization.\n\n"
                + "`SYSTEM_BLUEPRINT_ACCESS_FROM_PREPRESS="
                + "READ_ONLY_STRICT`\n"
            )

            write_text_if_changed(
                questions_path,
                questions,
            )

def sync_prompt_state(
    *,
    module_id: str,
    blueprint_index_path: Path,
    blueprint_module_dir: Path,
    received_dir: Path,
    active_dir: Path,
    archived_dir: Path,
    local_index_path: Path,
    status_yaml_path: Path,
    status_markdown_path: Path,
    prompt_id: str | None = None,
) -> PromptSyncResult:
    project_root = local_index_path.resolve().parents[2]

    for write_target in (
        received_dir,
        active_dir,
        archived_dir,
        local_index_path,
        status_yaml_path,
        status_markdown_path,
    ):
        ensure_write_under_module(write_target, project_root)

    blueprint_index = load_mapping(blueprint_index_path)
    if blueprint_index.get("module") != module_id:
        raise ValueError(f"Blueprint prompt index module does not match {module_id}")

    records = sorted_queue(blueprint_index)
    local_index = normalize_local_index(load_mapping(local_index_path), module_id)
    existing = existing_prompt_map(local_index)

    received_dir.mkdir(parents=True, exist_ok=True)
    active_dir.mkdir(parents=True, exist_ok=True)
    archived_dir.mkdir(parents=True, exist_ok=True)

    source_files: dict[str, Path] = {}
    received_files: dict[str, Path] = {}

    for record in records:
        record_prompt_id = str(record["prompt_id"])
        source = record_file(record, blueprint_module_dir)
        received = received_dir / source.name
        copy_if_changed(source, received)
        source_files[record_prompt_id] = source
        received_files[record_prompt_id] = received

    selected = choose_active_prompt(records, existing, prompt_id)
    active_prompt_id = str(selected["prompt_id"]) if selected is not None else None
    selected_name = (
        source_files[active_prompt_id].name
        if active_prompt_id is not None
        else None
    )

    for active_path in active_dir.glob("*.md"):
        if active_path.name == selected_name:
            continue
        archived_path = archived_dir / active_path.name
        copy_if_changed(active_path, archived_path)
        active_path.unlink()

    active_file_by_id: dict[str, Path] = {}

    if active_prompt_id is not None:
        selected_received = received_files[active_prompt_id]
        selected_active = active_dir / selected_received.name
        selected_archived = archived_dir / selected_received.name

        if selected_archived.exists():
            selected_archived.unlink()

        copy_if_changed(selected_received, selected_active)
        active_file_by_id[active_prompt_id] = selected_active

    entries: list[dict[str, Any]] = []
    for record in records:
        record_prompt_id = str(record["prompt_id"])
        source = source_files[record_prompt_id]
        received = received_files[record_prompt_id]
        active = active_file_by_id.get(
            record_prompt_id,
            active_dir / source.name,
        )
        archived = archived_dir / source.name

        entries.append(
            build_local_entry(
                record=record,
                existing=existing.get(record_prompt_id, {}),
                source_file=source,
                received_file=received,
                active_file=active,
                archived_file=archived,
                project_root=project_root,
                module_id=module_id,
                active_prompt_id=active_prompt_id,
            )
        )

    local_index = {
        "schema_version": "module_prompt_index_v0_1",
        "module_id": module_id,
        "prompts": sorted(entries, key=lambda item: int(item.get("sequence", 0))),
        "active_prompt_id": active_prompt_id,
    }
    write_yaml_if_changed(local_index_path, local_index)

    if selected is not None and active_prompt_id is not None:
        update_status_surfaces(
            status_yaml_path=status_yaml_path,
            status_markdown_path=status_markdown_path,
            record=selected,
            received_file=received_files[active_prompt_id],
            active_file=active_file_by_id[active_prompt_id],
            project_root=project_root,
        )

    if selected is None:
        terminal_from_active = [
            record
            for record in records
            if existing.get(
                str(record["prompt_id"]),
                {},
            ).get("status") == "active"
            and (
                execution_status(record) == "completed_by_module"
                or review_status(record) == "accepted_by_blueprint"
            )
        ]

        if len(terminal_from_active) > 1:
            raise ValueError(
                "Multiple previously active prompts became terminal"
            )

        if len(terminal_from_active) == 1:
            terminal_record = terminal_from_active[0]
            terminal_id = str(
                terminal_record["prompt_id"]
            )

            update_terminal_status_surfaces(
                status_yaml_path=status_yaml_path,
                status_markdown_path=status_markdown_path,
                record=terminal_record,
                archived_file=(
                    archived_dir
                    / source_files[terminal_id].name
                ),
                project_root=project_root,
            )

    return PromptSyncResult(
        active_prompt_id=active_prompt_id,
        active_prompt_title=(
            str(selected.get("title", "")) if selected is not None else None
        ),
        received_files=tuple(
            relative_path(path, project_root)
            for path in sorted(received_files.values())
        ),
        archived_files=tuple(
            relative_path(path, project_root)
            for path in sorted(archived_dir.glob("*.md"))
        ),
    )


def validate_prompt_state(
    *,
    local_index_path: Path,
    status_yaml_path: Path,
    received_dir: Path,
    active_dir: Path,
) -> list[str]:
    errors: list[str] = []

    try:
        local_index = load_mapping(local_index_path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return [
            f"Unable to read local prompt index: {exc}"
        ]

    try:
        status = load_mapping(status_yaml_path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return [
            f"Unable to read current status: {exc}"
        ]

    prompts = local_index.get("prompts")

    if not isinstance(prompts, list):
        return [
            "Local prompt index prompts must be a list"
        ]

    project_root = local_index_path.resolve().parents[2]

    prompt_entries = [
        entry
        for entry in prompts
        if isinstance(entry, dict)
    ]

    prompt_ids: list[str] = []

    for entry in prompt_entries:
        prompt_id = entry.get("prompt_id")

        if (
            not isinstance(prompt_id, str)
            or not prompt_id.strip()
        ):
            errors.append(
                "Every prompt entry must contain "
                "a non-empty prompt_id"
            )
            continue

        prompt_ids.append(prompt_id)

        received_value = entry.get("file")

        if (
            not isinstance(received_value, str)
            or not received_value.strip()
        ):
            errors.append(
                f"Prompt {prompt_id} has no received file path"
            )
            continue

        received_path = project_root / received_value

        if not received_path.is_file():
            errors.append(
                f"Received prompt file is missing for "
                f"{prompt_id}: {received_value}"
            )

    if len(prompt_ids) != len(set(prompt_ids)):
        errors.append(
            "Local prompt index contains duplicate prompt_id values"
        )

    active_files = sorted(
        active_dir.glob("*.md")
    )

    active_entries = [
        entry
        for entry in prompt_entries
        if entry.get("status") == "active"
    ]

    active_prompt_id = local_index.get(
        "active_prompt_id"
    )

    prompt_intake = status.get("prompt_intake")

    if not isinstance(prompt_intake, dict):
        errors.append(
            "Current status must contain prompt_intake mapping"
        )
        prompt_intake = {}

    intake_status = prompt_intake.get("status")

    active_mode = bool(
        active_files
        or active_entries
        or active_prompt_id is not None
        or intake_status == "active"
    )

    # --------------------------------------------------------------
    # ACTIVE MODE
    # --------------------------------------------------------------

    if active_mode:
        if len(active_files) != 1:
            errors.append(
                "coordination/prompts/active must contain "
                "exactly one Markdown prompt"
            )

        if len(active_entries) != 1:
            errors.append(
                "Local prompt index must contain "
                "exactly one active prompt entry"
            )

        if (
            not isinstance(active_prompt_id, str)
            or not active_prompt_id.strip()
        ):
            errors.append(
                "active_prompt_id must identify "
                "the active prompt"
            )

        if intake_status != "active":
            errors.append(
                "Current status prompt intake must be active"
            )

        if len(active_entries) == 1:
            entry = active_entries[0]
            entry_prompt_id = entry.get("prompt_id")

            if active_prompt_id != entry_prompt_id:
                errors.append(
                    "active_prompt_id does not match "
                    "the active prompt entry"
                )

            if (
                status.get("source_prompt_id")
                != entry_prompt_id
            ):
                errors.append(
                    "Current status active prompt does not "
                    "match local prompt index"
                )

            if (
                prompt_intake.get("active_prompt_id")
                != entry_prompt_id
            ):
                errors.append(
                    "Current status prompt intake active prompt "
                    "does not match local prompt index"
                )

            expected_active = entry.get("active_file")

            if (
                not isinstance(expected_active, str)
                or not expected_active.strip()
            ):
                errors.append(
                    "Active prompt entry has no active_file path"
                )
            else:
                expected_active_path = (
                    project_root / expected_active
                )

                if (
                    len(active_files) == 1
                    and expected_active_path.resolve()
                    != active_files[0].resolve()
                ):
                    errors.append(
                        "Active prompt file does not match "
                        "index active_file"
                    )

            received_value = entry.get("file")

            if (
                isinstance(received_value, str)
                and len(active_files) == 1
            ):
                received_file = (
                    project_root / received_value
                )

                if (
                    received_file.is_file()
                    and active_files[0].read_bytes()
                    != received_file.read_bytes()
                ):
                    errors.append(
                        "Active prompt differs from "
                        "its received copy"
                    )

        if (
            prompt_intake.get("blueprint_access")
            != "READ_ONLY_STRICT"
        ):
            errors.append(
                "Current status must preserve strict "
                "Blueprint read-only boundary"
            )

        implementation_started = prompt_intake.get(
            "implementation_started"
        )

        if not isinstance(
            implementation_started,
            bool,
        ):
            errors.append(
                "Current status implementation_started "
                "must be boolean"
            )

        elif implementation_started is True:
            if (
                prompt_intake.get(
                    "implementation_status"
                )
                != "VERIFIED_LOCAL_IMPLEMENTATION_PUBLISHED"
            ):
                errors.append(
                    "Started implementation must carry "
                    "verified local implementation status"
                )

            commits = prompt_intake.get(
                "implementation_commits"
            )

            if (
                not isinstance(commits, list)
                or not commits
            ):
                errors.append(
                    "Started implementation must carry "
                    "implementation commit evidence"
                )

    # --------------------------------------------------------------
    # TERMINAL MODE
    # --------------------------------------------------------------

    else:
        if active_files:
            errors.append(
                "Completed prompt state must not contain "
                "files in coordination/prompts/active"
            )

        if active_entries:
            errors.append(
                "Completed prompt state must not contain "
                "an active prompt index entry"
            )

        if active_prompt_id is not None:
            errors.append(
                "active_prompt_id must be null "
                "when no prompt is active"
            )

        source_prompt_id = status.get(
            "source_prompt_id"
        )

        if (
            not isinstance(source_prompt_id, str)
            or not source_prompt_id.strip()
        ):
            errors.append(
                "Terminal current status must contain "
                "source_prompt_id"
            )
        else:
            matching = [
                entry
                for entry in prompt_entries
                if entry.get("prompt_id")
                == source_prompt_id
            ]

            if len(matching) != 1:
                errors.append(
                    "Terminal current status must match "
                    "exactly one prompt index entry"
                )
            else:
                entry = matching[0]
                entry_status = entry.get("status")

                if (
                    entry_status
                    not in TERMINAL_LOCAL_STATUSES
                ):
                    errors.append(
                        "Terminal prompt index entry must "
                        "have a terminal local status"
                    )

                if "active_file" in entry:
                    errors.append(
                        "Terminal prompt entry must not "
                        "retain active_file"
                    )

                archived_value = entry.get(
                    "archived_file"
                )

                if (
                    not isinstance(archived_value, str)
                    or not archived_value.strip()
                ):
                    errors.append(
                        "Terminal prompt entry must "
                        "contain archived_file"
                    )
                else:
                    archived_file = (
                        project_root / archived_value
                    )

                    if not archived_file.is_file():
                        errors.append(
                            "Archived prompt file is missing: "
                            f"{archived_value}"
                        )
                    else:
                        received_value = entry.get("file")

                        if isinstance(
                            received_value,
                            str,
                        ):
                            received_file = (
                                project_root
                                / received_value
                            )

                            if (
                                received_file.is_file()
                                and archived_file.read_bytes()
                                != received_file.read_bytes()
                            ):
                                errors.append(
                                    "Archived prompt differs "
                                    "from its received copy"
                                )

                if (
                    entry_status
                    == "completed_in_module"
                ):
                    if (
                        entry.get(
                            "module_execution_status"
                        )
                        != "completed_by_module"
                    ):
                        errors.append(
                            "Completed module prompt must "
                            "record module_execution_status "
                            "as completed_by_module"
                        )

                    if not entry.get(
                        "completion_report"
                    ):
                        errors.append(
                            "Completed module prompt must "
                            "contain completion_report"
                        )

                    if not entry.get(
                        "completion_commit"
                    ):
                        errors.append(
                            "Completed module prompt must "
                            "contain completion_commit"
                        )

                if (
                    entry.get(
                        "blueprint_review_status"
                    )
                    == "accepted_by_blueprint"
                    and prompt_intake.get(
                        "completion_state"
                    )
                    != "ACCEPTED_BY_BLUEPRINT"
                ):
                    errors.append(
                        "Accepted Blueprint prompt must "
                        "record ACCEPTED_BY_BLUEPRINT "
                        "completion_state"
                    )

        if (
            intake_status
            not in TERMINAL_LOCAL_STATUSES
        ):
            errors.append(
                "Terminal prompt intake must have "
                "a terminal local status"
            )

        if (
            prompt_intake.get(
                "blueprint_queue_status"
            )
            != "completed_by_module"
        ):
            errors.append(
                "Terminal prompt intake must record "
                "completed_by_module Blueprint queue status"
            )

        if (
            prompt_intake.get(
                "blueprint_review_status"
            )
            != "accepted_by_blueprint"
        ):
            errors.append(
                "Terminal prompt intake must record "
                "accepted_by_blueprint review status"
            )

        if (
            prompt_intake.get(
                "next_contour_activated"
            )
            is not False
        ):
            errors.append(
                "Terminal acceptance must not activate "
                "the next contour"
            )

        if (
            prompt_intake.get("blueprint_access")
            != "READ_ONLY_STRICT"
        ):
            errors.append(
                "Terminal status must preserve strict "
                "Blueprint read-only boundary"
            )

        prompt_progress = status.get(
            "prompt_progress"
        )

        if (
            not isinstance(prompt_progress, dict)
            or prompt_progress.get("completion")
            != "completed"
        ):
            errors.append(
                "Terminal prompt status must record "
                "prompt_progress.completion as completed"
            )

    # --------------------------------------------------------------
    # GLOBAL SAFETY BOUNDARIES
    # --------------------------------------------------------------

    if (
        status.get("production_write_enabled")
        is not False
    ):
        errors.append(
            "Production write must remain disabled"
        )

    if (
        status.get(
            "graphic_design_lab_runtime_initialized"
        )
        is not False
    ):
        errors.append(
            "Graphic Design Lab runtime must remain "
            "uninitialized"
        )

    return errors

def print_prompt_status(
    local_index_path: Path,
) -> int:
    data = load_mapping(local_index_path)

    prompts = [
        prompt
        for prompt in data.get("prompts", [])
        if isinstance(prompt, dict)
    ]

    active = [
        prompt
        for prompt in prompts
        if prompt.get("status") == "active"
    ]

    if len(active) == 1:
        prompt = active[0]

        print("Active local prompt")
        print(f"Prompt ID: {prompt['prompt_id']}")
        print(f"Title: {prompt.get('title', '')}")
        print(f"Phase: {prompt.get('phase', '')}")
        print(f"Priority: {prompt.get('priority', '')}")
        print(f"Received: {prompt.get('file', '')}")
        print(f"Active: {prompt.get('active_file', '')}")
        print(
            "Blueprint module status: "
            f"{prompt.get('module_execution_status', '')}"
        )
        print(
            "Blueprint review status: "
            f"{prompt.get('blueprint_review_status', '')}"
        )
        return 0

    if len(active) > 1:
        print("Local prompt state invalid: multiple active prompts")
        return 1

    if data.get("active_prompt_id") is not None:
        print(
            "Local prompt state invalid: dangling active_prompt_id"
        )
        return 1

    terminal = [
        prompt
        for prompt in prompts
        if prompt.get("status") in TERMINAL_LOCAL_STATUSES
    ]

    if not terminal:
        print("Local prompt state: no active or terminal prompt")
        return 1

    prompt = sorted(
        terminal,
        key=lambda item: int(item.get("sequence", 0)),
    )[-1]

    print("Terminal local prompt")
    print(f"Prompt ID: {prompt['prompt_id']}")
    print(f"Status: {prompt.get('status', '')}")
    print(
        "Blueprint module status: "
        f"{prompt.get('module_execution_status', '')}"
    )
    print(
        "Blueprint review status: "
        f"{prompt.get('blueprint_review_status', '')}"
    )
    print(
        "Completion report: "
        f"{prompt.get('completion_report', '')}"
    )
    print(
        "Completion commit: "
        f"{prompt.get('completion_commit', '')}"
    )
    print(
        "Archived: "
        f"{prompt.get('archived_file', '')}"
    )

    return 0

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Synchronize and validate the current Prepress Blueprint prompt."
    )
    parser.add_argument("--module-id", default=MODULE_ID)
    parser.add_argument(
        "--blueprint-index",
        type=Path,
        default=Path(
            "../forprint_system_blueprint/coordination/outgoing_prompts/"
            "forprint_prepress_hub/index.yaml"
        ),
    )
    parser.add_argument(
        "--blueprint-module-dir",
        type=Path,
        default=Path(
            "../forprint_system_blueprint/coordination/outgoing_prompts/"
            "forprint_prepress_hub"
        ),
    )
    parser.add_argument("--received-dir", type=Path, default=Path("coordination/prompts/received"))
    parser.add_argument("--active-dir", type=Path, default=Path("coordination/prompts/active"))
    parser.add_argument("--archived-dir", type=Path, default=Path("coordination/prompts/archived"))
    parser.add_argument("--local-index", type=Path, default=Path("coordination/prompts/index.yaml"))
    parser.add_argument("--status-yaml", type=Path, default=Path("coordination/status/current_status.yaml"))
    parser.add_argument("--status-md", type=Path, default=Path("coordination/status/current_status.md"))
    parser.add_argument("--prompt-id")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--status-only", action="store_true")
    args = parser.parse_args()

    if args.status_only:
        return print_prompt_status(args.local_index)

    if args.check_only:
        errors = validate_prompt_state(
            local_index_path=args.local_index,
            status_yaml_path=args.status_yaml,
            received_dir=args.received_dir,
            active_dir=args.active_dir,
        )
        if errors:
            print("Prompt state check failed:")
            for error in errors:
                print(f"  - {error}")
            return 1
        print("Prompt state check passed.")
        print(STRICT_BLUEPRINT_MARKER)
        return 0

    try:
        result = sync_prompt_state(
            module_id=args.module_id,
            blueprint_index_path=args.blueprint_index,
            blueprint_module_dir=args.blueprint_module_dir,
            received_dir=args.received_dir,
            active_dir=args.active_dir,
            archived_dir=args.archived_dir,
            local_index_path=args.local_index,
            status_yaml_path=args.status_yaml,
            status_markdown_path=args.status_md,
            prompt_id=(args.prompt_id or None),
        )
    except (FileNotFoundError, OSError, ValueError, yaml.YAMLError) as exc:
        print(f"Prompt synchronization failed: {exc}")
        return 1

    print("Blueprint prompts synchronized locally.")
    print(f"Active prompt: {result.active_prompt_id or 'none'}")
    for path in result.received_files:
        print(f"Received: {path}")
    for path in result.archived_files:
        print(f"Archived: {path}")
    print(STRICT_BLUEPRINT_MARKER)
    print("BLUEPRINT_MUTATED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

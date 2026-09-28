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
                f"Requested prompt is not present in Blueprint queue: {requested_prompt_id}"
            )
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
        raise ValueError("Local prompt index contains multiple active prompts")

    if current_active:
        active_id = current_active[0]
        record = by_id.get(active_id)
        if record is not None and execution_status(record) in READY_BLUEPRINT_STATUSES:
            return record

    for record in records:
        prompt_id = str(record.get("prompt_id", ""))
        local_status = existing.get(prompt_id, {}).get("status")
        if local_status in TERMINAL_LOCAL_STATUSES:
            continue
        if execution_status(record) in READY_BLUEPRINT_STATUSES:
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
    execution = execution if isinstance(execution, dict) else {}
    review = review if isinstance(review, dict) else {}

    prompt_id = str(record["prompt_id"])
    if prompt_id == active_prompt_id:
        local_status = "active"
    elif entry.get("status") in TERMINAL_LOCAL_STATUSES:
        local_status = str(entry["status"])
    elif execution_status(record) in READY_BLUEPRINT_STATUSES:
        local_status = "received"
    else:
        local_status = execution_status(record)

    entry.update(
        {
            "prompt_id": prompt_id,
            "sequence": int(record.get("sequence", 0)),
            "title": str(record.get("title", "")),
            "phase": str(record.get("phase", "")),
            "priority": str(record.get("priority", "normal")),
            "source": "forprint_system_blueprint",
            "source_file": (
                f"coordination/outgoing_prompts/{module_id}/{record['file']}"
            ),
            "file": relative_path(received_file, project_root),
            "status": local_status,
            "received_at": entry.get("received_at", received_date(source_file)),
            "module_execution_status": execution_status(record),
            "blueprint_review_status": review_status(record),
            "completion_report": execution.get("completion_report"),
            "completion_commit": execution.get("completion_commit"),
            "blueprint_acceptance_commit": review.get("acceptance_commit"),
            "blueprint_accepted_at": review.get("accepted_at"),
        }
    )

    if active_file.is_file():
        entry["active_file"] = relative_path(active_file, project_root)
    else:
        entry.pop("active_file", None)

    if archived_file.is_file():
        entry["archived_file"] = relative_path(archived_file, project_root)
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

Formal module prompt intake is synchronized. Implementation has not started yet.

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
    status["prompt_intake"] = {
        "status": "active",
        "source": "forprint_system_blueprint",
        "active_prompt_id": str(record["prompt_id"]),
        "blueprint_queue_status": execution_status(record),
        "received_file": relative_path(received_file, project_root),
        "active_file": relative_path(active_file, project_root),
        "implementation_started": False,
        "blueprint_access": "READ_ONLY_STRICT",
    }

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
        status = load_mapping(status_yaml_path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return [f"Unable to read prompt/status state: {exc}"]

    if local_index.get("schema_version") != "module_prompt_index_v0_1":
        errors.append("Local prompt index must use module_prompt_index_v0_1")

    prompts = local_index.get("prompts")
    if not isinstance(prompts, list):
        return errors + ["Local prompt index prompts must be a list"]

    project_root = local_index_path.resolve().parents[2]
    prompt_entries = [item for item in prompts if isinstance(item, dict)]
    active_entries = [
        item for item in prompt_entries if item.get("status") == "active"
    ]
    active_files = sorted(active_dir.glob("*.md"))
    active_prompt_id = local_index.get("active_prompt_id")

    if len(active_entries) != 1:
        errors.append("Local prompt index must contain exactly one active prompt entry")
    if len(active_files) != 1:
        errors.append(
            "coordination/prompts/active must contain exactly one Markdown prompt"
        )
    if not isinstance(active_prompt_id, str) or not active_prompt_id.strip():
        errors.append("active_prompt_id must identify the active prompt")

    if len(active_entries) == 1 and len(active_files) == 1:
        entry = active_entries[0]
        active_file = active_files[0]

        if entry.get("prompt_id") != active_prompt_id:
            errors.append("active_prompt_id does not match active prompt entry")

        received_value = entry.get("file")
        active_value = entry.get("active_file")

        if not isinstance(received_value, str):
            errors.append("Active prompt entry has no received file path")
        else:
            received_file = project_root / received_value
            if not received_file.is_file():
                errors.append(f"Received prompt file is missing: {received_value}")
            elif file_hash(received_file) != file_hash(active_file):
                errors.append("Active prompt differs from received prompt")

        if not isinstance(active_value, str):
            errors.append("Active prompt entry has no active_file path")
        else:
            expected_active = project_root / active_value
            if expected_active.resolve() != active_file.resolve():
                errors.append("Active prompt file does not match index active_file")

    prompt_intake = status.get("prompt_intake")
    if not isinstance(prompt_intake, dict):
        errors.append("Current status must contain prompt_intake mapping")
    else:
        if prompt_intake.get("status") != "active":
            errors.append("Current status prompt_intake.status must be active")
        if prompt_intake.get("active_prompt_id") != active_prompt_id:
            errors.append("Current status active prompt does not match local prompt index")
        if prompt_intake.get("blueprint_access") != "READ_ONLY_STRICT":
            errors.append("Current status must preserve strict Blueprint read-only boundary")
        if prompt_intake.get("implementation_started") is not False:
            errors.append("Prompt intake commissioning must not claim implementation started")

    if status.get("production_write_enabled") is not False:
        errors.append("Production write must remain disabled")
    if status.get("graphic_design_lab_runtime_initialized") is not False:
        errors.append("Graphic Design Lab runtime must remain uninitialized")

    return errors


def print_prompt_status(local_index_path: Path) -> int:
    data = load_mapping(local_index_path)
    prompts = data.get("prompts", [])
    active = [
        prompt
        for prompt in prompts
        if isinstance(prompt, dict) and prompt.get("status") == "active"
    ]

    if len(active) != 1:
        print("Active prompt: invalid or missing")
        return 1

    prompt = active[0]
    print("Active local prompt")
    print(f"Prompt ID: {prompt['prompt_id']}")
    print(f"Title: {prompt.get('title', '')}")
    print(f"Phase: {prompt.get('phase', '')}")
    print(f"Priority: {prompt.get('priority', '')}")
    print(f"Received: {prompt.get('file', '')}")
    print(f"Active: {prompt.get('active_file', '')}")
    print("Blueprint module status: " + str(prompt.get("module_execution_status", "")))
    print("Blueprint review status: " + str(prompt.get("blueprint_review_status", "")))
    print(STRICT_BLUEPRINT_MARKER)
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

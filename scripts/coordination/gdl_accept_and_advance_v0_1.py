#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import yaml

REQUEST_SCHEMA = "gdl_accept_and_advance_request_v0_1"
EVIDENCE_SCHEMA = "gdl_accept_and_advance_evidence_v0_1"
SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")

PLAN_REL = Path(
    "coordination/graphic_design_lab/directions/greeting_cards/"
    "end_to_end_execution_plan_v0_1.yaml"
)
CURSOR_REL = Path(
    "coordination/graphic_design_lab/continuity/"
    "current_execution_cursor_v0_1.yaml"
)
EVIDENCE_DIR_REL = Path(
    "coordination/graphic_design_lab/execution/accept_and_advance"
)
CLOSEOUT_REL = Path(
    "coordination/graphic_design_lab/execution/"
    "current_transition_closeout_v0_1.json"
)

FORBIDDEN_PRIVATE_MARKERS = (
    "/srv/smb/",
    "\\\\192.168.",
    "+380",
)


class GdlAcceptAndAdvanceError(RuntimeError):
    pass


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise GdlAcceptAndAdvanceError(
            f"cannot load YAML: {path}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise GdlAcceptAndAdvanceError(
            f"expected YAML mapping: {path}"
        )
    return data


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _safe_id(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or SAFE_ID.fullmatch(value) is None
    ):
        raise GdlAcceptAndAdvanceError(
            f"{label} must be a safe non-empty id"
        )
    return value


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _atomic_write_yaml(path: Path, value: dict[str, Any]) -> None:
    _atomic_write_text(
        path,
        yaml.safe_dump(
            value,
            sort_keys=False,
            allow_unicode=True,
            width=100,
        ),
    )


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    _atomic_write_text(
        path,
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )


def _snapshot(paths: list[Path]) -> dict[Path, bytes | None]:
    return {
        path: path.read_bytes() if path.exists() else None
        for path in paths
    }


def _restore(snapshot: dict[Path, bytes | None]) -> None:
    for path, payload in snapshot.items():
        if payload is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)


def _iter_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _iter_strings(key)
            yield from _iter_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_strings(item)


def _validate_private_markers(request: dict[str, Any]) -> None:
    for text in _iter_strings(request):
        for marker in FORBIDDEN_PRIVATE_MARKERS:
            if marker in text:
                raise GdlAcceptAndAdvanceError(
                    "request contains forbidden private/live path marker"
                )


def _identity(request: dict[str, Any]) -> dict[str, Any]:
    if request.get("schema_version") != REQUEST_SCHEMA:
        raise GdlAcceptAndAdvanceError("request schema mismatch")

    operation_id = _safe_id(request.get("operation_id"), "operation_id")
    if request.get("explicit_operator_input") is not True:
        raise GdlAcceptAndAdvanceError(
            "explicit_operator_input=true is required"
        )

    task_id = _safe_id(request.get("task_id"), "task_id")

    accept = request.get("accept")
    if not isinstance(accept, dict):
        raise GdlAcceptAndAdvanceError("accept must be a mapping")
    if accept.get("decision") != "ACCEPT":
        raise GdlAcceptAndAdvanceError(
            "only an explicit ACCEPT decision is supported"
        )
    if accept.get("explicit_operator_input") is not True:
        raise GdlAcceptAndAdvanceError(
            "accept.explicit_operator_input=true is required"
        )
    current_step_id = _safe_id(
        accept.get("step_id"),
        "accept.step_id",
    )
    completion_evidence = accept.get("completion_evidence")
    if not isinstance(completion_evidence, dict):
        raise GdlAcceptAndAdvanceError(
            "accept.completion_evidence must be a mapping"
        )

    advance = request.get("advance")
    if not isinstance(advance, dict):
        raise GdlAcceptAndAdvanceError("advance must be a mapping")
    if advance.get("mode") != "activate_explicit_step":
        raise GdlAcceptAndAdvanceError(
            "advance.mode must be activate_explicit_step"
        )
    if advance.get("explicit_operator_input") is not True:
        raise GdlAcceptAndAdvanceError(
            "advance.explicit_operator_input=true is required"
        )
    next_step_id = _safe_id(
        advance.get("expected_step_id"),
        "advance.expected_step_id",
    )
    checkpoint_id = _safe_id(
        advance.get("current_checkpoint_id"),
        "advance.current_checkpoint_id",
    )
    next_action = advance.get("next_action")
    if not isinstance(next_action, str) or not next_action.strip():
        raise GdlAcceptAndAdvanceError(
            "advance.next_action is required"
        )

    closeout = request.get("closeout")
    if not isinstance(closeout, dict):
        raise GdlAcceptAndAdvanceError("closeout must be a mapping")
    commit_message = closeout.get("commit_message")
    if not isinstance(commit_message, str) or not commit_message.strip():
        raise GdlAcceptAndAdvanceError(
            "closeout.commit_message is required"
        )

    _validate_private_markers(request)

    return {
        "operation_id": operation_id,
        "task_id": task_id,
        "current_step_id": current_step_id,
        "next_step_id": next_step_id,
        "checkpoint_id": checkpoint_id,
        "next_action": next_action.strip(),
        "completion_evidence": completion_evidence,
        "commit_message": commit_message.strip(),
        "request_fingerprint_sha256": canonical_sha256(request),
    }


def _task(cursor: dict[str, Any], task_id: str) -> dict[str, Any]:
    tasks = cursor.get("active_tasks")
    if not isinstance(tasks, list):
        raise GdlAcceptAndAdvanceError(
            "cursor.active_tasks must be a list"
        )
    matches = [
        item
        for item in tasks
        if isinstance(item, dict)
        and item.get("task_id") == task_id
    ]
    if len(matches) != 1:
        raise GdlAcceptAndAdvanceError(
            f"expected one active task {task_id}, got {len(matches)}"
        )
    return matches[0]


def _steps(plan: dict[str, Any]) -> list[dict[str, Any]]:
    raw = plan.get("steps")
    if not isinstance(raw, list):
        raise GdlAcceptAndAdvanceError("plan.steps must be a list")
    if not all(isinstance(item, dict) for item in raw):
        raise GdlAcceptAndAdvanceError(
            "every plan step must be a mapping"
        )
    return raw


def _step_map(
    steps: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in steps:
        step_id = item.get("id")
        if not isinstance(step_id, str) or not step_id:
            raise GdlAcceptAndAdvanceError(
                "every plan step requires id"
            )
        if step_id in result:
            raise GdlAcceptAndAdvanceError(
                f"duplicate plan step id: {step_id}"
            )
        result[step_id] = item
    return result


def _dependency_blockers(
    step: dict[str, Any],
    steps: dict[str, dict[str, Any]],
    *,
    assumed_completed: set[str],
) -> list[str]:
    blockers: list[str] = []
    for field in ("depends_on", "blocked_by"):
        raw = step.get(field, [])
        if raw is None:
            continue
        if not isinstance(raw, list):
            raise GdlAcceptAndAdvanceError(
                f"{field} must be a list when present"
            )
        for dependency_id in raw:
            if not isinstance(dependency_id, str):
                raise GdlAcceptAndAdvanceError(
                    f"{field} values must be step ids"
                )
            dependency = steps.get(dependency_id)
            if dependency is None:
                blockers.append(
                    f"{field}:{dependency_id}:missing"
                )
                continue
            if (
                dependency_id not in assumed_completed
                and dependency.get("state") != "COMPLETED_LOCAL"
            ):
                blockers.append(
                    f"{field}:{dependency_id}:"
                    f"{dependency.get('state')}"
                )
    return blockers


def validate_state_consistency(
    plan: dict[str, Any],
    cursor: dict[str, Any],
    task_id: str,
) -> None:
    steps = _steps(plan)
    task = _task(cursor, task_id)

    active_ids = [
        item["id"]
        for item in steps
        if item.get("state") == "ACTIVE"
    ]
    if active_ids != [task.get("current_step")]:
        raise GdlAcceptAndAdvanceError(
            "plan/cursor active-step mismatch: "
            f"plan={active_ids} cursor={task.get('current_step')}"
        )

    completed_ids = [
        item["id"]
        for item in steps
        if item.get("state") == "COMPLETED_LOCAL"
    ]
    if task.get("completed_steps") != completed_ids:
        raise GdlAcceptAndAdvanceError(
            "plan/cursor completed-step mismatch"
        )

    checkpoint = task.get("current_checkpoint")
    if not isinstance(checkpoint, dict):
        raise GdlAcceptAndAdvanceError(
            "cursor.current_checkpoint must be a mapping"
        )
    if checkpoint.get("state") != "ACTIVE":
        raise GdlAcceptAndAdvanceError(
            "cursor.current_checkpoint must be ACTIVE"
        )
    next_action = task.get("next_action")
    if not isinstance(next_action, str) or not next_action.strip():
        raise GdlAcceptAndAdvanceError(
            "cursor.next_action must be non-empty"
        )


def _validate_exit_evidence(
    current: dict[str, Any],
    completion_evidence: dict[str, Any],
) -> None:
    criteria = current.get("exit_criteria")
    if not isinstance(criteria, list) or not criteria:
        raise GdlAcceptAndAdvanceError(
            "active step must declare exit_criteria"
        )
    satisfied = completion_evidence.get("exit_criteria_satisfied")
    if not isinstance(satisfied, dict):
        raise GdlAcceptAndAdvanceError(
            "completion evidence requires exit_criteria_satisfied mapping"
        )
    missing = [
        criterion
        for criterion in criteria
        if satisfied.get(criterion) is not True
    ]
    if missing:
        raise GdlAcceptAndAdvanceError(
            "completion evidence does not satisfy exit criteria: "
            + ", ".join(missing)
        )


def _evidence_path(root: Path, operation_id: str) -> Path:
    return root / EVIDENCE_DIR_REL / f"{operation_id}.yaml"


def _git_head(root: Path) -> str:
    cp = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if cp.returncode:
        raise GdlAcceptAndAdvanceError(
            "cannot resolve repository HEAD"
        )
    return cp.stdout.strip()


def _step_block_span(text: str, step_id: str) -> tuple[int, int]:
    pattern = re.compile(
        rf"(?ms)^  - id: {re.escape(step_id)}\n.*?(?=^  - id: |\Z)"
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise GdlAcceptAndAdvanceError(
            f"expected one textual plan block for {step_id}, got {len(matches)}"
        )
    return matches[0].span()


def _render_completion_evidence(
    evidence: dict[str, Any],
) -> str:
    rendered = yaml.safe_dump(
        {"completion_evidence": evidence},
        sort_keys=False,
        allow_unicode=True,
        width=100,
    ).rstrip("\n")
    return "\n".join(
        "    " + line if line else line
        for line in rendered.splitlines()
    )


def _mutate_plan_text(
    source: str,
    identity: dict[str, Any],
) -> str:
    current_start, current_end = _step_block_span(
        source,
        identity["current_step_id"],
    )
    current = source[current_start:current_end]
    state_line = "    state: ACTIVE"
    if current.count(state_line) != 1:
        raise GdlAcceptAndAdvanceError(
            "current textual step does not contain one ACTIVE state"
        )
    if "    completion_evidence:" in current:
        raise GdlAcceptAndAdvanceError(
            "current textual step already contains completion_evidence"
        )
    completion = _render_completion_evidence(
        identity["completion_evidence"]
    )
    current = current.replace(
        state_line,
        "    state: COMPLETED_LOCAL\n\n" + completion,
        1,
    )
    source = source[:current_start] + current + source[current_end:]

    next_start, next_end = _step_block_span(
        source,
        identity["next_step_id"],
    )
    candidate = source[next_start:next_end]
    planned_line = "    state: PLANNED"
    if candidate.count(planned_line) != 1:
        raise GdlAcceptAndAdvanceError(
            "next textual step does not contain one PLANNED state"
        )
    candidate = candidate.replace(
        planned_line,
        "    state: ACTIVE",
        1,
    )
    return source[:next_start] + candidate + source[next_end:]


def _replace_one_pattern(
    source: str,
    pattern: str,
    replacement: str,
    label: str,
) -> str:
    updated, count = re.subn(
        pattern,
        replacement,
        source,
        count=1,
        flags=re.MULTILINE | re.DOTALL,
    )
    if count != 1:
        raise GdlAcceptAndAdvanceError(
            f"textual cursor mutation failed: {label}"
        )
    return updated


def _mutate_cursor_text(
    source: str,
    *,
    completed_ids: list[str],
    identity: dict[str, Any],
) -> str:
    completed = (
        "    completed_steps:\n"
        + "".join(f"      - {step_id}\n" for step_id in completed_ids)
        + "\n"
    )
    source = _replace_one_pattern(
        source,
        r"^    completed_steps:\n.*?(?=^    current_step:)",
        completed,
        "completed_steps",
    )
    source = _replace_one_pattern(
        source,
        r"^    current_step: .*?$",
        "    current_step: " + identity["next_step_id"],
        "current_step",
    )
    checkpoint = (
        "    current_checkpoint:\n"
        f"      id: {identity['checkpoint_id']}\n"
        "      state: ACTIVE\n\n"
    )
    source = _replace_one_pattern(
        source,
        r"^    current_checkpoint:\n.*?(?=^    next_action:)",
        checkpoint,
        "current_checkpoint",
    )
    action_lines = identity["next_action"].splitlines() or [identity["next_action"]]
    next_action = (
        "    next_action: >\n"
        + "\n".join("      " + line for line in action_lines)
        + "\n\n"
    )
    source = _replace_one_pattern(
        source,
        r"^    next_action: >\n.*?(?=^    completion_criterion:)",
        next_action,
        "next_action",
    )
    return source


def prepare_operation(
    root: Path,
    request: dict[str, Any],
) -> dict[str, Any]:
    identity = _identity(request)
    plan = load_yaml(root / PLAN_REL)
    cursor = load_yaml(root / CURSOR_REL)
    validate_state_consistency(
        plan,
        cursor,
        identity["task_id"],
    )

    steps = _steps(plan)
    by_id = _step_map(steps)
    current = by_id.get(identity["current_step_id"])
    if current is None:
        raise GdlAcceptAndAdvanceError(
            "accepted current step is missing from plan"
        )
    if current.get("state") != "ACTIVE":
        raise GdlAcceptAndAdvanceError(
            "accepted current step is not ACTIVE"
        )

    task = _task(cursor, identity["task_id"])
    if task.get("current_step") != identity["current_step_id"]:
        raise GdlAcceptAndAdvanceError(
            "request current step does not match cursor"
        )

    _validate_exit_evidence(
        current,
        identity["completion_evidence"],
    )

    candidate = by_id.get(identity["next_step_id"])
    if candidate is None:
        raise GdlAcceptAndAdvanceError(
            "explicit next step is missing from plan"
        )
    if candidate.get("state") != "PLANNED":
        raise GdlAcceptAndAdvanceError(
            "explicit next step is no longer activatable"
        )

    blockers = _dependency_blockers(
        candidate,
        by_id,
        assumed_completed={identity["current_step_id"]},
    )
    if blockers:
        raise GdlAcceptAndAdvanceError(
            "dependency eligibility failed: "
            + ", ".join(blockers)
        )

    return {
        "result_state": "READY_TO_APPLY",
        "operation_id": identity["operation_id"],
        "task_id": identity["task_id"],
        "accepted_step_id": identity["current_step_id"],
        "explicit_next_step_id": identity["next_step_id"],
        "selection_source": "explicit_operator_bound_candidate",
        "blind_current_step_increment_performed": False,
        "automatic_next_step_activation_performed": False,
        "request_fingerprint_sha256": (
            identity["request_fingerprint_sha256"]
        ),
    }


def _closeout_manifest(
    *,
    identity: dict[str, Any],
    head: str,
    evidence_rel: Path,
) -> dict[str, Any]:
    return {
        "schema_version": "forprint_project_closeout_manifest_v0_1",
        "workstream_id": identity["operation_id"],
        "expected_head": head,
        "commit_message": identity["commit_message"],
        "visual_confirmation": "PASS",
        "visual_confirmation_reason": (
            "NON_VISUAL_COORDINATION_TRANSITION_OPERATOR_REVIEW"
        ),
        "verified_counts": {
            "focused_transition_tests": 0,
            "full_governance_tests": 0,
        },
        "write_set": [
            PLAN_REL.as_posix(),
            CURSOR_REL.as_posix(),
            evidence_rel.as_posix(),
            CLOSEOUT_REL.as_posix(),
        ],
        "review_commands": [
            ["make", "gdl-accept-and-advance-check"],
            ["make", "governance-check"],
        ],
    }


def apply_operation(
    root: Path,
    request: dict[str, Any],
    *,
    operator_confirmation: str | None,
) -> dict[str, Any]:
    identity = _identity(request)

    if operator_confirmation != identity["operation_id"]:
        raise GdlAcceptAndAdvanceError(
            "operator confirmation must equal operation_id"
        )

    evidence_path = _evidence_path(
        root,
        identity["operation_id"],
    )
    if evidence_path.is_file():
        evidence = load_yaml(evidence_path)
        if evidence.get(
            "request_fingerprint_sha256"
        ) != identity["request_fingerprint_sha256"]:
            raise GdlAcceptAndAdvanceError(
                "operation_id already exists with different request"
            )
        return {
            **evidence,
            "result_state": "ALREADY_APPLIED",
        }

    preview = prepare_operation(root, request)

    plan_path = root / PLAN_REL
    cursor_path = root / CURSOR_REL
    closeout_path = root / CLOSEOUT_REL
    snapshot = _snapshot(
        [
            plan_path,
            cursor_path,
            evidence_path,
            closeout_path,
        ]
    )

    try:
        plan = load_yaml(plan_path)
        cursor = load_yaml(cursor_path)
        steps = _steps(plan)
        by_id = _step_map(steps)
        current = by_id[identity["current_step_id"]]
        candidate = by_id[identity["next_step_id"]]
        task = _task(cursor, identity["task_id"])

        current["state"] = "COMPLETED_LOCAL"
        current["completion_evidence"] = identity[
            "completion_evidence"
        ]
        candidate["state"] = "ACTIVE"

        task["completed_steps"] = [
            item["id"]
            for item in steps
            if item.get("state") == "COMPLETED_LOCAL"
        ]
        task["current_step"] = identity["next_step_id"]
        task["current_checkpoint"] = {
            "id": identity["checkpoint_id"],
            "state": "ACTIVE",
        }
        task["next_action"] = identity["next_action"]

        validate_state_consistency(
            plan,
            cursor,
            identity["task_id"],
        )

        completed_ids = list(task["completed_steps"])
        plan_text = _mutate_plan_text(
            plan_path.read_text(encoding="utf-8"),
            identity,
        )
        cursor_text = _mutate_cursor_text(
            cursor_path.read_text(encoding="utf-8"),
            completed_ids=completed_ids,
            identity=identity,
        )

        rendered_plan = yaml.safe_load(plan_text)
        rendered_cursor = yaml.safe_load(cursor_text)
        if not isinstance(rendered_plan, dict) or not isinstance(rendered_cursor, dict):
            raise GdlAcceptAndAdvanceError(
                "rendered transition YAML root must remain a mapping"
            )
        validate_state_consistency(
            rendered_plan,
            rendered_cursor,
            identity["task_id"],
        )

        _atomic_write_text(plan_path, plan_text)
        _atomic_write_text(cursor_path, cursor_text)

        head = _git_head(root)
        evidence_rel = (
            EVIDENCE_DIR_REL
            / f"{identity['operation_id']}.yaml"
        )
        evidence = {
            "schema_version": EVIDENCE_SCHEMA,
            "operation_id": identity["operation_id"],
            "request_fingerprint_sha256": (
                identity["request_fingerprint_sha256"]
            ),
            "task_id": identity["task_id"],
            "accepted_step_id": identity["current_step_id"],
            "activated_step_id": identity["next_step_id"],
            "selection_source": (
                "explicit_operator_bound_candidate"
            ),
            "dependency_eligibility": "PASS",
            "explicit_operator_confirmation": True,
            "blind_current_step_increment_performed": False,
            "automatic_next_step_activation_performed": False,
            "rollback_model": "EXACT_PRE_TRANSITION_SNAPSHOT",
            "git_mutation_performed": False,
            "blueprint_runtime_dependency": False,
            "blueprint_mutation_performed": False,
            "completion_evidence": identity[
                "completion_evidence"
            ],
            "source_head": head,
        }
        _atomic_write_yaml(evidence_path, evidence)

        manifest = _closeout_manifest(
            identity=identity,
            head=head,
            evidence_rel=evidence_rel,
        )
        _atomic_write_json(closeout_path, manifest)

        return {
            **preview,
            "result_state": "ACCEPT_AND_ADVANCE_APPLIED",
            "evidence_path": evidence_rel.as_posix(),
            "closeout_manifest": CLOSEOUT_REL.as_posix(),
        }
    except Exception:
        _restore(snapshot)
        raise


def _print_result(result: dict[str, Any], *, applied: bool) -> None:
    marker = (
        "GDL_ACCEPT_AND_ADVANCE_APPLY"
        if applied
        else "GDL_ACCEPT_AND_ADVANCE_PREVIEW"
    )
    print(f"{marker}=PASS")
    print(f"RESULT_STATE={result['result_state']}")
    print(f"OPERATION_ID={result['operation_id']}")
    print(
        "ACCEPTED_STEP_ID="
        + str(result.get("accepted_step_id", "-"))
    )
    print(
        "ACTIVATED_OR_EXPECTED_STEP_ID="
        + str(
            result.get(
                "activated_step_id",
                result.get("explicit_next_step_id", "-"),
            )
        )
    )
    if applied:
        print(
            "EVIDENCE_PATH="
            + str(result.get("evidence_path", "-"))
        )
        print(
            "CLOSEOUT_MANIFEST="
            + str(result.get("closeout_manifest", "-"))
        )
    print("GIT_MUTATION_PERFORMED=false")
    print("BLUEPRINT_MUTATION_PERFORMED=false")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--request", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--operator-confirmation")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    request = load_yaml(Path(args.request).resolve())

    if args.apply:
        result = apply_operation(
            root,
            request,
            operator_confirmation=args.operator_confirmation,
        )
    else:
        result = prepare_operation(root, request)

    _print_result(result, applied=args.apply)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GdlAcceptAndAdvanceError as exc:
        print("GDL_ACCEPT_AND_ADVANCE=FAIL")
        print(f"ERROR={exc}")
        raise SystemExit(2)

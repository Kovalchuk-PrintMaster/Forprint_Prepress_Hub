#!/usr/bin/env python3
"""Read-only GDL index/cursor/execution plan consistency gate."""
from __future__ import annotations

import argparse
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
GDL = Path("coordination/graphic_design_lab")
INDEX = GDL / "index.yaml"


def validate(root: Path = ROOT) -> list[str]:
    """Return errors; no file mutation and no hardcoded current step."""
    root = Path(root).resolve()
    errors: list[str] = []
    index_path = root / INDEX
    if not index_path.is_file():
        return ["INDEX_MISSING"]
    try:
        index = yaml.safe_load(index_path.read_text(encoding="utf-8"))
        nav = index["local_execution"]
        cursor_path = root / GDL / nav["cursor"]
        plan_path = root / GDL / nav["current_execution_plan"]
        for candidate in (cursor_path, plan_path):
            candidate.resolve().relative_to((root / GDL).resolve())
        cursor = yaml.safe_load(cursor_path.read_text(encoding="utf-8"))
        plan = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError) as exc:
        return ["SOURCE_INVALID:" + type(exc).__name__ + ":" + str(exc)]

    active = [task for task in cursor.get("active_tasks", [])
              if task.get("task_id") == nav.get("current_primary_task")]
    if len(active) != 1:
        return ["PRIMARY_TASK_NOT_UNIQUE_OR_MISSING"]
    task = active[0]
    step_id = task.get("current_step")
    if nav.get("current_step") != step_id:
        errors.append("INDEX_CURSOR_STEP_MISMATCH:" + str(nav.get("current_step")) + ":" + str(step_id))
    if nav.get("current_direction") != task.get("direction_id"):
        errors.append("INDEX_CURSOR_DIRECTION_MISMATCH")
    if plan.get("direction_id") != task.get("direction_id"):
        errors.append("PLAN_CURSOR_DIRECTION_MISMATCH")
    steps = plan.get("steps") or []
    matches = [step for step in steps if step.get("id") == step_id]
    if len(matches) != 1:
        errors.append("ACTIVE_STEP_MISSING_OR_DUPLICATE_IN_PLAN")
    elif matches[0].get("state") != "ACTIVE":
        errors.append("ACTIVE_STEP_NOT_ACTIVE_IN_PLAN:" + str(matches[0].get("state")))
    completed = set(task.get("completed_steps") or [])
    noncompleted = [step.get("id") for step in steps
                    if step.get("id") in completed and step.get("state") != "COMPLETED_LOCAL"]
    if noncompleted:
        errors.append("CURSOR_COMPLETED_STEP_NOT_COMPLETE_IN_PLAN:" + ",".join(map(str, noncompleted)))
    if nav.get("blueprint_access") != "READ_ONLY_STRICT":
        errors.append("BLUEPRINT_BOUNDARY_MISMATCH")
    if nav.get("blueprint_work_front_binding") is not False:
        errors.append("NAVIGATION_MUST_NOT_GRANT_BLUEPRINT_AUTHORITY")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    errors = validate(args.root)
    if errors:
        print("GDL_EXECUTION_NAVIGATION=FAIL")
        for error in errors:
            print("ERROR=" + error)
        return 2
    print("GDL_EXECUTION_NAVIGATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import shutil
from pathlib import Path
import yaml

from scripts.validation.check_gdl_execution_navigation import validate

ROOT = Path(__file__).resolve().parents[2]
FILES = (
    "coordination/graphic_design_lab/index.yaml",
    "coordination/graphic_design_lab/continuity/current_execution_cursor_v0_1.yaml",
    "coordination/graphic_design_lab/directions/greeting_cards/end_to_end_execution_plan_v0_1.yaml",
)


def test_current_gdl_index_cursor_plan_are_consistent():
    assert validate(ROOT) == []


def test_stale_navigation_fails_closed(tmp_path):
    for rel in FILES:
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, target)
    target = tmp_path / FILES[0]
    index = yaml.safe_load(target.read_text(encoding="utf-8"))
    index["local_execution"]["current_step"] = "GC-E2E-04"
    target.write_text(yaml.safe_dump(index, allow_unicode=True), encoding="utf-8")
    errors = validate(tmp_path)
    assert any(error.startswith("INDEX_CURSOR_STEP_MISMATCH:") for error in errors)


def test_future_cursor_step_cannot_pass_without_plan_transition(tmp_path):
    for rel in FILES:
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, target)
    index_path = tmp_path / FILES[0]
    cursor_path = tmp_path / FILES[1]
    index = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    cursor = yaml.safe_load(cursor_path.read_text(encoding="utf-8"))
    index["local_execution"]["current_step"] = "GC-E2E-10"
    cursor["active_tasks"][0]["current_step"] = "GC-E2E-10"
    index_path.write_text(yaml.safe_dump(index, allow_unicode=True), encoding="utf-8")
    cursor_path.write_text(yaml.safe_dump(cursor, allow_unicode=True), encoding="utf-8")
    errors = validate(tmp_path)
    assert any(error.startswith("ACTIVE_STEP_NOT_ACTIVE_IN_PLAN:") for error in errors)

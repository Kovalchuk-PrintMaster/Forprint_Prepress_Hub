from __future__ import annotations
import json
from pathlib import Path

import pytest
import yaml

from scripts.coordination import module_assistant_context as c

ROOT = Path(__file__).resolve().parents[2]


def test_gdl_governance_strategy_semantics():
    strategy = yaml.safe_load((ROOT / "coordination/graphic_design_lab/continuity/governed_execution_strategy_v0_1.yaml").read_text(encoding="utf-8"))
    assert strategy["authority"]["blueprint_access_from_prepress"] == "READ_ONLY_STRICT"
    assert strategy["authority"]["blueprint_governed_worker_runtime_not_duplicated_in_gdl"] is True
    assert strategy["before_any_new_capability"]["decision_sequence"][0] == "INVENTORY"
    assert strategy["handoff_and_reporting"]["structured_ai_to_ai_handoff_required"] is True
    assert strategy["continuity_contract"]["absence_of_required_context_file_is_pack_failure"] is True
    assert strategy["current_work_admission"]["no_blind_next_step_activation"] is True


def test_gdl_strategy_is_always_included_and_scope_is_complete():
    candidates = {p.relative_to(ROOT).as_posix() for p in c.local_candidates(ROOT, "MODULE_CONTEXT", ["graphic_design_lab"])}
    candidates.update(p.relative_to(ROOT).as_posix() for p in c.scope_priority_candidates(ROOT, "graphic_design_lab"))
    assert "coordination/graphic_design_lab/continuity/governed_execution_strategy_v0_1.yaml" in candidates
    assert set(c.GDL_REQUIRED_CONTEXT_FILES).issubset(candidates)


def test_gdl_scope_resolves_from_topic():
    assert c.effective_scope_for_topics("bootstrap", ["graphic_design_lab"]) == "graphic_design_lab"
    assert "coordination/graphic_design_lab/continuity/governed_execution_strategy_v0_1.yaml" in c.ALWAYS_LOCAL


def test_pack_generator_guards_required_files():
    required = set(c.GDL_REQUIRED_CONTEXT_FILES)
    assert len(required) >= 7
    assert "coordination/graphic_design_lab/continuity/current_execution_cursor_v0_1.yaml" in required
    assert "coordination/graphic_design_lab/directions/greeting_cards/end_to_end_execution_plan_v0_1.yaml" in required
    assert "coordination/graphic_design_lab/continuity/roadmap_execution_alignment_2026_10_10_v0_1.yaml" in required

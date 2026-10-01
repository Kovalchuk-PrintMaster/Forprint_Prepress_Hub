from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/coordination/gdl_empirical_learning.py"
FIXTURE = ROOT / "tests/fixtures/graphic_design_lab/gdl_empirical_case_menu_sanitized_v0_1.yaml"
SCHEMA = ROOT / "coordination/roadmaps/graphic_design_lab/planning_evidence/empirical_learning/schemas/empirical_case_template_v0_1.yaml"
PROTOCOL = ROOT / "coordination/roadmaps/graphic_design_lab/planning_evidence/empirical_learning/operator_intake_experiment_protocol_v0_1.yaml"

spec = importlib.util.spec_from_file_location("gdl_empirical_learning", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def load(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_schema_covers_authorized_empirical_case_surface():
    assert module.validate_schema_surface(load(SCHEMA)) == []


def test_sanitized_fixture_validates_without_pii_or_heavy_artifact():
    case = load(FIXTURE)
    assert module.validate_case(case) == []
    assert case["artifact_policy"]["pii_allowed_in_git"] is False
    assert case["artifact_policy"]["repository_contains_heavy_artifact"] is False
    assert case["result"]["external_artifact_ref"]


def test_operator_customer_outcomes_remain_distinct():
    case = load(FIXTURE)
    assert "operator_acceptance" in case["outcome"]
    assert "customer_acceptance" in case["outcome"]
    assert "customer_explicit_satisfaction" in case["outcome"]


def test_possible_email_is_rejected_from_case_evidence():
    case = copy.deepcopy(load(FIXTURE))
    case["input_context"]["raw_summary"] = "Contact test@example.com"
    assert "case_possible_customer_pii_detected" in module.validate_case(case)


def test_metric_relationship_is_deterministic():
    case = copy.deepcopy(load(FIXTURE))
    case["outcome"]["first_attempt_accepted"] = True
    case["outcome"]["accepted_attempt"] = 2
    assert "case_first_attempt_metric_conflict" in module.validate_case(case)


def test_discovery_index_finds_live_menu_evidence_and_creator_v002():
    index = module.build_index()
    menu = next(
        item
        for item in index["experiments"]
        if item["experiment_id"] == "GDL-EXP-20261001-MENU-001"
    )
    assert "17_prompt_format_effect_observation.yaml" in menu["files"]
    assert "18_prompt_evolution_summary.md" in menu["files"]
    assert "19_prompt_evolution_source_manifest.yaml" in menu["files"]
    assert menu["file_count"] == 21
    assert menu["numbered_evidence_file_count"] == 20
    assert "v002" in index["registered_loaders"]["Creator Assistant"]


def test_summary_is_human_readable_and_non_authoritative():
    summary = module.render_summary(module.build_index())
    assert "GDL Empirical Learning Summary" in summary
    assert "LOCAL_EMPIRICAL_EVIDENCE_NOT_EXECUTION_AUTHORITY" in summary
    assert "GDL-EXP-20261001-MENU-001" in summary


def test_fresh_chat_protocol_preserves_authority_boundaries():
    protocol = load(PROTOCOL)
    assert protocol["mode"] == "MANUAL_EXPERIMENTAL"
    assert protocol["fresh_chat"]["operator_requires_design_skill"] is False
    assert protocol["uncertainty_policy"]["never_invent_missing_customer_facts"] is True
    assert protocol["authority"] == {
        "activates_runtime": False,
        "allows_provider_execution": False,
        "allows_production_write": False,
        "allows_automatic_customer_messaging": False,
        "mutates_blueprint": False,
        "activates_next_contour": False,
    }

from copy import deepcopy
from pathlib import Path

import yaml

from app.graphic_design_lab.greeting_card_photo_assessment import (
    validate_photo_assessment_package,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    ROOT
    / "tests/fixtures/graphic_design_lab/recurring_greeting_card_photo_assessment_v0_1.yaml"
)
ASSESSMENT_CONTRACT = (
    ROOT
    / "coordination/graphic_design_lab/directions/greeting_cards/"
    "per_photo_assessment_contract_v0_1.yaml"
)
TASK_CONTRACT = (
    ROOT
    / "coordination/graphic_design_lab/directions/greeting_cards/"
    "creator_portrait_task_contract_v0_1.yaml"
)


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def package():
    return load_yaml(FIXTURE)["photo_assessment_package"]


def test_contract_reuses_existing_creator_boundaries_without_execution():
    contract = load_yaml(ASSESSMENT_CONTRACT)
    assert contract["reuse"]["creator_task_boundary"]["disposition"] == "REUSE"
    assert (
        contract["reuse"]["creator_handoff_contract"]["disposition"]
        == "REUSE_AS_ENVELOPE_AND_AUTHORITY_BOUNDARY"
    )
    assert (
        contract["reuse"]["generic_intake_implementation"]["disposition"]
        == "UNCHANGED"
    )
    assert contract["output"]["creator_execution_authorized"] is False
    assert contract["output"]["provider_execution_required"] is False


def test_creator_task_contract_is_portrait_only_and_execution_deferred():
    contract = load_yaml(TASK_CONTRACT)
    assert contract["target_role"] == "inside_image.portrait"
    assert contract["preservation"]["likeness"] == "REQUIRED"
    assert contract["preservation"]["identity_change"] == "FORBIDDEN"
    assert contract["execution_authority"]["creator_execution_authorized"] is False
    assert contract["execution_authority"]["execution_begins_only_in"] == "GC-E2E-04"


def test_sanitized_assessment_fixture_is_valid():
    assert validate_photo_assessment_package(package()) == []


def test_fixture_exercises_all_routing_states():
    states = {item["assessment_state"] for item in package()["assessments"]}
    assert states == {
        "PASS_THROUGH",
        "DETERMINISTIC_TEMPLATE_NORMALIZATION",
        "CREATOR_TRANSFORMATION_REQUIRED",
        "HUMAN_REVIEW_REQUIRED",
    }


def test_ambiguous_portrait_binding_cannot_create_creator_task():
    bad = deepcopy(package())
    item = bad["assessments"][3]
    item["assessment_state"] = "CREATOR_TRANSFORMATION_REQUIRED"
    item["human_confirmation_required"] = False
    item["creator_operations"] = ["remove_background"]
    item["creator_task"] = deepcopy(bad["assessments"][2]["creator_task"])
    item["creator_task"]["job_id"] = item["job_id"]
    item["creator_task"]["assessment_id"] = item["assessment_id"]
    item["creator_task"]["source_asset"] = {
        "asset_id": item["asset_id"],
        "source_ref": "sanitized://assets/portrait_ambiguous.jpg",
    }
    item["creator_task"]["traceability"] = {
        "job_id": item["job_id"],
        "assessment_id": item["assessment_id"],
        "source_asset_id": item["asset_id"],
    }
    errors = validate_photo_assessment_package(bad)
    assert any("ambiguous_binding_requires_human_review" in error for error in errors)
    assert any("ambiguous_binding_forbids_creator_task" in error for error in errors)


def test_unknown_source_asset_is_rejected():
    bad = deepcopy(package())
    bad["assessments"][0]["asset_id"] = "asset_missing"
    errors = validate_photo_assessment_package(bad)
    assert "package.assessments[0].asset_id:unknown" in errors


def test_creator_task_must_preserve_likeness_and_realism():
    bad = deepcopy(package())
    task = bad["assessments"][2]["creator_task"]
    task["preservation"]["likeness"] = "OPTIONAL"
    task["preservation"]["realistic_appearance"] = "OPTIONAL"
    errors = validate_photo_assessment_package(bad)
    assert any("likeness:must_be_REQUIRED" in error for error in errors)
    assert any("realistic_appearance:must_be_REQUIRED" in error for error in errors)


def test_creator_task_cannot_take_document_composition_authority():
    bad = deepcopy(package())
    bad["assessments"][2]["creator_task"]["forbidden_changes"].remove(
        "document_geometry"
    )
    errors = validate_photo_assessment_package(bad)
    assert any("forbidden_changes:missing:document_geometry" in error for error in errors)


def test_directed_appearance_edit_requires_explicit_request_reference():
    bad = deepcopy(package())
    task = bad["assessments"][2]["creator_task"]
    task["directed_appearance_edits"] = ["skin_smoothing"]
    task["explicit_appearance_request_ref"] = None
    errors = validate_photo_assessment_package(bad)
    assert any("explicit_request_required" in error for error in errors)


def test_numeric_confidence_is_forbidden():
    bad = deepcopy(package())
    bad["assessments"][2]["confidence"] = 0.98
    errors = validate_photo_assessment_package(bad)
    assert "package:numeric_or_named_confidence_forbidden" in errors


def test_provider_execution_cannot_be_enabled_in_gc_e2e_03():
    bad = deepcopy(package())
    bad["provider_execution_required"] = True
    errors = validate_photo_assessment_package(bad)
    assert "package.provider_execution_required:must_be_false" in errors

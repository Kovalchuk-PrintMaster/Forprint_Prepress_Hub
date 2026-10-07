from copy import deepcopy
from pathlib import Path

import yaml

from app.graphic_design_lab.greeting_card_creator_correction import (
    CANONICAL_PATCH_OPERATION,
    CANONICAL_TARGET_OBJECT_ID,
    build_correction_cycle_record,
    compile_creator_correction_patch,
    validate_correction_cycle_record,
    validate_creator_correction_patch,
)
from app.graphic_design_lab.greeting_card_creator_review import (
    build_creator_review_record,
    validate_creator_review_record,
)
from app.graphic_design_lab.result_package import build_creator_result_package


ROOT = Path(__file__).resolve().parents[2]

BASE_FIXTURE = ROOT / (
    "tests/fixtures/graphic_design_lab/"
    "recurring_greeting_card_creator_review_pass_v0_1.yaml"
)
CYCLE_FIXTURE = ROOT / (
    "tests/fixtures/graphic_design_lab/"
    "recurring_greeting_card_creator_correction_cycle_v0_1.yaml"
)
RESULT_CONTRACT = ROOT / (
    "contracts/graphic_design_lab/creator_result_package_v0_1.yaml"
)
REVISION_CONTRACT = ROOT / (
    "contracts/graphic_design_lab/revision_patch_v0_1.yaml"
)
INDEX = ROOT / (
    "coordination/graphic_design_lab/directions/greeting_cards/index.yaml"
)
PLAN = ROOT / (
    "coordination/graphic_design_lab/directions/greeting_cards/"
    "end_to_end_execution_plan_v0_1.yaml"
)
CURSOR = ROOT / (
    "coordination/graphic_design_lab/continuity/"
    "current_execution_cursor_v0_1.yaml"
)


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def build_cycle():
    base = load_yaml(BASE_FIXTURE)
    fixture = load_yaml(CYCLE_FIXTURE)
    result_contract = load_yaml(RESULT_CONTRACT)
    revision_contract = load_yaml(REVISION_CONTRACT)

    r1_package = build_creator_result_package(
        deepcopy(base["creator_result_package_raw"])
    )

    fail_checks = dict(base["portrait_checks"])
    fail_checks.update(fixture["failed_review"]["failed_checks"])

    failed_review = build_creator_review_record(
        base["creator_task"],
        r1_package,
        result_contract,
        review_id=fixture["failed_review"]["review_id"],
        reviewer_source="SANITIZED_TEST_REVIEW",
        portrait_checks=fail_checks,
        review_note="Sanitized failing portrait review.",
    )

    correction = compile_creator_correction_patch(
        failed_review,
        base["creator_task"],
        revision_contract,
        revision_id=fixture["correction"]["revision_id"],
        parent_revision_id=fixture["correction"]["parent_revision_id"],
    )

    r2_raw = deepcopy(base["creator_result_package_raw"])
    corrected = fixture["corrected_result"]
    r2_raw["result_id"] = corrected["result_id"]
    r2_raw["revision"] = corrected["revision"]
    artifact = r2_raw["artifacts"][0]
    artifact["artifact_ref"] = corrected["artifact_ref"]
    artifact["external_ref"]["artifact_ref"] = (
        corrected["external_artifact_ref"]
    )
    artifact["external_ref"]["sha256"] = (
        corrected["external_artifact_sha256"]
    )

    r2_package = build_creator_result_package(r2_raw)

    corrected_review = build_creator_review_record(
        base["creator_task"],
        r2_package,
        result_contract,
        review_id=corrected["review_id"],
        reviewer_source="SANITIZED_TEST_REVIEW",
        portrait_checks=base["portrait_checks"],
        review_note="Sanitized corrected portrait re-review.",
    )

    cycle = build_correction_cycle_record(
        failed_review,
        correction,
        corrected_review,
    )

    return (
        base,
        fixture,
        revision_contract,
        failed_review,
        correction,
        corrected_review,
        cycle,
    )


def test_fail_review_requires_bounded_correction():
    (
        _,
        fixture,
        _,
        failed_review,
        correction,
        _,
        _,
    ) = build_cycle()

    assert validate_creator_review_record(failed_review) == []
    assert failed_review["outcome"] == "FAIL"
    assert failed_review["correction_required"] is True
    assert failed_review["accepted_artifact_refs"] == []
    assert correction["change_request"]["failed_checks"] == (
        fixture["correction"]["expected_failed_checks"]
    )


def test_compiled_patch_reuses_generic_revision_contract_shape():
    (
        base,
        fixture,
        revision_contract,
        _,
        correction,
        _,
        _,
    ) = build_cycle()

    assert validate_creator_correction_patch(
        correction,
        creator_task=base["creator_task"],
        revision_contract=revision_contract,
    ) == []

    assert correction["revision_id"] == (
        fixture["correction"]["revision_id"]
    )
    assert correction["parent_revision_id"] == (
        fixture["correction"]["parent_revision_id"]
    )
    assert correction["human_review_state"] == "review_requested"

    item = correction["patches"][0]
    assert item["operation"] == CANONICAL_PATCH_OPERATION
    assert item["target_object_id"] == CANONICAL_TARGET_OBJECT_ID


def test_patch_cannot_change_unrelated_stable_object():
    (
        base,
        _,
        revision_contract,
        _,
        correction,
        _,
        _,
    ) = build_cycle()

    bad = deepcopy(correction)
    bad["patches"][0]["target_object_id"] = "front.sender_logo"

    errors = validate_creator_correction_patch(
        bad,
        creator_task=base["creator_task"],
        revision_contract=revision_contract,
    )
    assert any(
        "must_be_inside_image_portrait" in item
        for item in errors
    )


def test_patch_cannot_expand_creator_requested_operations():
    (
        base,
        _,
        revision_contract,
        _,
        correction,
        _,
        _,
    ) = build_cycle()

    bad = deepcopy(correction)
    bad["creator_scope"]["requested_operations"].append(
        "canvas_extension"
    )

    errors = validate_creator_correction_patch(
        bad,
        creator_task=base["creator_task"],
        revision_contract=revision_contract,
    )
    assert any(
        "scope_expansion_or_reordering_forbidden" in item
        for item in errors
    )


def test_patch_forbids_full_regeneration():
    (
        base,
        _,
        revision_contract,
        _,
        correction,
        _,
        _,
    ) = build_cycle()

    bad = deepcopy(correction)
    bad["creator_scope"]["full_regeneration"] = True

    errors = validate_creator_correction_patch(
        bad,
        creator_task=base["creator_task"],
        revision_contract=revision_contract,
    )
    assert (
        "correction.creator_scope.full_regeneration:must_be_false"
        in errors
    )


def test_corrected_revision_re_reviews_to_pass():
    (
        _,
        fixture,
        _,
        _,
        _,
        corrected_review,
        _,
    ) = build_cycle()

    assert validate_creator_review_record(corrected_review) == []
    assert corrected_review["outcome"] == (
        fixture["corrected_result"]["expected_outcome"]
    )
    assert corrected_review["accepted_for_constructor_bundle"] is True
    assert corrected_review["customer_forwarding_allowed"] is False


def test_cycle_preserves_fail_then_pass_revision_history():
    (
        _,
        fixture,
        _,
        _,
        _,
        _,
        cycle,
    ) = build_cycle()

    assert validate_correction_cycle_record(cycle) == []
    assert cycle["state"] == fixture["expected_cycle"]["state"]
    assert [
        item["review_outcome"]
        for item in cycle["revision_history"]
    ] == fixture["expected_cycle"]["revision_history_outcomes"]
    assert cycle["revision_history"][0]["revision"] == 1
    assert cycle["revision_history"][1]["revision"] == 2


def test_cycle_accepts_only_corrected_artifact_and_not_customer_forwarding():
    (
        _,
        fixture,
        _,
        _,
        _,
        _,
        cycle,
    ) = build_cycle()

    assert cycle["accepted_artifact_refs"] == [
        fixture["corrected_result"]["artifact_ref"]
    ]
    assert cycle["accepted_for_constructor_bundle"] is True
    assert cycle["customer_forwarding_allowed"] is False
    assert cycle["correction"]["no_scope_expansion"] is True


def test_correction_cycle_contains_no_private_or_live_paths():
    (
        _,
        _,
        _,
        _,
        correction,
        _,
        cycle,
    ) = build_cycle()

    text = yaml.safe_dump(
        {"correction": correction, "cycle": cycle},
        sort_keys=False,
        allow_unicode=True,
    )
    assert "/srv/" not in text
    assert "gdl_live" not in text
    assert "+380" not in text


def test_greeting_card_index_registers_correction_contract():
    index = load_yaml(INDEX)
    assert index["creator_correction_contract"] == (
        "creator_correction_contract_v0_1.yaml"
    )
    assert "creator_correction_contract_v0_1.yaml" in (
        index["documents"]
    )


def test_gc_e2e_05_closes_and_gc_e2e_06_becomes_active():
    plan = load_yaml(PLAN)
    steps = {item["id"]: item for item in plan["steps"]}

    assert steps["GC-E2E-05"]["state"] == "COMPLETED_LOCAL"
    assert steps["GC-E2E-06"]["state"] == "ACTIVE"

    checkpoints = {
        item["id"]: item
        for item in steps["GC-E2E-05"]["execution_checkpoints"]
    }
    assert checkpoints["GC-E2E-05A"]["state"] == "COMPLETED_LOCAL"
    assert checkpoints["GC-E2E-05B"]["state"] == "COMPLETED_LOCAL"
    assert checkpoints["GC-E2E-05B"]["closes_parent_step"] is True
    assert checkpoints["GC-E2E-05B"]["no_creator_scope_expansion"] is True

    cursor = load_yaml(CURSOR)
    task = cursor["active_tasks"][0]
    assert task["current_step"] == "GC-E2E-06"
    assert "GC-E2E-05" in task["completed_steps"]
    assert "GC-E2E-05A" in task["completed_subcheckpoints"]
    assert "GC-E2E-05B" in task["completed_subcheckpoints"]
    assert task["current_checkpoint"]["id"] == (
        "ACCEPTED_CONSTRUCTOR_BUNDLE_REQUIRED"
    )

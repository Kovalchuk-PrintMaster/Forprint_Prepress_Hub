from copy import deepcopy
from pathlib import Path

import yaml

from app.graphic_design_lab.greeting_card_creator_review import (
    REQUIRED_PORTRAIT_CHECKS,
    build_creator_review_record,
    validate_creator_review_record,
)
from app.graphic_design_lab.result_package import build_creator_result_package


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / (
    "tests/fixtures/graphic_design_lab/"
    "recurring_greeting_card_creator_review_pass_v0_1.yaml"
)
RESULT_CONTRACT = ROOT / (
    "contracts/graphic_design_lab/creator_result_package_v0_1.yaml"
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


def build_from_fixture():
    fixture = load_yaml(FIXTURE)
    contract = load_yaml(RESULT_CONTRACT)
    package = build_creator_result_package(
        fixture["creator_result_package_raw"]
    )
    record = build_creator_review_record(
        fixture["creator_task"],
        package,
        contract,
        review_id=fixture["review_id"],
        reviewer_source=fixture["reviewer_source"],
        portrait_checks=fixture["portrait_checks"],
        review_note=fixture["review_note"],
    )
    return fixture, package, record


def test_sanitized_pass_fixture_builds_valid_review_record():
    fixture, _, record = build_from_fixture()
    assert validate_creator_review_record(record) == []
    assert record["outcome"] == fixture["expected_outcome"] == "PASS"
    assert record["structural_gate"]["state"] == "PASS"
    assert record["accepted_for_constructor_bundle"] is True
    assert record["correction_required"] is False
    assert record["customer_forwarding_allowed"] is False
    assert record["accepted_artifact_refs"] == [
        "sanitized-restored-portrait-r001"
    ]


def test_review_reuses_all_required_portrait_checks():
    _, _, record = build_from_fixture()
    assert tuple(record["portrait_checks"]) == REQUIRED_PORTRAIT_CHECKS
    assert all(
        record["portrait_checks"][item] == "PASS"
        for item in REQUIRED_PORTRAIT_CHECKS
    )


def test_review_projects_to_existing_global_review_gate():
    _, _, record = build_from_fixture()
    assert record["global_review_gate"] == {
        "source_fidelity": "PASS",
        "scope_completeness": "PASS",
        "no_invented_customer_content": "PASS",
        "language_consistency": "NOT_APPLICABLE",
        "identity_integrity": "PASS",
        "artifact_cleanliness": "PASS",
        "structure_truthfulness": "NOT_APPLICABLE",
        "unresolved_truthfulness": "PASS",
        "design_continuity": "PASS",
        "output_classification": "PASS",
    }


def test_fail_check_requires_correction_but_does_not_accept_asset():
    fixture = load_yaml(FIXTURE)
    contract = load_yaml(RESULT_CONTRACT)
    package = build_creator_result_package(
        fixture["creator_result_package_raw"]
    )
    checks = dict(fixture["portrait_checks"])
    checks["artifact_cleanliness"] = "FAIL"
    record = build_creator_review_record(
        fixture["creator_task"],
        package,
        contract,
        review_id="sanitized-fail-review",
        reviewer_source="HUMAN_OPERATOR_REVIEW",
        portrait_checks=checks,
    )
    assert validate_creator_review_record(record) == []
    assert record["outcome"] == "FAIL"
    assert record["correction_required"] is True
    assert record["accepted_artifact_refs"] == []
    assert record["accepted_for_constructor_bundle"] is False


def test_blocked_check_blocks_without_synthesizing_correction():
    fixture = load_yaml(FIXTURE)
    contract = load_yaml(RESULT_CONTRACT)
    package = build_creator_result_package(
        fixture["creator_result_package_raw"]
    )
    checks = dict(fixture["portrait_checks"])
    checks["likeness_preserved"] = "BLOCKED"
    record = build_creator_review_record(
        fixture["creator_task"],
        package,
        contract,
        review_id="sanitized-blocked-review",
        reviewer_source="HUMAN_OPERATOR_REVIEW",
        portrait_checks=checks,
    )
    assert validate_creator_review_record(record) == []
    assert record["outcome"] == "BLOCKED"
    assert record["blocked"] is True
    assert record["correction_required"] is False
    assert record["accepted_artifact_refs"] == []


def test_task_result_traceability_mismatch_blocks_review():
    fixture = load_yaml(FIXTURE)
    contract = load_yaml(RESULT_CONTRACT)
    raw = deepcopy(fixture["creator_result_package_raw"])
    raw["source"]["greeting_card_task_traceability"][
        "source_asset_id"
    ] = "wrong-source"
    package = build_creator_result_package(raw)
    record = build_creator_review_record(
        fixture["creator_task"],
        package,
        contract,
        review_id="sanitized-trace-block",
        reviewer_source="HUMAN_OPERATOR_REVIEW",
        portrait_checks=fixture["portrait_checks"],
    )
    assert record["outcome"] == "BLOCKED"
    assert any(
        "task_traceability.source_asset_id:mismatch" == item
        for item in record["structural_gate"]["errors"]
    )
    assert validate_creator_review_record(record) == []


def test_revision_history_preserves_result_identity_and_review_outcome():
    _, package, record = build_from_fixture()
    assert record["revision_history"] == [
        {
            "result_id": package["result_id"],
            "revision": package["revision"],
            "provenance_sha256": package["provenance"]["sha256"],
            "review_outcome": "PASS",
        }
    ]


def test_review_record_carries_no_live_result_package_or_heavy_asset():
    _, _, record = build_from_fixture()
    text = yaml.safe_dump(record, sort_keys=False, allow_unicode=True)
    assert "creator_result_package_raw" not in text
    assert "/srv/" not in text
    assert "tmp/gdl_live" not in text
    assert "heavy_artifact" not in text


def test_authority_remains_non_runtime_and_non_automatic():
    _, _, record = build_from_fixture()
    assert all(value is False for value in record["authority"].values())


def test_greeting_card_index_registers_review_contract():
    index = load_yaml(INDEX)
    assert index["creator_review_contract"] == (
        "creator_review_contract_v0_1.yaml"
    )
    assert "creator_review_contract_v0_1.yaml" in index["documents"]


def test_gc_e2e_05a_remains_recorded_after_later_progress():
    plan = load_yaml(PLAN)
    steps = {item["id"]: item for item in plan["steps"]}
    assert steps["GC-E2E-05"]["state"] == "COMPLETED_LOCAL"

    checkpoints = {
        item["id"]: item
        for item in steps["GC-E2E-05"]["execution_checkpoints"]
    }
    assert checkpoints["GC-E2E-05A"]["state"] == "COMPLETED_LOCAL"
    assert checkpoints["GC-E2E-05A"]["closes_parent_step"] is False
    assert checkpoints["GC-E2E-05B"]["state"] == "COMPLETED_LOCAL"

    cursor = load_yaml(CURSOR)
    task = cursor["active_tasks"][0]
    assert "GC-E2E-05A" in task["completed_subcheckpoints"]
    assert "GC-E2E-05B" in task["completed_subcheckpoints"]

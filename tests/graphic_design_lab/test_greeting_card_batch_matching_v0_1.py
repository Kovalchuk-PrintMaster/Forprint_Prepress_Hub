from copy import deepcopy
from pathlib import Path

import yaml

from app.graphic_design_lab.greeting_card_batch import (
    validate_greeting_card_normalized_batch,
)


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "coordination/graphic_design_lab/directions/greeting_cards"
CONTRACT = BASE / "normalized_batch_contract_v0_1.yaml"
PACKAGE = BASE / "intake_package_contract_v0_2.yaml"
PROFILE = BASE / "intake_prompt_profile_v0_2.yaml"
LOADER = BASE / "prompts/GDL-INTAKE-GREETING-CARDS-v002.md"
FIXTURE = (
    ROOT
    / "tests/fixtures/graphic_design_lab/"
    "recurring_greeting_card_batch_matching_v0_1.yaml"
)
PROMPT_INDEX = (
    ROOT / "coordination/graphic_design_lab/prompt_evidence/index.yaml"
)
CURSOR = (
    ROOT
    / "coordination/graphic_design_lab/continuity/"
    "current_execution_cursor_v0_1.yaml"
)
PLAN = BASE / "end_to_end_execution_plan_v0_1.yaml"


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def fixture_parts():
    fixture = load_yaml(FIXTURE)
    return (
        fixture,
        fixture["normalized_batch"],
        fixture["source_inventory"],
        fixture["entity_registry"],
    )


def validate(batch, inventory, entities):
    return validate_greeting_card_normalized_batch(
        batch,
        source_inventory=inventory,
        entity_registry=entities,
    )


def test_contract_refines_existing_batch_without_raw_parser():
    contract = load_yaml(CONTRACT)

    assert contract["reuse"]["generic_batch_contract"]["disposition"] == (
        "REUSE_AND_REFINE"
    )
    assert contract["reuse"]["raw_customer_parser"]["disposition"] == (
        "NOT_CREATED"
    )
    assert contract["cardinality"][
        "single_recipient_request_representation"
    ] == "ONE_ITEM_JOBS_LIST"


def test_sanitized_two_job_fixture_validates():
    fixture, batch, inventory, entities = fixture_parts()

    assert validate(batch, inventory, entities) == []
    assert len(batch["jobs"]) == fixture["expected"]["job_count"]


def test_single_recipient_uses_same_batch_schema():
    _, batch, inventory, entities = fixture_parts()

    one = deepcopy(batch)
    one["batch_id"] = "sanitized_batch_single"
    one["jobs"] = [deepcopy(batch["jobs"][0])]

    assert validate(one, inventory, entities) == []


def test_ambiguous_job_remains_explicitly_unresolved():
    _, batch, _, _ = fixture_parts()
    job = next(
        item for item in batch["jobs"]
        if item["job_id"] == "job_beta"
    )

    assert job["candidate_entity_id"] is None
    assert job["bindings"]["recipient_entity"]["state"] == "UNRESOLVED"
    assert job["bindings"]["portrait"]["state"] == "PROPOSED"
    assert job["bindings"]["recipient_branding"]["state"] == "UNRESOLVED"
    assert len(job["uncertainties"]) >= 3


def test_filename_similarity_cannot_confirm_binding():
    _, batch, inventory, entities = fixture_parts()

    bad = deepcopy(batch)
    portrait = bad["jobs"][1]["bindings"]["portrait"]
    portrait["state"] = "CONFIRMED"
    portrait["human_confirmation_required"] = False

    errors = validate(bad, inventory, entities)

    assert any(
        "confirmed_requires_deterministic_basis" in error
        for error in errors
    )


def test_unknown_asset_reference_is_rejected():
    _, batch, inventory, entities = fixture_parts()

    bad = deepcopy(batch)
    bad["jobs"][0]["bindings"]["portrait"]["source_id"] = (
        "asset_missing"
    )

    errors = validate(bad, inventory, entities)

    assert any(
        "unknown_asset:asset_missing" in error
        for error in errors
    )


def test_numeric_confidence_is_forbidden():
    _, batch, inventory, entities = fixture_parts()

    bad = deepcopy(batch)
    bad["jobs"][0]["bindings"]["portrait"]["confidence"] = 0.99

    errors = validate(bad, inventory, entities)

    assert "batch:numeric_or_named_confidence_forbidden" in errors


def test_v002_loader_is_current_and_v001_is_preserved():
    package = load_yaml(PACKAGE)
    profile = load_yaml(PROFILE)
    index = load_yaml(PROMPT_INDEX)

    assert package["extends"]["previous_contract"].endswith(
        "intake_package_contract_v0_1.yaml"
    )
    assert profile["extends"]["previous_loader"].endswith(
        "GDL-INTAKE-GREETING-CARDS-v001.md"
    )
    assert "normalized_batch.yaml" in LOADER.read_text(encoding="utf-8")

    greeting = next(
        row
        for row in index["direction_prompt_profiles"]
        if row["direction_id"] == "greeting_cards"
    )
    assert greeting["loader"].endswith(
        "GDL-INTAKE-GREETING-CARDS-v002.md"
    )
    assert greeting["previous_loader"].endswith(
        "GDL-INTAKE-GREETING-CARDS-v001.md"
    )


def test_gc_e2e_02_remains_closed_after_later_cursor_advances():
    cursor = load_yaml(CURSOR)
    task = cursor["active_tasks"][0]

    assert task["completed_steps"][:3] == [
        "GC-E2E-00",
        "GC-E2E-01",
        "GC-E2E-02",
    ]
    assert task["current_step"] not in {"GC-E2E-00", "GC-E2E-01", "GC-E2E-02"}

    plan = load_yaml(PLAN)
    steps = {item["id"]: item for item in plan["steps"]}
    assert steps["GC-E2E-02"]["state"] == "COMPLETED_LOCAL"

def test_gc_e2e_08_job_runner_gate_remains_untouched():
    plan = load_yaml(PLAN)
    steps = {item["id"]: item for item in plan["steps"]}

    checkpoint = steps["GC-E2E-08"][
        "mandatory_job_runner_reuse_checkpoint"
    ]

    assert checkpoint["do_not_discard_silently"] is True
    assert checkpoint["current_disposition"] == (
        "UNRESOLVED_REQUIRES_GC_E2E_08_RECONCILIATION"
    )

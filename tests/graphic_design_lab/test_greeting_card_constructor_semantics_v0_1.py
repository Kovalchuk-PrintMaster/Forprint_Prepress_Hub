from copy import deepcopy
from pathlib import Path

import yaml

from app.graphic_design_lab.greeting_card_batch import (
    validate_greeting_card_normalized_batch,
)
from app.graphic_design_lab.greeting_card_signature_variants import (
    resolve_signature_configuration,
    validate_signature_variant_catalog,
)


ROOT = Path(__file__).resolve().parents[2]

BATCH_FIXTURE = ROOT / (
    "tests/fixtures/graphic_design_lab/"
    "recurring_greeting_card_batch_matching_v0_1.yaml"
)
SIGNATURE_CATALOG = ROOT / (
    "coordination/graphic_design_lab/directions/greeting_cards/"
    "signature_variant_catalog_v0_1.yaml"
)
BATCH_CONTRACT = ROOT / (
    "coordination/graphic_design_lab/directions/greeting_cards/"
    "normalized_batch_contract_v0_1.yaml"
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


def test_confirmed_absent_recipient_branding_is_valid():
    fixture = load_yaml(BATCH_FIXTURE)
    batch = deepcopy(fixture["normalized_batch"])

    job = batch["jobs"][0]
    job["supplied_assets"].remove("asset_brand_alpha")
    job["bindings"]["recipient_branding"] = {
        "state": "CONFIRMED",
        "basis": "operator_assignment",
        "presence": "ABSENT",
        "source_id": None,
        "human_confirmation_required": False,
    }

    errors = validate_greeting_card_normalized_batch(
        batch,
        source_inventory=fixture["source_inventory"],
        entity_registry=fixture["entity_registry"],
    )
    assert errors == []


def test_confirmed_absent_is_not_encoded_as_unresolved():
    fixture = load_yaml(BATCH_FIXTURE)
    batch = deepcopy(fixture["normalized_batch"])

    job = batch["jobs"][0]
    job["supplied_assets"].remove("asset_brand_alpha")
    job["bindings"]["recipient_branding"] = {
        "state": "UNRESOLVED",
        "basis": "no_assignment",
        "presence": "ABSENT",
        "source_id": None,
        "human_confirmation_required": True,
    }
    job["uncertainties"] = [
        {
            "field": "recipient_branding",
            "reason": "test ambiguity",
            "human_confirmation_required": True,
        }
    ]

    errors = validate_greeting_card_normalized_batch(
        batch,
        source_inventory=fixture["source_inventory"],
        entity_registry=fixture["entity_registry"],
    )
    assert any(
        "recipient_branding:absence_must_be_CONFIRMED" in item
        for item in errors
    )


def test_branding_absence_forbids_source_asset():
    fixture = load_yaml(BATCH_FIXTURE)
    batch = deepcopy(fixture["normalized_batch"])

    binding = batch["jobs"][0]["bindings"]["recipient_branding"]
    binding["presence"] = "ABSENT"

    errors = validate_greeting_card_normalized_batch(
        batch,
        source_inventory=fixture["source_inventory"],
        entity_registry=fixture["entity_registry"],
    )
    assert any(
        "recipient_branding:absent_forbids_source" in item
        for item in errors
    )


def test_signature_catalog_current_matrix_matches_confirmed_order():
    catalog = load_yaml(SIGNATURE_CATALOG)

    assert validate_signature_variant_catalog(catalog) == []
    assert catalog["extensibility"] == "OPEN_CATALOG"
    assert catalog["selection_model"]["primary_key"] == "variant_id"

    assert [
        (
            item["variant_id"],
            item["sender_variant"],
            item["signature_component_count"],
        )
        for item in catalog["variants"]
    ] == [
        ("GRIGO", "SINGLE_PRIMARY", 1),
        ("HERASYMENKO", "SINGLE_SECONDARY", 1),
        ("DUAL_GRIGO_HERASYMENKO", "DUAL_SENDER", 2),
    ]


def test_signature_catalog_can_expand_without_new_code_enum():
    catalog = load_yaml(SIGNATURE_CATALOG)
    extended = deepcopy(catalog)

    extended["variants"].append(
        {
            "variant_id": "FUTURE_CONFIRMED_VARIANT",
            "sender_variant": "SINGLE_PRIMARY",
            "signature_component_count": 1,
            "coupled_object_ids": [
                "inside_text.sender_block",
                "inside_text.signature",
            ],
        }
    )

    assert validate_signature_variant_catalog(extended) == []

    resolved = resolve_signature_configuration(
        extended,
        variant_id="FUTURE_CONFIRMED_VARIANT",
    )
    assert resolved["variant_id"] == "FUTURE_CONFIRMED_VARIANT"
    assert resolved["sender_variant"] == "SINGLE_PRIMARY"


def test_signature_configuration_uses_explicit_variant_identity():
    catalog = load_yaml(SIGNATURE_CATALOG)

    grigo = resolve_signature_configuration(
        catalog,
        variant_id="GRIGO",
        sender_variant="SINGLE_PRIMARY",
    )
    herasymenko = resolve_signature_configuration(
        catalog,
        variant_id="HERASYMENKO",
        sender_variant="SINGLE_SECONDARY",
    )
    dual = resolve_signature_configuration(
        catalog,
        variant_id="DUAL_GRIGO_HERASYMENKO",
        sender_variant="DUAL_SENDER",
    )

    assert grigo["signature_component_count"] == 1
    assert herasymenko["signature_component_count"] == 1
    assert dual["signature_component_count"] == 2

    for item in (grigo, herasymenko, dual):
        assert item["coupled_object_ids"] == [
            "inside_text.sender_block",
            "inside_text.signature",
        ]


def test_sender_layout_mismatch_is_rejected():
    catalog = load_yaml(SIGNATURE_CATALOG)

    try:
        resolve_signature_configuration(
            catalog,
            variant_id="GRIGO",
            sender_variant="SINGLE_SECONDARY",
        )
    except ValueError as exc:
        assert (
            "signature_sender_variant_mismatch:"
            "GRIGO:SINGLE_SECONDARY"
        ) in str(exc)
    else:
        raise AssertionError("signature/layout mismatch accepted")


def test_unknown_signature_variant_requires_catalog_extension():
    catalog = load_yaml(SIGNATURE_CATALOG)

    try:
        resolve_signature_configuration(
            catalog,
            variant_id="FUTURE_NOT_REGISTERED",
        )
    except ValueError as exc:
        assert (
            "signature_configuration_missing_for_variant_id:"
            "FUTURE_NOT_REGISTERED"
        ) in str(exc)
    else:
        raise AssertionError("unknown signature configuration accepted")


def test_batch_contract_declares_constructor_signature_variant_identity():
    contract = load_yaml(BATCH_CONTRACT)
    extension = contract["signature_binding_extension"]

    assert extension["variant_id_field"] == "variant_id"
    assert extension["intake_field_required"] is False
    assert extension["constructor_ready_requires_variant_id"] is True
    assert (
        extension["sender_variant_is_layout_semantics_not_identity"]
        is True
    )


def test_gc_e2e_06a_remains_recorded_after_parent_closeout():
    plan = load_yaml(PLAN)
    steps = {item["id"]: item for item in plan["steps"]}

    assert steps["GC-E2E-06"]["state"] == "COMPLETED_LOCAL"
    assert steps["GC-E2E-07"]["state"] == "ACTIVE"

    checkpoints = {
        item["id"]: item
        for item in steps["GC-E2E-06"]["execution_checkpoints"]
    }
    assert checkpoints["GC-E2E-06A"]["state"] == "COMPLETED_LOCAL"
    assert checkpoints["GC-E2E-06A"]["closes_parent_step"] is False
    assert checkpoints["GC-E2E-06B"]["state"] == "COMPLETED_LOCAL"

    cursor = load_yaml(CURSOR)
    task = cursor["active_tasks"][0]
    assert "GC-E2E-06A" in task["completed_subcheckpoints"]
    assert "GC-E2E-06B" in task["completed_subcheckpoints"]
    assert "GC-E2E-06" in task["completed_steps"]

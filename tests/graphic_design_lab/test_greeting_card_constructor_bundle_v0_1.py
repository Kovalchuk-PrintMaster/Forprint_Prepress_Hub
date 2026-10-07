from copy import deepcopy
from pathlib import Path

import yaml

from app.graphic_design_lab.greeting_card_constructor_bundle import (
    accepted_visual_from_creator_review,
    build_accepted_constructor_bundle,
    compute_bundle_sha256,
    validate_accepted_constructor_bundle,
)
from app.graphic_design_lab.greeting_card_creator_review import (
    build_creator_review_record,
)
from app.graphic_design_lab.result_package import (
    build_creator_result_package,
)


ROOT = Path(__file__).resolve().parents[2]

FIXTURE = ROOT / (
    "tests/fixtures/graphic_design_lab/"
    "recurring_greeting_card_constructor_bundle_v0_1.yaml"
)
REVIEW_FIXTURE = ROOT / (
    "tests/fixtures/graphic_design_lab/"
    "recurring_greeting_card_creator_review_pass_v0_1.yaml"
)
RESULT_CONTRACT = ROOT / (
    "contracts/graphic_design_lab/creator_result_package_v0_1.yaml"
)
SIGNATURE_CATALOG = ROOT / (
    "coordination/graphic_design_lab/directions/greeting_cards/"
    "signature_variant_catalog_v0_1.yaml"
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


def build_review_record():
    fixture = load_yaml(REVIEW_FIXTURE)
    contract = load_yaml(RESULT_CONTRACT)

    package = build_creator_result_package(
        deepcopy(fixture["creator_result_package_raw"])
    )

    return build_creator_review_record(
        fixture["creator_task"],
        package,
        contract,
        review_id=fixture["review_id"],
        reviewer_source=fixture["reviewer_source"],
        portrait_checks=fixture["portrait_checks"],
        review_note=fixture["review_note"],
    )


def build_bundle():
    fixture = load_yaml(FIXTURE)
    catalog = load_yaml(SIGNATURE_CATALOG)

    visual = accepted_visual_from_creator_review(
        build_review_record()
    )

    bundle = build_accepted_constructor_bundle(
        fixture["normalized_batch"],
        source_inventory=fixture["source_inventory"],
        entity_registry=fixture["entity_registry"],
        accepted_visuals_by_job={
            fixture["normalized_batch"]["jobs"][0]["job_id"]: visual,
        },
        signature_catalog=catalog,
        intake_review=fixture["intake_review"],
        bundle_id=fixture["expected"]["bundle_id"],
        semantic_family_hints_by_job=fixture[
            "semantic_family_hints"
        ],
    )

    return fixture, catalog, visual, bundle


def test_creator_review_projects_accepted_portrait_for_bundle():
    fixture, _, visual, _ = build_bundle()

    assert visual["job_id"] == "sanitized_job_review_001"
    assert visual["target_object_id"] == "inside_image.portrait"
    assert visual["source_asset_id"] == (
        "sanitized_source_portrait_001"
    )
    assert visual["artifact_ref"] == fixture["expected"][
        "accepted_visual_artifact_ref"
    ]
    assert visual["acceptance_basis"] == (
        "CREATOR_INTERNAL_REVIEW_PASS"
    )
    assert visual["review_id"]
    assert visual["result_id"]
    assert visual["revision"] == 1
    assert len(visual["provenance_sha256"]) == 64


def test_bundle_materializes_exact_confirmed_constructor_input():
    fixture, catalog, _, bundle = build_bundle()

    assert validate_accepted_constructor_bundle(
        bundle,
        signature_catalog=catalog,
    ) == []

    assert bundle["constructor_input_class"] == fixture[
        "expected"
    ]["constructor_input_class"]
    assert bundle["intake_review"]["state"] == "PASS"
    assert bundle["intake_review"]["review_id"] == (
        "sanitized-intake-review-001"
    )
    assert bundle["provenance_manifest"]["intake_review_id"] == (
        "sanitized-intake-review-001"
    )
    assert len(bundle["jobs"]) == 1

    job = bundle["jobs"][0]
    assert job["job_id"] == "sanitized_job_review_001"
    assert job["structured_greeting_data"]["recipient_entity_id"] == (
        "entity_bundle_recipient"
    )
    assert job["structured_greeting_data"]["greeting_text"] == (
        "Sanitized birthday greeting."
    )


def test_bundle_uses_explicit_branding_presence_and_signature_variant():
    fixture, _, _, bundle = build_bundle()
    job = bundle["jobs"][0]

    assert job["branding_selection"] == {
        "target_object_id": "front.recipient_branding",
        "presence": fixture["expected"]["branding_presence"],
        "source_asset_id": None,
    }

    signature = job["signature_selection"]
    assert signature["variant_id"] == fixture["expected"][
        "signature_variant_id"
    ]
    assert signature["sender_variant"] == fixture["expected"][
        "sender_variant"
    ]
    assert signature["signature_source_asset_id"] == (
        "asset_signature_grigo"
    )
    assert signature["coupled_object_ids"] == [
        "inside_text.sender_block",
        "inside_text.signature",
    ]


def test_bundle_records_resolved_semantic_family_without_inference():
    fixture, _, _, bundle = build_bundle()
    hint = bundle["jobs"][0]["semantic_family_hint"]

    assert hint == {
        "family_id": fixture["expected"]["semantic_family_id"],
        "basis": "operator_assignment",
        "state": "RESOLVED",
    }


def test_bundle_rejects_unresolved_constructor_binding():
    fixture = load_yaml(FIXTURE)
    catalog = load_yaml(SIGNATURE_CATALOG)
    visual = accepted_visual_from_creator_review(
        build_review_record()
    )

    bad = deepcopy(fixture["normalized_batch"])
    signature = bad["jobs"][0]["bindings"]["signature"]
    signature["state"] = "UNRESOLVED"
    signature["basis"] = "no_assignment"
    signature["human_confirmation_required"] = True
    signature["source_id"] = None
    signature["variant_id"] = None
    bad["jobs"][0]["supplied_assets"].remove(
        "asset_signature_grigo"
    )
    bad["jobs"][0]["uncertainties"] = [
        {
            "field": "signature",
            "reason": "signature selection unresolved",
            "human_confirmation_required": True,
        }
    ]

    try:
        build_accepted_constructor_bundle(
            bad,
            source_inventory=fixture["source_inventory"],
            entity_registry=fixture["entity_registry"],
            accepted_visuals_by_job={
                "sanitized_job_review_001": visual
            },
            signature_catalog=catalog,
            intake_review=fixture["intake_review"],
            bundle_id="must-fail",
        )
    except ValueError as exc:
        assert (
            "constructor_job_uncertainties_must_be_empty"
            in str(exc)
            or "constructor_binding_not_confirmed"
            in str(exc)
        )
    else:
        raise AssertionError(
            "unresolved constructor binding unexpectedly accepted"
        )


def test_bundle_requires_explicit_branding_presence():
    fixture = load_yaml(FIXTURE)
    catalog = load_yaml(SIGNATURE_CATALOG)
    visual = accepted_visual_from_creator_review(
        build_review_record()
    )

    bad = deepcopy(fixture["normalized_batch"])
    inventory = deepcopy(fixture["source_inventory"])
    inventory["assets"].append(
        {
            "asset_id": "asset_brand_present",
            "kind": "raster",
            "logical_role": "recipient_branding",
            "provenance": {
                "source_class": "customer_supplied"
            },
        }
    )
    job = bad["jobs"][0]
    job["supplied_assets"].append("asset_brand_present")
    branding = job["bindings"]["recipient_branding"]
    branding.pop("presence")
    branding["source_id"] = "asset_brand_present"

    try:
        build_accepted_constructor_bundle(
            bad,
            source_inventory=inventory,
            entity_registry=fixture["entity_registry"],
            accepted_visuals_by_job={
                "sanitized_job_review_001": visual
            },
            signature_catalog=catalog,
            intake_review=fixture["intake_review"],
            bundle_id="must-fail",
        )
    except ValueError as exc:
        assert "branding_presence_must_be_explicit" in str(exc)
    else:
        raise AssertionError(
            "implicit branding presence unexpectedly accepted"
        )


def test_bundle_requires_explicit_signature_variant_id():
    fixture = load_yaml(FIXTURE)
    catalog = load_yaml(SIGNATURE_CATALOG)
    visual = accepted_visual_from_creator_review(
        build_review_record()
    )

    bad = deepcopy(fixture["normalized_batch"])
    del bad["jobs"][0]["bindings"]["signature"]["variant_id"]

    try:
        build_accepted_constructor_bundle(
            bad,
            source_inventory=fixture["source_inventory"],
            entity_registry=fixture["entity_registry"],
            accepted_visuals_by_job={
                "sanitized_job_review_001": visual
            },
            signature_catalog=catalog,
            intake_review=fixture["intake_review"],
            bundle_id="must-fail",
        )
    except ValueError as exc:
        assert "constructor_signature_variant_id_required" in str(exc)
    else:
        raise AssertionError(
            "missing signature variant unexpectedly accepted"
        )


def test_bundle_rejects_visual_source_mismatch():
    fixture = load_yaml(FIXTURE)
    catalog = load_yaml(SIGNATURE_CATALOG)
    visual = accepted_visual_from_creator_review(
        build_review_record()
    )
    visual["source_asset_id"] = "wrong-source"

    try:
        build_accepted_constructor_bundle(
            fixture["normalized_batch"],
            source_inventory=fixture["source_inventory"],
            entity_registry=fixture["entity_registry"],
            accepted_visuals_by_job={
                "sanitized_job_review_001": visual
            },
            signature_catalog=catalog,
            intake_review=fixture["intake_review"],
            bundle_id="must-fail",
        )
    except ValueError as exc:
        assert "accepted_visual_source_mismatch" in str(exc)
    else:
        raise AssertionError(
            "visual source mismatch unexpectedly accepted"
        )


def test_bundle_requires_explicit_intake_review_pass_evidence():
    fixture = load_yaml(FIXTURE)
    catalog = load_yaml(SIGNATURE_CATALOG)
    visual = accepted_visual_from_creator_review(
        build_review_record()
    )
    review = deepcopy(fixture["intake_review"])
    review["state"] = "PENDING"

    try:
        build_accepted_constructor_bundle(
            fixture["normalized_batch"],
            source_inventory=fixture["source_inventory"],
            entity_registry=fixture["entity_registry"],
            accepted_visuals_by_job={
                "sanitized_job_review_001": visual
            },
            signature_catalog=catalog,
            intake_review=review,
            bundle_id="must-fail",
        )
    except ValueError as exc:
        assert "intake_review_state_must_be_PASS" in str(exc)
    else:
        raise AssertionError(
            "non-PASS intake review unexpectedly accepted"
        )


def test_bundle_rejects_intake_review_for_another_batch():
    fixture = load_yaml(FIXTURE)
    catalog = load_yaml(SIGNATURE_CATALOG)
    visual = accepted_visual_from_creator_review(
        build_review_record()
    )
    review = deepcopy(fixture["intake_review"])
    review["source_batch_id"] = "different-batch"

    try:
        build_accepted_constructor_bundle(
            fixture["normalized_batch"],
            source_inventory=fixture["source_inventory"],
            entity_registry=fixture["entity_registry"],
            accepted_visuals_by_job={
                "sanitized_job_review_001": visual
            },
            signature_catalog=catalog,
            intake_review=review,
            bundle_id="must-fail",
        )
    except ValueError as exc:
        assert "intake_review_source_batch_mismatch" in str(exc)
    else:
        raise AssertionError(
            "mismatched intake review unexpectedly accepted"
        )


def test_bundle_provenance_is_deterministic_and_tamper_evident():
    _, catalog, _, bundle = build_bundle()

    digest = bundle["provenance_manifest"]["bundle_sha256"]
    assert len(digest) == 64
    assert digest == compute_bundle_sha256(bundle)

    tampered = deepcopy(bundle)
    tampered["jobs"][0]["structured_greeting_data"][
        "greeting_text"
    ] = "tampered"

    errors = validate_accepted_constructor_bundle(
        tampered,
        signature_catalog=catalog,
    )
    assert (
        "bundle.provenance_manifest.bundle_sha256:mismatch"
        in errors
    )


def test_bundle_validator_rejects_rehashed_internal_binding_mismatch():
    _, catalog, _, bundle = build_bundle()

    tampered = deepcopy(bundle)
    tampered["jobs"][0]["signature_selection"][
        "signature_source_asset_id"
    ] = "different-signature"
    tampered["provenance_manifest"]["bundle_sha256"] = (
        compute_bundle_sha256(tampered)
    )

    errors = validate_accepted_constructor_bundle(
        tampered,
        signature_catalog=catalog,
    )
    assert any(
        "signature_source_asset_id:binding_mismatch" in item
        for item in errors
    )


def test_bundle_validator_rejects_rehashed_target_object_mismatch():
    _, catalog, _, bundle = build_bundle()

    tampered = deepcopy(bundle)
    tampered["jobs"][0]["exact_person_text_asset_bindings"][
        "greeting_text"
    ]["target_object_id"] = "inside_text.wrong_target"
    tampered["provenance_manifest"]["bundle_sha256"] = (
        compute_bundle_sha256(tampered)
    )

    errors = validate_accepted_constructor_bundle(
        tampered,
        signature_catalog=catalog,
    )
    assert any(
        "greeting_text.target_object_id:mismatch" in item
        for item in errors
    )


def test_bundle_has_no_private_or_heavy_artifact_payload():
    _, _, _, bundle = build_bundle()

    text = yaml.safe_dump(
        bundle,
        sort_keys=False,
        allow_unicode=True,
    )

    assert "/srv/" not in text
    assert "gdl_live" not in text
    assert "+380" not in text
    assert "image/png" not in text
    assert "heavy_artifact" not in text


def test_index_registers_accepted_constructor_bundle_contract():
    index = load_yaml(INDEX)

    assert index["accepted_constructor_bundle_contract"] == (
        "accepted_constructor_bundle_contract_v0_1.yaml"
    )
    assert "accepted_constructor_bundle_contract_v0_1.yaml" in (
        index["documents"]
    )


def test_gc_e2e_06_remains_closed_while_08_unblocks_07():
    plan = load_yaml(PLAN)
    steps = {item["id"]: item for item in plan["steps"]}

    assert steps["GC-E2E-06"]["state"] == "COMPLETED_LOCAL"
    assert steps["GC-E2E-07"]["state"] == (
        "BLOCKED_BY_GC_E2E_08"
    )
    assert steps["GC-E2E-08"]["state"] == "ACTIVE"

    checkpoints = {
        item["id"]: item
        for item in steps["GC-E2E-06"]["execution_checkpoints"]
    }
    assert checkpoints["GC-E2E-06A"]["state"] == "COMPLETED_LOCAL"
    assert checkpoints["GC-E2E-06B"]["state"] == "COMPLETED_LOCAL"
    assert checkpoints["GC-E2E-06B"]["closes_parent_step"] is True

    cursor = load_yaml(CURSOR)
    task = cursor["active_tasks"][0]
    assert "GC-E2E-06" in task["completed_steps"]
    assert "GC-E2E-06A" in task["completed_subcheckpoints"]
    assert "GC-E2E-06B" in task["completed_subcheckpoints"]
    assert task["current_step"] == "GC-E2E-08"
    assert task["current_checkpoint"]["id"] == (
        "CONSTRUCTOR_BUNDLE_INGEST_IMPLEMENTATION"
    )

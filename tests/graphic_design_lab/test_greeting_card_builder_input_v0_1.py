
from copy import deepcopy
from pathlib import Path

import yaml

from app.graphic_design_lab.greeting_card_builder_input import (
    BUILDER_PAYLOAD_SCHEMA,
    attach_builder_payload_v1,
    validate_builder_payload_v1,
    validate_builder_ready_bundle_v1,
)
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
    "contracts/graphic_design_lab/"
    "creator_result_package_v0_1.yaml"
)

CATALOG_PATH = ROOT / (
    "coordination/graphic_design_lab/directions/greeting_cards/"
    "signature_variant_catalog_v0_1.yaml"
)

FLOWERS_SHA256 = (
    "d9113f8d6f9627f9b106f5550e6187aaa562139fef6122e4834e7d4f2f3bbd67"
)


def load_yaml(path: Path):
    return yaml.safe_load(
        path.read_text(encoding="utf-8")
    )


def catalog():
    return load_yaml(CATALOG_PATH)


def build_review_record():
    fixture = load_yaml(REVIEW_FIXTURE)
    contract = load_yaml(RESULT_CONTRACT)

    package = build_creator_result_package(
        deepcopy(
            fixture["creator_result_package_raw"]
        )
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


def base_bundle():
    fixture = load_yaml(FIXTURE)
    signature_catalog = catalog()

    visual = accepted_visual_from_creator_review(
        build_review_record()
    )

    job_id = (
        fixture["normalized_batch"]
        ["jobs"][0]["job_id"]
    )

    bundle = build_accepted_constructor_bundle(
        fixture["normalized_batch"],
        source_inventory=fixture["source_inventory"],
        entity_registry=fixture["entity_registry"],
        accepted_visuals_by_job={
            job_id: visual,
        },
        signature_catalog=signature_catalog,
        intake_review=fixture["intake_review"],
        bundle_id=fixture["expected"]["bundle_id"],
        semantic_family_hints_by_job=(
            fixture["semantic_family_hints"]
        ),
    )

    assert visual["revision"] == 1

    assert (
        validate_accepted_constructor_bundle(
            bundle,
            signature_catalog=signature_catalog,
        )
        == []
    )

    return bundle


def portrait_payload(bundle):
    job = bundle["jobs"][0]

    portrait = (
        job["exact_person_text_asset_bindings"]
        ["portrait"]
    )
    accepted_visual = (
        job["accepted_visual_assets"][0]
    )
    signature = (
        job["signature_selection"]
    )

    return {
        "schema_version": BUILDER_PAYLOAD_SCHEMA,
        "revision": "r001",
        "front": {
            "family": "STANDARD",
            "occasion": {
                "kind": (
                    job["structured_greeting_data"]
                    ["occasion"]
                ),
                "display_text": (
                    "ÐŸÑ€Ð¸Ð²Ñ–Ñ‚Ð°Ð½Ð½Ñ Ð· Ð½Ð°Ð³Ð¾Ð´Ð¸ "
                    "Ð”Ð½Ñ ÐÐ°Ñ€Ð¾Ð´Ð¶ÐµÐ½Ð½Ñ!"
                ),
            },
        },
        "inside_image": {
            "mode": "PORTRAIT",
            "asset_id": portrait["source_asset_id"],
            "asset_sha256": "2" * 64,
            "accepted_artifact_ref": (
                accepted_visual["artifact_ref"]
            ),
        },
        "sender_text": {
            "signature_variant_id": (
                signature["variant_id"]
            ),
            "lines": [
                {
                    "id": "closing_phrase",
                    "text": (
                        "Ð— Ð½Ð°Ð¹Ñ‰Ð¸Ñ€Ñ–ÑˆÐ¸Ð¼Ð¸ Ð¿Ð¾Ð±Ð°Ð¶Ð°Ð½Ð½ÑÐ¼Ð¸"
                    ),
                },
                {
                    "id": "primary_name",
                    "text": "Sanitized Sender",
                },
            ],
        },
    }


def test_existing_bundle_keeps_semantic_occasion_not_visible_title():
    bundle = base_bundle()
    job = bundle["jobs"][0]

    assert (
        job["exact_person_text_asset_bindings"]
        ["occasion_text"]["value"]
        == "birthday"
    )

    errors = validate_builder_ready_bundle_v1(
        bundle,
        signature_catalog=catalog(),
    )

    assert any(
        ".builder_v1.schema_version:unsupported"
        in item
        for item in errors
    )


def test_attach_payload_adds_exact_visible_title_without_reinterpreting_occasion():
    bundle = base_bundle()
    job_id = bundle["jobs"][0]["job_id"]

    ready = attach_builder_payload_v1(
        bundle,
        payload_by_job={
            job_id: portrait_payload(bundle),
        },
        signature_catalog=catalog(),
    )

    job = ready["jobs"][0]

    assert (
        job["structured_greeting_data"]["occasion"]
        == "birthday"
    )

    assert (
        job["builder_v1"]["front"]
        ["occasion"]["display_text"]
        == "ÐŸÑ€Ð¸Ð²Ñ–Ñ‚Ð°Ð½Ð½Ñ Ð· Ð½Ð°Ð³Ð¾Ð´Ð¸ Ð”Ð½Ñ ÐÐ°Ñ€Ð¾Ð´Ð¶ÐµÐ½Ð½Ñ!"
    )

    assert (
        validate_builder_ready_bundle_v1(
            ready,
            signature_catalog=catalog(),
        )
        == []
    )


def test_attach_payload_rehashes_same_bundle_after_exact_render_extension():
    bundle = base_bundle()
    job_id = bundle["jobs"][0]["job_id"]

    before = (
        bundle["provenance_manifest"]
        ["bundle_sha256"]
    )

    ready = attach_builder_payload_v1(
        bundle,
        payload_by_job={
            job_id: portrait_payload(bundle),
        },
        signature_catalog=catalog(),
    )

    after = (
        ready["provenance_manifest"]
        ["bundle_sha256"]
    )

    assert before != after
    assert after == compute_bundle_sha256(
        ready
    )


def test_builder_payload_requires_exact_sender_line_ids_and_text():
    bundle = base_bundle()
    payload = portrait_payload(bundle)

    payload["sender_text"]["lines"][1]["id"] = (
        "closing_phrase"
    )

    errors = validate_builder_payload_v1(
        payload
    )

    assert (
        "builder_v1.sender_text.lines[1].id:duplicate"
        in errors
    )


def test_builder_payload_requires_front_family_consistent_with_branding_state():
    bundle = base_bundle()
    payload = portrait_payload(bundle)

    payload["front"]["family"] = (
        "RECIPIENT_BRANDING_OVERLAY"
    )

    ready = deepcopy(bundle)
    ready["jobs"][0]["builder_v1"] = payload

    ready["provenance_manifest"]["bundle_sha256"] = ""
    ready["provenance_manifest"]["bundle_sha256"] = (
        compute_bundle_sha256(
            ready
        )
    )

    errors = validate_builder_ready_bundle_v1(
        ready,
        signature_catalog=catalog(),
    )

    assert any(
        "branding_absent_forbids_overlay_family"
        in item
        for item in errors
    )


def test_default_flowers_payload_is_explicit_and_carries_exact_hash():
    payload = {
        "schema_version": BUILDER_PAYLOAD_SCHEMA,
        "revision": "r001",
        "front": {
            "family": "STANDARD",
            "occasion": {
                "kind": "birthday",
                "display_text": (
                    "ÐŸÑ€Ð¸Ð²Ñ–Ñ‚Ð°Ð½Ð½Ñ Ð· Ð½Ð°Ð³Ð¾Ð´Ð¸ "
                    "Ð”Ð½Ñ ÐÐ°Ñ€Ð¾Ð´Ð¶ÐµÐ½Ð½Ñ!"
                ),
            },
        },
        "inside_image": {
            "mode": "DEFAULT_ASSET",
            "asset_id": "flowers.default.v1",
            "asset_sha256": FLOWERS_SHA256,
            "accepted_artifact_ref": None,
        },
        "sender_text": {
            "signature_variant_id": "GRIGO",
            "lines": [
                {
                    "id": "closing_phrase",
                    "text": (
                        "Ð— Ð½Ð°Ð¹Ñ‰Ð¸Ñ€Ñ–ÑˆÐ¸Ð¼Ð¸ Ð¿Ð¾Ð±Ð°Ð¶Ð°Ð½Ð½ÑÐ¼Ð¸"
                    ),
                }
            ],
        },
    }

    assert validate_builder_payload_v1(
        payload
    ) == []

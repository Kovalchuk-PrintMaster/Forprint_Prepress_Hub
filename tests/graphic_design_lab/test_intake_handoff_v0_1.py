from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from app.graphic_design_lab.intake import (
    build_creator_handoff,
    normalize_guided_intake,
    validate_creator_handoff,
    validate_guided_intake,
    validate_product_playbook,
)

ROOT = Path(__file__).resolve().parents[2]
PLAYBOOK = (
    ROOT
    / "config/graphic_design_lab/product_playbooks/"
    "recurring_greeting_card_v0_1.yaml"
)
FIXTURE = (
    ROOT
    / "tests/fixtures/graphic_design_lab/"
    "recurring_greeting_card_intake_v0_1.yaml"
)


def load(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def build_case():
    playbook = load(PLAYBOOK)
    fixture = load(FIXTURE)
    raw = fixture["raw_input"]
    intake = normalize_guided_intake(playbook, raw)
    handoff = build_creator_handoff(
        playbook,
        intake,
        assets=raw["assets"],
        references=raw["references"],
    )
    return playbook, fixture, raw, intake, handoff


def test_product_playbook_is_valid_and_reusable():
    playbook = load(PLAYBOOK)
    assert validate_product_playbook(playbook) == []
    assert playbook["rules"]["reusable_across_customer_instances"] is True
    assert playbook["rules"]["customer_specific_content_present"] is False
    assert "customer_id" not in playbook
    assert "order_id" not in playbook


def test_guided_intake_preserves_answered_and_unresolved_questions():
    playbook, fixture, raw, intake, _ = build_case()
    assert (
        validate_guided_intake(
            intake,
            playbook=playbook,
            assets=raw["assets"],
            references=raw["references"],
        )
        == []
    )
    assert [item["question_id"] for item in intake["answered_questions"]] == (
        fixture["expected"]["answered_question_ids"]
    )
    assert [item["question_id"] for item in intake["unresolved_questions"]] == (
        fixture["expected"]["unresolved_question_ids"]
    )


def test_mapping_states_and_human_confirmation_are_explicit():
    _, fixture, _, intake, _ = build_case()
    assert {item["mapping_state"] for item in intake["asset_mappings"]} == set(
        fixture["expected"]["mapping_states"]
    )
    for mapping in intake["asset_mappings"]:
        if mapping["mapping_state"] in {"PROPOSED", "UNRESOLVED"}:
            assert mapping["human_confirmation_required"] is True
        if mapping["mapping_state"] == "CONFIRMED":
            assert mapping["human_confirmation_required"] is False


def test_asset_identity_is_reused_by_reference_not_recreated():
    _, _, raw, intake, handoff = build_case()
    asset_ids = {asset["asset_id"] for asset in raw["assets"]}
    assert {
        item["source_id"]
        for item in intake["asset_mappings"]
        if item["source_kind"] == "asset"
    } <= asset_ids
    assert {
        item["source_id"]
        for item in handoff["asset_manifest"]
        if item["source_kind"] == "asset"
    } <= asset_ids
    for item in handoff["asset_manifest"]:
        assert "provenance" not in item
        assert "fingerprint_sha256" not in item


def test_confidence_is_rejected():
    playbook, _, raw, intake, _ = build_case()
    broken = deepcopy(intake)
    broken["asset_mappings"][0]["confidence"] = 0.99
    errors = validate_guided_intake(
        broken,
        playbook=playbook,
        assets=raw["assets"],
        references=raw["references"],
    )
    assert any("confidence_forbidden" in error for error in errors)


def test_proposed_mapping_cannot_be_silently_confirmed():
    playbook, _, raw, intake, _ = build_case()
    broken = deepcopy(intake)
    proposed = next(
        item
        for item in broken["asset_mappings"]
        if item["mapping_state"] == "PROPOSED"
    )
    proposed["human_confirmation_required"] = False
    errors = validate_guided_intake(
        broken,
        playbook=playbook,
        assets=raw["assets"],
        references=raw["references"],
    )
    assert any("proposed_requires_human_confirmation" in error for error in errors)


def test_confirmed_mapping_requires_explicit_basis():
    playbook, _, raw, intake, _ = build_case()
    broken = deepcopy(intake)
    confirmed = next(
        item
        for item in broken["asset_mappings"]
        if item["mapping_state"] == "CONFIRMED"
    )
    confirmed["mapping_source"] = "heuristic_guess"
    errors = validate_guided_intake(
        broken,
        playbook=playbook,
        assets=raw["assets"],
        references=raw["references"],
    )
    assert any(
        "confirmed_requires_explicit_deterministic_basis" in error
        for error in errors
    )


def test_creator_handoff_is_deterministic_and_valid():
    playbook, _, raw, intake, first = build_case()
    second = build_creator_handoff(
        playbook,
        intake,
        assets=raw["assets"],
        references=raw["references"],
    )
    assert first == second
    assert (
        validate_creator_handoff(
            first,
            playbook=playbook,
            assets=raw["assets"],
            references=raw["references"],
        )
        == []
    )


def test_creator_handoff_preserves_deferred_execution_boundaries():
    _, fixture, _, _, handoff = build_case()
    assert handoff["creator_execution_authorized"] is False
    assert handoff["provider_execution_required"] is False
    assert fixture["expected"]["creator_execution_authorized"] is False
    assert fixture["expected"]["provider_execution_required"] is False
    assert handoff["creator_brief"]["human_confirmation_required"] is True


def test_fixture_is_sanitized_and_has_multiple_photos():
    fixture = load(FIXTURE)
    assets = fixture["raw_input"]["assets"]
    assert fixture["sanitized"] is True
    assert len([asset for asset in assets if asset["kind"] == "raster"]) >= 2
    assert all(
        str(asset["source_ref"]).startswith("sanitized://")
        for asset in assets
    )

def test_choice_answer_must_be_declared_by_playbook():
    playbook = load(PLAYBOOK)
    fixture = load(FIXTURE)
    raw = deepcopy(fixture["raw_input"])
    raw["answers"]["occasion"] = "not_a_declared_choice"

    with pytest.raises(ValueError) as exc:
        normalize_guided_intake(playbook, raw)

    assert "raw_input.answers.occasion:not_in_declared_choices" in str(exc.value)


def test_mapping_source_kind_must_match_playbook_role():
    playbook = load(PLAYBOOK)
    fixture = load(FIXTURE)
    raw = deepcopy(fixture["raw_input"])

    raw["references"] = [
        {
            "reference_id": "reference_demo_logo",
            "logical_role": "logo",
            "provenance": {"source_class": "customer_supplied"},
            "source_ref": "sanitized://references/demo_logo.pdf",
        }
    ]

    logo = next(
        item for item in raw["mappings"] if item["role_id"] == "logo"
    )
    logo["source_kind"] = "reference"
    logo["source_id"] = "reference_demo_logo"

    with pytest.raises(ValueError) as exc:
        normalize_guided_intake(playbook, raw)

    assert "source_kind:not_accepted_for_role" in str(exc.value)


def test_final_open_question_contract_is_typed():
    playbook = load(PLAYBOOK)
    broken = deepcopy(playbook)
    broken["final_open_question"]["enabled"] = "yes"

    errors = validate_product_playbook(broken)

    assert "playbook.final_open_question.enabled:must_be_boolean" in errors


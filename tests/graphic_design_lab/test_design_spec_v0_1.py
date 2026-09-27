from copy import deepcopy
from datetime import date
from pathlib import Path

import yaml

from app.graphic_design_lab.validation import validate_design_spec, validate_product_profile

ROOT = Path(__file__).resolve().parents[2]


def load(rel):
    return yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))


def inputs():
    contract = load("contracts/graphic_design_lab/design_spec_v0_1.yaml")
    profile = load("config/graphic_design_lab/product_profiles/dated_diary_a5_v0_1.yaml")
    fixture = load("tests/fixtures/graphic_design_lab/dated_diary_a5_phase1_v0_1.yaml")
    return contract, profile, fixture


def test_dated_diary_profile_is_valid():
    _, profile, _ = inputs()
    assert validate_product_profile(profile) == []


def test_phase1_fixture_is_valid():
    contract, profile, fixture = inputs()
    assert validate_design_spec(fixture, contract, profile) == []


def test_duplicate_object_id_is_rejected():
    contract, profile, fixture = inputs()
    broken = deepcopy(fixture)
    duplicate = deepcopy(broken["spreads"][0]["objects"][0])
    broken["spreads"][1]["objects"].append(duplicate)
    errors = validate_design_spec(broken, contract, profile)
    assert any("id:duplicate" in error for error in errors)


def test_wrong_page_width_is_rejected_against_profile():
    contract, profile, fixture = inputs()
    broken = deepcopy(fixture)
    broken["document"]["page"]["width_mm"] = 149
    errors = validate_design_spec(broken, contract, profile)
    assert "spec.document.page.width_mm:profile_mismatch" in errors


def test_unknown_object_type_is_rejected():
    contract, profile, fixture = inputs()
    broken = deepcopy(fixture)
    broken["spreads"][0]["objects"][0]["type"] = "magic_art_object"
    errors = validate_design_spec(broken, contract, profile)
    assert any("type:unsupported" in error for error in errors)


def test_invalid_cmyk_profile_component_is_rejected():
    _, profile, _ = inputs()
    broken = deepcopy(profile)
    broken["month_colors_cmyk"]["10"] = [0, 25, 193, 9]
    errors = validate_product_profile(broken)
    assert "profile.month_colors_cmyk.10:component_out_of_range" in errors


def test_phase1_fixture_keeps_full_rollout_blocked():
    _, _, fixture = inputs()
    assert fixture["review"]["full_rollout_allowed"] is False


def test_phase1_fixture_requires_no_photo_assets():
    _, _, fixture = inputs()
    assert fixture["assets"] == []


def test_reference_svg_is_structural_only():
    _, _, fixture = inputs()
    ref = fixture["references"][0]
    assert ref["logical_role"] == "structural_reference_only"
    assert "visual_treatment" in ref["change"]


def test_transition_week_contains_november_style():
    _, _, fixture = inputs()
    transition = next(x for x in fixture["spreads"] if x["id"].startswith("spread.week.transition"))
    sunday = next(x for x in transition["objects"] if x["role"] == "sunday")
    assert sunday["style_ref"] == "month.november"


def test_calendar_period_is_explicit_not_inferred_from_id():
    contract, profile, fixture = inputs()
    broken = deepcopy(fixture)
    del broken["spreads"][0]["period"]
    errors = validate_design_spec(broken, contract, profile)
    assert "spec.spreads[0].period:required_for_monthly" in errors


def test_weekly_period_reversed_range_is_rejected():
    contract, profile, fixture = inputs()
    broken = deepcopy(fixture)
    broken["spreads"][1]["period"] = {
        "start_date": "2026-10-18",
        "end_date": "2026-10-15",
    }
    errors = validate_design_spec(broken, contract, profile)
    assert "spec.spreads[1].period:reversed_range" in errors

def test_yaml_native_dates_are_accepted_by_contract_validation():
    contract, profile, fixture = inputs()
    start = fixture["spreads"][1]["period"]["start_date"]
    end = fixture["spreads"][1]["period"]["end_date"]
    assert isinstance(start, date)
    assert isinstance(end, date)
    assert validate_design_spec(fixture, contract, profile) == []

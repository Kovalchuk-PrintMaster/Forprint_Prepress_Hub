"""Regression contract: the two implemented variants remain explicit and closed."""
import copy
from pathlib import Path

import yaml

from scripts.validation.check_graphic_design_lab_project_first import (
    _validate_implemented_slices,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "coordination/graphic_design_lab/directions/greeting_cards/deterministic_builder_v0_1.yaml"


def current_contract():
    return yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))


def test_both_implemented_signatures_pass():
    assert _validate_implemented_slices(current_contract()) == []


def test_old_first_slice_only_is_not_accepted():
    doc = current_contract()
    doc.pop("implemented_slices")
    doc["first_slice"] = {"front_family": "STANDARD", "inside_image_mode": "PORTRAIT", "signature_variant": "GRIGO"}
    assert "builder_contract:implemented_slices_missing" in _validate_implemented_slices(doc)


def test_unapproved_extra_signature_is_rejected():
    doc = copy.deepcopy(current_contract())
    doc["implemented_slices"]["signature_variants"].append("DUAL_GRIGO_HERASYMENKO")
    assert "builder_contract:implemented_signatures" in _validate_implemented_slices(doc)


def test_missing_herasymenko_is_rejected():
    doc = copy.deepcopy(current_contract())
    doc["implemented_slices"]["signature_variants"] = ["GRIGO"]
    assert "builder_contract:implemented_signatures" in _validate_implemented_slices(doc)


def test_wrong_front_or_image_is_rejected():
    doc = copy.deepcopy(current_contract())
    doc["implemented_slices"]["shared"]["front_family"] = "RECIPIENT_BRANDING_OVERLAY"
    doc["implemented_slices"]["shared"]["inside_image_mode"] = "OTHER"
    issues = _validate_implemented_slices(doc)
    assert "builder_contract:implemented_front" in issues
    assert "builder_contract:implemented_image" in issues


def test_open_ended_variants_are_rejected():
    doc = copy.deepcopy(current_contract())
    doc["implemented_slices"]["unsupported_variants_fail_closed"] = False
    assert "builder_contract:unsupported_variants_not_closed" in _validate_implemented_slices(doc)

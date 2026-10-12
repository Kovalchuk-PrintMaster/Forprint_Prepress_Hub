from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

PATH = Path("scripts/validation/gdl_greeting_card_sender_zone_audit_v0_1.py")
SPEC = importlib.util.spec_from_file_location("gdl_sender_zone_audit", PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_center_geometry_and_invalid_size():
    assert module.bbox_from_center([120, 240],[77,70]) == [81.5,205,158.5,275]
    with pytest.raises(ValueError, match="nonpositive_container_size"):
        module.bbox_from_center([10,10],[-1,25])


def test_outside_does_not_invent_proportional_fit():
    assert module.outside_mm([80.877,212.875,126.258,272.141],
                             [112,215,158,275])["left"] == 31.123
    assert module.outside_mm([80.877,212.875,126.258,272.141],
                             [112,215,158,275])["top"] == 2.125


def test_source_profile_audit_requires_manual_binding_review():
    if not module.ZONE_FILE.is_file() or not module.EMBEDDED.is_file():
        pytest.skip("Project sources required")
    report = module.audit_contract()
    assert len(report["profiles"]) == 3
    assert report["bottom_reserved_visual_lines"] == 2
    assert report["dual_runtime_enabled"] is False
    assert report["profile_activation_authorized"] is False
    assert all(not p["source_signature_fits_candidate"] for p in report["profiles"])


def test_overlap_is_bbox_not_real_ink():
    assert module.overlap_area([0,0,10,10],[10,0,20,10]) == 0
    assert module.overlap_area([0,0,10,10],[5,5,20,20]) == 25

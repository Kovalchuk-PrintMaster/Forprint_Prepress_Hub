from pathlib import Path

import pytest
import yaml

from app.graphic_design_lab.greeting_card_sender_zone_planner_v0_1 import (
    SenderZoneBlocked, candidate_v03_slots, source_locked_slots,
)

REGISTRY = Path("coordination/graphic_design_lab/directions/greeting_cards/geometry_zones_v0_1.yaml")


def profile(variant="HERASYMENKO"):
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["pages"]["physical_4"]["signature_profiles_candidate_v0_3"][variant]


@pytest.mark.parametrize("count", [2, 3, 6])
def test_source_locked_equals_previous_renderer_geometry_exactly(count):
    ids = [f"sender_role_{i}" for i in range(count)]
    for start in (214.0, 224.0, 236.0):
        slots = source_locked_slots(ids, start_y_pdf_mm=start)
        assert [s.bbox_pdf_mm for s in slots] == [
            (31.0, start + i*8.0, 101.0, start + (i+1)*8.0)
            for i in range(count)
        ]


@pytest.mark.parametrize("count", [2, 3])
def test_herasymenko_candidate_accepts_2_3_slot_geometry(count):
    ids = [f"sender_role_{i}" for i in range(count)]
    slots = candidate_v03_slots(ids, variant="HERASYMENKO", profile=profile())
    # Candidate sender zone remains fixed: (32, 224.5, 82, 249.5) PDF mm.
    # Text is aligned 0.5 mm lower *inside* it, leaving 0.5 mm at bottom
    # in the three-line case; no source signature is moved or scaled.
    assert slots[0].bbox_pdf_mm == (32.0, 225.0, 82.0, 233.0)
    assert slots[-1].bbox_pdf_mm[3] <= 249.5
    assert slots[-1].bbox_pdf_mm[3] == 225.0 + 8.0 * count


def test_six_lines_fail_closed_in_25mm_container():
    with pytest.raises(SenderZoneBlocked, match="sender_lines_exceed_candidate_height"):
        candidate_v03_slots([f"sender_role_{i}" for i in range(6)], variant="HERASYMENKO", profile=profile())


def test_dual_never_activates_runtime_by_geometry_planner():
    p = profile("DUAL_GRIGO_HERASYMENKO")
    assert p["runtime_enabled"] is False
    slots = candidate_v03_slots(["role_1", "role_2"], variant="DUAL_GRIGO_HERASYMENKO", profile=p)
    assert slots[0].bbox_pdf_mm == (29.5, 214.5, 104.5, 222.5)
    bad = dict(p, runtime_enabled=True)
    with pytest.raises(SenderZoneBlocked, match="dual_runtime_gate_missing"):
        candidate_v03_slots(["role_1"], variant="DUAL_GRIGO_HERASYMENKO", profile=bad)


def test_unstable_or_duplicate_ids_blocked():
    with pytest.raises(SenderZoneBlocked, match="sender_line_id_duplicate"):
        candidate_v03_slots(["sender_name", "sender_name"], variant="HERASYMENKO", profile=profile())
    assert len(source_locked_slots(["same", "same"], start_y_pdf_mm=214)) == 2
    with pytest.raises(SenderZoneBlocked, match="sender_line_ids_missing"):
        source_locked_slots([], start_y_pdf_mm=214)


def test_grigo_candidate_uses_previous_operator_coordinates():
    slots = candidate_v03_slots(["role_1", "role_2"], variant="GRIGO", profile=profile("GRIGO"))
    assert slots[0].bbox_pdf_mm == (32.0, 222.0, 92.0, 230.0)
    assert slots[1].bbox_pdf_mm == (32.0, 230.0, 92.0, 238.0)


def test_renderer_bridge_defaults_only_to_source_locked_profile():
    import ast
    renderer = Path("app/graphic_design_lab/greeting_card_builder_renderer.py").read_text(encoding="utf-8")
    tree = ast.parse(renderer)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_render_sender_lines")
    source = ast.get_source_segment(renderer, fn)
    assert "source_locked_slots(" in source
    assert "candidate_v03_slots(" not in source
    assert "_insert_textbox_exact(" in source


def test_herasymenko_top_inset_is_registry_driven_and_fail_closed():
    p = profile()
    assert p["sender_text_inner_top_inset_mm"] == 0.5
    original = candidate_v03_slots(["a", "b", "c"], variant="HERASYMENKO", profile=p)
    assert original[-1].bbox_pdf_mm[3] == 249.0
    removed = dict(p)
    removed.pop("sender_text_inner_top_inset_mm")
    zero_inset = candidate_v03_slots(["a", "b", "c"], variant="HERASYMENKO", profile=removed)
    assert zero_inset[0].bbox_pdf_mm == (32.0, 224.5, 82.0, 232.5)
    for bad in (-0.1, float("nan"), float("inf"), "not-a-number"):
        invalid = dict(p, sender_text_inner_top_inset_mm=bad)
        with pytest.raises(SenderZoneBlocked, match="sender_inner_top_inset_invalid"):
            candidate_v03_slots(["a"], variant="HERASYMENKO", profile=invalid)
    too_large = dict(p, sender_text_inner_top_inset_mm=1.01)
    with pytest.raises(SenderZoneBlocked, match="sender_lines_exceed_candidate_height"):
        candidate_v03_slots(["a", "b", "c"], variant="HERASYMENKO", profile=too_large)


def test_no_candidate_inset_crosses_to_grigo_or_dual():
    for variant in ("GRIGO", "DUAL_GRIGO_HERASYMENKO"):
        p = profile(variant)
        assert "sender_text_inner_top_inset_mm" not in p
        original = candidate_v03_slots(["a", "b"], variant=variant, profile=p)
        altered = dict(p, sender_text_inner_top_inset_mm=0.5)
        with pytest.raises(SenderZoneBlocked, match="sender_inner_top_inset_variant_not_verified"):
            candidate_v03_slots(["a", "b"], variant=variant, profile=altered)
        assert original[0].bbox_pdf_mm[1] == (222.0 if variant == "GRIGO" else 214.5)

from __future__ import annotations

import inspect
from pathlib import Path

import yaml

from app.graphic_design_lab import greeting_card_builder_renderer as b

ZONES = Path(
    "coordination/graphic_design_lab/directions/greeting_cards/geometry_zones_v0_1.yaml"
)


def test_fixed_zone_reserves_two_usable_line_slots_inside_pdf_bbox():
    assert b.GREETING_BOTTOM_RESERVED_LINE_SLOTS == 2
    assert (
        b.GREETING_BODY_LEFT_MM,
        b.GREETING_BODY_TOP_MM,
        b.GREETING_BODY_RIGHT_MM,
        b.GREETING_BODY_MAX_BOTTOM_MM,
    ) == (27.0, 32.0, 187.0, 212.0)
    for size in b.GREETING_FONT_SIZE_TIERS_PT:
        line_mm = size * b.MM_PER_PT * b.GREETING_LINE_ADVANCE_RATIO
        content_bottom = min(
            212.0 - 2.0 * line_mm,
            214.0 - b.MIN_SENDER_GAP_LINE_HEIGHTS * line_mm,
        )
        assert content_bottom <= 212.0 - 2.0 * line_mm
        assert content_bottom > 32.0
    source = inspect.getsource(b._fit_greeting)
    assert "GREETING_BOTTOM_RESERVED_LINE_SLOTS * line_height_mm" in source


def test_fit_returns_effective_rectangle_with_reserved_rows(monkeypatch):
    class ScratchPage:
        def insert_textbox(self, rect, text, **kwargs):
            return 0
    class ScratchDoc:
        def new_page(self, **kwargs):
            return ScratchPage()
        def close(self):
            pass
    class TargetPage:
        rect = b.pymupdf.Rect(0, 0, 606, 853)
    monkeypatch.setattr(b.pymupdf, "open", lambda: ScratchDoc())
    monkeypatch.setattr(b, "_greeting_pdf_lineheight", lambda _font_path: 1.0)
    pt, start, rect = b._fit_greeting(
        TargetPage(), "Synthetic sample", font_path=Path("fake-font-used-only-by-stub"),
        sender_line_count=2,
    )
    assert pt == b.GREETING_FONT_SIZE_TIERS_PT[0]
    assert start == 214.0
    line_mm = pt * b.MM_PER_PT * b.GREETING_LINE_ADVANCE_RATIO
    expected = min(
        b.GREETING_BODY_MAX_BOTTOM_MM
        - b.GREETING_BOTTOM_RESERVED_LINE_SLOTS * line_mm,
        start - b.MIN_SENDER_GAP_LINE_HEIGHTS * line_mm,
    )
    assert abs(rect.y1 * b.MM_PER_PT - expected) < 0.000001


def test_v03_operator_signature_geometry_is_registry_only():
    d = yaml.safe_load(ZONES.read_text(encoding="utf-8"))
    page = d["pages"]["physical_4"]
    z = page["zones"]["inside_text.greeting"]
    assert z["bottom_visual_line_reservation"]["count"] == 2
    assert z["bbox_trim_mm"] == [25.0, 30.0, 185.0, 210.0]
    variants = page["signature_profiles_candidate_v0_3"]
    assert variants["GRIGO"]["signature_center_trim_mm"] == [125.0, 230.0]
    assert variants["HERASYMENKO"]["signature_center_trim_mm"] == [135.0, 245.0]
    assert variants["DUAL_GRIGO_HERASYMENKO"]["signature_center_trim_mm"] == [120.0, 240.0]
    assert variants["DUAL_GRIGO_HERASYMENKO"]["signature_size_mm"] == [77.0, 70.0]
    assert variants["DUAL_GRIGO_HERASYMENKO"]["runtime_enabled"] is False
    assert d["not_authorized"] and "DUAL_RUNTIME_ACTIVATION" in d["not_authorized"]


def test_dual_two_empty_rows_alone_do_not_claim_ink_clearance():
    d = yaml.safe_load(ZONES.read_text(encoding="utf-8"))
    dual = d["pages"]["physical_4"]["signature_profiles_candidate_v0_3"]["DUAL_GRIGO_HERASYMENKO"]
    # Real source ink begins at y=194.983 mm in TRIM coordinates,
    # above the nominal composite signature rectangle starting at y=205 mm.
    assert dual["source_ink_top_trim_mm"] == 194.983
    assert dual["requires_visible_ink_collision_check"] is True
    assert dual["minimum_ink_clearance_mm"] == 2.0
    assert dual["runtime_enabled"] is False

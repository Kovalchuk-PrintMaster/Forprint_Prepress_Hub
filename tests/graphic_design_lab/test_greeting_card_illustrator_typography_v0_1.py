from __future__ import annotations

import inspect
import math
from pathlib import Path

import yaml
from app.graphic_design_lab import greeting_card_builder_renderer as b


def test_illustrator_reference_font_size_and_leading(monkeypatch):
    class FakeFont:
        ascender = 0.9
    monkeypatch.setattr(b.pymupdf, 'Font', lambda **kwargs: FakeFont())
    assert b.GREETING_REFERENCE_FONT_SIZE_MM == 7.0
    assert b.GREETING_REFERENCE_LINE_ADVANCE_MM == 8.0
    assert math.isclose(b.GREETING_FONT_SIZE_TIERS_PT[0] * b.MM_PER_PT, 7.0, abs_tol=1e-6)
    assert math.isclose(b.GREETING_LINE_ADVANCE_RATIO, 8.0 / 7.0)
    assert math.isclose(b._greeting_pdf_lineheight(Path('dummy')), 8.0 / 7.0 / 0.9, rel_tol=1e-10)
    assert tuple(b.GREETING_FONT_SIZE_TIERS_PT) == tuple(sorted(b.GREETING_FONT_SIZE_TIERS_PT, reverse=True))
    assert b.GREETING_FONT_SIZE_TIERS_PT[1:] == (18.5, 17.0, 16.5, 16.0)


def test_both_fit_and_final_pdf_use_identical_leading():
    fit = inspect.getsource(b._fit_greeting)
    build = inspect.getsource(b._build_one_job)
    assert 'lineheight=lineheight_factor' in fit
    assert 'lineheight=_greeting_pdf_lineheight(greeting_font_path)' in build
    assert 'font_size * MM_PER_PT * GREETING_LINE_ADVANCE_RATIO' in fit
    assert 'GREETING_BOTTOM_RESERVED_LINE_SLOTS * line_height_mm' in fit


def test_geometry_box_and_signature_preservation():
    assert (b.GREETING_BODY_LEFT_MM, b.GREETING_BODY_TOP_MM, b.GREETING_BODY_RIGHT_MM, b.GREETING_BODY_MAX_BOTTOM_MM) == (27.0, 32.0, 187.0, 212.0)
    assert b.GREETING_BOTTOM_RESERVED_LINE_SLOTS == 2
    assert b.SENDER_LINE_ADVANCE_MM == 8.0
    assert b.SENDER_TEXT_LEFT_MM == 31.0
    assert b.SENDER_TEXT_RIGHT_MM == 101.0
    assert b.SUPPORTED_SIGNATURE_VARIANTS == ('GRIGO', 'HERASYMENKO')
    d = yaml.safe_load(Path('coordination/graphic_design_lab/directions/greeting_cards/geometry_zones_v0_1.yaml').read_text(encoding='utf-8'))
    z = d['pages']['physical_4']['zones']['inside_text.greeting']
    assert z['bbox_trim_mm'] == [25.0, 30.0, 185.0, 210.0]
    assert z['typography_reference']['preferred_font_size_mm'] == 7.0
    assert z['typography_reference']['preferred_line_advance_mm'] == 8.0
    assert z['typography_reference']['alignment'] == 'CENTER'
    assert z['bottom_visual_line_reservation']['count'] == 2
    assert d['pages']['physical_4']['signature_profiles_candidate_v0_3']['DUAL_GRIGO_HERASYMENKO']['runtime_enabled'] is False

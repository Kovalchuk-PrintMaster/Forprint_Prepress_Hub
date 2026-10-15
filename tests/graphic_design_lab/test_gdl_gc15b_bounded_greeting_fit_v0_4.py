"""Review-only opt-in font fallback bound. Synthetic text; no client data."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.graphic_design_lab import greeting_card_builder_renderer as b


class FakePage:
    def __init__(self, fit_below: float):
        self.fit_below = fit_below
        self.sizes = []

    def insert_textbox(self, rect, text, *, fontsize, **kwargs):
        self.sizes.append(fontsize)
        return 0.0 if fontsize <= self.fit_below else -1.0


class FakePDF:
    def __init__(self, fit_below: float):
        self.page = FakePage(fit_below)

    def new_page(self, **kwargs):
        return self.page

    def close(self):
        pass


def test_original_tiers_are_prioritized_and_minimum_is_16():
    size = b.GREETING_FONT_SIZE_TIERS_PT
    assert size[0] == pytest.approx(7 * 72 / 25.4)
    assert size[1:] == (18.5, 17.0, 16.5, 16.0)
    assert min(size) == 16.0


@pytest.mark.parametrize('threshold,expected', [(30.0, 7*72/25.4), (17.0, 17.0), (16.0, 16.0)])
def test_fallback_prefers_largest_fitting_tier_without_moving_sender(monkeypatch, threshold, expected):
    scratch = FakePDF(threshold)
    monkeypatch.setattr(b, '_greeting_pdf_lineheight', lambda path: 1.0)
    monkeypatch.setattr(b.pymupdf, 'open', lambda *args, **kwargs: scratch)
    dummy_page = SimpleNamespace(rect=SimpleNamespace(width=608.0, height=853.0))
    size, sender, rect = b._fit_greeting(dummy_page, 'Sanitized greeting example',
                                        font_path=Path('sanitized.otf'), sender_line_count=4,
                                        fixed_sender_y_mm=224.5)
    assert size == pytest.approx(expected)
    assert sender == 224.5
    assert rect.x0 == pytest.approx(27 * b.PT_PER_MM)
    assert rect.x1 == pytest.approx(187 * b.PT_PER_MM)
    assert rect.y1 <= 212 * b.PT_PER_MM
    assert all(x >= 16.0 for x in scratch.page.sizes)


def test_cannot_silently_shrink_below_16(monkeypatch):
    scratch = FakePDF(15.9)
    monkeypatch.setattr(b, '_greeting_pdf_lineheight', lambda path: 1.0)
    monkeypatch.setattr(b.pymupdf, 'open', lambda *args, **kwargs: scratch)
    dummy_page = SimpleNamespace(rect=SimpleNamespace(width=608.0, height=853.0))
    with pytest.raises(ValueError, match='greeting_text_does_not_fit_canonical_tiers'):
        b._fit_greeting(dummy_page, 'Sanitized text', font_path=Path('no.otf'),
                        sender_line_count=4, fixed_sender_y_mm=224.5)
    assert min(scratch.page.sizes) == 16.0


def test_paragraph_compaction_keeps_every_word():
    source = 'First words\n\nSecond words\n\n\nThird words'
    result = b._page4_greeting_compact_paragraphs(source)
    assert result == 'First words\nSecond words\nThird words'

"""Pure geometric checks for candidate sender block, no private fonts or PDFs."""

from scripts.validation.gdl_greeting_card_sender_zone_plan_v0_1 import (
    bbox_excess_mm,
    candidate_container_bbox_pdf_mm,
)


def test_container_is_bleed_adjusted_but_size_preserved():
    profile = {"sender_text_center_trim_mm": [55.0, 235.0],
               "sender_text_size_mm": [50.0, 25.0]}
    assert candidate_container_bbox_pdf_mm(profile) == (32.0, 224.5, 82.0, 249.5)


def test_glyph_metrics_can_exceed_individual_slot_without_leaving_whole_container():
    # Glyph bounds below nominal 8-mm typesetting box, still within 25-mm block.
    glyph = [(32.3, 231.0, 79.2, 233.1)]
    slot = bbox_excess_mm(glyph, (32.0, 224.5, 82.0, 232.5), pt_per_mm=1.0)
    whole = bbox_excess_mm(glyph, (32.0, 224.5, 82.0, 249.5), pt_per_mm=1.0)
    assert slot["inside"] is False
    assert slot["outside_mm"] == {"left": 0.0, "top": 0.0,
                                  "right": 0.0, "bottom": 0.6}
    assert whole["inside"] is True


def test_real_excess_of_full_container_is_not_silently_allowed():
    glyph = [(31.4, 226.0, 83.1, 250.25)]
    proof = bbox_excess_mm(glyph, (32.0, 224.5, 82.0, 249.5), pt_per_mm=1.0)
    assert proof["inside"] is False
    assert proof["outside_mm"] == {"left": 0.6, "top": 0.0,
                                   "right": 1.1, "bottom": 0.75}


def test_empty_glyph_list_is_not_a_pass():
    proof = bbox_excess_mm([], (32.0, 224.5, 82.0, 249.5), pt_per_mm=1.0)
    assert not proof["inside"]
    assert proof["outside_mm"]["bottom"] is None


def test_union_bounds_across_glyphs_is_checked():
    glyphs = [(10, 20, 21, 28), (19, 23, 30, 40)]
    result = bbox_excess_mm(glyphs, (12, 19, 28, 39), pt_per_mm=1.0)
    assert result["outside_mm"] == {"left": 2.0, "top": 0.0,
                                    "right": 2.0, "bottom": 1.0}


def test_mm_to_pdf_point_normalization():
    ratio = 72.0 / 25.4
    glyphs = [(32.0 * ratio, 224.5 * ratio, 82.0 * ratio, 249.5 * ratio)]
    result = bbox_excess_mm(glyphs, (32, 224.5, 82, 249.5), pt_per_mm=ratio)
    assert result["inside"] is True

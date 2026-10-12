from pathlib import Path
import yaml
from app.graphic_design_lab import greeting_card_builder_renderer as b

SPEC = Path('coordination/graphic_design_lab/directions/greeting_cards/geometry_zones_v0_1.yaml')

def test_page4_greeting_zone_matches_illustrator_coordinates():
    d = yaml.safe_load(SPEC.read_text(encoding='utf-8'))
    zone = d['pages']['physical_4']['zones']['inside_text.greeting']
    assert zone['bbox_trim_mm'] == [25.0, 30.0, 185.0, 210.0]
    assert zone['bbox_pdf_mm'] == [27.0, 32.0, 187.0, 212.0]
    assert zone['illustrator_center_trim_mm'] == [105.0, 120.0]
    assert zone['max_width_mm'] == 160.0
    assert zone['max_height_mm'] == 180.0
    assert d['page_coordinate_system']['physical_pdf_mm'] == [214.0, 301.0]
    assert d['page_coordinate_system']['bleed_each_side_mm'] == 2.0

def test_renderer_uses_confirmed_maximum_text_zone():
    assert (b.GREETING_BODY_LEFT_MM, b.GREETING_BODY_TOP_MM, b.GREETING_BODY_RIGHT_MM, b.GREETING_BODY_MAX_BOTTOM_MM) == (27.0, 32.0, 187.0, 212.0)

def test_existing_sender_gap_and_overflow_guard_remain_in_force():
    assert b.MIN_SENDER_GAP_LINE_HEIGHTS == 2.0
    assert b.SENDER_CONSERVATIVE_SAFE_BOTTOM_MM == 285.0
    assert b._sender_block_within_conservative_safe_zone(214.0, 6)
    assert not b._sender_block_within_conservative_safe_zone(224.0, 8)

def test_registry_does_not_pretend_other_page_zones_are_approved():
    d = yaml.safe_load(SPEC.read_text(encoding='utf-8'))
    assert d['pages']['physical_1']['existing_slots']['front.recipient_branding']['status'] == 'DEFERRED_EXISTING_VARIANT_GEOMETRY'
    assert d['pages']['physical_3']['existing_slots']['inside_image.portrait']['status'] == 'REUSE_CURRENT_CANONICAL_REFERENCE_GEOMETRY'
    assert 'DUAL_RUNTIME_ACTIVATION' in d['not_authorized']

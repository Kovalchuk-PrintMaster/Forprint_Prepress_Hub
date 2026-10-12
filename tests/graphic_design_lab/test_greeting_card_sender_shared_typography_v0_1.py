from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.graphic_design_lab.greeting_card_sender_typography_v0_1 import (
    SenderTypographyBlocked,
    plan_single_sender_lines,
    shared_single_profile,
)


def test_shared_profile_common_for_both_single_variants():
    ids = ['closing_phrase', 'sender_name', 'sender_role_1', 'sender_role_2']
    a = plan_single_sender_lines(ids, start_y_pdf_mm=224, variant='GRIGO', font_ascender=0.9)
    b = plan_single_sender_lines(ids, start_y_pdf_mm=224, variant='HERASYMENKO', font_ascender=0.9)
    assert a == b
    assert [r.semantic_role for r in a] == ['closing_phrase', 'sender_name', 'sender_role', 'sender_role']
    assert [round(x.baseline_pdf_mm-y.baseline_pdf_mm, 2) for y,x in zip(a,a[1:])] == [7.24,7.24,5.17]
    assert [round(s.font_size_pt / (72 / 25.4),2) for s in a] == [4.44,5.0,4.44,4.44]


def test_repeated_roles_and_max_6_rows_stay_in_page():
    ids = ['closing_phrase','sender_name'] + [f'sender_role_{i}' for i in range(1,5)]
    slots = plan_single_sender_lines(ids, start_y_pdf_mm=236, variant='HERASYMENKO')
    assert slots[-1].bbox_pdf_mm[3] < 285
    assert len({s.object_id for s in slots}) == len(ids)


def test_dual_is_fail_closed():
    with pytest.raises(SenderTypographyBlocked, match='sender_single_variant_only'):
        plan_single_sender_lines(['closing_phrase'], start_y_pdf_mm=224, variant='DUAL_GRIGO_HERASYMENKO')
    p = shared_single_profile()
    assert p['applies_to'] == ['GRIGO', 'HERASYMENKO']


@pytest.mark.parametrize('ids', [[], ['sender_name','sender_name'], [''], ['  ']])
def test_invalid_ids_block(ids):
    with pytest.raises(SenderTypographyBlocked):
        plan_single_sender_lines(ids, start_y_pdf_mm=224, variant='GRIGO')


def test_invalid_profile_blocks_without_fallback():
    from copy import deepcopy
    import yaml
    from app.graphic_design_lab.greeting_card_sender_typography_v0_1 import REGISTRY
    d = yaml.safe_load(REGISTRY.read_text(encoding='utf-8'))
    bad = deepcopy(d)
    bad['profiles']['DUAL_INDIVIDUAL_V0_1']['runtime_enabled'] = True
    with pytest.raises(SenderTypographyBlocked, match='dual_sender_typography_gate_invalid'):
        shared_single_profile(bad)
    bad = deepcopy(d)
    bad['profiles']['SINGLE_SHARED_V0_1']['baseline_advance_mm']['role_to_role'] = 10
    with pytest.raises(SenderTypographyBlocked, match='sender_type_group_gap_not_larger'):
        shared_single_profile(bad)


def test_renderer_reuses_same_typography_for_single_variants():
    source = Path('app/graphic_design_lab/greeting_card_builder_renderer.py').read_text(encoding='utf-8')
    fn = next(x for x in ast.parse(source).body if isinstance(x, ast.FunctionDef) and x.name == '_render_sender_lines')
    snippet = ast.get_source_segment(source, fn)
    assert 'plan_single_sender_lines(' in snippet
    assert 'source_locked_slots(' in snippet  # existing source origin binding retained
    assert 'candidate_v03_slots(' not in snippet
    assert 'variant="DUAL' not in snippet

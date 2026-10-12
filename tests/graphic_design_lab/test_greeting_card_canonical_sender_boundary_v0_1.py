"""Source-verified signatory is not editable from Intake. No private assets."""
from __future__ import annotations

import hashlib
import inspect
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.graphic_design_lab import greeting_card_canonical_sender_v0_1 as c
from app.graphic_design_lab import greeting_card_builder_renderer as renderer
from app.graphic_design_lab.greeting_card_builder_input import validate_builder_payload_v1


def fake_doc_for(variant: str):
    info = c._expected_for_variant(variant)
    blocks = []
    for i, (text, bbox) in enumerate(zip(info['texts'], info['bboxes_pdf_mm'])):
        box = tuple(x / c.MM_PER_PT for x in bbox)
        blocks.append({'type': 0, 'bbox': box, 'lines': [{
            'bbox': box,
            'spans': [{'text': text, 'size': 13.0, 'color': 0x603913,
                       'origin': (box[0], box[3] - 0.5)}],
        }]})
    page = MagicMock()
    page.rect.width = 214 / c.MM_PER_PT
    page.rect.height = 301 / c.MM_PER_PT
    page.get_text.return_value = {'blocks': blocks}
    doc = MagicMock()
    doc.__enter__.return_value = doc
    doc.__exit__.return_value = None
    doc.__len__.return_value = 4
    doc.__getitem__.return_value = page
    return doc


@pytest.mark.parametrize('variant,count', [('GRIGO', 6), ('HERASYMENKO', 4)])
def test_exact_registered_source_rows_ignore_all_external_sender_text(monkeypatch, variant, count):
    monkeypatch.setattr(c, '_sha256_file', lambda _p: c._expected_for_variant(variant)['source_sha256'])
    monkeypatch.setattr(c.pymupdf, 'open', lambda _p: fake_doc_for(variant))
    rows = c.source_sender_rows(variant, Path('/PRIVATE/source.pdf'))
    assert len(rows) == count
    assert '\n'.join(r['text'] for r in rows) == '\n'.join(c._expected_for_variant(variant)['texts'])
    assert hashlib.sha256('\n'.join(r['text'] for r in rows).encode()).hexdigest() == c._expected_for_variant(variant)['text_sha256']


def test_unknown_and_disabled_dual_fail_closed():
    with pytest.raises(ValueError, match='unknown_canonical_sender_variant'):
        c._expected_for_variant('OTHER')
    with pytest.raises(ValueError, match='dual_runtime_disabled'):
        c._expected_for_variant('DUAL_GRIGO_HERASYMENKO')


def test_wrong_source_digest_fail_closed(monkeypatch):
    monkeypatch.setattr(c, '_sha256_file', lambda _p: '0' * 64)
    with pytest.raises(ValueError, match='canonical_sender_source_sha256_mismatch'):
        c.source_sender_rows('GRIGO', Path('/PRIVATE/source.pdf'))


def test_sender_text_is_not_an_input_to_builder_render():
    source = inspect.getsource(renderer._build_one_job)
    assert 'source_sender_rows(' in source
    assert 'render_source_sender_text(' in source
    assert '_mapping(data["signature_selection"])["variant_id"]' in source
    assert 'sender.get(\'lines\')' not in source
    assert 'sender.get("lines")' not in source


def test_legacy_extra_sender_lines_ignored_by_payload_validator():
    from app.graphic_design_lab.greeting_card_builder_input import BUILDER_PAYLOAD_SCHEMA
    data = {
        'schema_version': BUILDER_PAYLOAD_SCHEMA, 'revision': 'r001',
        'front': {'family': 'STANDARD', 'occasion': {'display_text': 'Test'}},
        'inside_image': {'mode': 'PORTRAIT', 'asset_id': 'p', 'asset_sha256': 'a'*64, 'accepted_artifact_ref': 'a'},
        'sender_text': {'signature_variant_id': 'GRIGO', 'lines': [
            {'id': 'wrong', 'text': 'INJECTED TITLE'}, {'id': 'wrong', 'text': 'INJECTED TITLE AGAIN'},
        ], 'signature_coordinates': [0, 0], 'signature_asset': 'CUSTOMER_SIG'},
    }
    assert validate_builder_payload_v1(data) == []
    data['sender_text'].pop('signature_variant_id')
    assert any('signature_variant_id:required' in x for x in validate_builder_payload_v1(data))


def test_render_native_source_spans_no_photographs_or_intake_artwork():
    calls = []
    class Target:
        def insert_text(self, *args, **kwargs):
            calls.append((args, kwargs))
    c.render_source_sender_text(Target(), [
        {'spans': [{'text': 'З щирою повагою,', 'origin': (88.4, 690.2),
                    'size': 12.0, 'color': 0x603913}]}
    ], font_path=Path('/PRIVATE/font.otf'))
    assert len(calls) == 1
    assert calls[0][1]['fontname'] == 'ZapfChanceryC'
    assert calls[0][1]['color'] == pytest.approx((96/255, 57/255, 19/255))
    assert calls[0][1]['fontfile'] == '/PRIVATE/font.otf'

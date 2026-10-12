"""GC-E2E page4 controlled geometry/structural regression tests."""
from __future__ import annotations
import io
from pathlib import Path

import pymupdf
import pytest
from PIL import Image

from app.graphic_design_lab import greeting_card_builder_renderer as b


def test_exact_page4_coordinates_source_profile_and_opacity():
    g = b._page4_runtime_profile('GRIGO')
    h = b._page4_runtime_profile('HERASYMENKO')
    assert g['greeting_bbox_pdf_mm'] == [27., 32., 187., 212.]
    assert g['single_sender']['GRIGO']['start_y_pdf_mm'] == 222.
    assert h['single_sender']['HERASYMENKO']['start_y_pdf_mm'] == 224.5
    assert g['watermark_opacity'] == 0.5
    assert g['single_sender']['GRIGO']['text_x_pdf_mm'] == [31., 101.]
    with pytest.raises(ValueError):
        b._page4_runtime_profile('DUAL_GRIGO_HERASYMENKO')


def test_sender_order_does_not_invent_or_lose_any_confirmed_text():
    rows = [
        {'id':'closing_phrase','text':'Closing'},
        {'id':'sender_role_1','text':'Role 1'},
        {'id':'sender_role_2','text':'Role 2'},
        {'id':'sender_name','text':'Name'},
    ]
    out=b._canonical_single_sender_lines(rows)
    assert [r['id'] for r in out] == ['closing_phrase','sender_name','sender_role_1','sender_role_2']
    assert sorted(r['text'] for r in out)==sorted(r['text'] for r in rows)
    with pytest.raises(ValueError):
        b._canonical_single_sender_lines(rows + [rows[1]])
    with pytest.raises(ValueError):
        b._canonical_single_sender_lines(rows[:-1])


def test_greeting_paragraphs_compacted_without_word_rewrite():
    raw='Перший абзац.\n\n\nДругий абзац.\n\nТретій абзац.'
    compact=b._page4_greeting_compact_paragraphs(raw)
    assert compact == 'Перший абзац.\nДругий абзац.\nТретій абзац.'
    assert b._normalized_whitespace(compact)==b._normalized_whitespace(raw)


def test_watermark_pil_pixel_alpha_halved_no_rgb_mutation(monkeypatch):
    im=Image.new('RGB',(4,4),(80,150,200))
    f=io.BytesIO(); im.save(f,format='PNG')
    fake={'xref':1,'bbox_rect':pymupdf.Rect(10,10,20,20)}
    monkeypatch.setattr(b,'_find_image',lambda *a,**kw: fake)
    monkeypatch.setattr(b,'_raw_image_payload',lambda *a,**kw:(f.getvalue(),None))
    class Target:
        def insert_image(self,rect,*,stream,keep_proportion,overlay):
            assert tuple(rect)==(10,10,20,20)
            with Image.open(io.BytesIO(stream)) as actual:
                assert actual.getpixel((0,0))==(80,150,200,128)
    b._insert_page4_watermark_half_opacity(None,None,Target())


def test_grigo_native_vector_only_replay_is_no_pdf_form():
    src=pymupdf.open();p=src.new_page(width=606.614,height=853.228)
    # Shape source has seven blue filled paths, within GRIGO source clip.
    for n in range(7):
        q=p.new_shape();cx=310+n*12
        q.draw_bezier(
            pymupdf.Point(cx,640),pymupdf.Point(cx+6,640),
            pymupdf.Point(cx+6,648),pymupdf.Point(cx+1,648),
        )
        q.finish(color=None,fill=(0.15,0.13,0.38),closePath=True)
        q.commit()
    dest=pymupdf.open();t=dest.new_page(width=606.614,height=853.228)
    # The raw source is deliberately in-memory; no source references in new page.
    b._overlay_grigo_signature(t,src)
    assert len(t.get_drawings()) == 7
    assert not t.get_text().strip()
    assert not t.get_images()
    assert not t.get_fonts()
    src.close();dest.close()

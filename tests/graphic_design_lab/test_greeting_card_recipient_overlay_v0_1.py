"""Review-only source-bound recipient logo capability regression tests."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pymupdf
import pytest
from PIL import Image

from app.graphic_design_lab.greeting_card_builder_input import validate_builder_payload_v1
from app.graphic_design_lab.greeting_card_builder_renderer import (
    _artifact_manifest_entry, _validate_first_slice_job,
)
from app.graphic_design_lab.greeting_card_recipient_overlay_v0_1 import (
    SENDER_BBOX_PDF_MM, RECIPIENT_ZONE_PDF_MM, validate_overlay_job,
    verify_canonical_geometry, verify_logo_file, fitted_bbox_mm,
    insert_recipient_logo, verify_rendered_recipient_logo,
)


def source_job():
    return {
        'job_id': 'fixture_source_only',
        'branding_selection': {'presence':'PRESENT','source_asset_id':'logo-001',
                               'target_object_id':'front.recipient_branding'},
        'exact_person_text_asset_bindings': {'recipient_branding': {
            'source_asset_id': 'logo-001'}},
        'builder_v1': {'schema_version':'gdl_greeting_card_builder_payload_v0_1',
            'revision':'r001', 'front':{'family':'RECIPIENT_BRANDING_OVERLAY',
                'occasion':{'kind':'BIRTHDAY','display_text':'Fixture Occasion'},
                'recipient_branding':{'asset_id':'logo-001',
                    'asset_sha256':'a'*64, 'accepted_artifact_ref':'accepted:logo-001'}},
            'inside_image':{'mode':'PORTRAIT','asset_id':'portrait-001',
                            'asset_sha256':'b'*64,'accepted_artifact_ref':'accepted:portrait'},
            'sender_text':{'signature_variant_id':'HERASYMENKO'}},
    }


def test_canonical_geometry_is_locked():
    verify_canonical_geometry()
    assert SENDER_BBOX_PDF_MM == (69.,39.,145.,115.)
    assert RECIPIENT_ZONE_PDF_MM == (26.,134.,188.,191.)


def test_confirmed_overlay_validates():
    job=source_job()
    validate_overlay_job(job)
    _validate_first_slice_job(job)
    assert validate_builder_payload_v1(job['builder_v1']) == []


def test_missing_branding_fails_closed():
    j=source_job();j['branding_selection']['presence']='ABSENT'
    with pytest.raises(ValueError, match='recipient_overlay_requires_present_branding'):
        _validate_first_slice_job(j)


def test_wrong_logo_source_id_fails_closed():
    j=source_job();j['builder_v1']['front']['recipient_branding']['asset_id']='other'
    with pytest.raises(ValueError, match='recipient_overlay_source_identity_mismatch'):
        _validate_first_slice_job(j)


def test_disagreeing_accepted_source_binding_fails_closed():
    j=source_job();j['exact_person_text_asset_bindings']['recipient_branding']['source_asset_id']='other'
    with pytest.raises(ValueError, match='recipient_overlay_source_identity_mismatch'):
        _validate_first_slice_job(j)


def test_arbitrary_logo_coordinates_cannot_override_canonical_geometry():
    j=source_job();j['builder_v1']['front']['recipient_branding']['bbox_pdf_mm']=[0,0,214,301]
    with pytest.raises(ValueError, match='recipient_overlay_binding_fields_invalid'):
        _validate_first_slice_job(j)


def test_standard_rejects_branding_override():
    j=source_job();j['builder_v1']['front']['family']='STANDARD'
    with pytest.raises(ValueError, match='standard_front_forbids_recipient_branding'):
        _validate_first_slice_job(j)


def test_artifact_must_match_selected_source_and_sha(tmp_path):
    p=tmp_path/'logo.png';Image.new('RGBA',(256,144),(80,20,100,160)).save(p)
    checksum=hashlib.sha256(p.read_bytes()).hexdigest()
    manifest={'schema_version':'gdl_greeting_card_builder_artifact_manifest_v0_1',
              'artifacts':{'a':{'source_asset_id':'logo-001','path':str(p),'sha256':checksum}}}
    assert _artifact_manifest_entry(manifest,artifact_ref='a',source_asset_id='logo-001',expected_sha256=checksum) == p
    with pytest.raises(ValueError, match='source_asset_id_mismatch'):
        _artifact_manifest_entry(manifest,artifact_ref='a',source_asset_id='wrong',expected_sha256=checksum)
    with pytest.raises(ValueError, match='sha256_mismatch'):
        _artifact_manifest_entry(manifest,artifact_ref='a',source_asset_id='logo-001',expected_sha256='0'*64)


def test_logo_proportions_centered_without_crop():
    box=fitted_bbox_mm((1954,1097))
    assert box[1]==134 and box[3]==191
    assert 26<box[0]<box[2]<188
    assert (box[2]-box[0])/(box[3]-box[1])==pytest.approx(1954/1097)


def test_png_composition_is_geometry_identical_in_saved_pdf(tmp_path):
    p=tmp_path/'logo.png';Image.new('RGBA',(256,144),(45,75,130,185)).save(p)
    meta=verify_logo_file(p)
    out=tmp_path/'out.pdf'
    with pymupdf.open() as d:
        page=d.new_page(width=214*72/25.4,height=301*72/25.4)
        inserted=insert_recipient_logo(page,p,meta)
        d.save(out)
    with pymupdf.open(out) as d:
        verify_rendered_recipient_logo(d[0],inserted['bbox_pdf_mm'],inserted['source_image_size_px'])


def test_renderer_rejects_unsupported_signature_variant():
    j=source_job();j['builder_v1']['sender_text']['signature_variant_id']='DUAL_GRIGO_HERASYMENKO'
    with pytest.raises(ValueError, match='signature_variant_not_implemented'):
        _validate_first_slice_job(j)


def test_payload_blocks_unsafe_logo_ref():
    j=source_job();j['builder_v1']['front']['recipient_branding']['accepted_artifact_ref']=''
    assert any('invalid_asset_binding' in e for e in validate_builder_payload_v1(j['builder_v1']))


def test_logo_rejects_non_png(tmp_path):
    p=tmp_path/'bad.jpg';Image.new('RGB',(256,144)).save(p)
    with pytest.raises(ValueError,match='only_png_supported'):
        verify_logo_file(p)

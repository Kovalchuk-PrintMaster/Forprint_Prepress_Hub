"""ZIP-level asset-binding regressions for Generic Recipient Branding Handoff.

These tests cover the transport boundary only. Canonical Accepted Constructor
Bundle validation remains owned by Builder Input, and print approval is outside
this worker's authority.
"""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest
import yaml
from PIL import Image

from scripts.graphic_design_lab.greeting_cards import intake_handoff_runner_v0_1 as handoff


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new('RGBA', (128, 96), (20, 60, 120, 180)).save(buf, format='PNG')
    return buf.getvalue()


@pytest.fixture
def package_case(tmp_path, monkeypatch):
    # Only the existing upstream bundle validator and digest function are
    # stubbed; this suite exercises the real transport/identity envelope.
    monkeypatch.setattr(handoff, 'validate_builder_ready_bundle_v1', lambda *a, **kw: [])
    monkeypatch.setattr(handoff, 'compute_bundle_sha256', lambda *a, **kw: 'verified-upstream-bundle')
    catalog = tmp_path / 'signature_catalog.yaml'
    catalog.write_text('catalog: fixture\n', encoding='utf-8')
    monkeypatch.setattr(handoff, 'CATALOG', catalog)
    resource = tmp_path / 'verified_server_resources.yaml'
    resource.write_text('resource_schema: fixture\n', encoding='utf-8')
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({'resource_manifest': str(resource)}), encoding='utf-8')
    image = png_bytes()
    buf = io.BytesIO()
    Image.new('RGBA', (210, 118), (150, 30, 10, 100)).save(buf, format='PNG')
    logo = buf.getvalue()
    jobs = [{
        'job_id': 'fixture_branded',
        'branding_selection': {'presence': 'PRESENT', 'source_asset_id': 'logo-source-1',
                               'target_object_id': 'front.recipient_branding'},
        'exact_person_text_asset_bindings': {'recipient_branding': {'source_asset_id': 'logo-source-1'}},
        'builder_v1': {
            'inside_image': {'mode': 'PORTRAIT', 'accepted_artifact_ref': 'portrait-ref-1',
                             'asset_id': 'portrait-source-1', 'asset_sha256': sha(image)},
            'front': {'family': 'RECIPIENT_BRANDING_OVERLAY',
                      'recipient_branding': {'asset_id': 'logo-source-1',
                                             'asset_sha256': sha(logo),
                                             'accepted_artifact_ref': 'logo-ref-1'}}
        }
    }]
    bundle = {'jobs': jobs, 'provenance_manifest': {'bundle_sha256': 'verified-upstream-bundle'}}
    assets = {
        'portrait-ref-1': {'source_asset_id': 'portrait-source-1', 'path': 'assets/portrait.png', 'sha256': sha(image)},
        'logo-ref-1': {'source_asset_id': 'logo-source-1', 'path': 'assets/recipient.png', 'sha256': sha(logo)},
    }
    members = {'assets/portrait.png': image, 'assets/recipient.png': logo}

    def save():
        bundle_raw = yaml.safe_dump(bundle, allow_unicode=True).encode('utf-8')
        artifacts_raw = yaml.safe_dump({'schema_version': handoff.ARTIFACT_SCHEMA, 'artifacts': assets}).encode('utf-8')
        header = json.dumps({'schema_version': handoff.SCHEMA, 'mode': 'REVIEW_ONLY',
                             'accepted_bundle_file_sha256': sha(bundle_raw),
                             'artifact_manifest_file_sha256': sha(artifacts_raw)}).encode('utf-8')
        zipfile_path = tmp_path / 'gdl_intake_handoff.zip'
        with zipfile.ZipFile(zipfile_path, 'w') as z:
            z.writestr('handoff_manifest.json', header)
            z.writestr('accepted_constructor_bundle.yaml', bundle_raw)
            z.writestr('artifact_manifest.yaml', artifacts_raw)
            for name, content in members.items():
                z.writestr(name, content)
        return zipfile_path, config

    return bundle, assets, members, save


def test_generic_branded_archive_has_two_source_bound_assets(package_case):
    _, _, _, save = package_case
    p, config = save()
    check = handoff.inspect_zip(p, config)
    assert check['assets'] == 2 and check['jobs'] == 1
    assert check['synthetic'] is False


def test_standard_archive_keeps_exactly_one_portrait_asset(package_case):
    bundle, assets, members, save = package_case
    job = bundle['jobs'][0]
    job['branding_selection'] = {'presence': 'ABSENT'}
    job['builder_v1']['front'] = {'family': 'STANDARD'}
    del assets['logo-ref-1']
    del members['assets/recipient.png']
    check = handoff.inspect_zip(*save())
    assert check['assets'] == 1


def test_missing_brand_logo_binding_blocks(package_case):
    _, assets, _, save = package_case
    del assets['logo-ref-1']
    with pytest.raises(handoff.HandoffBlocked, match='artifact_binding_set_mismatch'):
        handoff.inspect_zip(*save())


def test_logo_bytes_tampered_blocks(package_case):
    _, _, members, save = package_case
    members['assets/recipient.png'] = members['assets/recipient.png'] + b'UNTRUSTED'
    with pytest.raises(handoff.HandoffBlocked, match='artifact_asset_sha256_mismatch'):
        handoff.inspect_zip(*save())


def test_logo_source_identity_mismatch_blocks(package_case):
    bundle, _, _, save = package_case
    bundle['jobs'][0]['builder_v1']['front']['recipient_branding']['asset_id'] = 'incorrect-logo-source'
    with pytest.raises(handoff.HandoffBlocked, match='recipient_logo_source_identity_mismatch'):
        handoff.inspect_zip(*save())


def test_logo_exact_binding_mismatch_blocks(package_case):
    bundle, _, _, save = package_case
    bundle['jobs'][0]['exact_person_text_asset_bindings']['recipient_branding']['source_asset_id'] = 'incorrect'
    with pytest.raises(handoff.HandoffBlocked, match='recipient_logo_source_identity_mismatch'):
        handoff.inspect_zip(*save())


def test_branding_without_overlay_family_blocks(package_case):
    bundle, _, _, save = package_case
    bundle['jobs'][0]['builder_v1']['front']['family'] = 'STANDARD'
    with pytest.raises(handoff.HandoffBlocked, match='recipient_logo_family_presence_mismatch'):
        handoff.inspect_zip(*save())


def test_overlay_family_without_present_branding_blocks(package_case):
    bundle, _, _, save = package_case
    bundle['jobs'][0]['branding_selection']['presence'] = 'ABSENT'
    with pytest.raises(handoff.HandoffBlocked, match='recipient_logo_family_presence_mismatch'):
        handoff.inspect_zip(*save())


def test_same_artifact_ref_cannot_be_portrait_and_logo(package_case):
    bundle, _, _, save = package_case
    bundle['jobs'][0]['builder_v1']['front']['recipient_branding']['accepted_artifact_ref'] = 'portrait-ref-1'
    with pytest.raises(handoff.HandoffBlocked, match='artifact_ref_reused_across_roles'):
        handoff.inspect_zip(*save())


def test_unreviewed_noncanonical_default_asset_still_blocks(package_case):
    bundle, _, _, save = package_case
    bundle['jobs'][0]['builder_v1']['inside_image']['mode'] = 'DEFAULT_ASSET'
    with pytest.raises(handoff.HandoffBlocked, match='default_flowers_review_or_identity_invalid'):
        handoff.inspect_zip(*save())


def test_unknown_image_mode_keeps_fail_closed(package_case):
    bundle, _, _, save = package_case
    bundle['jobs'][0]['builder_v1']['inside_image']['mode'] = 'UNSUPPORTED_IMAGE_MODE'
    with pytest.raises(handoff.HandoffBlocked, match='image_mode_not_supported_in_handoff_v0_1'):
        handoff.inspect_zip(*save())


def test_unreferenced_branding_asset_is_rejected(package_case):
    bundle, assets, _, save = package_case
    bundle['jobs'][0]['branding_selection'] = {'presence': 'ABSENT'}
    bundle['jobs'][0]['builder_v1']['front'] = {'family': 'STANDARD'}
    with pytest.raises(handoff.HandoffBlocked, match='artifact_binding_set_mismatch'):
        handoff.inspect_zip(*save())


def test_missing_logo_source_file_blocks(package_case):
    _, _, members, save = package_case
    del members['assets/recipient.png']
    with pytest.raises(handoff.HandoffBlocked, match='artifact_path_not_in_archive'):
        handoff.inspect_zip(*save())


def test_two_jobs_reusing_one_confirmed_logo_are_allowed(package_case):
    bundle, _, _, save = package_case
    from copy import deepcopy
    second = deepcopy(bundle['jobs'][0])
    second['job_id'] = 'fixture_branded_second'
    second['builder_v1']['inside_image'] = dict(second['builder_v1']['inside_image'])
    # Same portrait and logo identity across jobs may be deduplicated.
    bundle['jobs'].append(second)
    check = handoff.inspect_zip(*save())
    assert check['jobs'] == 2 and check['assets'] == 2

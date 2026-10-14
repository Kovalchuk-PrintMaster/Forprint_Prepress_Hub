"""GC15-A: SHA-locked default flowers, no fabricated Creator or operator PASS."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from app.graphic_design_lab import greeting_card_builder_input as builder_input
from app.graphic_design_lab import greeting_card_builder_renderer as renderer
from app.graphic_design_lab.greeting_card_constructor_bundle import compute_bundle_sha256
from app.graphic_design_lab.greeting_card_private_resources import (
    EXPECTED_RESOURCES, RESOURCE_DEFAULT_FLOWERS,
)
from scripts.graphic_design_lab.greeting_cards import intake_handoff_runner_v0_1 as handoff
from scripts.graphic_design_lab.greeting_cards import unified_private_cycle_v0_1 as gc10

FLOWERS_SHA = EXPECTED_RESOURCES[RESOURCE_DEFAULT_FLOWERS]['sha256']


def payload(*, asset_id='flowers.default.v1', sha=FLOWERS_SHA, artifact_ref=None):
    return {
        'schema_version': builder_input.BUILDER_PAYLOAD_SCHEMA,
        'revision': 'r001',
        'front': {'family': 'STANDARD', 'occasion': {'kind': 'birthday', 'display_text': 'Approved exact title'}},
        'inside_image': {
            'mode': 'DEFAULT_ASSET', 'asset_id': asset_id,
            'asset_sha256': sha, 'accepted_artifact_ref': artifact_ref,
        },
        'sender_text': {'signature_variant_id': 'GRIGO', 'lines': []},
    }


def job(*, basis='SOURCE_ASSET_OPERATOR_REVIEW_PASS', visual_sha=FLOWERS_SHA):
    return {
        'job_id': 'approved-job-01',
        'builder_v1': payload(),
        'structured_greeting_data': {'occasion': 'birthday'},
        'exact_person_text_asset_bindings': {
            'portrait': {'source_asset_id': 'flowers.default.v1'}
        },
        'accepted_visual_assets': [{
            'acceptance_basis': basis, 'source_asset_id': 'flowers.default.v1',
            'artifact_ref': 'operator-reviewed-default-asset',
            'provenance_sha256': visual_sha,
        }],
        'branding_selection': {'presence': 'ABSENT'},
        'signature_selection': {'variant_id': 'GRIGO'},
    }


def test_default_is_declared_and_source_sha_is_canonical():
    assert 'DEFAULT_ASSET' in renderer.SUPPORTED_IMAGE_MODES
    assert FLOWERS_SHA == 'd9113f8d6f9627f9b106f5550e6187aaa562139fef6122e4834e7d4f2f3bbd67'
    assert builder_input.validate_builder_payload_v1(payload()) == []


@pytest.mark.parametrize('item', [
    payload(asset_id='noncanonical_flowers'),
    payload(sha='0' * 64),
    payload(artifact_ref='fake_creator_output'),
])
def test_default_does_not_allow_substitution_or_artifact_ref(item):
    errors = builder_input.validate_builder_payload_v1(item)
    assert errors


def test_default_requires_actual_operator_review_evidence(monkeypatch):
    monkeypatch.setattr(builder_input, 'validate_accepted_constructor_bundle', lambda *a, **kw: [])
    base_job = job()
    bundle = {'jobs': [base_job], 'provenance_manifest': {'bundle_sha256': ''}}
    bundle['provenance_manifest']['bundle_sha256'] = compute_bundle_sha256(bundle)
    assert builder_input.validate_builder_ready_bundle_v1(bundle, signature_catalog={}) == []

    unreviewed = deepcopy(bundle)
    unreviewed['jobs'][0]['accepted_visual_assets'][0]['acceptance_basis'] = 'CREATOR_INTERNAL_REVIEW_PASS'
    unreviewed['provenance_manifest']['bundle_sha256'] = compute_bundle_sha256(unreviewed)
    errors = builder_input.validate_builder_ready_bundle_v1(unreviewed, signature_catalog={})
    assert any('default_operator_review_required' in e for e in errors)

    mismatched = deepcopy(bundle)
    mismatched['jobs'][0]['accepted_visual_assets'][0]['provenance_sha256'] = '0' * 64
    mismatched['provenance_manifest']['bundle_sha256'] = compute_bundle_sha256(mismatched)
    errors = builder_input.validate_builder_ready_bundle_v1(mismatched, signature_catalog={})
    assert any('default_visual_digest_mismatch' in e for e in errors)


def test_renderer_requests_private_flowers_only_for_default_jobs():
    default = {'jobs': [job()]}
    ordinary = deepcopy(default)
    ordinary['jobs'][0]['builder_v1']['inside_image']['mode'] = 'PORTRAIT'
    assert RESOURCE_DEFAULT_FLOWERS in renderer._required_resource_ids_for_bundle(default)
    assert RESOURCE_DEFAULT_FLOWERS not in renderer._required_resource_ids_for_bundle(ordinary)


def test_handoff_does_not_require_flower_bytes_in_transport_zip():
    result = handoff._bundle_artifacts({'jobs': [job()]})
    assert result == {}
    bad = job(basis='CREATOR_INTERNAL_REVIEW_PASS')
    with pytest.raises(handoff.HandoffBlocked, match='default_flowers_review_or_identity_invalid'):
        handoff._bundle_artifacts({'jobs': [bad]})


def test_source_preflight_recognizes_supported_default_mode(monkeypatch, tmp_path):
    package = tmp_path / handoff.HANDOFF_FILENAME
    package.write_bytes(b'fixture_not_real_approved_zip')
    gc_job = job()
    monkeypatch.setattr(gc10.handoff, 'inspect_zip', lambda *a, **kw: {
        'archive_sha256': gc10.file_sha(package),
        'synthetic': False, 'jobs': 1, 'bundle': {'jobs': [gc_job]},
    })
    info = gc10.source_preflight(package, tmp_path / 'config.json')
    assert info['jobs'] == 1
    assert info['archive_sha256'] == gc10.file_sha(package)

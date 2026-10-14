"""GC-E2E-10 private one-command orchestration, without private customer data."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from scripts.graphic_design_lab.greeting_cards import unified_private_cycle_v0_1 as gc10


@pytest.fixture
def isolated_root(monkeypatch, tmp_path):
    (tmp_path / 'tmp').mkdir()
    monkeypatch.setattr(gc10, 'ROOT', tmp_path)
    monkeypatch.setattr(gc10, 'OUTPUT_ROOT', tmp_path / 'tmp/gdl_gc10_unified_private_cycle_v0_1')
    return tmp_path


def fake_source(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'acceptance_fixture_archive_bytes')
    return gc10.file_sha(path)


def test_input_path_fail_closed_outside_project_tmp(isolated_root):
    with pytest.raises(gc10.UnifiedBlocked, match='path_outside_project_tmp'):
        gc10.inside_tmp(isolated_root / 'outside')
    assert gc10.relative_tmp(isolated_root / 'tmp/safe') == 'tmp/safe'


def test_symlink_escape_not_accepted(isolated_root):
    shortcut = isolated_root / 'tmp/outbound'
    shortcut.symlink_to(isolated_root / 'outside', target_is_directory=True)
    with pytest.raises(gc10.UnifiedBlocked, match='path_outside_project_tmp'):
        gc10.inside_tmp(shortcut / 'artifact')


def test_source_preflight_rejects_unaccepted_and_synthetic(monkeypatch, tmp_path):
    pkg = tmp_path / gc10.handoff.HANDOFF_FILENAME
    sha = fake_source(pkg)
    inspection = {'package': pkg, 'archive_sha256': sha, 'jobs': 1, 'synthetic': True,
                  'bundle': {'jobs': [{'signature_selection': {'variant_id': 'GRIGO'},
                                      'builder_v1': {'sender_text': {'signature_variant_id': 'GRIGO'}, 'front': {'family': 'STANDARD'}, 'inside_image': {'mode': 'PORTRAIT'}}}]}}
    monkeypatch.setattr(gc10.handoff, 'inspect_zip', lambda *a: inspection)
    with pytest.raises(gc10.UnifiedBlocked, match='synthetic_package'):
        gc10.source_preflight(pkg, tmp_path / 'private-config.json')
    inspection['synthetic'] = False
    assert gc10.source_preflight(pkg, tmp_path / 'private-config.json')['jobs'] == 1
    inspection['archive_sha256'] = '0' * 64
    with pytest.raises(gc10.UnifiedBlocked, match='source_changed_during_preflight'):
        gc10.source_preflight(pkg, tmp_path / 'private-config.json')


def test_source_preflight_requires_proven_default_variant(monkeypatch, tmp_path):
    pkg = tmp_path / gc10.handoff.HANDOFF_FILENAME
    sha = fake_source(pkg)
    inspect = {'package': pkg, 'archive_sha256': sha, 'jobs': 1, 'synthetic': False,
               'bundle': {'jobs': [{'signature_selection': {'variant_id': 'DUAL_GRIGO_HERASYMENKO'},
                                    'builder_v1': {'sender_text': {'signature_variant_id': 'DUAL_GRIGO_HERASYMENKO'}, 'front': {'family': 'STANDARD'}, 'inside_image': {'mode': 'PORTRAIT'}}}]}}
    monkeypatch.setattr(gc10.handoff, 'inspect_zip', lambda *a: inspect)
    with pytest.raises(gc10.UnifiedBlocked, match='signature_variant_not_in_first_loop'):
        gc10.source_preflight(pkg, tmp_path / 'config.json')


def test_private_source_copy_exact_and_not_overwritable(isolated_root):
    source = isolated_root / 'external' / gc10.handoff.HANDOFF_FILENAME
    sha = fake_source(source)
    run = isolated_root / 'tmp' / 'a-run'
    run.mkdir()
    candidate = gc10.copy_source_to_private_tmp(source, run, sha)
    assert candidate.name == gc10.handoff.HANDOFF_FILENAME
    assert gc10.file_sha(candidate) == sha
    with pytest.raises(FileExistsError):
        gc10.copy_source_to_private_tmp(source, run, sha)


def test_private_source_copy_digest_change_fails_closed(isolated_root):
    source = isolated_root / 'external' / gc10.handoff.HANDOFF_FILENAME
    fake_source(source)
    run = isolated_root / 'tmp' / 'a-run'
    run.mkdir()
    with pytest.raises(gc10.UnifiedBlocked, match='copy_digest_mismatch'):
        gc10.copy_source_to_private_tmp(source, run, '0' * 64)


def test_manifest_binds_exact_handoff_constructor_and_review(isolated_root):
    run = isolated_root / 'tmp' / 'handoff' / 'runs' / 'x-1234567890'
    ingest = run / 'input_PRIVATE/output/report/job_result.json'
    handoff_report = run / 'handoff_result.json'
    review_root = isolated_root / 'tmp/review-run'
    review = review_root / 'review/review_summary.json'
    archive = review_root / 'full_card_review_PRIVATE.zip'
    for p in (ingest, handoff_report, review, archive):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('{}')
    source = isolated_root / 'tmp/source/gdl_intake_handoff.zip'
    source.parent.mkdir(parents=True)
    source.write_bytes(b'archive')
    result = {'status': 'PASS_REQUIRES_VISUAL_APPROVAL', 'client_review_published': False,
              'client_output_subdir': None, 'customer_approved': False,
              'production_approved': False, 'source_zip_unchanged': True,
              'private_review_dir': str(review_root.relative_to(isolated_root))}
    manifest = isolated_root / 'tmp/formal.yaml'
    pointers = gc10.make_manifest(run, result, source, manifest)
    document = yaml.safe_load(manifest.read_text())
    assert document['schema_version'] == gc10.closeout.SCHEMA
    assert document['sources'][0] == {
        'kind': 'STANDARD_REVIEW', 'report': pointers['review'],
        'constructor_ingest_report': pointers['ingest'],
        'handoff_report': pointers['handoff'],
        'handoff_package': 'tmp/source/gdl_intake_handoff.zip',
    }
    assert pointers['manifest'] == 'tmp/formal.yaml'


@pytest.mark.parametrize('key,value', [
    ('formal_constructor_acceptance_for_all_jobs', False),
    ('client_published', True),
    ('production_approvals', 1),
    ('page_count', 8),
    ('pdf_count', 2),
])
def test_closeout_must_be_fully_bound_and_nonproduction(key, value):
    record = {'status': 'INTERNAL_LAYOUT_CYCLE_VERIFIED_NOT_FOR_PRINT',
              'formal_constructor_acceptance_for_all_jobs': True,
              'job_count': 1, 'pdf_count': 1, 'page_count': 4,
              'production_approvals': 0, 'customer_approvals': 0,
              'client_published': False}
    gc10.require_closeout(record, 1)
    record[key] = value
    with pytest.raises(gc10.UnifiedBlocked, match='formal_constructor_closeout_not_verified'):
        gc10.require_closeout(record, 1)


def test_formal_closeout_record_matches_check_exactly(isolated_root, monkeypatch):
    manifest = isolated_root / 'tmp/manifest.yaml'
    manifest.write_text('schema_version: test\n')
    receipt = isolated_root / 'tmp/records/receipt.json'
    receipt.parent.mkdir()
    checked = {'schema_version': 'gdl_gc_review_cycle_closeout_v0_1',
               'status': 'INTERNAL_LAYOUT_CYCLE_VERIFIED_NOT_FOR_PRINT',
               'formal_constructor_acceptance_for_all_jobs': True,
               'job_count': 1, 'pdf_count': 1, 'page_count': 4,
               'production_approvals': 0, 'customer_approvals': 0,
               'client_published': False, 'manifest_sha256': gc10.file_sha(manifest)}
    receipt.write_text(json.dumps(checked))
    monkeypatch.setattr(gc10.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(
        returncode=0, stdout='GDL_GC_CYCLE_RECORD=tmp/records/receipt.json\n'))
    assert gc10.record_closeout(manifest, checked, 1) == receipt
    checked['page_count'] = 8
    with pytest.raises(gc10.UnifiedBlocked, match='formal_closeout_check_record_mismatch'):
        gc10.record_closeout(manifest, checked, 1)


def test_handoff_selector_rejects_ambiguous_parallel_runs(isolated_root, monkeypatch):
    folder = isolated_root / 'tmp/handoff/runs'
    folder.mkdir(parents=True)
    monkeypatch.setattr(gc10.handoff, 'RUNTIME', folder.parent)
    (folder / 'a-1234567890').mkdir()
    assert gc10.new_handoff_run(set(), '1234567890' + 'a'*54) == (folder / 'a-1234567890')
    (folder / 'b-1234567890').mkdir()
    with pytest.raises(gc10.UnifiedBlocked, match='identity_ambiguous'):
        gc10.new_handoff_run(set(), '1234567890' + 'a'*54)


def test_run_private_routes_through_existing_code_without_publishing(isolated_root, monkeypatch):
    source = isolated_root / 'external' / gc10.handoff.HANDOFF_FILENAME
    source_sha = fake_source(source)
    config = isolated_root / 'private_config.json'
    monkeypatch.setattr(gc10.handoff, 'RUNTIME', isolated_root / 'tmp/handoff')

    def inspected(pkg, _config):
        return {'package': pkg, 'archive_sha256': gc10.file_sha(pkg), 'jobs': 1,
                'synthetic': False,
                'bundle': {'jobs': [{'signature_selection': {'variant_id': 'GRIGO'},
                                    'builder_v1': {'sender_text': {'signature_variant_id': 'GRIGO'}, 'front': {'family': 'STANDARD'}, 'inside_image': {'mode': 'PORTRAIT'}}}]}}
    monkeypatch.setattr(gc10.handoff, 'inspect_zip', inspected)
    called = []

    def fake_handoff(inspection, _config, *, publish_client):
        called.append(publish_client)
        assert inspection['archive_sha256'] == source_sha
        runs = gc10.handoff.RUNTIME / 'runs'
        p = runs / ('stamp-' + source_sha[:10])
        for filepath in (
            p / 'input_PRIVATE/output/report/job_result.json', p / 'handoff_result.json',
            isolated_root / 'tmp/private-review/review/review_summary.json',
            isolated_root / 'tmp/private-review/full_card_review_PRIVATE.zip',
        ):
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text('{}')
        return {'source_zip_sha256': source_sha, 'job_count': 1,
                'status': 'PASS_REQUIRES_VISUAL_APPROVAL', 'client_review_published': False,
                'client_output_subdir': None, 'customer_approved': False,
                'production_approved': False, 'source_zip_unchanged': True,
                'private_review_dir': 'tmp/private-review'}
    monkeypatch.setattr(gc10.handoff, 'materialize_and_run', fake_handoff)

    checked = {'status': 'INTERNAL_LAYOUT_CYCLE_VERIFIED_NOT_FOR_PRINT',
               'formal_constructor_acceptance_for_all_jobs': True, 'job_count': 1,
               'pdf_count': 1, 'page_count': 4, 'production_approvals': 0,
               'customer_approvals': 0, 'client_published': False}
    monkeypatch.setattr(gc10.closeout, 'compile_closeout', lambda path: dict(checked))
    receipt = isolated_root / 'tmp/closeout.json'
    receipt.write_text('{}')
    monkeypatch.setattr(gc10, 'record_closeout', lambda *args: receipt)
    output = gc10.run_private(source, config)
    assert called == [False]
    assert output['summary']['formal_constructor_evidence_verified_for_all_jobs'] is True
    assert output['summary']['client_published'] is False
    assert output['summary']['source_zip_sha256'] == source_sha
    assert (isolated_root / output['report']).is_file()

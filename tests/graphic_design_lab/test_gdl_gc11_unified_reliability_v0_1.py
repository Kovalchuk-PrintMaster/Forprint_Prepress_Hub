"""GC11: lock, explicit rerun, source-before-receipt, immutable prior evidence."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from scripts.graphic_design_lab.greeting_cards import unified_private_cycle_v0_1 as gc10


@pytest.fixture
def private_root(monkeypatch, tmp_path):
    (tmp_path / 'tmp').mkdir()
    monkeypatch.setattr(gc10, 'ROOT', tmp_path)
    monkeypatch.setattr(gc10, 'OUTPUT_ROOT', tmp_path / 'tmp/gdl_gc10_unified_private_cycle_v0_1')
    return tmp_path


def sample_source(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'reviewed_private_source_fixture')
    return gc10.file_sha(path)


def accepted_closeout(manifest):
    return {
        'schema_version': 'gdl_gc_review_cycle_closeout_v0_1',
        'status': 'INTERNAL_LAYOUT_CYCLE_VERIFIED_NOT_FOR_PRINT',
        'formal_constructor_acceptance_for_all_jobs': True,
        'job_count': 1, 'pdf_count': 1, 'page_count': 4,
        'production_approvals': 0, 'customer_approvals': 0,
        'client_published': False, 'manifest_sha256': gc10.file_sha(manifest),
    }


def make_prior_success(root, monkeypatch):
    run = root / 'tmp/gdl_gc10_unified_private_cycle_v0_1/runs/old-run'
    original = run / 'source' / gc10.handoff.HANDOFF_FILENAME
    source_sha = sample_source(original)
    manifest = root / 'tmp/private_manifest.yaml'
    manifest.write_text('schema_version: fixture\n', encoding='utf-8')
    closeout = accepted_closeout(manifest)
    receipt = root / 'tmp/records/receipt.json'
    receipt.parent.mkdir(parents=True)
    receipt.write_text(json.dumps(closeout), encoding='utf-8')
    report = {
        'schema_version': gc10.SCHEMA,
        'status': 'PRIVATE_CYCLE_PASS_REQUIRES_VISUAL_REVIEW',
        'source_zip_sha256': source_sha,
        'job_count': 1, 'client_published': False,
        'production_approved': False,
        'formal_closeout_manifest': str(manifest.relative_to(root)),
        'closeout_receipt': str(receipt.relative_to(root)),
        'closeout_receipt_sha256': gc10.file_sha(receipt),
    }
    (run / 'unified_cycle_result.json').write_text(json.dumps(report), encoding='utf-8')
    monkeypatch.setattr(gc10.closeout, 'compile_closeout', lambda path: dict(closeout))
    return source_sha, receipt


def test_lock_conflict_and_release(private_root):
    with gc10.operator_cycle_lock():
        with pytest.raises(gc10.UnifiedBlocked, match='unified_cycle_already_running'):
            with gc10.operator_cycle_lock():
                pass
    # Releasing the file lock, not unlinking the lock file, is important.
    with gc10.operator_cycle_lock():
        pass
    assert (gc10.OUTPUT_ROOT / '.operator_cycle.lock').is_file()


def test_lock_fails_closed_on_symlink(private_root):
    lockroot = gc10.OUTPUT_ROOT
    lockroot.mkdir(parents=True)
    (private_root / 'outside').write_text('never acquire', encoding='utf-8')
    (lockroot / '.operator_cycle.lock').symlink_to(private_root / 'outside')
    with pytest.raises(gc10.UnifiedBlocked, match='cycle_lock_open_failed'):
        with gc10.operator_cycle_lock():
            pass


def test_prior_success_zero_when_no_history(private_root):
    assert gc10.prior_successful_cycles('1'*64) == 0


def test_prior_success_revalidates_manifest_and_receipt(private_root, monkeypatch):
    source_sha, receipt = make_prior_success(private_root, monkeypatch)
    assert gc10.prior_successful_cycles(source_sha) == 1
    receipt.write_text('{"tampered": true}', encoding='utf-8')
    with pytest.raises(gc10.UnifiedBlocked, match='prior_receipt_digest_invalid'):
        gc10.prior_successful_cycles(source_sha)


def test_prior_success_does_not_count_failed_or_other_source(private_root, monkeypatch):
    source_sha, _ = make_prior_success(private_root, monkeypatch)
    assert gc10.prior_successful_cycles('f'*64) == 0
    report = next(gc10.OUTPUT_ROOT.glob('runs/*/unified_cycle_result.json'))
    obj = json.loads(report.read_text())
    obj['status'] = 'BLOCKED'
    report.write_text(json.dumps(obj), encoding='utf-8')
    assert gc10.prior_successful_cycles(source_sha) == 0


def test_duplicate_source_blocked_before_new_run(private_root, monkeypatch):
    source_sha, _ = make_prior_success(private_root, monkeypatch)
    pkg = private_root / 'external' / gc10.handoff.HANDOFF_FILENAME
    sample_source(pkg)
    # In this unit check the preflight's already validated fields are supplied.
    monkeypatch.setattr(gc10, 'source_preflight', lambda p, c: {'archive_sha256': source_sha, 'jobs': 1})
    with pytest.raises(gc10.UnifiedBlocked, match='repeat_policy_blocked'):
        gc10.run_private(pkg, private_root / 'config.json')
    assert len(list(gc10.OUTPUT_ROOT.glob('runs/*/unified_cycle_result.json'))) == 1


def test_operator_repeat_opt_in_reaches_private_handoff(private_root, monkeypatch):
    source_sha, _ = make_prior_success(private_root, monkeypatch)
    pkg = private_root / 'external' / gc10.handoff.HANDOFF_FILENAME
    pkg.parent.mkdir()
    # The original fixture bytes must be exact for a real replay.
    pkg.write_bytes(b'reviewed_private_source_fixture')
    monkeypatch.setattr(gc10, 'source_preflight', lambda p, c: {'archive_sha256': source_sha, 'jobs': 1})
    invoked = []
    monkeypatch.setattr(gc10.handoff, 'RUNTIME', private_root / 'tmp/runtime')

    def block_handoff(inspection, config, *, publish_client):
        invoked.append(publish_client)
        raise RuntimeError('intentional test boundary')

    monkeypatch.setattr(gc10.handoff, 'materialize_and_run', block_handoff)
    with pytest.raises(gc10.UnifiedBlocked, match='private_handoff_builder_blocked'):
        gc10.run_private(pkg, private_root / 'config.json', allow_repeat=True)
    assert invoked == [False]
    blocked = [json.loads(p.read_text()) for p in gc10.OUTPUT_ROOT.glob('runs/*/unified_cycle_result.json')
               if json.loads(p.read_text()).get('status') == 'BLOCKED']
    assert len(blocked) == 1
    assert blocked[0]['blocked_stage'] == 'PRIVATE_HANDOFF_BUILDER'


def test_receipt_not_recorded_if_source_changes_before_record(private_root, monkeypatch):
    pkg = private_root / 'external' / gc10.handoff.HANDOFF_FILENAME
    source_sha = sample_source(pkg)
    monkeypatch.setattr(gc10, 'source_preflight', lambda p, c: {'archive_sha256': source_sha, 'jobs': 1})
    monkeypatch.setattr(gc10, 'prior_successful_cycles', lambda sha: 0)
    monkeypatch.setattr(gc10.handoff, 'RUNTIME', private_root / 'tmp/runtime')
    monkeypatch.setattr(gc10.handoff, 'materialize_and_run', lambda *a, **kw: {
        'source_zip_sha256': source_sha, 'job_count': 1,
        'status': 'PASS_REQUIRES_VISUAL_APPROVAL',
    })
    monkeypatch.setattr(gc10, 'new_handoff_run', lambda *args: private_root / 'tmp/fake_handoff')

    def make_manifest(run, result, source, path):
        path.write_text('schema_version: fixture\n', encoding='utf-8')
        return {'manifest': str(path.relative_to(private_root)), 'ingest': 'tmp/fake_ingest',
                'handoff': 'tmp/fake_handoff', 'review': 'tmp/fake_review'}

    monkeypatch.setattr(gc10, 'make_manifest', make_manifest)

    def mutate_after_closeout_check(manifest):
        pkg.write_bytes(b'changed_during_builder')
        return accepted_closeout(manifest)

    monkeypatch.setattr(gc10.closeout, 'compile_closeout', mutate_after_closeout_check)
    recorded = []
    monkeypatch.setattr(gc10, 'record_closeout', lambda *a: recorded.append(True))
    with pytest.raises(gc10.UnifiedBlocked, match='pre_record_source_check_blocked'):
        gc10.run_private(pkg, private_root / 'config.json')
    assert recorded == []
    blocked = [json.loads(p.read_text()) for p in gc10.OUTPUT_ROOT.glob('runs/*/unified_cycle_result.json')]
    assert len(blocked) == 1
    assert blocked[0]['blocked_stage'] == 'PRE_RECORD_SOURCE_CHECK'
    assert blocked[0]['client_published'] is False


def test_repeat_option_allowed_in_run_mode_only(private_root, monkeypatch, capsys):
    pkg = private_root / 'external' / gc10.handoff.HANDOFF_FILENAME
    monkeypatch.setattr(sys, 'argv', ['gc10', '--mode', 'preflight', '--package', str(pkg), '--allow-repeat'])
    assert gc10.main() == 2
    output = capsys.readouterr().out
    assert 'allow_repeat_run_mode_only' in output
    assert 'CLIENT_PUBLISHED=false' in output

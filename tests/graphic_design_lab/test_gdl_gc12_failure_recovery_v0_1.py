"""GC12: receipt-boundary fault injections without customer data or real rendering.

The runtime continues to use existing Constructor/Builder/closeout components.
These tests simulate only control-plane crashes and authority boundaries.
"""
from __future__ import annotations
import json
from pathlib import Path

import pytest

from scripts.graphic_design_lab.greeting_cards import unified_private_cycle_v0_1 as gc10


@pytest.fixture
def sandbox(monkeypatch, tmp_path):
    (tmp_path / 'tmp').mkdir()
    monkeypatch.setattr(gc10, 'ROOT', tmp_path)
    monkeypatch.setattr(gc10, 'OUTPUT_ROOT', tmp_path / 'tmp/gdl_gc10_unified_private_cycle_v0_1')
    monkeypatch.setattr(gc10.handoff, 'RUNTIME', tmp_path / 'tmp/handoff')
    pkg = tmp_path / 'private' / gc10.handoff.HANDOFF_FILENAME
    pkg.parent.mkdir()
    pkg.write_bytes(b'GC12_OPERATOR_APPROVED_PRIVATE_TEST_ONLY')
    sha = gc10.file_sha(pkg)
    config = tmp_path / 'private_config.json'

    monkeypatch.setattr(gc10, 'source_preflight', lambda p, c: {
        'archive_sha256': sha, 'jobs': 1,
    })
    monkeypatch.setattr(gc10.handoff, 'materialize_and_run', lambda *args, **kwargs: {
        'status': 'PASS_REQUIRES_VISUAL_APPROVAL',
        'source_zip_sha256': sha, 'job_count': 1,
        'client_review_published': False,
    })
    monkeypatch.setattr(gc10, 'new_handoff_run', lambda *args: tmp_path / 'tmp/handoff-run')

    def fake_manifest(run, result, source, path):
        path.write_text('schema_version: test-only\n', encoding='utf-8')
        return {'manifest': str(path.relative_to(tmp_path)),
                'ingest': 'tmp/fake-ingest',
                'handoff': 'tmp/fake-handoff',
                'review': 'tmp/fake-review'}

    monkeypatch.setattr(gc10, 'make_manifest', fake_manifest)

    def checked(path):
        return {
            'status': 'INTERNAL_LAYOUT_CYCLE_VERIFIED_NOT_FOR_PRINT',
            'formal_constructor_acceptance_for_all_jobs': True,
            'job_count': 1, 'pdf_count': 1, 'page_count': 4,
            'production_approvals': 0, 'customer_approvals': 0,
            'client_published': False,
            'manifest_sha256': gc10.file_sha(path),
        }

    monkeypatch.setattr(gc10.closeout, 'compile_closeout', checked)
    return pkg, config, sha, tmp_path, monkeypatch


def _cycle(root):
    results = list((root / 'tmp/gdl_gc10_unified_private_cycle_v0_1/runs').glob('*/unified_cycle_result.json'))
    assert len(results) == 1
    return json.loads(results[0].read_text('utf-8')), results[0].parent


def test_receipt_failure_marks_unresolved_and_blocks_repeat(sandbox):
    package, config, sha, root, monkeypatch = sandbox
    before = gc10.file_sha(package)
    recorded = []

    def break_record(*args):
        recorded.append(1)
        raise gc10.UnifiedBlocked('forced_receipt_io_failure')

    monkeypatch.setattr(gc10, 'record_closeout', break_record)
    with pytest.raises(gc10.UnifiedBlocked, match='formal_closeout_record_blocked'):
        gc10.run_private(package, config)
    report, run = _cycle(root)
    marker = run / 'closeout_record_intent.json'
    assert marker.is_file() and len(recorded) == 1
    assert json.loads(marker.read_text())['source_zip_sha256'] == sha
    assert report['status'] == 'BLOCKED'
    assert report['blocked_stage'] == 'FORMAL_CLOSEOUT_RECORD'
    assert report['requires_operator_reconciliation'] is True
    assert report['next_action'] == 'RECONCILE_PENDING_RECEIPT_BEFORE_ANY_REPEAT'
    assert report['client_published'] is False
    assert report['production_approved'] is False
    assert 'closeout_receipt' not in report
    with pytest.raises(gc10.UnifiedBlocked, match='unresolved_closeout_finalization_requires_review'):
        gc10.prior_successful_cycles(sha)
    with pytest.raises(gc10.UnifiedBlocked, match='repeat_policy_blocked'):
        gc10.run_private(package, config, allow_repeat=True)
    assert len(recorded) == 1
    assert gc10.file_sha(package) == before


def test_post_receipt_integrity_failure_keeps_receipt_but_not_success(sandbox):
    package, config, sha, root, monkeypatch = sandbox
    receipts = []
    def finished_record(manifest, checked, job_count):
        receipt = root / 'tmp/records/receipt.json'
        receipt.parent.mkdir()
        receipt.write_text(json.dumps(checked), encoding='utf-8')
        receipts.append(receipt)
        # Simulate source change during the post-receipt integrity window.
        package.write_bytes(b'changed-after-immutable-receipt')
        return receipt

    monkeypatch.setattr(gc10, 'record_closeout', finished_record)
    with pytest.raises(gc10.UnifiedBlocked, match='final_source_check_blocked'):
        gc10.run_private(package, config)
    report, run = _cycle(root)
    assert len(receipts) == 1 and receipts[0].is_file()
    assert report['status'] == 'BLOCKED'
    assert report['blocked_stage'] == 'FINAL_SOURCE_CHECK'
    assert report['requires_operator_reconciliation'] is True
    assert report['closeout_receipt_sha256'] == gc10.file_sha(receipts[0])
    assert report['source_zip_sha256'] == sha
    assert (run / 'closeout_record_intent.json').is_file()
    assert report['production_approved'] is False
    with pytest.raises(gc10.UnifiedBlocked, match='unresolved_closeout_finalization_requires_review'):
        gc10.prior_successful_cycles(sha)


def test_sigkill_like_missing_terminal_report_blocks_rerun(sandbox):
    package, config, sha, root, monkeypatch = sandbox
    run = root / 'tmp/gdl_gc10_unified_private_cycle_v0_1/runs/unfinished-after-sigkill'
    run.mkdir(parents=True)
    marker = run / 'closeout_record_intent.json'
    marker.write_text(json.dumps({'schema_version': gc10.SCHEMA,
                                  'status': 'RECEIPT_RECORD_INTENT',
                                  'source_zip_sha256': sha,
                                  'manifest_sha256': 'f' * 64,
                                  'job_count': 1,
                                  'production_approved': False,
                                  'customer_approved': False,
                                  'client_published': False}), encoding='utf-8')
    with pytest.raises(gc10.UnifiedBlocked, match='unresolved_closeout_finalization_requires_review'):
        gc10.prior_successful_cycles(sha)
    with pytest.raises(gc10.UnifiedBlocked, match='repeat_policy_blocked'):
        gc10.run_private(package, config, allow_repeat=True)
    assert not list((root / 'tmp/gdl_gc10_unified_private_cycle_v0_1/runs').glob('*/source/*'))


def test_completed_marker_remains_safe_and_prior_evidence_still_verified(sandbox):
    package, config, sha, root, monkeypatch = sandbox
    run = root / 'tmp/gdl_gc10_unified_private_cycle_v0_1/runs/closed'
    run.mkdir(parents=True)
    (run / 'closeout_record_intent.json').write_text(json.dumps({
        'schema_version': gc10.SCHEMA,
        'status': 'RECEIPT_RECORD_INTENT',
        'source_zip_sha256': sha,
    }), encoding='utf-8')
    (run / 'unified_cycle_result.json').write_text(json.dumps({
        'schema_version': gc10.SCHEMA,
        'status': 'PRIVATE_CYCLE_PASS_REQUIRES_VISUAL_REVIEW',
        'source_zip_sha256': sha,
    }), encoding='utf-8')
    verified = []
    monkeypatch.setattr(gc10, '_verified_prior_success', lambda path, checksum: verified.append((path, checksum)))
    assert gc10.prior_successful_cycles(sha) == 1
    assert len(verified) == 1 and verified[0][1] == sha


def test_unrelated_source_marker_does_not_block(sandbox):
    package, config, sha, root, monkeypatch = sandbox
    run = root / 'tmp/gdl_gc10_unified_private_cycle_v0_1/runs/other-source'
    run.mkdir(parents=True)
    (run / 'closeout_record_intent.json').write_text(json.dumps({
        'schema_version': gc10.SCHEMA,
        'status': 'RECEIPT_RECORD_INTENT',
        'source_zip_sha256': 'f' * 64,
    }), encoding='utf-8')
    assert gc10.prior_successful_cycles(sha) == 0


def test_corrupt_pending_marker_fails_closed(sandbox):
    package, config, sha, root, monkeypatch = sandbox
    run = root / 'tmp/gdl_gc10_unified_private_cycle_v0_1/runs/corrupt'
    run.mkdir(parents=True)
    (run / 'closeout_record_intent.json').write_text('{broken-json', encoding='utf-8')
    with pytest.raises(gc10.UnifiedBlocked, match='finalization_marker_unreadable'):
        gc10.prior_successful_cycles(sha)

"""Sanitized GC14 client queue regression, no real SMB/user data."""
import base64
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
import yaml
from scripts.graphic_design_lab.greeting_cards import smb_workspace_queue_v0_1 as q


def test_unicode_workspace_resolution_and_escape(tmp_path):
    share = tmp_path / 'share'
    root = share / 'Клієнт Тест' / '_forprint_automation'
    root.mkdir(parents=True)
    token = base64.urlsafe_b64encode('Клієнт Тест/_forprint_automation'.encode()).decode().rstrip('=')
    assert q.workspace_path('In_Progress', token, roots={'In_Progress': share}) == root
    for invalid in ('../_forprint_automation', 'a/../_forprint_automation', 'a/b/c', '/a/b'):
        t = base64.urlsafe_b64encode(invalid.encode()).decode().rstrip('=')
        with pytest.raises(q.QueueBlocked):
            q.workspace_path('In_Progress', t, roots={'In_Progress': share})


def staging(path, bad=False):
    blobs = {
        'SERVER_INGEST_STAGING.yaml': yaml.safe_dump({'packet_kind': 'STRUCTURED_INTAKE_STAGING_NOT_ACCEPTED_BUNDLE', 'asset_selection_rule': {'all_job_ids': ['one', 'two']}}).encode(),
        'BLOCKERS.yaml': yaml.safe_dump({'final_handoff_allowed': False, 'blockers': [{'code': 'DEFAULT_ASSET_BUILDER_RUNTIME_UNSUPPORTED'}]}).encode(),
        'assets/flowers.default.v1.png': b'sanitized_flowers_bytes',
    }
    manifest = {'schema_version': 'gdl_intake_staging_packet_manifest_v0_1',
                'entries': [{'path': name, 'sha256': hashlib.sha256(blob).hexdigest(), 'bytes': len(blob)}
                            for name, blob in blobs.items()]}
    if bad:
        manifest['entries'][0]['sha256'] = '0' * 64
    with ZipFile(path, 'w') as z:
        for name, blob in blobs.items(): z.writestr(name, blob)
        z.writestr('packet_manifest.json', json.dumps(manifest))


def test_staging_report_no_pdfs_and_stable_rerun(tmp_path, monkeypatch):
    workspace = tmp_path / '_forprint_automation'
    inp = workspace / 'input'; out = workspace / 'output'
    inp.mkdir(parents=True); out.mkdir()
    source = inp / 'gdl_intake_blocked_packet_flowers_test.zip'
    staging(source)
    monkeypatch.setattr(q, 'ROOT', tmp_path)
    assert q.run(workspace) == {'BLOCKED': 1}
    d = next(out.iterdir())
    assert list((d / 'pdf').iterdir()) == []
    assert list((d / 'png').iterdir()) == []
    report = json.loads((d / 'report.json').read_text())
    assert report['source_archive'] == source.name
    assert report['source_sha256'] == q.sha_file(source)
    assert report['status'] == 'BLOCKED'
    assert report['blocker_codes'] == ['DEFAULT_ASSET_BUILDER_RUNTIME_UNSUPPORTED']
    assert q.run(workspace) == {'SKIPPED_ALREADY_REPORTED': 1}
    assert len(list(out.iterdir())) == 1


def test_staging_bad_digest_is_blocked_without_creator(tmp_path, monkeypatch):
    inp = tmp_path / '_forprint_automation/input'
    out = inp.parent / 'output'
    inp.mkdir(parents=True); out.mkdir()
    staging(inp / 'bad.zip', bad=True)
    monkeypatch.setattr(q, 'ROOT', tmp_path)
    monkeypatch.setattr(q, 'gc10_module', lambda: pytest.fail('never call GC10 for staging'))
    assert q.run(inp.parent) == {'BLOCKED': 1}
    d = next(out.iterdir())
    assert json.loads((d/'report.json').read_text())['reason'] == 'staging_file_digest_mismatch'


def test_unknown_archive_is_not_automatically_accepted(tmp_path, monkeypatch):
    inp = tmp_path / '_forprint_automation/input'
    out = inp.parent / 'output'
    inp.mkdir(parents=True); out.mkdir()
    with ZipFile(inp / 'untrusted.zip', 'w') as z: z.writestr('untrusted.txt', b'no')
    monkeypatch.setattr(q, 'ROOT', tmp_path)
    monkeypatch.setattr(q, 'gc10_module', lambda: pytest.fail('never call GC10 for unknown'))
    assert q.run(inp.parent) == {'BLOCKED': 1}
    d = next(out.iterdir())
    assert json.loads((d/'report.json').read_text())['reason'] == 'UNSUPPORTED_ARCHIVE_ENVELOPE'


def test_new_handoff_delegates_only_to_gc10_and_exports_no_zip(tmp_path, monkeypatch):
    workspace = tmp_path / '_forprint_automation'
    inp, out = workspace / 'input', workspace / 'output'
    inp.mkdir(parents=True); out.mkdir()
    src = inp / 'arbitrary_acceptance_name.zip'
    with ZipFile(src, 'w') as z:
        for name in q.GC10_REQUIRED: z.writestr(name, b'fixture')
    source_sha = q.sha_file(src)
    root = tmp_path
    private = root / 'tmp/private'
    report_file = private / 'unified_cycle_result.json'
    review_path = root / 'tmp/review/review/review_summary.json'
    review_path.parent.mkdir(parents=True)
    archive = review_path.parent.parent / 'full_card_review_PRIVATE.zip'
    jobid = 'sanitized_job'; rev = 'r001'
    pdf_name = f'builder_outputs_PRIVATE/completed/{jobid}__{rev}.pdf'
    pdf_data = b'%PDF-FAKE-TEST-ONLY'
    review = {'review_state': 'READY_FOR_INTERNAL_VISUAL_REVIEW', 'synthetic_fixture': False,
              'pdf_preview_pixel_replay': 'PASS', 'job_count': 1, 'pdf_count': 1, 'png_preview_count': 4,
              'jobs': [{'job_id': jobid, 'revision': rev, 'pdf': pdf_name,
                        'pdf_sha256': hashlib.sha256(pdf_data).hexdigest(), 'page_count': 4,
                        'preview_count': 4, 'preview_pixel_replay': 'PASS'}]}
    review_path.write_text(json.dumps(review))
    with ZipFile(archive, 'w') as z:
        z.writestr(pdf_name, pdf_data)
        for i in range(1, 5):
            z.writestr(f'builder_outputs_PRIVATE/preview/{jobid}__{rev}__{i:02}.png', b'PNG' + bytes([i]))
    private.mkdir(parents=True)
    report_file.write_text(json.dumps({'status': 'PRIVATE_CYCLE_PASS_REQUIRES_VISUAL_REVIEW',
                    'source_zip_sha256': source_sha, 'private_review_report': str(review_path.relative_to(root)),
                    'job_count': 1, 'pdf_count': 1, 'png_preview_count': 4,
                    'closeout_receipt': 'tmp/receipt.json', 'closeout_receipt_sha256': 'f' * 64}))
    invoked = []
    fake = SimpleNamespace(
        OUTPUT_ROOT=root / 'tmp/private_run',
        prior_successful_cycles=lambda s: 0,
        file_sha=q.sha_file,
        run_private=lambda path, config, allow_repeat: (invoked.append((path, allow_repeat)) or {
            'summary': {'source_zip_sha256': source_sha},
            'report': str(report_file.relative_to(root)),
        }),
        inside_tmp=lambda p: p,
        _verified_prior_success=lambda path, sha: None,
    )
    monkeypatch.setattr(q, 'ROOT', root)
    monkeypatch.setattr(q, 'gc10_module', lambda: fake)
    assert q.run(workspace) == {'READY_FOR_VISUAL_REVIEW': 1}
    assert len(invoked) == 1 and invoked[0][0].name == q.GC10_NAME and invoked[0][1] is False
    d = next(out.iterdir())
    assert len(list((d/'pdf').iterdir())) == 1
    assert len(list((d/'png').iterdir())) == 4
    assert not list(d.rglob('*.zip'))
    result = json.loads((d/'report.json').read_text())
    assert result['source_archive'] == src.name
    assert result['source_sha256'] == source_sha
    assert result['status'] == 'READY_FOR_VISUAL_REVIEW'
    assert result['production_approved'] is False
    assert q.sha_file(src) == source_sha
    assert q.run(workspace) == {'SKIPPED_ALREADY_REPORTED': 1}


def test_crash_marker_prevents_reentry(tmp_path):
    out = tmp_path / 'output'; out.mkdir()
    src = 'a' * 64
    d = out / '2026-10-14_0001_test'; d.mkdir()
    (d / 'source_info.json').write_text(json.dumps({'source_sha256': src}))
    assert q.reports_for_source(out, src) == (None, True)


def test_windows_launcher_is_smb_relative_and_no_logs_in_input():
    p = q.ROOT / 'scripts/graphic_design_lab/greeting_cards/windows/gdl_greeting_card_queue.ps1'
    cmd = q.ROOT / 'scripts/graphic_design_lab/greeting_cards/windows/launch_greeting_card_queue.cmd'
    assert 'workspace-relative-b64' not in p.read_text(encoding='utf-8').lower()
    assert 'WORKSPACE_RELATIVE_B64' in p.read_text(encoding='utf-8')
    assert 'BatchMode=yes' in p.read_text(encoding='utf-8')
    assert '%~dp0gdl_greeting_card_queue.ps1' in cmd.read_text(encoding='utf-8')

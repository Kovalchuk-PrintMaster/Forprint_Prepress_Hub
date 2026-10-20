"""Regression: GC14 synthetic proof checks empty artifact directories correctly.

All data is synthetic. No SMB, PDF Builder, Illustrator, network or customer files.
"""
import json
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

import pytest
import yaml
from scripts.graphic_design_lab.greeting_cards import workspace_restore_synthetic_v0_1 as r


def prepared(tmp_path):
    (tmp_path / 'tmp').mkdir()
    contract = tmp_path / r.CONTRACT
    contract.parent.mkdir(parents=True)
    contract.write_text(yaml.safe_dump({
        'schema_version': 'gdl_client_workspace_architecture_v0_1',
        'workspace_dir_name': '_forprint_automation',
        'status': 'ACTIVE_EMPIRICAL_ARCHITECTURE',
        'tree': {'jobs': [], 'previews': [], 'archive': []},
    }))
    ws = r.create(tmp_path, 'existing-case')
    expected = {}
    for i, (name, payload) in enumerate(r.SYNTHETIC_INPUTS, start=1):
        archive = ws / 'input' / name
        with ZipFile(archive, 'x') as z:
            z.writestr(r.SYNTHETIC_MEMBER, payload)
        digest = sha256(archive.read_bytes()).hexdigest()
        expected[name] = digest
        out = ws / 'output' / f'2026-10-20_{i:04}_synthetic__{digest[:10]}'
        (out / 'pdf').mkdir(parents=True)
        (out / 'png').mkdir()
        fields = {'schema_version': 'gdl_gc14_smb_workspace_queue_v0_1',
                  'source_archive': name, 'source_sha256': digest,
                  'production_approved': False, 'client_published': False}
        (out / 'source_info.json').write_text(json.dumps(fields))
        (out / 'report.json').write_text(json.dumps({**fields, 'status': 'BLOCKED',
                                                    'reason': 'UNSUPPORTED_ARCHIVE_ENVELOPE'}))
    return ws, expected


def test_empty_pdf_png_are_not_wrongly_considered_artifacts(tmp_path):
    ws, expected = prepared(tmp_path)
    assert r._verify_smoke_evidence(ws, expected) == 2


def test_actual_pdf_or_png_is_rejected(tmp_path):
    ws, expected = prepared(tmp_path)
    first = next((ws / 'output').iterdir())
    (first / 'png' / 'should_not_exist.png').write_bytes(b'synthetic')
    with pytest.raises(r.RestoreBlocked, match='gc14_synthetic_evidence_invalid'):
        r._verify_smoke_evidence(ws, expected)


def test_resume_reuses_existing_inputs_and_reports_without_overwriting(tmp_path, monkeypatch):
    ws, _ = prepared(tmp_path)
    before = {str(p.relative_to(ws)): sha256(p.read_bytes()).hexdigest()
              for p in ws.rglob('*') if p.is_file()}
    invoked = []
    from scripts.graphic_design_lab.greeting_cards import smb_workspace_queue_v0_1 as queue
    monkeypatch.setattr(
        queue, 'run',
        lambda workspace: (invoked.append(workspace) or
                           {'SKIPPED_ALREADY_REPORTED': 2}),
    )
    result = r.resume_smoke(tmp_path, 'existing-case')
    assert result['status'] == 'GC14_SYNTHETIC_QUEUE_SMOKE_PASS'
    assert result['processed'] == 2
    assert result['pdf_builder_invoked'] is False
    assert invoked == [ws]
    after = {str(p.relative_to(ws)): sha256(p.read_bytes()).hexdigest()
             for p in ws.rglob('*') if p.is_file()}
    assert after == before


def test_resume_refuses_changed_synthetic_input(tmp_path):
    ws, _ = prepared(tmp_path)
    (ws / 'input' / r.SYNTHETIC_INPUTS[0][0]).write_bytes(b'changed')
    with pytest.raises(r.RestoreBlocked, match='input_identity_invalid'):
        r.resume_smoke(tmp_path, 'existing-case')


def test_resume_fails_on_extra_output_without_reprocessing(tmp_path):
    ws, _ = prepared(tmp_path)
    (ws / 'output' / 'unexpected').mkdir()
    with pytest.raises(r.RestoreBlocked, match='result_count_invalid'):
        r._verify_smoke_evidence(ws, {name: r.sha_path(ws / 'input' / name) for name,_ in r.SYNTHETIC_INPUTS})

"""Scoped GC14 BLOCKED retry; synthetic fixtures and no private source content."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.graphic_design_lab.greeting_cards import smb_workspace_queue_v0_1 as q


def _blocked_record(output: Path, digest: str, name: str):
    d = output / name
    d.mkdir()
    (d / 'source_info.json').write_text(json.dumps({'source_sha256': digest}))
    (d / 'report.json').write_text(json.dumps({
        'schema_version': q.SCHEMA, 'source_sha256': digest, 'status': 'BLOCKED'}))


def test_only_pinned_digest_receives_blocked_retry(tmp_path, monkeypatch):
    workspace = tmp_path / '_forprint_automation'
    inp, out = workspace / 'input', workspace / 'output'
    inp.mkdir(parents=True)
    out.mkdir()
    for name in ('first.zip', 'other.zip'):
        with ZipFile(inp / name, 'w') as z:
            z.writestr('fixture.txt', name)
    first_sha, other_sha = (q.sha_file(inp / name) for name in ('first.zip', 'other.zip'))
    _blocked_record(out, first_sha, 'old1')
    _blocked_record(out, other_sha, 'old2')
    initial = {name: q.sha_file(inp / name) for name in ('first.zip','other.zip')}
    assert q.run(workspace) == {'SKIPPED_ALREADY_REPORTED': 2}
    outcome = q.run(workspace, retry_blocked_sha256=first_sha)
    assert outcome == {'SKIPPED_ALREADY_REPORTED': 1, 'BLOCKED': 1}
    assert len(list(out.iterdir())) == 3
    assert sum(1 for p in out.glob('*/source_info.json')
               if first_sha in p.read_text()) == 2
    assert sum(1 for p in out.glob('*/source_info.json')
               if other_sha in p.read_text()) == 1
    assert all(initial[name] == q.sha_file(inp / name) for name in initial)


def test_scoped_retry_rejects_invalid_or_ambiguous_arguments(tmp_path):
    workspace = tmp_path / '_forprint_automation'
    workspace.mkdir()
    for value in ('', 'unverified', '../unsafe', 'f' * 63):
        with pytest.raises(q.QueueBlocked, match='scoped_retry_arguments_invalid'):
            q.run(workspace, retry_blocked_sha256=value)
    with pytest.raises(q.QueueBlocked, match='scoped_retry_arguments_invalid'):
        q.run(workspace, retry_blocked=True, retry_blocked_sha256='f' * 64)


def test_scoped_retry_does_not_override_completed_result(tmp_path, monkeypatch):
    workspace = tmp_path / '_forprint_automation'
    inp, out = workspace / 'input', workspace / 'output'
    inp.mkdir(parents=True)
    out.mkdir()
    with ZipFile(inp / 'accepted.zip', 'w') as z:
        z.writestr('fixture.txt', b'safe')
    digest = q.sha_file(inp / 'accepted.zip')
    d = out / 'completed'; d.mkdir()
    (d/'source_info.json').write_text(json.dumps({'source_sha256': digest}))
    (d/'report.json').write_text(json.dumps({
        'schema_version': q.SCHEMA,
        'source_sha256': digest, 'status': 'READY_FOR_VISUAL_REVIEW'}))
    assert q.run(workspace, retry_blocked_sha256=digest) == {'SKIPPED_ALREADY_REPORTED': 1}
    assert len(list(out.iterdir())) == 1


def test_scoped_retry_requires_exact_existing_source_before_any_processing(tmp_path):
    workspace = tmp_path / '_forprint_automation'
    inp, out = workspace / 'input', workspace / 'output'
    inp.mkdir(parents=True)
    out.mkdir()
    with ZipFile(inp / 'one.zip', 'w') as z:
        z.writestr('fixture.txt', b'fixture')
    with pytest.raises(q.QueueBlocked, match='scoped_retry_source_not_unique'):
        q.run(workspace, retry_blocked_sha256='a'*64)
    assert not list(out.iterdir())

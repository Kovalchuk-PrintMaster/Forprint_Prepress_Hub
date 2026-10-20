"""GC18 task-candidate boundary: no GC10, rendering, SMB writes or dispatch."""
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.graphic_design_lab.greeting_cards import illustrator_task_candidates_v0_1 as c


def env(tmp_path):
    repo = tmp_path / 'repo'
    (repo / 'tmp').mkdir(parents=True)
    ws = tmp_path / '_forprint_automation'
    (ws / 'input').mkdir(parents=True)
    (ws / 'output').mkdir()
    return repo, ws


def make_zip(path, accepted=False):
    with ZipFile(path, 'w') as z:
        if accepted:
            for name in c.gc14.GC10_REQUIRED:
                z.writestr(name, 'synthetic-envelopes-only-not-accepted-' + path.stem)
        else:
            z.writestr('unsupported.synthetic', 'not an intake handoff')


def snapshot(path):
    return {str(p.relative_to(path)): sha256(p.read_bytes()).hexdigest()
            for p in path.rglob('*') if p.is_file()}


def test_check_multiple_sources_without_creating_receipts(tmp_path):
    repo, ws = env(tmp_path)
    make_zip(ws / 'input/z.zip', accepted=True)
    make_zip(ws / 'input/b.zip')
    before = snapshot(ws)
    rows = c.run(repo, ws, mode='check')
    assert rows['CANDIDATE_AWAITING_DEEP_ACCEPTANCE'] == 1
    assert rows['BLOCKED'] == 1
    assert not (repo / 'tmp' / c.RECEIPTS).exists()
    assert snapshot(ws) == before


def test_prepare_immutable_review_only_candidates_and_replay(tmp_path):
    repo, ws = env(tmp_path)
    make_zip(ws / 'input/accepted.zip', accepted=True)
    make_zip(ws / 'input/rejected.zip')
    before = snapshot(ws)
    with pytest.raises(c.CandidateBlocked, match='explicit_candidate'):
        c.run(repo, ws, mode='prepare')
    result = c.run(repo, ws, mode='prepare', confirm=True)
    assert result['CREATED'] == 2
    folder = repo / 'tmp' / c.RECEIPTS
    receipts = list(folder.glob('*.json'))
    assert len(receipts) == 2
    for path in receipts:
        record = json.loads(path.read_text())
        assert not record['worker_dispatch_authorized']
        assert not record['deep_intake_validated']
        assert not record['windows_worker_executed']
        assert not record['pdf_builder_invoked']
        assert 'tmp/' not in json.dumps(record)
        assert path.name == record['source_sha256'] + '.json'
    before_receipts = snapshot(folder)
    second = c.run(repo, ws, mode='prepare', confirm=True)
    assert second['REUSED'] == 2
    assert snapshot(folder) == before_receipts
    assert snapshot(ws) == before


def test_conflicting_receipt_refused_without_overwrite(tmp_path):
    repo, ws = env(tmp_path)
    source = ws / 'input/accepted.zip'
    make_zip(source, accepted=True)
    c.run(repo, ws, mode='prepare', confirm=True)
    receipt = repo / 'tmp' / c.RECEIPTS / (c._sha(source) + '.json')
    receipt.write_text('{}')
    with pytest.raises(c.CandidateBlocked, match='existing_receipt_identity_conflict'):
        c.run(repo, ws, mode='prepare', confirm=True)
    assert receipt.read_text() == '{}'


def test_duplicate_sha_does_not_create_second_candidate(tmp_path):
    repo, ws = env(tmp_path)
    make_zip(ws / 'input/1.zip', accepted=True)
    (ws / 'input/2.zip').write_bytes((ws / 'input/1.zip').read_bytes())
    result = c.run(repo, ws, mode='prepare', confirm=True)
    assert result['DUPLICATE_SOURCE_SHA'] == 1
    assert result['CREATED'] == 1
    assert len(list((repo / 'tmp' / c.RECEIPTS).glob('*.json'))) == 1


def test_symlink_source_not_followed(tmp_path):
    repo, ws = env(tmp_path)
    outside = tmp_path / 'outside.zip'
    make_zip(outside, accepted=True)
    (ws / 'input/alias.zip').symlink_to(outside)
    result = c.run(repo, ws, mode='check')
    assert result == {'UNSAFE_ENTRY': 1}


def test_unrecognized_zip_blocked_and_never_dispatched(tmp_path):
    repo, ws = env(tmp_path)
    make_zip(ws / 'input/unknown.zip')
    result = c.run(repo, ws, mode='prepare', confirm=True)
    assert result['BLOCKED'] == 1
    receipt = next((repo / 'tmp' / c.RECEIPTS).glob('*.json'))
    item = json.loads(receipt.read_text())
    assert item['state'] == 'BLOCKED'
    assert item['gc14_envelope_kind'] == 'UNSUPPORTED'
    assert item['worker_dispatch_authorized'] is False


def test_empty_queue_safe_and_no_repo_write_on_check(tmp_path):
    repo, ws = env(tmp_path)
    assert c.run(repo, ws, mode='check') == {}
    assert not (repo / 'tmp' / c.RECEIPTS).exists()


def test_three_zip_batch_independent_statuses(tmp_path):
    repo, ws = env(tmp_path)
    make_zip(ws / 'input/one.zip', accepted=True)
    make_zip(ws / 'input/two.zip', accepted=True)
    make_zip(ws / 'input/three.zip')
    result = c.run(repo, ws, mode='prepare', confirm=True)
    assert result['CANDIDATE_AWAITING_DEEP_ACCEPTANCE'] == 2
    assert result['BLOCKED'] == 1
    assert result['CREATED'] == 3


def test_malformed_zip_fails_closed_per_source(tmp_path):
    repo, ws = env(tmp_path)
    (ws / 'input/bad.zip').write_bytes(b'not a zip')
    make_zip(ws / 'input/valid.zip', accepted=True)
    result = c.run(repo, ws, mode='check')
    assert result['BLOCKED'] == 1
    assert result['CANDIDATE_AWAITING_DEEP_ACCEPTANCE'] == 1

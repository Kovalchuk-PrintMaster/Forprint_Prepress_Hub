"""GC18 strict Intake inspector reuse: per-ZIP, no renders, no SMB edits."""
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.graphic_design_lab.greeting_cards import illustrator_task_candidates_v0_1 as candidates
from scripts.graphic_design_lab.greeting_cards import intake_handoff_runner_v0_1 as handoff


def setup(tmp_path):
    repo = tmp_path / 'repo'
    (repo / 'tmp').mkdir(parents=True)
    ws = tmp_path / '_forprint_automation'
    (ws / 'input').mkdir(parents=True)
    (ws / 'output').mkdir()
    cfg = tmp_path / 'config.json'
    cfg.write_text('{"resource_manifest": "fake-test-only"}')
    return repo, ws, cfg


def pkg(dst, accepted=True):
    with ZipFile(dst, 'w') as z:
        for name in (candidates.gc14.GC10_REQUIRED if accepted else {'not_handoff.txt'}):
            z.writestr(name, 'synthetic-dummy-not-customer-data')


def digest_tree(root):
    return {str(p.relative_to(root)): sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def approved_stub(calls):
    def inspect(path, cfg):
        assert path.name == handoff.HANDOFF_FILENAME
        assert cfg.name == 'config.json'
        calls.append(path)
        return {'archive_sha256': candidates._sha(path),
                'jobs': 4, 'assets': 0, 'synthetic': False}
    return inspect


def test_deep_check_real_queue_per_source_and_temporary_staging_removed(tmp_path, monkeypatch, capsys):
    repo, ws, cfg = setup(tmp_path)
    pkg(ws / 'input/one.zip')
    pkg(ws / 'input/no.zip', accepted=False)
    before = digest_tree(ws)
    seen = []
    monkeypatch.setattr(handoff, 'inspect_zip', approved_stub(seen))
    result = candidates.run(repo, ws, mode='deep-check', config=cfg)
    assert result == {'DEEP_INTAKE_PASS_NATIVE_CONTRACT_PENDING': 1, 'BLOCKED': 1}
    assert len(seen) == 1 and not seen[0].exists()
    assert digest_tree(ws) == before
    assert list((repo / 'tmp').iterdir()) == []
    out = capsys.readouterr().out
    assert 'PDF_BUILDER_INVOKED=false' in out
    assert 'NATIVE_WORKER_ADMISSION=false' in out
    assert 'WINDOWS_DISPATCH=false' in out


def test_deep_check_does_not_call_inspector_on_invalid_archive(tmp_path, monkeypatch):
    repo, ws, cfg = setup(tmp_path)
    pkg(ws / 'input/no.zip', accepted=False)
    monkeypatch.setattr(handoff, 'inspect_zip', lambda *a: pytest.fail('unexpected inspector'))
    assert candidates.run(repo, ws, mode='deep-check', config=cfg) == {'BLOCKED': 1}


def test_validator_failure_blocks_just_one_zip(tmp_path, monkeypatch, capsys):
    repo, ws, cfg = setup(tmp_path)
    pkg(ws / 'input/one.zip')
    pkg(ws / 'input/two.zip')
    first_sha = candidates._sha(ws / 'input/one.zip')
    # If bytes identical second candidate is classified duplicate; make them distinct.
    with ZipFile(ws / 'input/two.zip', 'a') as z:
        z.writestr('intake_evidence/test.txt', 'independent dummy')
    def inspect(path, cfg):
        if candidates._sha(path) == first_sha:
            raise handoff.HandoffBlocked('synthetic_validation_rejected')
        return {'archive_sha256': candidates._sha(path), 'jobs': 1, 'assets': 0, 'synthetic': False}
    monkeypatch.setattr(handoff, 'inspect_zip', inspect)
    counts = candidates.run(repo, ws, mode='deep-check', config=cfg)
    assert counts['DEEP_INTAKE_BLOCKED'] == 1
    assert counts['DEEP_INTAKE_PASS_NATIVE_CONTRACT_PENDING'] == 1
    assert 'synthetic_validation_rejected' not in capsys.readouterr().out


def test_synthetic_only_never_marked_as_worker_ready(tmp_path, monkeypatch):
    repo, ws, cfg = setup(tmp_path)
    pkg(ws / 'input/one.zip')
    monkeypatch.setattr(handoff, 'inspect_zip', lambda p,c: {
        'archive_sha256': candidates._sha(p), 'jobs': 1, 'assets': 0, 'synthetic': True})
    assert candidates.run(repo, ws, mode='deep-check', config=cfg) == {'DEEP_INTAKE_SYNTHETIC_REVIEW_ONLY': 1}


def test_mismatched_inspection_digest_fails_closed(tmp_path, monkeypatch):
    repo, ws, cfg = setup(tmp_path)
    pkg(ws / 'input/one.zip')
    monkeypatch.setattr(handoff, 'inspect_zip', lambda p,c: {
        'archive_sha256': '0'*64, 'jobs': 1, 'assets': 0, 'synthetic': False})
    assert candidates.run(repo, ws, mode='deep-check', config=cfg) == {'DEEP_INTAKE_BLOCKED': 1}
    assert not list((repo / 'tmp').iterdir())


def test_missing_config_causes_source_block_not_dispatch(tmp_path):
    repo, ws, cfg = setup(tmp_path)
    pkg(ws / 'input/one.zip')
    cfg.unlink()
    assert candidates.run(repo, ws, mode='deep-check', config=cfg) == {'DEEP_INTAKE_BLOCKED': 1}


def test_requires_explicit_config_for_deep_mode(tmp_path):
    repo, ws, _ = setup(tmp_path)
    with pytest.raises(candidates.CandidateBlocked, match='deep_intake_config_required'):
        candidates.run(repo, ws, mode='deep-check')


def test_empty_queue_deep_check_never_creates_files(tmp_path):
    repo, ws, cfg = setup(tmp_path)
    assert candidates.run(repo, ws, mode='deep-check', config=cfg) == {}
    assert not list((repo / 'tmp').iterdir())


def test_refuses_zero_job_result(tmp_path, monkeypatch):
    repo, ws, cfg = setup(tmp_path)
    pkg(ws / 'input/one.zip')
    monkeypatch.setattr(handoff, 'inspect_zip', lambda p,c: {
        'archive_sha256': candidates._sha(p), 'jobs': 0, 'assets': 0, 'synthetic': False})
    assert candidates.run(repo, ws, mode='deep-check', config=cfg) == {'DEEP_INTAKE_BLOCKED': 1}

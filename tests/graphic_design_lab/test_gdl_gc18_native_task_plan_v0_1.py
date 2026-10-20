"""GC18 strict pre-dispatch native planning, sanitized fixtures only."""
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

import pytest
from scripts.graphic_design_lab.greeting_cards import illustrator_task_candidates_v0_1 as c
from scripts.graphic_design_lab.greeting_cards import intake_handoff_runner_v0_1 as handoff


def env(tmp_path):
    repo = tmp_path / 'repo'
    (repo / 'tmp').mkdir(parents=True)
    ws = tmp_path / '_forprint_automation'
    (ws / 'input').mkdir(parents=True)
    (ws / 'output').mkdir()
    config = tmp_path / 'config.json'
    config.write_text('{"resource_manifest":"sanitized-only"}', encoding='utf-8')
    return repo, ws, config


def package(path, kind='candidate'):
    with ZipFile(path, 'w') as z:
        for name in (c.gc14.GC10_REQUIRED if kind == 'candidate' else {'unsupported.txt'}):
            z.writestr(name, 'sanitized-fixture-only')


def snapshot(ws):
    return {str(p.relative_to(ws)): sha256(p.read_bytes()).hexdigest()
            for p in ws.rglob('*') if p.is_file()}


def deep_stub(job_count=4, synthetic=False, duplicate=False, missing_revision=False):
    def fn(path, config):
        assert path.name == handoff.HANDOFF_FILENAME
        jobs = []
        for i in range(job_count):
            job_id = f'sanitized_job_{i}'
            if duplicate:
                job_id = 'sanitized_same_job'
            row = {'job_id': job_id, 'builder_v1': {'revision': 'r001'}}
            if missing_revision:
                row['builder_v1'] = {}
            jobs.append(row)
        return {'archive_sha256': c._sha(path), 'jobs': job_count, 'assets': 1,
                'synthetic': synthetic, 'bundle': {'jobs': jobs}}
    return fn


def test_four_job_native_plan_sourced_from_one_zip_no_customer_mutation(tmp_path, monkeypatch, capsys):
    repo, ws, cfg = env(tmp_path)
    package(ws / 'input/current.zip')
    package(ws / 'input/old.zip', 'blocked')
    original = snapshot(ws)
    monkeypatch.setattr(handoff, 'inspect_zip', deep_stub())
    with pytest.raises(c.CandidateBlocked, match='explicit_candidate_confirmation_required'):
        c.run(repo, ws, mode='plan-native', config=cfg)
    counters = c.run(repo, ws, mode='plan-native', confirm=True, config=cfg)
    assert counters == {'NATIVE_PLAN_CREATED': 1, 'NATIVE_TASK_PLAN_REVIEW_ONLY': 1, 'BLOCKED': 1}
    files = list((repo/'tmp'/c.NATIVE_PLAN_DIR).glob('*.json'))
    assert len(files) == 1
    plan = json.loads(files[0].read_text())
    assert plan['source_job_count'] == 4
    assert len(plan['tasks']) == 4
    assert all(t['expected_outputs'] == ['editable_ai','review_pdf','page_png','worker_result'] for t in plan['tasks'])
    assert all(t['worker_authorized'] is False for t in plan['tasks'])
    assert plan['dispatch_authorized'] is False
    assert plan['pdf_builder_invoked'] is False
    assert plan['admission']['illustrator_script_pinned'] is False
    assert 'sanitized_job' not in json.dumps(plan)
    assert 'current.zip' not in json.dumps(plan)
    assert snapshot(ws) == original
    assert 'WINDOWS_DISPATCH=false' in capsys.readouterr().out
    assert not list((repo/'tmp').glob('gc18-deep-intake-*'))


def test_exact_replay_reuses_receipt_without_modifying_bytes(tmp_path, monkeypatch):
    repo, ws, cfg = env(tmp_path)
    package(ws / 'input/a.zip')
    monkeypatch.setattr(handoff, 'inspect_zip', deep_stub())
    c.run(repo, ws, mode='plan-native', confirm=True, config=cfg)
    receipt = next((repo/'tmp'/c.NATIVE_PLAN_DIR).glob('*.json'))
    orig = receipt.read_bytes()
    assert c.run(repo, ws, mode='plan-native', confirm=True, config=cfg) == {
        'NATIVE_PLAN_REUSED': 1, 'NATIVE_TASK_PLAN_REVIEW_ONLY': 1}
    assert receipt.read_bytes() == orig


def test_changed_planning_receipt_is_never_overwritten(tmp_path, monkeypatch):
    repo, ws, cfg = env(tmp_path)
    package(ws / 'input/a.zip')
    monkeypatch.setattr(handoff, 'inspect_zip', deep_stub())
    c.run(repo, ws, mode='plan-native', confirm=True, config=cfg)
    receipt = next((repo/'tmp'/c.NATIVE_PLAN_DIR).glob('*.json'))
    receipt.write_text('{"tampered":true}')
    result = c.run(repo, ws, mode='plan-native', confirm=True, config=cfg)
    assert result == {'DEEP_INTAKE_BLOCKED': 1}
    assert receipt.read_text() == '{"tampered":true}'


def test_synthetic_validated_intake_never_creates_worker_plan(tmp_path, monkeypatch):
    repo, ws, cfg = env(tmp_path)
    package(ws / 'input/a.zip')
    monkeypatch.setattr(handoff, 'inspect_zip', deep_stub(synthetic=True))
    assert c.run(repo, ws, mode='plan-native', confirm=True, config=cfg) == {
        'DEEP_INTAKE_SYNTHETIC_REVIEW_ONLY': 1}
    assert not (repo/'tmp'/c.NATIVE_PLAN_DIR).exists()


def test_duplicate_job_identity_fails_closed(tmp_path, monkeypatch):
    repo, ws, cfg = env(tmp_path)
    package(ws / 'input/a.zip')
    monkeypatch.setattr(handoff, 'inspect_zip', deep_stub(duplicate=True))
    assert c.run(repo, ws, mode='plan-native', confirm=True, config=cfg) == {'DEEP_INTAKE_BLOCKED': 1}
    assert not (repo/'tmp'/c.NATIVE_PLAN_DIR).exists()


def test_missing_revision_fails_closed(tmp_path, monkeypatch):
    repo, ws, cfg = env(tmp_path)
    package(ws / 'input/a.zip')
    monkeypatch.setattr(handoff, 'inspect_zip', deep_stub(missing_revision=True))
    assert c.run(repo, ws, mode='plan-native', confirm=True, config=cfg) == {'DEEP_INTAKE_BLOCKED': 1}


def test_validator_failure_is_isolated_from_other_source(tmp_path, monkeypatch):
    repo, ws, cfg = env(tmp_path)
    package(ws / 'input/a.zip')
    package(ws / 'input/b.zip')
    with ZipFile(ws/'input/b.zip','a') as z:
        z.writestr('intake_evidence/extra.txt','distinct-src')
    digest = c._sha(ws/'input/a.zip')
    good = deep_stub(job_count=2)
    def inspect(path, config):
        if c._sha(path) == digest:
            raise handoff.HandoffBlocked('synthetic_failure')
        return good(path, config)
    monkeypatch.setattr(handoff, 'inspect_zip', inspect)
    assert c.run(repo, ws, mode='plan-native', confirm=True, config=cfg) == {
        'DEEP_INTAKE_BLOCKED': 1, 'NATIVE_TASK_PLAN_REVIEW_ONLY': 1,
        'NATIVE_PLAN_CREATED': 1}
    assert len(list((repo/'tmp'/c.NATIVE_PLAN_DIR).glob('*.json'))) == 1


def test_deep_check_stays_read_only_with_native_planning_available(tmp_path, monkeypatch):
    repo, ws, cfg = env(tmp_path)
    package(ws/'input/a.zip')
    monkeypatch.setattr(handoff, 'inspect_zip', deep_stub())
    before = snapshot(ws)
    assert c.run(repo, ws, mode='deep-check', config=cfg) == {
        'DEEP_INTAKE_PASS_NATIVE_CONTRACT_PENDING':1}
    assert not (repo/'tmp'/c.NATIVE_PLAN_DIR).exists()
    assert snapshot(ws) == before

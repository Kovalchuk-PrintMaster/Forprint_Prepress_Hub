"""Offline/synthetic Windows Worker v1 tests; no customer/SMB/Windows writes."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import importlib.util
import os
from pathlib import Path
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/graphic_design_lab/worker_runtime/windows_worker_w1_pilot_v0_1.py'
CONFIG = ROOT / 'coordination/graphic_design_lab/worker_runtime/windows_worker_w1_pilot_contract_v0_1.yaml'
SPEC = importlib.util.spec_from_file_location('worker_w1_pilot_test_module', SCRIPT)
w = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(w)
TASK = 'gc18-' + 'a' * 24
SOURCE = 'b' * 64
ATTEMPT = 'a0001'


def contract():
    return yaml.safe_load(CONFIG.read_text(encoding='utf-8'))


def result_fixture(tmp_path):
    export = tmp_path / 'export'
    export.mkdir()
    source = export / 'dummy.ai'
    source.write_bytes(b'SYNTHETIC FIXTURE - NOT AN AI FILE')
    item = {'kind': 'editable_ai', 'filename': source.name,
            'size_bytes': source.stat().st_size,
            'sha256': sha256(source.read_bytes()).hexdigest()}
    result = {'schema_version': w.RESULT_SCHEMA, 'task_id': TASK,
              'attempt_id': ATTEMPT, 'source_sha256': SOURCE,
              'adapter_id': 'illustrator', 'worker_rc': 0,
              'worker_state': 'LOCAL_COMPLETE', 'production_ready': False,
              'dispatch_authorized': False, 'artifacts': [item]}
    return export, result


def test_real_contract_fails_closed_and_is_a_proposal():
    raw = contract()
    assert w.check_contract(raw)['authority']['portfolio_worker_owner'] == 'BLUEPRINT_DECISION_PENDING'
    assert raw['windows']['root'] == 'D:\\ForPrint_Automation\\GraficsDesignLab\\Automation'
    assert raw['workspace']['service_root_status'].startswith('NOT_CREATED')
    assert raw['cleanup']['no_automatic_deletion'] is True


def test_legacy_worker_root_is_explicitly_rejected():
    legacy = deepcopy(contract())
    legacy['windows']['root'] = 'D:\\ForPrint\\Automation'
    with pytest.raises(w.W1Blocked, match='windows_local_root_unexpected'):
        w.check_contract(legacy)


@pytest.mark.parametrize('part,key,value', [
    ('authority', 'automatic_acceptance', True),
    ('authority', 'worker_launch', True),
    ('authority', 'production_publish', True),
    ('authority', 'client_workspace_mutation', True),
    ('authority', 'portfolio_worker_owner', 'GDL'),
    ('authority', 'client_smb_2777_private_data_safe', True),
    ('workspace', 'cleaning_client_output', 'ALLOWED'),
    ('workspace', 'service_root_status', 'CREATED'),
    ('windows', 'root', 'C:\\Windows'),
    ('windows', 'one_active_attempt_per_worker', False),
    ('windows', 'windows_host_initialized', True),
    ('windows', 'adapters_implemented', ['illustrator']),
    ('cleanup', 'no_automatic_deletion', False),
    ('identity', 'attempt_fencing_required_before_retry', False),
    ('terminal_acceptance', 'requires_independent_verification', False),
    ('terminal_acceptance', 'worker_rc_zero_not_sufficient', False),
])
def test_contradictory_contract_blocked(part, key, value):
    bad = deepcopy(contract())
    bad[part][key] = value
    with pytest.raises(w.W1Blocked):
        w.check_contract(bad)


@pytest.mark.parametrize('task,attempt', [
    ('../evil', 'a0001'), ('gc18-' + 'a' * 24, '../'),
    ('gc18-' + 'a' * 24, 'a00001'), ('gc18_bad', 'a0001')
])
def test_workdir_identity_safe(task, attempt):
    with pytest.raises(w.W1Blocked):
        w.windows_attempt_relative(task, attempt)


def test_module_agnostic_task_identity():
    assert str(w.windows_attempt_relative('forprint-acrobat-foo-001', 'a0001')).startswith('jobs/forprint-acrobat-foo-001/')


def test_workdir_exact():
    assert str(w.windows_attempt_relative(TASK, ATTEMPT)) == 'jobs/' + TASK + '/a0001'


def test_recovery_refuses_ambiguous_fencing():
    assert w.recovery_decision(server_state='RUNNING', current_owner_fenced=False,
                               local_result_verified=False, old_attempt_finished=True) == 'WAIT_FOR_FENCING'
    assert w.recovery_decision(server_state='RESULT_LOCAL_COMPLETE', current_owner_fenced=False,
                               local_result_verified=True, old_attempt_finished=True) == 'WAIT_FOR_FENCING'


def test_recovery_retries_only_fenced():
    assert w.recovery_decision(server_state='RETRY_REQUIRED', current_owner_fenced=True,
                               local_result_verified=False, old_attempt_finished=True) == 'START_NEW_ATTEMPT'
    assert w.recovery_decision(server_state='RETRY_REQUIRED', current_owner_fenced=True,
                               local_result_verified=False, old_attempt_finished=False) == 'WAIT_FOR_FENCING'


def test_recovery_never_uploads_during_running_or_unfinished_attempt():
    assert w.recovery_decision(server_state='RUNNING', current_owner_fenced=True,
                               local_result_verified=True, old_attempt_finished=True) == 'MANUAL_REVIEW'
    assert w.recovery_decision(server_state='RESULT_LOCAL_COMPLETE', current_owner_fenced=True,
                               local_result_verified=True, old_attempt_finished=False) == 'MANUAL_REVIEW'


def test_recovery_upload_only_after_verified_local():
    assert w.recovery_decision(server_state='RESULT_LOCAL_COMPLETE', current_owner_fenced=True,
                               local_result_verified=True, old_attempt_finished=True) == 'VERIFY_AND_REUPLOAD'


@pytest.mark.parametrize('state', ['ACCEPTED', 'VERIFIED'])
def test_accepted_is_idempotent(state):
    assert w.recovery_decision(server_state=state, current_owner_fenced=False,
                               local_result_verified=False, old_attempt_finished=False) == 'DO_NOT_RERUN'


@pytest.mark.parametrize('state', ['BLOCKED', 'NEEDS_RECONCILIATION'])
def test_ambiguous_or_blocked_is_manual(state):
    assert w.recovery_decision(server_state=state, current_owner_fenced=True,
                               local_result_verified=True, old_attempt_finished=True) == 'MANUAL_REVIEW'


def test_recovery_rejects_nonbool_flag():
    with pytest.raises(w.W1Blocked):
        w.recovery_decision(server_state='RUNNING', current_owner_fenced=1,
                            local_result_verified=False, old_attempt_finished=True)


def test_rc0_with_full_synthetic_evidence_is_review_only(tmp_path):
    export, result = result_fixture(tmp_path)
    verified = w.verify_synthetic_result(export, result, task=TASK, attempt=ATTEMPT, source_sha=SOURCE)
    assert verified['state'] == 'SYNTHETIC_LOCAL_EVIDENCE_VERIFIED_REVIEW_ONLY'
    assert verified['production_ready'] is False
    assert verified['human_accepted'] is False
    assert verified['windows_execution'] is False


def test_rc0_without_output_rejected(tmp_path):
    export, result = result_fixture(tmp_path)
    (export / 'dummy.ai').unlink()
    with pytest.raises(w.W1Blocked, match='artifact_missing_or_unsafe'):
        w.verify_synthetic_result(export, result, task=TASK, attempt=ATTEMPT, source_sha=SOURCE)


@pytest.mark.parametrize('field,modified', [
    ('task_id', 'gc18-' + 'f' * 24), ('attempt_id', 'a0002'),
    ('source_sha256', 'f' * 64), ('dispatch_authorized', True),
    ('production_ready', True), ('worker_rc', 1),
])
def test_wrong_binding_or_authority_rejected(tmp_path, field, modified):
    export, result = result_fixture(tmp_path)
    result[field] = modified
    with pytest.raises(w.W1Blocked):
        w.verify_synthetic_result(export, result, task=TASK, attempt=ATTEMPT, source_sha=SOURCE)


def test_tampered_bytes_detected(tmp_path):
    export, result = result_fixture(tmp_path)
    (export / 'dummy.ai').write_bytes(b'DIFFERENT BYTES SAME SIZE NO')
    with pytest.raises(w.W1Blocked):
        w.verify_synthetic_result(export, result, task=TASK, attempt=ATTEMPT, source_sha=SOURCE)


@pytest.mark.parametrize('unsafe', ['../outside.ai', '/etc/passwd', 'folder/file.ai', r'd:\tmp\output.ai', './dummy.ai'])
def test_export_path_traversal_blocked(tmp_path, unsafe):
    export, result = result_fixture(tmp_path)
    result['artifacts'][0]['filename'] = unsafe
    with pytest.raises(w.W1Blocked, match='artifact_path'):
        w.verify_synthetic_result(export, result, task=TASK, attempt=ATTEMPT, source_sha=SOURCE)


def test_symlink_artifact_blocked(tmp_path):
    export, result = result_fixture(tmp_path)
    (export / 'dummy.ai').unlink()
    real = tmp_path / 'outside.ai'
    real.write_bytes(b'X')
    (export / 'dummy.ai').symlink_to(real)
    with pytest.raises(w.W1Blocked):
        w.verify_synthetic_result(export, result, task=TASK, attempt=ATTEMPT, source_sha=SOURCE)


def test_synthetic_smoke_removes_only_its_temporary_directory(tmp_path):
    (tmp_path / 'tmp').mkdir()
    sentinel = tmp_path / 'tmp' / 'keep.txt'
    sentinel.write_text('untouched')
    before = set((tmp_path / 'tmp').iterdir())
    out = w.synthetic_smoke(tmp_path, contract())
    assert out['state'] == 'SYNTHETIC_SMOKE_PASS'
    assert set((tmp_path / 'tmp').iterdir()) == before
    assert sentinel.read_text() == 'untouched'


def test_synthetic_smoke_requires_existing_non_symlink_tmp(tmp_path):
    with pytest.raises(w.W1Blocked):
        w.synthetic_smoke(tmp_path, contract())
    outside = tmp_path / 'outside'
    outside.mkdir()
    (tmp_path / 'tmp').symlink_to(outside, target_is_directory=True)
    with pytest.raises(w.W1Blocked):
        w.synthetic_smoke(tmp_path, contract())
    assert list(outside.iterdir()) == []


def test_cli_check_and_smoke_do_not_modify_repo_sources(tmp_path, capsys, monkeypatch):
    import shutil
    relative_config = CONFIG.relative_to(ROOT)
    (tmp_path / relative_config.parent).mkdir(parents=True)
    (tmp_path / 'tmp').mkdir()
    shutil.copyfile(CONFIG, tmp_path / relative_config)
    before = list(tmp_path.rglob('*'))
    monkeypatch.setattr(sys, 'argv', ['program', '--repo', str(tmp_path), '--mode', 'check'])
    assert w.main() == 0
    assert 'CONTRACT_CHECK_PASS' in capsys.readouterr().out
    monkeypatch.setattr(sys, 'argv', ['program', '--repo', str(tmp_path), '--mode', 'smoke'])
    assert w.main() == 0
    report = capsys.readouterr().out
    assert 'SYNTHETIC_SMOKE_PASS' in report
    assert 'WINDOWS_EXECUTION=false' in report
    assert 'SMB_WRITE=false' in report
    assert 'AUTOMATIC_CLEANUP=false' in report
    assert list(tmp_path.rglob('*')) == before

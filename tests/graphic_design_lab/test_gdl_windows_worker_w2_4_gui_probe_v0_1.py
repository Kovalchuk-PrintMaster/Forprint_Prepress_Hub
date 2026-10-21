"""Offline W2.4 synthetic GUI proof tests. No SSH, Windows, Adobe or SMB calls."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/graphic_design_lab/worker_runtime/windows_worker_w2_4_gui_probe_v0_1.py'
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location('gdl_w24_gui_probe_test', SCRIPT)
w = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(w)
DIGEST = '1' * 64


def sample_result():
    return {
        'schema_version': w.PAYLOAD_SCHEMA, 'task_id': w.TASK_ID,
        'attempt_id': w.ATTEMPT_ID, 'host': 'PREPRESS',
        'windows_account': r'PREPRESS\Work', 'source_sha256': DIGEST,
        'expected_session_id': 2, 'actual_session_id': 2,
        'user_interactive': True, 'explorer_same_session': True,
        'state': 'PASS_SYNTHETIC_INTERACTIVE', 'illustrator_execution': False,
        'smb_mutation': False, 'client_files_touched': False,
        'production_ready': False, 'cleanup_executed': False,
    }


def sample_report(mode):
    states = {'check': 'READY_FOR_SYNTHETIC_TASK',
              'launch': 'TASK_STARTED_RESULT_NOT_YET_VERIFIED',
              'verify': 'SYNTHETIC_GUI_RESULT_REPORTED',
              'resume-check': 'READY_TO_RESUME_EXISTING_UNRUN_TASK',
              'resume-start': 'TASK_RESUMED_RESULT_NOT_YET_VERIFIED'}
    return {
        'schema_version': w.CONTROLLER_SCHEMA, 'mode': mode,
        'state': states[mode], 'host': 'PREPRESS', 'ssh_account': r'PREPRESS\Work',
        'task_name': w.TASK_NAME, 'task_id': w.TASK_ID,
        'attempt_id': w.ATTEMPT_ID, 'expected_source_sha256': DIGEST,
        'session_id': 2, 'registered_and_started': mode == 'launch',
        'resumed_existing': mode == 'resume-start',
        'windows_mutation': mode in ('launch', 'resume-start'),
        'illustrator_execution': False, 'smb_mutation': False,
        'client_files_touched': False, 'cleanup_executed': False,
        'production_ready': False,
        'gui_result': sample_result() if mode == 'verify' else None,
    }


def test_source_check_existing_w1_contract():
    ps, payload = w.source_check()
    assert '__MODE__' in ps and b'PASS_SYNTHETIC_INTERACTIVE' in payload
    assert w.WINDOWS_ROOT == r'D:\ForPrint_Automation\GraficsDesignLab\Automation'


def test_render_sha_and_no_markers():
    ctrl, payload = w.source_check()
    code, digest = w.render('check', ctrl, payload)
    assert digest == sha256(payload).hexdigest()
    assert "'check'" in code
    assert w.WINDOWS_ROOT in code
    for marker in ('__MODE__', '__PAYLOAD_B64__', '__PAYLOAD_SHA__'):
        assert marker not in code


@pytest.mark.parametrize('mode', ['source-check', 'bad', 'initialize', 'run'])
def test_render_no_unsafe_mode(mode):
    c, p = w.source_check()
    with pytest.raises(w.GuiProbeBlocked):
        w.render(mode, c, p)


@pytest.mark.parametrize('mode', ['check', 'launch', 'verify', 'resume-check', 'resume-start'])
def test_accept_valid_controller_evidence(mode):
    out = w.validate_report(json.dumps(sample_report(mode)), mode=mode, digest=DIGEST)
    assert out['state'] == sample_report(mode)['state']


def test_verify_waiting_is_not_a_pass():
    x = sample_report('verify')
    x.update(state='WAITING_FOR_SYNTHETIC_RESULT', gui_result=None, session_id=None)
    assert w.validate_report(json.dumps(x), mode='verify', digest=DIGEST)['state'] == 'WAITING_FOR_SYNTHETIC_RESULT'


def test_verify_failed_result_not_promoted():
    x = sample_report('verify')
    x['state'] = 'SYNTHETIC_GUI_RESULT_REQUIRES_REVIEW'
    x['gui_result']['state'] = 'FAIL_GUI_CONTEXT'
    assert w.validate_report(json.dumps(x), mode='verify', digest=DIGEST)['state'] == 'SYNTHETIC_GUI_RESULT_REQUIRES_REVIEW'


@pytest.mark.parametrize('key,value', [
    ('state', 'ACCEPTED'), ('task_id', 'different'),
    ('attempt_id', 'a0002'), ('source_sha256', 'f'*64),
    ('expected_session_id', 0), ('actual_session_id', 1),
    ('user_interactive', False), ('explorer_same_session', False),
    ('illustrator_execution', True), ('smb_mutation', True),
    ('client_files_touched', True), ('production_ready', True),
    ('cleanup_executed', True),
])
def test_synthetic_result_tampering_blocked(key, value):
    x = sample_result()
    x[key] = value
    with pytest.raises(w.GuiProbeBlocked):
        w.validate_result(x, DIGEST)


@pytest.mark.parametrize('key,value', [
    ('expected_source_sha256', 'f'*64), ('task_name', 'Other'),
    ('mode', 'launch'), ('host', 'Other'), ('windows_mutation', True),
    ('registered_and_started', True), ('smb_mutation', True),
    ('illustrator_execution', True), ('production_ready', True),
])
def test_readonly_check_rejects_false_claims(key, value):
    x = sample_report('check')
    x[key] = value
    with pytest.raises(w.GuiProbeBlocked):
        w.validate_report(json.dumps(x), mode='check', digest=DIGEST)


def test_verify_rejects_false_result():
    x = sample_report('verify')
    x['gui_result']['source_sha256'] = 'b'*64
    with pytest.raises(w.GuiProbeBlocked):
        w.validate_report(json.dumps(x), mode='verify', digest=DIGEST)


def test_remote_invocation_disallowed_without_confirmation(monkeypatch):
    monkeypatch.setattr(w, 'remote_run', lambda _: (_ for _ in ()).throw(AssertionError('remote was invoked')))
    assert w.main(['--mode','launch']) == 2
    assert w.main(['--mode','check','--confirm-synthetic-gui-probe']) == 2
    assert w.main(['--mode','verify','--confirm-synthetic-gui-probe']) == 2
    assert w.main(['--mode','source-check','--confirm-synthetic-gui-probe']) == 2
    assert w.main(['--mode','resume-start']) == 2
    assert w.main(['--mode','resume-check','--confirm-resume-existing-synthetic-task']) == 2
    assert w.main(['--mode','launch','--confirm-resume-existing-synthetic-task']) == 2
    assert w.main(['--mode','verify','--confirm-resume-existing-synthetic-task']) == 2
    assert w.main(['--mode','source-check','--confirm-resume-existing-synthetic-task']) == 2


def test_source_check_never_calls_remote(monkeypatch, capsys):
    monkeypatch.setattr(w, 'remote_run', lambda _: (_ for _ in ()).throw(AssertionError('remote was invoked')))
    assert w.main(['--mode','source-check']) == 0
    assert 'SOURCE_CHECK_PASS' in capsys.readouterr().out


def test_no_illustrator_or_cleanup_commands():
    controller, payload = w.source_check()
    joined = controller.lower() + payload.decode('ascii').lower()
    for unsafe in ('remove-item', 'unregister-scheduledtask', 'stop-process',
                   'illustrator.exe', 'acrobatr.exe', 'coreldrw.exe',
                   '\\in_progress\\', '/srv/smb/', 'get-smbshare'):
        assert unsafe not in joined
    assert 'createNew'.lower() in joined
    assert '-logontype interactive' in joined
    assert '-runlevel highest' in joined
    assert 'start-scheduledtask' in joined
    assert 'multipleinstances ignorenew' in joined


def test_invalid_json_blocked():
    with pytest.raises(w.GuiProbeBlocked):
        w.validate_report('broken', mode='check', digest=DIGEST)


def test_sid_normalization_is_safe_and_text_match_removed():
    controller, _ = w.source_check()
    assert "Principal.UserId -ine 'PREPRESS\\Work'" not in controller
    assert '$owner.Translate([Security.Principal.SecurityIdentifier]).Value' in controller
    assert '[Security.Principal.WindowsIdentity]::GetCurrent().User.Value' in controller
    assert "SCHEDULED_TASK_OWNER_SID_MISMATCH" in controller
    assert "SCHEDULED_TASK_OWNER_SID_UNRESOLVED" in controller


def test_resume_gate_never_regenerates_existing_task_or_payload():
    c, _ = w.source_check()
    section = c.split("elseif ($Mode -in @('resume-check','resume-start'))", 1)[1].split("} else {", 1)[0]
    assert 'Assert-ExistingUnrunAttempt' in section
    assert 'Active-WorkSession' in section
    assert 'Register-ScheduledTask' not in section
    assert 'New-ScheduledTaskPrincipal' not in section
    assert 'Payload-Bytes' not in section
    assert 'Start-ScheduledTask' in section
    assert 'Claim-ResumeStart' in section


def test_resume_never_run_gate_bound_to_scheduler_info_and_actual_result():
    c, _ = w.source_check()
    fn = c.split('function Assert-ExistingUnrunAttempt', 1)[1].split('function Claim-ResumeStart', 1)[0]
    for marker in ('Get-ScheduledTaskInfo', '267011', 'LastRunTime',
                   "[string]$task.State -ne 'Ready'", 'Task-Metadata $sid',
                   'RESUME_RESULT_ALREADY_PRESENT', 'RESUME_STAGED_SCRIPT_SHA_MISMATCH',
                   'RESUME_START_ALREADY_CLAIMED', 'ReparsePoint'):
        assert marker in fn


def test_resume_fence_new_only_and_never_removed():
    c, _ = w.source_check()
    fn = c.split('function Claim-ResumeStart', 1)[1].split('try {', 1)[0]
    assert '[IO.FileMode]::CreateNew' in fn
    assert '$ResumeClaimPath' in fn
    assert 'source_sha256=$ExpectedSha' in fn
    assert 'expected_session_id=$sid' in fn
    assert 'FileMode]::OpenOrCreate' not in fn
    assert 'FileMode]::Create,' not in fn


def test_resume_render_still_binds_original_source_sha():
    c, p = w.source_check()
    for mode in ('resume-check', 'resume-start'):
        code, sha = w.render(mode, c, p)
        assert sha == sha256(p).hexdigest()
        assert f"$Mode = '{mode}'" in code
        assert 'gdl-w24-gui-probe-001' in code
        assert 'a0001' in code


def test_resume_check_read_only_claims():
    x = sample_report('resume-check')
    assert w.validate_report(json.dumps(x), mode='resume-check', digest=DIGEST)['state'] == 'READY_TO_RESUME_EXISTING_UNRUN_TASK'
    for k, val in [('windows_mutation', True), ('registered_and_started', True),
                   ('resumed_existing', True), ('state', 'TASK_RESUMED_RESULT_NOT_YET_VERIFIED'),
                   ('session_id', None), ('gui_result', sample_result())]:
        xx = sample_report('resume-check')
        xx[k] = val
        with pytest.raises(w.GuiProbeBlocked):
            w.validate_report(json.dumps(xx), mode='resume-check', digest=DIGEST)


def test_resume_start_report_requires_explicit_existing_only_boundary():
    for k, val in [('windows_mutation', False), ('registered_and_started', True),
                   ('resumed_existing', False), ('state', 'ACCEPTED'),
                   ('session_id', 0), ('gui_result', sample_result())]:
        xx = sample_report('resume-start')
        xx[k] = val
        with pytest.raises(w.GuiProbeBlocked):
            w.validate_report(json.dumps(xx), mode='resume-start', digest=DIGEST)


@pytest.mark.parametrize('mode', ['check', 'launch', 'verify', 'resume-check', 'resume-start'])
def test_resumed_flag_never_accepted_for_incorrect_mode(mode):
    x = sample_report(mode)
    x['resumed_existing'] = mode != 'resume-start'
    with pytest.raises(w.GuiProbeBlocked):
        w.validate_report(json.dumps(x), mode=mode, digest=DIGEST)


def test_resume_no_cleanup_and_original_payload_not_changed():
    c, payload = w.source_check()
    assert sha256(payload).hexdigest() == '0b0605d93d0b4611cbdba7c9702ce68c59fa78d97a188d4fe1dbb548525a78d6'
    assert 'Remove-Item' not in c
    assert 'Unregister-ScheduledTask' not in c
    assert "if ($Mode -eq 'resume-start')" in c


def test_registered_task_name_must_be_unique_under_expected_taskpath():
    c, _ = w.source_check()
    assert "SCHEDULED_TASK_NOT_UNIQUE" in c
    assert "SCHEDULED_TASK_WRONG_PATH" in c
    assert "$task.TaskPath -cne '\\'" in c

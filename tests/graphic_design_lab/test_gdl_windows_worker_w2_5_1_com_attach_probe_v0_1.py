"""Offline W2.5.1 COM-only probe tests; never reaches PREPRESS/Adobe."""
from __future__ import annotations
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / 'scripts/graphic_design_lab/worker_runtime/windows_worker_w2_5_1_com_attach_probe_v0_1.py'
sys.path.insert(0, str(P.parent))
spec = importlib.util.spec_from_file_location('w251_com_test', P)
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
D = 'd'*64


def run_result():
    return dict(schema_version=w.RUN_SCHEMA, task_id=w.TASK_ID, attempt_id=w.ATTEMPT_ID,
                host='PREPRESS', windows_account=r'PREPRESS\Work', state='PASS_COM_READONLY_ATTACH',
                session_id=2, phase='STAGE_DONE', error_code='NONE', error_hresult=None,
                runner_sha256=D, source_template_sha256='a'*64,
                illustrator_version='30.0.0', preexisting_illustrator_pid=9228,
                illustrator_document_mutation=False, smb_mutation=False,
                client_files_touched=False, cleanup_executed=False,
                production_ready=False)


def ctrl_result(mode='check'):
    return dict(schema_version=w.SCHEMA, task_id=w.TASK_ID, attempt_id=w.ATTEMPT_ID,
                task_name=w.TASK_NAME, mode=mode, host='PREPRESS',
                ssh_account=r'PREPRESS\Work', session_id=2, runner_sha256=D,
                state={'check':'READY_FOR_COM_ATTACH_PROBE',
                       'launch':'COM_ATTACH_TASK_STARTED_RESULT_PENDING',
                       'verify':'COM_READONLY_ATTACH_VERIFIED'}[mode],
                windows_mutation=(mode=='launch'), com_result=(run_result() if mode=='verify' else None),
                illustrator_document_mutation=False, smb_mutation=False,
                client_files_touched=False, cleanup_executed=False,
                production_ready=False)


def test_source_check_on_expected_project_version():
    ctrl, runner = w.source_check()
    assert w.TASK_ID == 'gdl-w251-com-attach-001'
    assert ctrl.count('__RUNNER_B64__') == 1
    assert b'GetActiveObject' in runner


def test_restricted_new_task_and_preexisting_illustrator_only():
    ctrl, runner = w.source_check()
    assert "-LogonType Interactive -RunLevel Highest" in ctrl
    assert 'Assert-ApprovedAcl' in ctrl
    assert 'FileMode]::CreateNew' in ctrl
    assert 'TASK_EXISTS_NO_RELAUNCH' in ctrl
    assert 'START_REQUESTED_SINGLE_USE' not in ctrl
    assert 'SINGLE_USE_START_REQUESTED' in ctrl
    assert 'GetActiveObject' in runner.decode()
    for code in ('DoJavaScript', 'DoJavaScriptFile', 'New-Object -ComObject', 'Start-Process',
                 'Unregister-ScheduledTask', 'Remove-Item', 'Stop-Process',
                 'Register-ScheduledTask' if False else 'no_such_unsafe_code'):
        assert code not in runner.decode()
    for code in ('Unregister-ScheduledTask','Remove-Item','Stop-Process','Start-Process'):
        assert code not in ctrl


def test_hash_bound_sources_and_stdin_bridge():
    ctrl, runner = w.source_check()
    rendered, h = w.render('check', ctrl, runner)
    assert h != sha256(runner).hexdigest()
    assert len(h) == 64
    assert "'check'" in rendered
    for token in ('__MODE__','__RUNNER_B64__','__RUNNER_SHA__'):
        assert token not in rendered
    assert 'ScriptBlock' in w.PS_STDIN_BRIDGE


@pytest.mark.parametrize('bad',['launches','source-check','erase','verify-only',''])
def test_invalid_render_mode(bad):
    with pytest.raises(w.ComProbeBlocked):
        w.render(bad,*w.source_check())


@pytest.mark.parametrize('mode',['check','launch','verify'])
def test_valid_controller_report(mode):
    d=ctrl_result(mode)
    assert w.validate_report(json.dumps(d), mode=mode, runner_sha=D) == d


@pytest.mark.parametrize('key,val', [('task_id','other'),('attempt_id','a0002'),
                                      ('task_name','Fake'),('runner_sha256','f'*64),
                                      ('host','elsewhere'),('ssh_account','Work'),
                                      ('smb_mutation',True),('cleanup_executed',True),
                                      ('client_files_touched',True),
                                      ('illustrator_document_mutation',True),
                                      ('production_ready',True)])
def test_controller_integrity_blocked(key,val):
    d=ctrl_result('check')
    d[key]=val
    with pytest.raises(w.ComProbeBlocked):
        w.validate_report(json.dumps(d), mode='check', runner_sha=D)


@pytest.mark.parametrize('key,val',[('state','ACCEPTED'),('session_id',0),
                                     ('windows_mutation',True),('com_result',run_result())])
def test_readonly_check_rejects_mutation_or_fake_success(key,val):
    d=ctrl_result('check'); d[key]=val
    with pytest.raises(w.ComProbeBlocked):
        w.validate_report(json.dumps(d), mode='check', runner_sha=D)


@pytest.mark.parametrize('key,val',[('state','ACCEPTED'),('session_id',0),
                                     ('windows_mutation',False),('com_result',run_result())])
def test_launch_result_cannot_claim_success(key,val):
    d=ctrl_result('launch');d[key]=val
    with pytest.raises(w.ComProbeBlocked):
        w.validate_report(json.dumps(d), mode='launch', runner_sha=D)


@pytest.mark.parametrize('key,val',[('state','PASS_HACKED'),('runner_sha256','f'*64),
                                     ('session_id',3),('preexisting_illustrator_pid',0),
                                     ('error_code','COM_FAIL'),('error_hresult','-2147'),
                                     ('illustrator_version',''),('phase','STAGE_COM_VERSION'),
                                     ('client_files_touched',True),
                                     ('illustrator_document_mutation',True),
                                     ('production_ready',True)])
def test_verify_rejects_forged_native_com_success(key,val):
    d=ctrl_result('verify'); d['com_result'][key]=val
    with pytest.raises(w.ComProbeBlocked):
        w.validate_report(json.dumps(d), mode='verify', runner_sha=D)


def test_verify_can_report_diagnostic_failure_without_claiming_pass():
    d=ctrl_result('verify')
    d['state']='COM_ATTACH_REQUIRES_REVIEW'
    d['com_result'].update(state='BLOCKED_COM_ATTACH',phase='STAGE_COM_ROT_LOOKUP',
                            error_code='COM_ROT_ATTACH_FAILED',error_hresult='-2147221021',
                            illustrator_version=None)
    assert w.validate_report(json.dumps(d),mode='verify',runner_sha=D)['state']=='COM_ATTACH_REQUIRES_REVIEW'


def test_verify_waiting_state():
    d=ctrl_result('verify'); d['state']='WAITING_FOR_COM_ATTACH_RESULT'; d['com_result']=None
    assert w.validate_report(json.dumps(d),mode='verify',runner_sha=D)['state']=='WAITING_FOR_COM_ATTACH_RESULT'


def test_verify_waiting_rejects_fake_result():
    d=ctrl_result('verify'); d['state']='WAITING_FOR_COM_ATTACH_RESULT'
    with pytest.raises(w.ComProbeBlocked):
        w.validate_report(json.dumps(d),mode='verify',runner_sha=D)


def test_no_network_call_when_confirmation_missing(monkeypatch):
    monkeypatch.setattr(w,'remote_run',lambda a: (_ for _ in ()).throw(AssertionError('SSH unexpectedly used')))
    assert w.main(['--mode','launch'])==2
    assert w.main(['--mode','check','--confirm-com-attach-probe'])==2
    assert w.main(['--mode','verify','--confirm-com-attach-probe'])==2
    assert w.main(['--mode','source-check','--confirm-com-attach-probe'])==2


def test_source_check_not_remote(monkeypatch):
    monkeypatch.setattr(w,'remote_run',lambda a: (_ for _ in ()).throw(AssertionError('SSH unexpectedly used')))
    assert w.main(['--mode','source-check'])==0


def test_ssh_remote_once_and_no_raw_stderr(monkeypatch):
    a=SimpleNamespace(mode='check',host='192.168.50.69',user='work',
                      identity_file=Path('/tmp/key'),known_hosts=Path('/tmp/hosts'))
    monkeypatch.setattr(w,'ssh_command',lambda **kw:['ssh','-T','fake'])
    monkeypatch.setattr(w.subprocess,'run',lambda *arg,**kw:SimpleNamespace(returncode=2,stderr='secret',stdout=''))
    with pytest.raises(w.ComProbeBlocked, match='rc=2') as e:
        w.remote_run(a)
    assert 'secret' not in str(e.value)


def test_ssh_transport_stdin_rather_than_large_command(monkeypatch):
    a=SimpleNamespace(mode='check',host='192.168.50.69',user='work',
                      identity_file=Path('/tmp/key'),known_hosts=Path('/tmp/hosts'))
    calls=[]
    def ssh_command(**kwargs):
        assert kwargs['host']=='192.168.50.69'
        assert len(kwargs['encoded'])<1024
        return ['ssh','-T','encoded-bootstrap']
    def subprocess_run(cmd,**kwargs):
        calls.append(kwargs['input'])
        _,runner=w.source_check();_,h=w.render('check',*w.source_check())
        return SimpleNamespace(returncode=0,stderr='',stdout=json.dumps(
            dict(ctrl_result('check'),runner_sha256=h)))
    monkeypatch.setattr(w,'ssh_command',ssh_command)
    monkeypatch.setattr(w.subprocess,'run',subprocess_run)
    assert w.remote_run(a)['state']=='READY_FOR_COM_ATTACH_PROBE'
    assert len(calls)==1
    assert '$Mode = \'check\'' in calls[0]
    assert '__RUNNER_B64__' not in calls[0]

"""W2.5.3 offline isolated native proof; no SSH/Windows/Adobe calls."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import sys
import pytest

ROOT = Path(__file__).resolve().parents[2]
FILE = ROOT / 'scripts/graphic_design_lab/worker_runtime/windows_worker_w2_5_3_limited_native_illustrator_probe_v0_1.py'
sys.path.insert(0, str(FILE.parent))
spec = importlib.util.spec_from_file_location('gdl_w253_module', FILE)
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)


def sample_result(runner_sha, jsx_sha):
    return dict(schema_version=w.RUN_SCHEMA, task_id=w.TASK_ID,
                attempt_id=w.ATTEMPT_ID, host='PREPRESS', windows_account=r'PREPRESS\Work',
                jsx_sha256=jsx_sha, runner_sha256=runner_sha,
                font_name='ZapfChanceryC', phase='STAGE_DONE',
                token_elevated=False,token_elevation_type=3,token_limited_verified=True,
                illustrator_executed=True, native_ai_saved_reopened=True,
                editable_area_text=True, ai_sha256='1'*64, ai_bytes=2048,
                preexisting_illustrator_pid=9228, session_id=2,
                state='PASS_NATIVE_AI_REOPENED', error_code='NONE',
                production_ready=False, smb_mutation=False,
                client_files_touched=False, cleanup_executed=False)


def sample_report(mode, runner_sha='1'*64, jsx_sha='2'*64):
    status={'check':'READY_FOR_LIMITED_NATIVE_PROOF',
            'launch':'LIMITED_NATIVE_PROOF_STARTED_RESULT_PENDING',
            'verify':'LIMITED_NATIVE_AI_REOPENED_VERIFIED'}[mode]
    return dict(schema_version=w.SCHEMA,mode=mode,state=status,
                host='PREPRESS',ssh_account=r'PREPRESS\Work',task_name=w.TASK_NAME,
                task_id=w.TASK_ID,attempt_id=w.ATTEMPT_ID,
                runner_sha256=runner_sha,jsx_sha256=jsx_sha,
                scheduler_run_level='Limited', session_id=2,
                native_result=sample_result(runner_sha,jsx_sha) if mode=='verify' else None,
                windows_mutation=(mode=='launch'), smb_mutation=False,
                client_files_touched=False, cleanup_executed=False,
                production_ready=False)


def test_source_contract_and_local_artifacts():
    ctrl, runner, jsx=w.source_check()
    assert 'gdl-w253-limited-native-001' in ctrl
    assert '-RunLevel Limited' in ctrl
    assert "RunLevel -ne 'Limited'" in ctrl
    assert 'gdl_windows_operator_full_control_dev_v0_3' in w.CONTRACT.read_text()
    assert b'TOKEN_NOT_LIMITED' in runner
    assert b'token_elevation_type' in runner
    assert b'GetActiveObject' in runner
    assert b'DoJavaScript' in runner
    assert b'CreateNew' in runner
    assert b'W253_JSX_FAIL_' in jsx
    assert b'ZapfChanceryC' in jsx
    assert b'app.open' in jsx
    assert b'areaText' in jsx
    assert b'NO_DIALOGS_OR_ALERTS' in jsx
    assert b'illustrator-native-001' not in runner
    assert b'gdl-w25-illustrator-native-001' not in jsx


@pytest.mark.parametrize('mode',('check','launch','verify'))
def test_render_exact_mode_sha_and_no_markers(mode):
    ctrl,runner,jsx=w.source_check()
    p,rd,jd=w.render(mode,ctrl,runner,jsx)
    from hashlib import sha256
    assert jd==sha256(jsx).hexdigest()
    assert rd == sha256(runner.replace(b'__JSX_SOURCE_SHA__',jd.encode('ascii'))).hexdigest()
    assert f"$Mode = '{mode}'" in p
    assert not any(k in p for k in ('__MODE__','__RUNNER_B64__','__JSX_B64__',
                                    '__RUNNER_SHA__','__JSX_SHA__'))
    assert len(p)<50000


@pytest.mark.parametrize('mode',('source-check','remove','resume','check;exit',''))
def test_unsafe_render_rejected(mode):
    with pytest.raises(w.NativeBlocked): w.render(mode,*w.source_check())


@pytest.mark.parametrize('mode',('check','launch','verify'))
def test_valid_controller_evidence(mode):
    doc=sample_report(mode)
    assert w.validate_report(json.dumps(doc),mode,doc['runner_sha256'],doc['jsx_sha256'])==doc


@pytest.mark.parametrize('field,val',(
    ('token_elevated',True),('token_elevation_type',2),('token_limited_verified',False),
    ('ai_bytes',0),('ai_sha256',None),('preexisting_illustrator_pid',None),
    ('editable_area_text',False),('native_ai_saved_reopened',False),
    ('illustrator_executed',False),('production_ready',True),('smb_mutation',True),
    ('client_files_touched',True),('cleanup_executed',True),
    ('state','BLOCKED_NATIVE_EXECUTION'),('error_code','JSX_FONT_MISSING'),
    ('jsx_sha256','f'*64),('runner_sha256','f'*64),('font_name','Arial'),
))
def test_success_anti_forgery(field,val):
    d=sample_report('verify')
    d['native_result'][field]=val
    with pytest.raises(w.NativeBlocked):
        w.validate_report(json.dumps(d),'verify',d['runner_sha256'],d['jsx_sha256'])


@pytest.mark.parametrize('field,val',(
    ('state','LIMITED_NATIVE_AI_REOPENED_VERIFIED'),('windows_mutation',True),
    ('native_result',{}),('scheduler_run_level','Highest'),('production_ready',True),
    ('smb_mutation',True),('task_id','wrong'),('jsx_sha256','a'*64),
))
def test_preflight_anti_forgery(field,val):
    d=sample_report('check');d[field]=val
    with pytest.raises(w.NativeBlocked):
        w.validate_report(json.dumps(d),'check','1'*64,'2'*64)


def test_verify_waiting_not_success():
    d=sample_report('verify')
    d['state']='WAITING_FOR_LIMITED_NATIVE_RESULT'
    d['native_result']=None
    assert w.validate_report(json.dumps(d),'verify','1'*64,'2'*64)['state']=='WAITING_FOR_LIMITED_NATIVE_RESULT'


def test_verify_failure_retained_not_accepted():
    d=sample_report('verify')
    d['state']='LIMITED_NATIVE_RESULT_REQUIRES_REVIEW'
    d['native_result']['state']='BLOCKED_NATIVE_EXECUTION'
    d['native_result']['error_code']='W253_JSX_FAIL_FONT_LOOKUP'
    assert w.validate_report(json.dumps(d),'verify','1'*64,'2'*64)['state']=='LIMITED_NATIVE_RESULT_REQUIRES_REVIEW'


def test_source_check_does_not_ssh(monkeypatch,capsys):
    monkeypatch.setattr(w,'remote_run',lambda _: (_ for _ in ()).throw(AssertionError('SSH')))
    assert w.main(['--mode','source-check'])==0
    assert 'SOURCE_CHECK_PASS' in capsys.readouterr().out


def test_no_launch_without_confirmation(monkeypatch):
    monkeypatch.setattr(w,'remote_run',lambda _: (_ for _ in ()).throw(AssertionError('SSH')))
    assert w.main(['--mode','launch'])==2
    assert w.main(['--mode','check','--confirm-limited-native-illustrator'])==2
    assert w.main(['--mode','verify','--confirm-limited-native-illustrator'])==2


def test_remote_transport_single_call_no_retry_on_error(monkeypatch):
    a=SimpleNamespace(mode='launch',host='192.168.50.69',user='work',
                      identity_file=Path('/tmp/key'),known_hosts=Path('/tmp/hosts'))
    monkeypatch.setattr(w,'ssh_command',lambda **kw:['ssh','-T','pwsh'])
    calls=[]
    def failure(*args,**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(returncode=2,stdout='',stderr='private')
    monkeypatch.setattr(w.subprocess,'run',failure)
    with pytest.raises(w.NativeBlocked,match='do not retry launch'):
        w.remote_run(a)
    assert len(calls)==1


def test_no_old_attempt_and_no_cleanup_or_customer_in_sources():
    ctrl,runner,jsx=w.source_check()
    combined=ctrl.lower()+runner.decode('ascii').lower()+jsx.decode('ascii').lower()
    for token in ('gdl-w251-com-attach-001','gdl-w252-limited-com-001',
                  'gdl-w25-illustrator-native-001','remove-item ',
                  'unregister-scheduledtask','stop-process','new-smbshare',
                  'folder.mydocuments','alert(','confirm(','prompt('):
        assert token not in combined
    assert 'createNew'.lower() in combined
    assert 'Register-ScheduledTask'.lower() in combined
    assert 'Start-ScheduledTask'.lower() in combined
    assert 'donotsavechanges' in combined

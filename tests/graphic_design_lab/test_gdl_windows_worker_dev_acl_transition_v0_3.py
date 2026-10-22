"""DEV ACL tests: pure offline, no Windows, no SSH, no mutations."""
from __future__ import annotations
from types import SimpleNamespace
from unittest.mock import Mock
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import pytest

D=Path(__file__).resolve().parents[2]/'scripts/graphic_design_lab/worker_runtime'
sys.path.insert(0,str(D))
S=D/'windows_worker_dev_acl_transition_v0_3.py'
spec=importlib.util.spec_from_file_location('gdl_dev_acl_migration_test',S)
w=importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)

def evidence(mode='check',state='READY_FOR_DEV_FULL_CONTROL',prior='CURRENT_RX',mutated=False):
    return dict(schema_version=w.SCHEMA,policy_id=w.POLICY,mode=mode,
        state=state,previous_state=prior,host='PREPRESS',ssh_account=r'PREPRESS\Work',
        boundary=w.SHARED,gdl_root=w.GDL_ROOT,directories_checked=8,
        operator_sid_verified=True,root_inheritance_protected=True,
        windows_mutation=mutated,scheduled_tasks_mutated=False,
        client_files_touched=False,smb_mutation=False,illustrator_execution=False,
        cleanup_executed=False,production_ready=False)

def test_source_check_contract_and_safety_markers():
    s=w.source_check()
    assert s.count('__DEV_ACL_MODE__')==1
    assert 'Set-Acl -LiteralPath $Shared' in s
    assert 'Set-Acl -LiteralPath $Root' not in s
    assert 'Remove-Item ' not in s
    assert 'icacls' not in s.lower()
    assert "'PREPRESS\\Work'" in s
    assert 'NO_AUTOMATIC_CLEANUP' in s
    assert "'D:\\ForPrint_Automation'" in s

@pytest.mark.parametrize('mode,state,prior,mutated',[
    ('check','READY_FOR_DEV_FULL_CONTROL','CURRENT_RX',False),
    ('check','DEV_FULL_CONTROL_VERIFIED','DEV_FULL',False),
    ('apply','DEV_FULL_CONTROL_VERIFIED','CURRENT_RX',True),
])
def test_valid_evidence(mode,state,prior,mutated):
    v=evidence(mode,state,prior,mutated)
    assert w.validate_report(json.dumps(v),mode)==v

@pytest.mark.parametrize('k,v',[
    ('policy_id','other'),('host','DESKTOP'),('boundary','D:\\'),
    ('directories_checked',7),('root_inheritance_protected',False),
    ('windows_mutation',True),('scheduled_tasks_mutated',True),
    ('client_files_touched',True),('smb_mutation',True),
    ('illustrator_execution',True),('cleanup_executed',True),('production_ready',True),
])
def test_check_forgery_rejected(k,v):
    x=evidence();x[k]=v
    with pytest.raises(w.DevAclBlocked):w.validate_report(json.dumps(x),'check')

def test_check_does_not_accept_mixed_or_unexpected_mode():
    for vals in [('DEV_FULL_CONTROL_VERIFIED','CURRENT_RX'),('READY_FOR_DEV_FULL_CONTROL','DEV_FULL')]:
        x=evidence(state=vals[0],prior=vals[1])
        with pytest.raises(w.DevAclBlocked):w.validate_report(json.dumps(x),'check')

def test_apply_must_have_effect_and_transition():
    for vals in [('READY_FOR_DEV_FULL_CONTROL','CURRENT_RX',True),('DEV_FULL_CONTROL_VERIFIED','DEV_FULL',False)]:
        x=evidence('apply',*vals)
        with pytest.raises(w.DevAclBlocked):w.validate_report(json.dumps(x),'apply')

def test_no_remote_without_exact_confirmation(monkeypatch):
    monkeypatch.setattr(w,'remote_run',lambda a: (_ for _ in ()).throw(AssertionError('Remote invoked')))
    assert w.main(['--mode','apply'])==2
    assert w.main(['--mode','check','--confirm-dev-full-control'])==2
    assert w.main(['--mode','source-check','--confirm-dev-full-control'])==2
    assert w.main(['--mode','source-check'])==0

def test_check_uses_guarded_stdin(monkeypatch):
    args=SimpleNamespace(mode='check',host='192.168.50.69',user='work',
        identity_file=Path('/tmp/key'),known_hosts=Path('/tmp/hosts'))
    monkeypatch.setattr(w,'ssh_command',Mock(return_value=['ssh','-T','encoded']))
    calls=[]
    def run(*aa,**kw):
        calls.append(kw)
        return SimpleNamespace(returncode=0,stdout=json.dumps(evidence()),stderr='')
    monkeypatch.setattr(subprocess,'run',run)
    assert w.remote_run(args)['state']=='READY_FOR_DEV_FULL_CONTROL'
    assert len(calls)==1
    assert "'check'" in calls[0]['input']
    assert '__DEV_ACL_MODE__' not in calls[0]['input']
    assert calls[0]['timeout']<=90

def test_windows_failure_has_no_automatic_retry(monkeypatch):
    args=SimpleNamespace(mode='apply',host='192.168.50.69',user='work',
        identity_file=Path('/tmp/key'),known_hosts=Path('/tmp/hosts'))
    monkeypatch.setattr(w,'ssh_command',lambda **kw:['ssh','-T','encoded'])
    seen=[]
    def fake(*a,**kw):
        seen.append(kw)
        return SimpleNamespace(returncode=2,stdout='',stderr='PRIVATE_DETAILS')
    monkeypatch.setattr(subprocess,'run',fake)
    with pytest.raises(w.DevAclBlocked,match='no automatic retry') as e:
        w.remote_run(args)
    assert 'PRIVATE_DETAILS' not in str(e.value)
    assert len(seen)==1

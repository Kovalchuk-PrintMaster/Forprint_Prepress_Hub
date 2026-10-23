"""Offline W2.7-C2 regression. NO Windows calls, no SSH, no launch."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

SOURCE = Path(__file__).resolve().parents[2] / 'scripts/graphic_design_lab/worker_runtime/gdl_w27c2_native_execution_preflight_v0_1.py'
SRC_DIR = SOURCE.parent
sys.path.insert(0, str(SRC_DIR))
if not (SRC_DIR / 'gdl_w27_illustrator_task_package_v0_1.py').exists():
    pkg=ModuleType('gdl_w27_illustrator_task_package_v0_1')
    pkg.PackageBlocked=type('PackageBlocked',(ValueError,),{})
    pkg.read_regular=lambda path,limit:path.read_bytes()
    pkg.repo_tmp_path=lambda path,must_exist:path
    sys.modules[pkg.__name__]=pkg
    native=ModuleType('gdl_w27c_native_candidate_review_v0_1')
    native.CandidateBlocked=type('CandidateBlocked',(RuntimeError,),{})
    native.TASK='gdl-w27c-native-001'
    native.ATTEMPT='a0001'
    native.source_check=lambda:({
        'launch_authorized':False,'blueprint_review_pending':True,
        'runner_implementation':'NOT_IMPLEMENTED',
        'jsx_sha256':'98780bcd7939df58f16aa0e123ced5efc4956ed43cc6438d0516b43d4d819902',
        'jsx_bytes':3791},b'x')
    native.inspect_candidate=lambda raw,expected,profile,script:{
        'state':'SYNTHETIC_NATIVE_CANDIDATE_VERIFIED_NOT_EXECUTABLE_BY_WORKER',
        'worker_launch_authorized':False}
    sys.modules[native.__name__]=native
    stage=ModuleType('gdl_w27b_windows_package_staging_v0_1')
    stage.StageBlocked=type('StageBlocked',(RuntimeError,),{})
    stage.source_check=lambda:None
    sys.modules[stage.__name__]=stage
    host=ModuleType('windows_worker_w2_host_inspector_v0_1')
    host.InspectionBlocked=type('InspectionBlocked',(RuntimeError,),{})
    host.ssh_command=lambda **kw:['ssh','-T','mock']
    sys.modules[host.__name__]=host
    bridge=ModuleType('windows_worker_w2_3_workspace_initializer_v0_1')
    bridge.PS_STDIN_BRIDGE='$s=[Console]::In.ReadToEnd(); & ([ScriptBlock]::Create($s))'
    sys.modules[bridge.__name__]=bridge
spec=importlib.util.spec_from_file_location('gdl_w27c2_preflight_under_test',SOURCE)
w=importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)


def report(state='STAGED_NATIVE_HOST_PREREQUISITES_PRESENT_AUTHORITY_PENDING'):
    out={
        'schema_version':w.SCHEMA,'state':state,
        'task_id':w.TASK,'attempt_id':w.ATTEMPT,'host':'PREPRESS',
        'windows_account':r'PREPRESS\Work',
        'archive_sha256':w.ARCHIVE_SHA,'archive_bytes':w.ARCHIVE_BYTES,
        'jsx_sha256':w.JSX_SHA,'jsx_bytes':w.JSX_BYTES,
        'staging_receipt_sha256':'a'*64,
        'session_id':2,'preexisting_illustrator_pid':9228,
    }
    for key in ('windows_mutation','payload_extracted','illustrator_execution',
                'com_attach_performed','scheduled_tasks_mutated','worker_launch_authorized',
                'dispatch_authorized','production_ready','accepted','cleanup_executed',
                'client_files_touched','smb_mutation'):
        out[key]=False
    if state=='WAITING_FOR_INTERACTIVE_SESSION_NOT_AUTHORIZED':
        out['session_id']=None;out['preexisting_illustrator_pid']=None
    if state=='WAITING_FOR_ILLUSTRATOR_OR_DESKTOP_NOT_AUTHORIZED':
        out['preexisting_illustrator_pid']=None
    return out


def test_real_powershell_source_is_read_only():
    ps=w.CONTROLLER.read_text(encoding='ascii')
    for forbidden in ('Start-ScheduledTask','Register-ScheduledTask','GetActiveObject',
                      'DoJavaScript','Remove-Item','Set-Acl','WriteAllBytes','CreateDirectory'):
        assert forbidden.lower() not in ps.lower()
    for mark in w.MARKERS:
        assert ps.count(mark)==1
    assert 'task_package.zip' in ps and 'staging_receipt.json' in ps


def test_render_exact_bindings():
    ps=w.render(w.CONTROLLER.read_text('ascii'))
    assert w.ARCHIVE_SHA in ps and w.JSX_SHA in ps
    assert w.TASK in ps and w.ATTEMPT in ps
    assert not any(m in ps for m in w.MARKERS)


def test_render_double_marker_blocked():
    ps=w.CONTROLLER.read_text('ascii')+'\n__TASK_ID__'
    with pytest.raises(w.PreflightBlocked):w.render(ps)


@pytest.mark.parametrize('state', sorted(w.STATES))
def test_three_valid_states(state):
    assert w.validate_report(json.dumps(report(state)))['state']==state


@pytest.mark.parametrize('field,value',[
    ('schema_version','invalid'),('state','PRODUCTION_READY'),
    ('task_id','other'),('attempt_id','a0002'),
    ('host','S01'),('windows_account',r'PREPRESS\Admin'),
    ('archive_sha256','0'*64),('archive_bytes',True),('archive_bytes',5121),
    ('jsx_sha256','0'*64),('jsx_bytes',True),
    ('staging_receipt_sha256','bad'),
    ('windows_mutation',True),('payload_extracted',True),
    ('illustrator_execution',True),('com_attach_performed',True),
    ('scheduled_tasks_mutated',True),('worker_launch_authorized',True),
    ('dispatch_authorized',True),('production_ready',True),
    ('accepted',True),('cleanup_executed',True),
    ('client_files_touched',True),('smb_mutation',True),
    ('session_id',None),('preexisting_illustrator_pid',None),
])
def test_invalid_machine_result_rejected(field,value):
    item=report();item[field]=value
    with pytest.raises(w.PreflightBlocked):w.validate_report(json.dumps(item))


@pytest.mark.parametrize('bad', ['','false','[]','null','{}','{}\n{}','Not JSON'])
def test_invalid_json_rejected(bad):
    with pytest.raises(w.PreflightBlocked):w.validate_report(bad)


def test_waiting_state_rejects_pid():
    item=report('WAITING_FOR_INTERACTIVE_SESSION_NOT_AUTHORIZED')
    item['preexisting_illustrator_pid']=9228
    with pytest.raises(w.PreflightBlocked):w.validate_report(json.dumps(item))


def test_source_check_blocks_profile_grant(monkeypatch):
    monkeypatch.setattr(w,'stage_source_check',lambda:None)
    monkeypatch.setattr(w,'native_source_check',lambda:({'launch_authorized':True},b'x'))
    with pytest.raises(w.PreflightBlocked):w.source_check()


def test_source_check_blocks_mismatched_profile_digest(monkeypatch):
    monkeypatch.setattr(w,'stage_source_check',lambda:None)
    monkeypatch.setattr(w,'native_source_check',lambda:({
        'launch_authorized':False,'blueprint_review_pending':True,
        'runner_implementation':'NOT_IMPLEMENTED','jsx_sha256':w.JSX_SHA,
        'jsx_bytes':w.JSX_BYTES},b'wrong'))
    with pytest.raises(w.PreflightBlocked):w.source_check()


def test_source_check_rejects_missing_controller(monkeypatch,tmp_path):
    monkeypatch.setattr(w,'stage_source_check',lambda:None)
    monkeypatch.setattr(w,'native_source_check',lambda:({
        'launch_authorized':False,'blueprint_review_pending':True,
        'runner_implementation':'NOT_IMPLEMENTED',
        'jsx_sha256':w.JSX_SHA,'jsx_bytes':w.JSX_BYTES},b'abc'))
    monkeypatch.setattr(w,'CONTROLLER',tmp_path/'missing.ps1')
    with pytest.raises(w.PreflightBlocked):w.source_check()


def test_cli_source_check_no_remote(monkeypatch):
    monkeypatch.setattr(w,'source_check',lambda:'safe')
    monkeypatch.setattr(w,'remote_check',lambda *x:(_ for _ in ()).throw(AssertionError('unexpected')))
    assert w.main(['--mode','source-check'])==0
    assert w.main(['--mode','source-check','--host','192.168.50.69'])==2
    assert w.main(['--mode','check'])==2


def test_archive_requires_known_digest():
    with pytest.raises(w.PreflightBlocked):
        w.check_archive(Path('anything.zip'),'f'*64)


def test_archive_fails_on_unknown_size(monkeypatch,tmp_path):
    p=tmp_path/'mock.zip';p.write_bytes(b'bad')
    monkeypatch.setattr(w,'repo_tmp_path',lambda path, must_exist:path)
    monkeypatch.setattr(w,'read_regular',lambda path,n:path.read_bytes())
    monkeypatch.setattr(w,'native_source_check',lambda:({},b'x'))
    monkeypatch.setattr(w,'inspect_candidate',lambda raw,digest,config,jsx:{
        'state':'SYNTHETIC_NATIVE_CANDIDATE_VERIFIED_NOT_EXECUTABLE_BY_WORKER',
        'worker_launch_authorized':False})
    with pytest.raises(w.PreflightBlocked):
        w.check_archive(p,w.ARCHIVE_SHA)


def test_remote_no_retry_on_error(monkeypatch):
    monkeypatch.setattr(w,'ssh_command',lambda **kw:['ssh','test'])
    calls=[]
    def fake(*args,**kwargs):
        calls.append((args,kwargs))
        return SimpleNamespace(returncode=255,stdout='',stderr='PRIVATE_SECRET')
    monkeypatch.setattr(w.subprocess,'run',fake)
    args=SimpleNamespace(host='192.168.50.69',user='work',identity_file=Path('/tmp/key'),known_hosts=Path('/tmp/k'))
    with pytest.raises(w.PreflightBlocked) as e:w.remote_check(args,w.CONTROLLER.read_text('ascii'))
    assert len(calls)==1 and calls[0][1]['timeout']==90
    assert 'PRIVATE_SECRET' not in str(e.value)


def test_remote_success_validate(monkeypatch):
    monkeypatch.setattr(w,'ssh_command',lambda **kw:['ssh','test'])
    monkeypatch.setattr(w.subprocess,'run',lambda *args,**kwargs:SimpleNamespace(
        returncode=0,stdout=json.dumps(report()),stderr=''))
    args=SimpleNamespace(host='192.168.50.69',user='work',identity_file=Path('/tmp/key'),known_hosts=Path('/tmp/k'))
    assert w.remote_check(args,w.CONTROLLER.read_text('ascii'))['worker_launch_authorized'] is False

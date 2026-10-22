"""Offline-only W2.7-B synthetic opaque ZIP staging tests; NEVER contacts PREPRESS."""
from __future__ import annotations

import importlib.util
import json
from hashlib import sha256
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/graphic_design_lab/worker_runtime/gdl_w27b_windows_package_staging_v0_1.py'
sys.path.insert(0, str(SCRIPT.parent))

# Only for running the release artifact outside the live ForPrint repository.
if not (SCRIPT.parent / 'windows_worker_w2_host_inspector_v0_1.py').exists():
    host = ModuleType('windows_worker_w2_host_inspector_v0_1')
    host.InspectionBlocked = type('InspectionBlocked',(Exception,),{})
    host.ssh_command = lambda **kw: ['ssh','-T','stub']
    bridge = ModuleType('windows_worker_w2_3_workspace_initializer_v0_1')
    bridge.PS_STDIN_BRIDGE = '$s=[Console]::In.ReadToEnd(); & ([ScriptBlock]::Create($s))'
    sys.modules.setdefault(host.__name__, host)
    sys.modules.setdefault(bridge.__name__, bridge)

spec = importlib.util.spec_from_file_location('gdl_w27b_stage_under_test', SCRIPT)
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
from gdl_w27_illustrator_task_package_v0_1 import archive_bytes, manifest_for, inspect_zip


def sample():
    req={'task_id':'gdl-w27-synthetic-001', 'attempt_id':'a0001',
         'expected_outputs':[
           {'path':'export/native_result.ai','kind':'native_ai','required':True},
           {'path':'export/worker_result.json','kind':'machine_result','required':True},
         ]}
    blobs={'input/main.jsx':b'#target illustrator\n(function(){return "TEST";})();\n'}
    doc=manifest_for(req,blobs)
    archive=archive_bytes(doc,blobs)
    got,hash_=inspect_zip(archive)
    assert got==doc
    return doc,archive,hash_


def report(mode='check',state=None,**values):
    m,a,d=sample()
    state=state or {'check':'READY_FOR_SYNTHETIC_STAGE',
                    'stage':'SYNTHETIC_PACKAGE_STAGED_NOT_EXECUTED',
                    'verify':'SYNTHETIC_STAGE_SHA_VERIFIED_NOT_EXECUTED'}[mode]
    x={
      'schema_version':w.SCHEMA,'mode':mode,'state':state,'host':'PREPRESS',
      'ssh_account':r'PREPRESS\Work','task_id':m['task_id'],'attempt_id':m['attempt_id'],
      'archive_sha256':d,'archive_bytes':len(a),
      'staging_receipt_sha256': None if mode=='check' else 'a'*64,
      'windows_mutation': mode=='stage',
      'payload_extracted':False,'illustrator_execution':False,
      'worker_launch_authorized':False,'production_ready':False,'accepted':False,
      'scheduled_tasks_mutated':False,'client_files_touched':False,'smb_mutation':False,
      'cleanup_executed':False,
    }
    x.update(values)
    return x


def test_powershell_source_guards(monkeypatch):
    monkeypatch.setattr(w,'check_static',lambda: {})
    s=w.source_check()
    for mark in ('TASK_EXISTS_NO_RESTAGE','STAGED_ARCHIVE_CHANGED',
                 'SYNTHETIC_PACKAGE_STAGED_NOT_EXECUTED',
                 'SYNTHETIC_STAGE_SHA_VERIFIED_NOT_EXECUTED','CreateNew',
                 'NO_AUTOMATIC_CLEANUP','NO_TASK_SCHEDULER','NO_JSX_EXECUTION'):
        assert mark in s
    assert 'Start-ScheduledTask' not in s
    assert 'DoJavaScript' not in s
    assert 'Remove-Item' not in s
    assert 'Set-Acl' not in s
    assert 'ExtractToDirectory' not in s


def test_template_marker_missing_blocks(tmp_path,monkeypatch):
    monkeypatch.setattr(w,'check_static',lambda: {})
    path=tmp_path/'bad.ps1';path.write_text('bad', encoding='ascii')
    monkeypatch.setattr(w,'CONTROLLER',path)
    with pytest.raises(w.StageBlocked,match='template binding'):w.source_check()


def test_source_authority_rejection(monkeypatch):
    def block():raise w.PackageBlocked('wrong authority')
    monkeypatch.setattr(w,'check_static',block)
    with pytest.raises(w.StageBlocked,match='source/authority'):w.source_check()


def test_archive_round_trip():
    m,a,d=sample()
    assert m['state']=='PREPARED_NOT_DISPATCH_AUTHORIZED'
    assert m['authority']['dispatch_authorized'] is False
    assert len(a)<w.MAX_STAGE and sha256(a).hexdigest()==d


def test_load_archive_exact_digest(tmp_path,monkeypatch):
    m,a,d=sample();p=tmp_path/'task.zip';p.write_bytes(a)
    monkeypatch.setattr(w,'repo_tmp_path',lambda x, must_exist: x)
    got,raw,digest=w.load_archive(p,d)
    assert got==m and raw==a and digest==d


@pytest.mark.parametrize('bad', ['a'*64,'incorrect','A'*64,''])
def test_load_archive_wrong_digest_blocked(tmp_path,monkeypatch,bad):
    _,a,_=sample();p=tmp_path/'task.zip';p.write_bytes(a)
    monkeypatch.setattr(w,'repo_tmp_path',lambda x,must_exist:x)
    with pytest.raises(w.StageBlocked):w.load_archive(p,bad)


def test_load_archive_mutation_blocked(tmp_path,monkeypatch):
    _,a,d=sample();p=tmp_path/'task.zip';p.write_bytes(a[:-2]+b'xx')
    monkeypatch.setattr(w,'repo_tmp_path',lambda x,must_exist:x)
    with pytest.raises(w.StageBlocked):w.load_archive(p,d)


def test_load_archive_oversize_blocked(tmp_path,monkeypatch):
    p=tmp_path/'task.zip';p.write_bytes(b'x'*(w.MAX_STAGE+1))
    monkeypatch.setattr(w,'repo_tmp_path',lambda x,must_exist:x)
    with pytest.raises(w.StageBlocked):w.load_archive(p,'a'*64)


@pytest.mark.parametrize('mode', ['check','stage','verify'])
def test_template_render_exact(monkeypatch,mode):
    monkeypatch.setattr(w,'check_static',lambda:{})
    s=w.source_check();m,a,d=sample()
    out=w.render(mode,s,m,a,d)
    assert '__MODE__' not in out and '__TASK_ID__' not in out
    assert f"$Mode = '{mode}'" in out
    assert f"$TaskId = '{m['task_id']}'" in out
    assert f"$ArchiveSha = '{d}'" in out
    assert len(out)>len(s)


def test_template_rejects_remote_run(monkeypatch):
    monkeypatch.setattr(w,'check_static',lambda:{})
    s=w.source_check();m,a,d=sample()
    with pytest.raises(w.StageBlocked):w.render('launch',s,m,a,d)


@pytest.mark.parametrize('mode', ['check','stage','verify'])
def test_validate_passes_expected_modes(mode):
    m,a,d=sample();doc=report(mode)
    assert w.validate_report(json.dumps(doc),mode,m,d,len(a))==doc


@pytest.mark.parametrize('key,value', [
    ('host','WRONG'),('ssh_account','PREPRESS\\Admin'),('task_id','other'),
    ('attempt_id','a9999'),('archive_sha256','b'*64),('archive_bytes',True),
    ('payload_extracted',True),('illustrator_execution',True),
    ('worker_launch_authorized',True),('production_ready',True),
    ('accepted',True),('scheduled_tasks_mutated',True),
    ('client_files_touched',True),('smb_mutation',True),
    ('cleanup_executed',True),('state','PUBLISHED'),
    ('windows_mutation',True),('staging_receipt_sha256','a'*64),
])
def test_validate_check_tamper_rejected(key,value):
    m,a,d=sample();doc=report('check',**{key:value})
    with pytest.raises(w.StageBlocked):w.validate_report(json.dumps(doc),'check',m,d,len(a))


@pytest.mark.parametrize('key,value',[
    ('windows_mutation',False),('state','READY_FOR_SYNTHETIC_STAGE'),
    ('staging_receipt_sha256',None),('staging_receipt_sha256','xyz'),
    ('payload_extracted',True),('production_ready',True),
])
def test_validate_stage_tamper_rejected(key,value):
    m,a,d=sample();doc=report('stage',**{key:value})
    with pytest.raises(w.StageBlocked):w.validate_report(json.dumps(doc),'stage',m,d,len(a))


@pytest.mark.parametrize('key,value',[
    ('windows_mutation',True),('state','READY_FOR_SYNTHETIC_STAGE'),
    ('staging_receipt_sha256',None),('worker_launch_authorized',True),
])
def test_validate_verify_tamper_rejected(key,value):
    m,a,d=sample();doc=report('verify',**{key:value})
    with pytest.raises(w.StageBlocked):w.validate_report(json.dumps(doc),'verify',m,d,len(a))


def test_validate_bad_json():
    m,a,d=sample()
    with pytest.raises(w.StageBlocked):w.validate_report('not a report','check',m,d,len(a))


def test_ssh_failure_single_call_private(monkeypatch):
    m,a,d=sample()
    monkeypatch.setattr(w,'source_check',lambda:w.CONTROLLER.read_text())
    monkeypatch.setattr(w,'ssh_command',lambda **kwargs:['ssh','-T','unit'])
    calls=[]
    def fake(*args,**kw):
        calls.append(kw)
        return SimpleNamespace(returncode=2,stdout='',stderr='SECRET')
    monkeypatch.setattr(w.subprocess,'run',fake)
    args=SimpleNamespace(mode='stage',host='192.168.50.69',user='work',
                         identity_file=Path('/tmp/key'),known_hosts=Path('/tmp/known'))
    with pytest.raises(w.StageBlocked,match='no blind retry') as e:w.remote_run(args,m,a,d)
    assert len(calls)==1 and calls[0]['timeout']==120
    assert 'SECRET' not in str(e.value)


def test_remote_result_check_one_call(monkeypatch):
    m,a,d=sample()
    monkeypatch.setattr(w,'source_check',lambda:w.CONTROLLER.read_text())
    monkeypatch.setattr(w,'ssh_command',lambda **kwargs:['ssh','-T','unit'])
    monkeypatch.setattr(w.subprocess,'run',lambda *args,**kw: SimpleNamespace(returncode=0,stdout=json.dumps(report('check')),stderr=''))
    args=SimpleNamespace(mode='check',host='192.168.50.69',user='work',
                         identity_file=Path('/tmp/key'),known_hosts=Path('/tmp/known'))
    assert w.remote_run(args,m,a,d)['state']=='READY_FOR_SYNTHETIC_STAGE'


def test_source_check_no_ssh(monkeypatch):
    monkeypatch.setattr(w,'source_check',lambda:'ok')
    monkeypatch.setattr(w,'remote_run',lambda *args: (_ for _ in ()).throw(AssertionError('SSH contacted')))
    assert w.main(['--mode','source-check'])==0
    assert w.main(['--mode','source-check','--confirm-synthetic-stage'])==2


@pytest.mark.parametrize('mode', ['stage','check','verify'])
def test_missing_credentials_no_ssh(monkeypatch,mode):
    monkeypatch.setattr(w,'source_check',lambda:'ok')
    monkeypatch.setattr(w,'remote_run',lambda *args: (_ for _ in ()).throw(AssertionError('SSH')))
    a=['--mode',mode,'--archive','tmp/file.zip','--expected-archive-sha256','a'*64]
    if mode=='stage':a+=['--confirm-synthetic-stage']
    assert w.main(a)==2


def test_no_execution_in_python_source():
    s=w.CONTROLLER.read_text()
    assert 'Register-ScheduledTask' not in s
    assert 'DoJavaScript(' not in s
    assert 'NO_AUTOMATIC_CLEANUP' in s

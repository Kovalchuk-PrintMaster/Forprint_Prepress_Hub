"""W2.7-C3D offline regression and fail-closed evidence inspection tests."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'scripts/graphic_design_lab/worker_runtime'
sys.path.insert(0,str(SCRIPTS))
import gdl_w27c3d_live_attempt_inspector_v0_1 as w


def example(present=()):
    artifacts={k: {'present':k in present,
                   'bytes': 123 if k in present else None,
                   'sha256':'a'*64 if k in present else None}
               for k in w.EVIDENCE}
    return dict(
        schema_version=w.REPORT_SCHEMA,
        state=w.FENCED if present else w.INERT,
        task_id=w.TASK,attempt_id=w.ATTEMPT,
        host='PREPRESS',windows_account=r'PREPRESS\Work',
        archive_sha256=w.PACKAGE_SHA,archive_bytes=w.ARCHIVE_BYTES,
        staging_receipt_sha256=w.RECEIPT_SHA,
        artifacts=artifacts,execution_evidence_present=bool(present),
        live_observation=True,no_rerun_authorized=True,
        worker_launch_authorized=False,dispatch_authorized=False,
        production_ready=False,accepted=False,windows_mutation=False,
        jsx_executed_by_inspector=False,com_attach_performed=False,
        scheduler_mutation=False,cleanup_executed=False,
        client_files_touched=False,smb_mutation=False,
    )


def fail(r):
    with pytest.raises(w.InspectionFailure):
        w.validate_report(json.dumps(r))


def test_source_check_contract_sha_and_no_launch():
    c,s=w.source_check()
    assert c['execution_authorized'] is False
    assert c['automatic_retry'] is False
    assert 'Register-ScheduledTask' not in s
    assert 'DoJavaScript(' not in s
    assert 'GetActiveObject(' not in s
    assert 'Remove-Item ' not in s
    assert len(s)>1500


def test_render_exact_identifiers_and_no_placeholders():
    _,s=w.source_check()
    data=w.render(s)
    for placeholder in w.MARKERS:
        assert placeholder not in data
    assert w.PACKAGE_SHA in data and w.RECEIPT_SHA in data
    assert w.TASK in data and w.ATTEMPT in data


def test_render_tampered_placeholder():
    _,s=w.source_check()
    with pytest.raises(w.InspectionFailure):w.render(s.replace(w.MARKERS[0],'BROKEN'))


def test_source_check_contract_mutation(monkeypatch, tmp_path):
    obj=json.loads(w.CONTRACT.read_text())
    obj['dispatch_authorized']=True
    p=tmp_path/'bad.json';p.write_text(json.dumps(obj))
    monkeypatch.setattr(w,'CONTRACT',p)
    with pytest.raises(w.InspectionFailure):w.source_check()


def test_source_check_ps_mutation(monkeypatch, tmp_path):
    p=tmp_path/'bad.ps1';p.write_bytes(w.CONTROLLER.read_bytes()+b' ')
    monkeypatch.setattr(w,'CONTROLLER',p)
    with pytest.raises(w.InspectionFailure):w.source_check()


def test_inert_inspection_result():
    r=w.validate_report(json.dumps(example()))
    assert r['execution_evidence_present'] is False
    assert r['no_rerun_authorized'] is True


@pytest.mark.parametrize('artifact', w.EVIDENCE)
def test_any_single_artifact_requires_reconciliation(artifact):
    r=w.validate_report(json.dumps(example((artifact,))))
    assert r['state']==w.FENCED


def test_all_artifacts_require_reconciliation():
    r=w.validate_report(json.dumps(example(w.EVIDENCE)))
    assert r['state']==w.FENCED


@pytest.mark.parametrize('field', [
    'schema_version','task_id','attempt_id','host','windows_account',
    'archive_sha256','archive_bytes','staging_receipt_sha256',
    'live_observation','no_rerun_authorized','worker_launch_authorized',
    'dispatch_authorized','production_ready','accepted','windows_mutation',
    'jsx_executed_by_inspector','com_attach_performed','scheduler_mutation',
    'cleanup_executed','client_files_touched','smb_mutation',
])
def test_report_field_tamper_blocked(field):
    d=example()
    value=d[field]
    d[field]='malicious' if isinstance(value,str) else (not value if isinstance(value,bool) else 42)
    fail(d)


def test_extra_report_field_blocked():
    d=example();d['execution_authorized']=True;fail(d)


def test_missing_report_field_blocked():
    d=example();d.pop('windows_mutation');fail(d)


def test_bad_json_report_blocked():
    for v in ('', '[1]', '{} {}', 'not json'):
        with pytest.raises(w.InspectionFailure):w.validate_report(v)


def test_false_evidence_field_state_blocked():
    d=example(('start_claim',));d['state']=w.INERT;fail(d)


def test_false_evidence_present_blocked():
    d=example(('worker_result',));d['execution_evidence_present']=False;fail(d)


def test_invented_presence_blocked():
    d=example();d['execution_evidence_present']=True;fail(d)


@pytest.mark.parametrize('bad',[-1,False,1.2,104857601])
def test_bad_evidence_size_blocked(bad):
    d=example(('native_ai',));d['artifacts']['native_ai']['bytes']=bad;fail(d)


@pytest.mark.parametrize('bad',[None,'not-sha','A'*64,False,3])
def test_bad_evidence_sha_blocked(bad):
    d=example(('jsx',));d['artifacts']['jsx']['sha256']=bad;fail(d)


@pytest.mark.parametrize('bad',[None,0,'a'*64])
def test_absent_metadata_must_be_null(bad):
    d=example();d['artifacts']['jsx']['sha256']=bad
    if bad is not None:fail(d)
    else:assert w.validate_report(json.dumps(d))


@pytest.mark.parametrize('artifact',w.EVIDENCE)
def test_artifact_wrong_shape_blocked(artifact):
    d=example();d['artifacts'][artifact]['unexpected']='x';fail(d)


def test_artifact_absent_as_present_with_no_meta_blocked():
    d=example();d['artifacts']['worker_result']['present']=True;fail(d)


def test_artifact_present_size_bounds():
    d=example(('start_claim',));d['artifacts']['start_claim']['bytes']=w.MAX_EVIDENCE_BYTES['start_claim'];assert w.validate_report(json.dumps(d))
    d['artifacts']['start_claim']['bytes']+=1;fail(d)


def test_unrecognized_artifact_blocked():
    d=example();d['artifacts']['secret']={'present':False,'sha256':None,'bytes':None};fail(d)


def test_remote_ssh_rc_denies(monkeypatch):
    monkeypatch.setattr(w,'ssh_command',lambda **kwargs:['ssh','stub','ps'])
    monkeypatch.setattr(w,'subprocess',SimpleNamespace(
        run=lambda *a,**kw:SimpleNamespace(returncode=255,stdout='',stderr='secret'),
        TimeoutExpired=subprocess.TimeoutExpired))
    args=SimpleNamespace(host='192.168.50.69',user='work',identity_file=Path('/a'),known_hosts=Path('/b'))
    _,s=w.source_check()
    with pytest.raises(w.InspectionFailure,match='rc=255'):
        w.remote_inspect(args,s)


def test_remote_ssh_pass_and_stdin(monkeypatch):
    seen={}
    def run(cmd,**kw):
        seen['input']=kw['input'];seen['command']=cmd
        return SimpleNamespace(returncode=0,stdout=json.dumps(example()),stderr='')
    monkeypatch.setattr(w,'ssh_command',lambda **kwargs:['ssh','stub','ps'])
    monkeypatch.setattr(w,'subprocess',SimpleNamespace(run=run,TimeoutExpired=subprocess.TimeoutExpired))
    args=SimpleNamespace(host='192.168.50.69',user='work',identity_file=Path('/a'),known_hosts=Path('/b'))
    _,s=w.source_check()
    r=w.remote_inspect(args,s)
    assert r['state']==w.INERT and w.RECEIPT_SHA in seen['input']
    assert '__TASK_ID__' not in seen['input']


def test_source_cli_only(capsys):
    assert w.main(['--mode','source-check'])==0
    assert 'SOURCE_CHECK_PASS' in capsys.readouterr().out
    assert w.main(['--mode','source-check','--host','192.168.50.69'])==2


def test_unsupported_or_ambiguous_host_rejected():
    assert w.main(['--mode','check','--host','anywhere','--user','work',
                   '--identity-file','/a','--known-hosts','/b'])==2


def test_check_requires_all_transport_args():
    assert w.main(['--mode','check','--host','192.168.50.69','--user','work'])==2


def test_zero_byte_partial_marker_requires_reconciliation():
    d=example(('execution_started',)); d['artifacts']['execution_started']['bytes']=0
    assert w.validate_report(json.dumps(d))['state']==w.FENCED

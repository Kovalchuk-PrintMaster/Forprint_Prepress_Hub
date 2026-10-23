"""Synthetic offline regression/negative tests: no Windows execution."""
from __future__ import annotations

import copy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / 'scripts/graphic_design_lab/worker_runtime'
sys.path.insert(0,str(D))
import gdl_w27c3e_recovery_decision_engine_v0_1 as e
from gdl_w27c3d_live_attempt_inspector_v0_1 import validate_report, INERT, FENCED

EMPTY = {'bytes':None,'present':False,'sha256':None}
PRESENT = {'bytes':0,'present':True,'sha256':sha256(b'').hexdigest()}


def example() -> dict:
    return {
        'accepted':False, 'archive_bytes':5120, 'archive_sha256':e.PACKAGE_SHA,
        'artifacts':{key:dict(EMPTY) for key in
                     ('execution_started','jsx','native_ai','start_claim','worker_result')},
        'attempt_id':e.ATTEMPT, 'cleanup_executed':False,
        'client_files_touched':False, 'com_attach_performed':False,
        'dispatch_authorized':False, 'execution_evidence_present':False,
        'host':'PREPRESS', 'jsx_executed_by_inspector':False,
        'live_observation':True, 'no_rerun_authorized':True,
        'production_ready':False, 'scheduler_mutation':False,
        'schema_version':'gdl_w27c3d_live_attempt_inspection_v0_1',
        'smb_mutation':False,'staging_receipt_sha256':e.RECEIPT_SHA,
        'state':INERT,'task_id':e.TASK,'windows_account':r'PREPRESS\Work',
        'windows_mutation':False,'worker_launch_authorized':False,
    }


def make_fenced(kind='start_claim') -> dict:
    doc=example()
    doc['artifacts'][kind]=dict(PRESENT)
    doc['execution_evidence_present']=True
    doc['state']=FENCED
    return doc


def persisted(tmp_path:Path,doc:dict, tail=True):
    folder=tmp_path/'captures'
    folder.mkdir(exist_ok=True)
    p=folder/'observation.txt'
    p.write_text(json.dumps(doc)+'\n'+('GDL_W27C3D_LIVE_ATTEMPT='+doc['state'] if tail else '')+'\n')
    return p


def assert_denied(doc:dict):
    assert doc['retry_authorized'] is False
    assert doc['worker_launch_authorized'] is False
    assert doc['dispatch_authorized'] is False
    assert doc['new_attempt_authorized'] is False
    assert doc['accepted'] is False
    assert doc['production_ready'] is False
    assert doc['fencing_released'] is False
    assert doc['observation_freshness_proven_now'] is False
    assert doc['windows_mutation'] is False
    assert doc['network_probe_performed'] is False


def test_source_contract():
    assert e.source_check()['task_id']==e.TASK


def test_source_cli(capsys):
    assert e.main(['--mode','source-check'])==0
    assert 'SOURCE_CHECK_PASS' in capsys.readouterr().out


def test_source_arguments_rejected(capsys):
    assert e.main(['--mode','source-check','--incident','SSH_LOSS'])==2


def test_exact_c3d_validator():
    assert validate_report(json.dumps(example()))['state']==INERT


@pytest.mark.parametrize('kind', ['start_claim','execution_started','jsx','native_ai','worker_result'])
def test_zero_length_evidence_fences(kind):
    doc=make_fenced(kind)
    result=e.decide('NONE',doc,'a'*64)
    assert result['state']=='EXISTING_EXECUTION_EVIDENCE_RECONCILIATION_REQUIRED'
    assert result['execution_evidence_present'] is True
    assert_denied(result)


@pytest.mark.parametrize('incident,state,decision',[
    ('NONE','INERT_STAGED_SNAPSHOT_NO_EXECUTION_OR_LAUNCH_AUTHORITY','DO_NOT_RERUN'),
    ('SSH_LOSS','TRANSPORT_INTERRUPTION_REQUIRES_NEW_LIVE_OBSERVATION','MANUAL_REVIEW'),
    ('HOST_REBOOT','HOST_REBOOT_RECONCILIATION_REQUIRED','MANUAL_REVIEW'),
    ('SCHEDULER_RC0_WITHOUT_VALID_RESULT','RC0_WITHOUT_VALID_RESULT_RECONCILIATION_REQUIRED','MANUAL_REVIEW'),
    ('PARTIAL_WRITE','UNCERTAIN_EXECUTION_RECONCILIATION_REQUIRED','MANUAL_REVIEW'),
    ('WORKER_RC_NONZERO','UNCERTAIN_EXECUTION_RECONCILIATION_REQUIRED','MANUAL_REVIEW'),
    ('UNKNOWN_PROCESS_EXIT','UNCERTAIN_EXECUTION_RECONCILIATION_REQUIRED','MANUAL_REVIEW'),
])
def test_inert_incident_matrix(incident,state,decision):
    result=e.decide(incident,example(),'a'*64)
    assert result['state']==state
    assert result['recovery_decision']==decision
    assert result['source_snapshot_not_current_authority'] is True
    assert_denied(result)


@pytest.mark.parametrize('incident',e.INCIDENTS)
def test_fenced_overrides_all_incidents(incident):
    result=e.decide(incident,make_fenced(),'a'*64)
    assert result['state']=='EXISTING_EXECUTION_EVIDENCE_RECONCILIATION_REQUIRED'
    assert_denied(result)


@pytest.mark.parametrize('incident',e.INCIDENTS[1:])
def test_no_live_capture_never_green(incident):
    result=e.decide(incident,None)
    assert result['state']=='STATE_UNOBSERVED_RECONCILIATION_REQUIRED'
    assert result['capture_sha256'] is None
    assert_denied(result)


def test_missing_capture_and_none_incident_rejected():
    with pytest.raises(e.RecoveryBlocked): e.decide('NONE',None)


def test_capture_digest_mismatch_type_rejected():
    with pytest.raises(e.RecoveryBlocked): e.decide('NONE',example(),'short')


@pytest.mark.parametrize('field,value',[
    ('task_id','gdl-other'),('attempt_id','a9999'),('archive_sha256','a'*64),
    ('staging_receipt_sha256','f'*64),('windows_account','PREPRESS\\Admin'),
    ('worker_launch_authorized',True),('live_observation',False),('accepted',True),
    ('dispatch_authorized',True),('windows_mutation',True),('cleanup_executed',True),
    ('no_rerun_authorized',False),('state',FENCED),
])
def test_tamper_c3d_capture_rejected(field,value):
    x=example();x[field]=value
    with pytest.raises(e.RecoveryBlocked):e.decide('NONE',x,'a'*64)


def test_inconsistent_evidence_presence_rejected():
    x=example(); x['artifacts']['start_claim']=dict(PRESENT)
    with pytest.raises(e.RecoveryBlocked):e.decide('NONE',x,'a'*64)


def test_extra_fields_rejected():
    x=example();x['permit_execution']=True
    with pytest.raises(e.RecoveryBlocked):e.decide('NONE',x,'a'*64)


def test_bogus_incident_rejected():
    with pytest.raises(e.RecoveryBlocked):e.decide('RETRY',example(),'a'*64)


def test_capture_path_tmp_scope(tmp_path,monkeypatch):
    monkeypatch.setattr(e,'ROOT',tmp_path)
    (tmp_path/'tmp').mkdir()
    path=tmp_path/'tmp'/'captures'/'observation.txt'
    assert e.read_capture(persisted(tmp_path/'tmp',example()))[0]['state']==INERT
    assert e.capture_path(path)==path


def test_capture_no_status_marker(tmp_path,monkeypatch):
    monkeypatch.setattr(e,'ROOT',tmp_path)
    (tmp_path/'tmp').mkdir()
    assert e.read_capture(persisted(tmp_path/'tmp',example(),False))[0]['state']==INERT


def test_capture_extraneous_marker_rejected(tmp_path,monkeypatch):
    monkeypatch.setattr(e,'ROOT',tmp_path)
    (tmp_path/'tmp').mkdir()
    p=persisted(tmp_path/'tmp',example())
    p.write_text(p.read_text()+'\nGDL_W27C3D_READONLY_CHECK=COMPLETE\n')
    with pytest.raises(e.RecoveryBlocked):e.read_capture(p)


def test_capture_mismatch_status_marker(tmp_path,monkeypatch):
    monkeypatch.setattr(e,'ROOT',tmp_path)
    (tmp_path/'tmp').mkdir()
    p=persisted(tmp_path/'tmp',example())
    p.write_text(p.read_text().replace(INERT,FENCED))
    with pytest.raises(e.RecoveryBlocked):e.read_capture(p)


def test_duplicate_json_key_rejected(tmp_path,monkeypatch):
    monkeypatch.setattr(e,'ROOT',tmp_path)
    (tmp_path/'tmp').mkdir()
    p=persisted(tmp_path/'tmp',example(),False)
    original=p.read_text().strip()
    p.write_text(original[:-1]+',"accepted":true}')
    with pytest.raises(e.RecoveryBlocked):e.read_capture(p)


@pytest.mark.parametrize('unsafe', ['../escape.txt','observation.json','captures/../other.txt','captures/deep/obs.txt'])
def test_capture_wrong_shape_rejected(unsafe,tmp_path,monkeypatch):
    monkeypatch.setattr(e,'ROOT',tmp_path)
    (tmp_path/'tmp').mkdir()
    with pytest.raises(e.RecoveryBlocked):e.capture_path(tmp_path/'tmp'/unsafe)


def test_capture_symlink_rejected(tmp_path,monkeypatch):
    monkeypatch.setattr(e,'ROOT',tmp_path)
    (tmp_path/'tmp').mkdir()
    p=persisted(tmp_path/'tmp',example())
    l=p.with_name('symlink.txt'); l.symlink_to(p)
    with pytest.raises(e.RecoveryBlocked):e.read_capture(l)


def test_capture_directory_symlink_rejected(tmp_path,monkeypatch):
    monkeypatch.setattr(e,'ROOT',tmp_path)
    (tmp_path/'tmp').mkdir()
    p=persisted(tmp_path/'tmp',example())
    (tmp_path/'tmp'/'link').symlink_to(p.parent,target_is_directory=True)
    with pytest.raises(e.RecoveryBlocked):e.read_capture(tmp_path/'tmp'/'link'/'observation.txt')


def test_cli_incident_rc0_without_capture(capsys):
    assert e.main(['--mode','incident','--incident','SCHEDULER_RC0_WITHOUT_VALID_RESULT'])==0
    obj=capsys.readouterr().out
    assert 'STATE_UNOBSERVED_RECONCILIATION_REQUIRED' in obj
    assert '"retry_authorized": false' in obj


def test_cli_incident_none_rejected(capsys):
    assert e.main(['--mode','incident'])==2


def test_cli_evaluate_without_capture_rejected(capsys):
    assert e.main(['--mode','evaluate'])==2


def test_cli_evaluate_capture_valid(tmp_path,monkeypatch,capsys):
    monkeypatch.setattr(e,'ROOT',tmp_path)
    (tmp_path/'tmp').mkdir()
    p=persisted(tmp_path/'tmp',example())
    assert e.main(['--mode','evaluate','--capture',str(p)])==0
    result=capsys.readouterr().out
    assert 'INERT_STAGED_SNAPSHOT_NO_EXECUTION_OR_LAUNCH_AUTHORITY' in result
    assert '"retry_authorized": false' in result


def test_capture_size_limit_rejected(tmp_path,monkeypatch):
    monkeypatch.setattr(e,'ROOT',tmp_path)
    (tmp_path/'tmp').mkdir()
    p=persisted(tmp_path/'tmp',example(),False)
    p.write_bytes(p.read_bytes()+b' '*33000)
    with pytest.raises(e.RecoveryBlocked):e.read_capture(p)


def test_capture_hash_binds_original_bytes(tmp_path,monkeypatch):
    monkeypatch.setattr(e,'ROOT',tmp_path)
    (tmp_path/'tmp').mkdir()
    p=persisted(tmp_path/'tmp',example())
    _,digest=e.read_capture(p)
    assert digest==sha256(p.read_bytes()).hexdigest()


def test_result_is_json_serializable_and_no_secret_data():
    r=e.decide('NONE',example(),'a'*64)
    text=json.dumps(r)
    assert 'PREPRESS\\\\Work' not in text
    assert 'C:\\' not in text
    assert len(text)<4000

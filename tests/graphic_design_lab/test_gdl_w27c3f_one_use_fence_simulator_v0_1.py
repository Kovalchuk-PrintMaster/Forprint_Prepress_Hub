"""C3F: fail-closed offline atomic claim prototype; NEVER Windows/COM/dispatch."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import copy
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/graphic_design_lab/worker_runtime'))
import gdl_w27c3f_one_use_fence_simulator_v0_1 as f
import gdl_w27c3e_recovery_decision_engine_v0_1 as e
from gdl_w27c3d_live_attempt_inspector_v0_1 import INERT,FENCED

DIGEST='a'*64
ABSENT={'present':False,'bytes':None,'sha256':None}
PRESENT={'present':True,'bytes':0,'sha256':sha256(b'').hexdigest()}
NAMES=('start_claim','execution_started','jsx','native_ai','worker_result')


def observation(kind=None):
    doc={
        'accepted':False,'archive_bytes':5120,'archive_sha256':f.PACKAGE_SHA,
        'artifacts':{n:dict(ABSENT) for n in NAMES},'attempt_id':f.ATTEMPT,
        'cleanup_executed':False,'client_files_touched':False,'com_attach_performed':False,
        'dispatch_authorized':False,'execution_evidence_present':False,
        'host':'PREPRESS','jsx_executed_by_inspector':False,'live_observation':True,
        'no_rerun_authorized':True,'production_ready':False,'scheduler_mutation':False,
        'schema_version':'gdl_w27c3d_live_attempt_inspection_v0_1',
        'smb_mutation':False,'staging_receipt_sha256':f.RECEIPT_SHA,
        'state':INERT,'task_id':f.TASK,'windows_account':r'PREPRESS\Work',
        'windows_mutation':False,'worker_launch_authorized':False,
    }
    if kind:
        doc['artifacts'][kind]=dict(PRESENT)
        doc['execution_evidence_present']=True
        doc['state']=FENCED
    return doc


@pytest.fixture
def sandbox(tmp_path,monkeypatch):
    (tmp_path/'tmp').mkdir()
    (tmp_path/'tmp'/'fencepilot').mkdir()
    monkeypatch.setattr(f,'ROOT',tmp_path)
    monkeypatch.setattr(e,'ROOT',tmp_path)
    return tmp_path/'tmp'/'fencepilot'/'fence_simulation.json'


def denied(doc):
    for k in ('execution_authorized','dispatch_authorized','retry_authorized',
              'fencing_released','accepted','production_ready','windows_write',
              'live_freshness_proven','cleanup_executed'):
        assert doc[k] is False,k
    assert doc['simulation_only'] is True


def test_source_contract():
    assert f.source_check()['task_id']==f.TASK
    assert f.source_check()['windows_write'] is False


def test_cli_source_check(capsys):
    assert f.main(['--mode','source-check'])==0
    assert 'SOURCE_CHECK_PASS' in capsys.readouterr().out


@pytest.mark.parametrize('incident',e.INCIDENTS)
def test_recovery_incidents_cannot_grant_execution(incident):
    doc=f.projection(incident,observation(),DIGEST)
    denied(doc)
    if incident=='NONE':
        assert doc['state']=='INERT_SNAPSHOT_SIMULATION_ELIGIBLE_ONLY'
    else:
        assert doc['state']=='RECOVERY_INCIDENT_BLOCKS_FENCE_SIMULATION'


@pytest.mark.parametrize('incident',e.INCIDENTS)
@pytest.mark.parametrize('kind',NAMES)
def test_any_execution_evidence_blocks_local_simulation(incident,kind):
    doc=f.projection(incident,observation(kind),DIGEST)
    denied(doc)
    assert doc['state']=='RECOVERY_INCIDENT_BLOCKS_FENCE_SIMULATION'


def test_missing_observation_only_incident_allowed():
    doc=f.projection('HOST_REBOOT',None,None)
    denied(doc)
    assert doc['state']=='RECOVERY_INCIDENT_BLOCKS_FENCE_SIMULATION'
    with pytest.raises(f.FenceBlocked):f.projection('NONE',None,None)


def test_claim_creation_and_inspection(sandbox):
    claim=f.build_claim(DIGEST)
    digest=f.create_once(sandbox,claim)
    assert sandbox.is_file()
    assert sandbox.stat().st_mode & 0o777==0o600
    read,actual=f.inspect(sandbox)
    assert read==claim and actual==digest
    doc=f.projection('NONE',observation(),DIGEST,read,actual)
    denied(doc)
    assert doc['state']=='SIMULATED_CLAIM_EXISTS_FENCED_MANUAL_REVIEW'
    with pytest.raises(f.FenceBlocked):f.create_once(sandbox,claim)


def test_claim_race_one_winner(sandbox):
    claim=f.build_claim(DIGEST)
    def attempt(_):
        try:return f.create_once(sandbox,claim)
        except f.FenceBlocked:return None
    with ThreadPoolExecutor(max_workers=16) as pool:
        hashes=list(pool.map(attempt,range(40)))
    assert sum(bool(x) for x in hashes)==1
    assert f.inspect(sandbox)[1]==next(x for x in hashes if x)


def test_claim_empty_after_crash_is_fence(sandbox):
    sandbox.touch()
    with pytest.raises(f.FenceBlocked,match='partial|empty'):
        f.inspect(sandbox)
    with pytest.raises(f.FenceBlocked):f.create_once(sandbox,f.build_claim(DIGEST))
    assert sandbox.exists()


@pytest.mark.parametrize('payload',[b'',b'{}',b'{invalid',b'abc',b' '*8193,b'[]',b'{"state":"hi"}'])
def test_partial_and_invalid_existing_claim_blocks_and_persists(sandbox,payload):
    sandbox.write_bytes(payload)
    with pytest.raises(f.FenceBlocked):f.inspect(sandbox)
    with pytest.raises(f.FenceBlocked):f.create_once(sandbox,f.build_claim(DIGEST))
    assert sandbox.read_bytes()==payload


@pytest.mark.parametrize('key,value',[
    ('task_id','gdl-other-task'),('attempt_id','a9999'),
    ('package_sha256','e'*64),('jsx_sha256','d'*64),
    ('staging_receipt_sha256','f'*64),('source_capture_sha256','bad'),
    ('simulation_only',False),('windows_write',True),
    ('worker_launch_authorized',True),('dispatch_authorized',True),
    ('retry_authorized',True),('accepted',True),('production_ready',True),
    ('cleanup_executed',True),('state','AUTHORIZED_TO_RUN'),
    ('schema_version','wrong')])
def test_mutated_claim_always_rejected(sandbox,key,value):
    claim=f.build_claim(DIGEST)
    claim[key]=value
    sandbox.write_bytes(f.canonical(claim))
    with pytest.raises(f.FenceBlocked):f.inspect(sandbox)
    assert sandbox.exists()


def test_duplicate_fields_denied(sandbox):
    raw=b'{"task_id":"x","task_id":"y"}'
    sandbox.write_bytes(raw)
    with pytest.raises(f.FenceBlocked):f.inspect(sandbox)


@pytest.mark.parametrize('suffix',[b' ',b'\n',b'\x00'])
def test_noncanonical_bytes_rejected(sandbox,suffix):
    sandbox.write_bytes(f.canonical(f.build_claim(DIGEST))+suffix)
    with pytest.raises(f.FenceBlocked):f.inspect(sandbox)


def test_wrong_capture_claim_never_matches(sandbox):
    sha=f.create_once(sandbox,f.build_claim(DIGEST))
    claim,_=f.inspect(sandbox)
    with pytest.raises(f.FenceBlocked):
        f.projection('NONE',observation(),'b'*64,claim,sha)


def test_claim_digest_missing_rejected():
    with pytest.raises(f.FenceBlocked):f.build_claim('not sha')
    with pytest.raises(f.FenceBlocked):f.build_claim(None)


def test_claim_policy_direct_input_rejected(sandbox):
    claim=f.build_claim(DIGEST)
    claim['worker_launch_authorized']=True
    with pytest.raises(f.FenceBlocked):f.create_once(sandbox,claim)
    assert not sandbox.exists()


@pytest.mark.parametrize('location',[
    'tmp/fencepilot/other.json','tmp/../fencepilot/fence_simulation.json',
    'outside/fence_simulation.json','tmp/fencepilot/nested/fence_simulation.json',
    'tmp/.hidden/fence_simulation.json','tmp/x/fence_simulation.json',
])
def test_invalid_paths_denied(sandbox,location):
    with pytest.raises(f.FenceBlocked):f.location(Path(location),must_exist=False)


def test_symlinked_parent_rejected(sandbox):
    other=sandbox.parent.parent/'actual'
    other.mkdir()
    fake=sandbox.parent.parent/'imitation'
    fake.symlink_to(other,target_is_directory=True)
    with pytest.raises(f.FenceBlocked):
        f.location(fake/f.NAME,must_exist=False)


def test_symlinked_claim_rejected(sandbox):
    target=sandbox.parent/'target.txt'
    target.write_text('no')
    sandbox.symlink_to(target)
    with pytest.raises(f.FenceBlocked):f.inspect(sandbox)
    with pytest.raises(f.FenceBlocked):f.create_once(sandbox,f.build_claim(DIGEST))


def test_dir_as_claim_rejected(sandbox):
    sandbox.mkdir()
    with pytest.raises(f.FenceBlocked):f.inspect(sandbox)
    with pytest.raises(f.FenceBlocked):f.create_once(sandbox,f.build_claim(DIGEST))


def test_c3e_capture_end_to_end(sandbox,monkeypatch,capsys):
    cap=sandbox.parent/'live_inspection.txt'
    x=observation()
    cap.write_text(json.dumps(x)+'\nGDL_W27C3D_LIVE_ATTEMPT='+x['state']+'\n')
    name='tmp/fencepilot/live_inspection.txt'
    claim='tmp/fencepilot/fence_simulation.json'
    assert f.main(['--mode','assess','--capture',name])==0
    assert 'INERT_SNAPSHOT_SIMULATION_ELIGIBLE_ONLY' in capsys.readouterr().out
    assert f.main(['--mode','simulate-create','--capture',name,'--simulation',claim,
                   '--confirm-local-simulation'])==0
    assert sandbox.is_file()
    assert 'FENCED_MANUAL_REVIEW' in capsys.readouterr().out
    assert f.main(['--mode','inspect-simulation','--capture',name,'--simulation',claim])==0
    assert 'SIMULATED_CLAIM_EXISTS_FENCED_MANUAL_REVIEW' in capsys.readouterr().out
    assert f.main(['--mode','simulate-create','--capture',name,'--simulation',claim,
                   '--confirm-local-simulation'])==2
    assert sandbox.is_file()


def test_unsafe_cli_argument_combinations(sandbox,capsys):
    assert f.main(['--mode','source-check','--confirm-local-simulation'])==2
    assert f.main(['--mode','assess'])==2
    assert f.main(['--mode','inspect-simulation'])==2


def test_incident_simulation_disallowed_even_with_confirmation(sandbox,capsys):
    cap=sandbox.parent/'live_inspection.txt'
    x=observation()
    cap.write_text(json.dumps(x))
    assert f.main(['--mode','simulate-create','--capture',str(cap),
                   '--simulation',str(sandbox),'--incident','HOST_REBOOT',
                   '--confirm-local-simulation'])==2
    assert not sandbox.exists()


def test_corrupt_evidence_rejected_before_simulation(sandbox,capsys):
    cap=sandbox.parent/'live_inspection.txt'
    x=observation();x['dispatch_authorized']=True
    cap.write_text(json.dumps(x))
    assert f.main(['--mode','simulate-create','--capture',str(cap),
                   '--simulation',str(sandbox),'--confirm-local-simulation'])==2
    assert not sandbox.exists()


def test_claim_contains_no_dispatch_grant():
    claim=f.build_claim(DIGEST)
    assert all(claim[x] is False for x in ['worker_launch_authorized',
        'dispatch_authorized','retry_authorized','accepted','production_ready'])
    assert 'start_claim.json' not in f.canonical(claim).decode('ascii')

"""C3I uses existing C3H/C3F verifiers and never grants authority."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / 'scripts/graphic_design_lab/worker_runtime'
sys.path.insert(0, str(SCRIPTS))
import gdl_w27c3i_closeout_readiness_v0_1 as i
import gdl_w27c3h_worker_return_handoff_v0_1 as h
import gdl_w27c3f_one_use_fence_simulator_v0_1 as f
import gdl_w27c3d_live_attempt_inspector_v0_1 as d
import gdl_w27c3g_windows_fence_probe_v0_1 as g


def observation(present=()):
    return dict(schema_version=d.REPORT_SCHEMA,
      state=d.FENCED if present else d.INERT,
      task_id=d.TASK, attempt_id=d.ATTEMPT, host='PREPRESS',
      windows_account=r'PREPRESS\Work', archive_sha256=d.PACKAGE_SHA,
      archive_bytes=d.ARCHIVE_BYTES, staging_receipt_sha256=d.RECEIPT_SHA,
      artifacts={name:{'present':name in present,
                       'bytes':10 if name in present else None,
                       'sha256':'a'*64 if name in present else None}
                 for name in d.EVIDENCE},
      execution_evidence_present=bool(present), live_observation=True,
      no_rerun_authorized=True, worker_launch_authorized=False,
      dispatch_authorized=False, production_ready=False, accepted=False,
      windows_mutation=False, jsx_executed_by_inspector=False,
      com_attach_performed=False, scheduler_mutation=False,
      cleanup_executed=False, client_files_touched=False, smb_mutation=False)


def proof(mode, claim='b'*64):
    return dict(schema_version=g.REPORT, mode=mode, state=g.STATES[mode],
      host='PREPRESS', windows_account=r'PREPRESS\Work', task_id=g.TASK,
      attempt_id=g.ATTEMPT, native_task_id=g.NATIVE_TASK,
      native_attempt_id=g.NATIVE_ATTEMPT,
      native_package_sha256=g.PACKAGE_SHA, native_receipt_sha256=g.RECEIPT_SHA,
      claim_sha256=claim, windows_mutation=mode=='probe',
      duplicate_create_denied=mode!='check', com_attach_performed=False,
      jsx_execution=False, runner_execution=False, scheduler_mutated=False,
      dispatch_authorized=False, execution_authorized=False,
      retry_authorized=False, production_ready=False, accepted=False,
      client_files_touched=False, smb_mutation=False, cleanup_executed=False)


def save(path, obj, marker):
    path.write_text(json.dumps(obj,sort_keys=True)+'\n'+marker+'\n',encoding='utf-8')


@pytest.fixture
def evidence():
    with TemporaryDirectory(prefix='w27c3i_case_',dir=i.ROOT/'tmp') as name:
        folder = Path(name)
        cap, p, v = (folder/x for x in ('capture.txt','probe.txt','verify.txt'))
        save(cap, observation(), 'GDL_W27C3D_LIVE_ATTEMPT='+d.INERT)
        save(p, proof('probe'), 'GDL_W27C3G_WINDOWS_FENCE='+h.PROBE_STATE)
        save(v, proof('verify'), 'GDL_W27C3G_WINDOWS_FENCE='+h.VERIFY_STATE)
        simulation = folder/'fence_simulation.json'
        yield folder, cap, p, v, simulation


def assert_safety(doc):
    assert doc['accepted'] is False
    assert doc['dispatch_authorized'] is False
    assert doc['worker_launch_authorized'] is False
    assert doc['retry_authorized'] is False
    assert doc['native_closeout_completed'] is False
    assert doc['production_ready'] is False
    assert doc['windows_write'] is False
    assert doc['ssh_used'] is False
    assert doc['cleanup_executed'] is False
    assert doc['real_execution_fence_verified'] is False
    assert doc['fresh_dispatch_readiness_proven'] is False
    assert doc['blueprint_review_deferred_not_waived'] is True
    assert 'INDEPENDENT_EXECUTION_AUTHORITY' in doc['blocking_gate_ids']
    assert 'OWNER_TECHNICAL_CLOSEOUT' in doc['blocking_gate_ids']
    assert 'SINGLE_DISPATCH_OWNER_AND_ACTION' in doc['blocking_gate_ids']
    assert doc['blocking_gate_count'] == len(doc['blocking_gate_ids'])


def test_source_check():
    assert i.source_check()['mode'] == 'INDEPENDENT_READ_ONLY_GATE_ATLAS'


@pytest.mark.parametrize('field,value', [
    ('task_id','invalid'),('attempt_id','a0002'),
    ('package_sha256','a'*64),('staging_receipt_sha256','f'*64),
    ('source_handoff_schema','bad'),('source_local_fence_schema','bad'),
    ('mode','LAUNCH'),('pilot_scope','PRODUCTION'),('state','READY'),
    ('authority_issued',True),('dispatcher_owner_approved',True),
    ('real_attempt_claim_created',True),('native_execution_independently_proven',True),
    ('editability_independently_proven',True),('operator_acceptance_recorded',True),
    ('realtime_readiness_proven',True),('launch_enabled',True),
    ('retry_enabled',True),('cleanup_enabled',True),('production_ready',True),
    ('windows_write',True),('ssh_used',True),
    ('blueprint_review_deferred_not_waived',False)
])
def test_authority_mutation_fails(tmp_path,monkeypatch,field,value):
    doc=json.loads(i.CONTRACT.read_text());doc[field]=value
    tmp=tmp_path/'contract.json';tmp.write_text(json.dumps(doc))
    monkeypatch.setattr(i,'CONTRACT',tmp)
    with pytest.raises(i.ReadinessBlocked): i.source_check()


def test_contract_extra_field_fails(tmp_path,monkeypatch):
    doc=json.loads(i.CONTRACT.read_text());doc['run_authorized']=True
    tmp=tmp_path/'contract.json';tmp.write_text(json.dumps(doc))
    monkeypatch.setattr(i,'CONTRACT',tmp)
    with pytest.raises(i.ReadinessBlocked): i.source_check()


def test_duplicate_contract_fields_fail(tmp_path,monkeypatch):
    raw=i.CONTRACT.read_text()
    tmp=tmp_path/'duplicate.json';tmp.write_text(raw.replace('"mode":', '"mode":"LAUNCH", "mode":'))
    monkeypatch.setattr(i,'CONTRACT',tmp)
    with pytest.raises(i.ReadinessBlocked): i.source_check()


def test_contract_symlink_fails(tmp_path,monkeypatch):
    link=tmp_path/'link';link.symlink_to(i.CONTRACT)
    monkeypatch.setattr(i,'CONTRACT',link)
    with pytest.raises(i.ReadinessBlocked): i.source_check()


def test_inert_handoff_without_simulation(evidence):
    _,cap,p,v,_=evidence
    doc=i.review(cap,p,v,'NONE')
    assert doc['state']=='TECHNICAL_FOUNDATIONS_RECONCILED_AUTHORITY_BLOCKED'
    assert doc['local_simulation_claim_sha256'] is None
    gate={x['id']:x for x in doc['gates']}
    assert gate['C3F_LINUX_ATOMIC_CLAIM']['status']=='SOURCE_CONTRACT_ONLY'
    assert gate['NATIVE_RESULT_AND_AI_RETURN']['status']=='ABSENT'
    assert_safety(doc)


def test_with_preexisting_local_simulation(evidence):
    _,cap,p,v,path=evidence
    _,capture_digest=f.read_capture(cap)
    expected=f.create_once(path, f.build_claim(capture_digest))
    doc=i.review(cap,p,v,'NONE',path)
    assert doc['local_simulation_claim_sha256']==expected
    gate={x['id']:x for x in doc['gates']}
    assert gate['C3F_LINUX_ATOMIC_CLAIM']['status']=='OFFLINE_SIMULATION_VERIFIED'
    assert_safety(doc)


def test_duplicate_claim_does_not_get_recreated(evidence):
    _,cap,p,v,path=evidence
    _,cd=f.read_capture(cap)
    f.create_once(path,f.build_claim(cd))
    before=path.read_bytes()
    i.review(cap,p,v,'NONE',path)
    assert path.read_bytes()==before
    with pytest.raises(f.FenceBlocked): f.create_once(path,f.build_claim(cd))


def test_bad_local_simulation_fails(evidence):
    _,cap,p,v,path=evidence
    path.write_text('{}')
    with pytest.raises(f.FenceBlocked):i.review(cap,p,v,'NONE',path)


def test_foreign_capture_fails_with_old_claim(evidence):
    _,cap,p,v,path=evidence
    _,cd=f.read_capture(cap);f.create_once(path,f.build_claim(cd))
    save(cap,observation(['start_claim']), 'GDL_W27C3D_LIVE_ATTEMPT='+d.FENCED)
    with pytest.raises((i.ReadinessBlocked,f.FenceBlocked)):i.review(cap,p,v,'NONE',path)


@pytest.mark.parametrize('incident', sorted(x for x in f.INCIDENTS if x!='NONE'))
def test_incident_fails_closed(evidence,incident):
    _,cap,p,v,_=evidence
    doc=i.review(cap,p,v,incident)
    assert doc['state']=='INCIDENT_STATE_STALE_REINSPECTION_REQUIRED'
    assert_safety(doc)


def test_execution_evidence_without_native_return_blocks_closeout(evidence):
    _,cap,p,v,_=evidence
    save(cap,observation(['start_claim']),'GDL_W27C3D_LIVE_ATTEMPT='+d.FENCED)
    doc=i.review(cap,p,v,'NONE')
    assert doc['state']=='EXECUTION_EVIDENCE_PRESENT_MANUAL_RECONCILIATION'
    assert_safety(doc)


def test_tampered_probe_fails(evidence):
    _,cap,p,v,_=evidence
    bad=proof('probe');bad['dispatch_authorized']=True
    save(p,bad,'GDL_W27C3G_WINDOWS_FENCE='+h.PROBE_STATE)
    with pytest.raises(h.HandoffBlocked):i.review(cap,p,v,'NONE')


def test_mismatched_probe_sha_fails(evidence):
    _,cap,p,v,_=evidence
    save(v,proof('verify',claim='f'*64),'GDL_W27C3G_WINDOWS_FENCE='+h.VERIFY_STATE)
    with pytest.raises(h.HandoffBlocked):i.review(cap,p,v,'NONE')


def test_bad_C3H_authorization_projection_blocks():
    hdoc={
      'schema_version':'gdl_w27c3h_worker_return_handoff_v0_1',
      'task_id':i.TASK,'attempt_id':i.ATTEMPT,
      'package_sha256':i.PACKAGE,'staging_receipt_sha256':i.RECEIPT,
      'execution_authorized':True,
    }
    with pytest.raises(i.ReadinessBlocked):i.atlas(hdoc)


def test_unknown_C3H_state_fails(evidence):
    _,cap,p,v,_=evidence
    doc=h.review(cap,p,v,'NONE')
    doc['state']='SHOULD_EXECUTE'
    with pytest.raises(i.ReadinessBlocked):i.atlas(doc)


def test_missing_C3H_schema_fails():
    with pytest.raises(i.ReadinessBlocked):i.atlas({'state':'anything'})


def test_cli_source_check_no_args(capsys):
    assert i.main(['--mode','source-check'])==0
    assert 'SOURCE_CHECK_PASS' in capsys.readouterr().out


def test_cli_source_check_rejects_path(evidence,capsys):
    _,cap,_,_,_=evidence
    assert i.main(['--mode','source-check','--capture',str(cap)])==2
    assert 'BLOCKED' in capsys.readouterr().err


def test_cli_review_inert(evidence,capsys):
    _,cap,p,v,path=evidence
    assert i.main(['--mode','review','--capture',str(cap),'--probe',str(p),
                   '--verify',str(v)])==0
    assert 'TECHNICAL_FOUNDATIONS_RECONCILED_AUTHORITY_BLOCKED' in capsys.readouterr().out


def test_cli_review_missing_capture(capsys):
    assert i.main(['--mode','review'])==2
    assert 'BLOCKED' in capsys.readouterr().err


def test_partial_return_rejected(evidence):
    _,cap,p,v,_=evidence
    with pytest.raises(h.HandoffBlocked):
        i.review(cap,p,v,'NONE',result=Path('somewhere'))


def test_source_bound_to_existing_prerequisites(monkeypatch):
    def fail(): raise h.HandoffBlocked('broken parent source')
    monkeypatch.setattr(i,'h_source_check',fail)
    with pytest.raises(i.ReadinessBlocked): i.source_check()


def test_boolean_authority_cannot_be_injected_via_C3H(evidence,monkeypatch):
    _,cap,p,v,_=evidence
    original=i.h_review
    def malicious(*args,**kw):
        result=original(*args,**kw);result['owner_approval_recorded']=True;return result
    monkeypatch.setattr(i,'h_review',malicious)
    with pytest.raises(i.ReadinessBlocked):i.review(cap,p,v,'NONE')


def test_mock_return_bytes_never_imply_editable_ai_or_acceptance(evidence):
    # The bytes deliberately are NOT AI. C3B can verify only their SHA and report.
    from hashlib import sha256
    import gdl_w27c3b_native_worker_review_v0_1 as b
    folder, cap, p, v, _ = evidence
    native = b'%!PS-Adobe MOCK NONEDITABLE\n' + b'X'*2048
    path_ai = folder/'native_result.ai'; path_ai.write_bytes(native)
    result = dict(schema_version=b.RESULT_SCHEMA,state='NATIVE_AI_REOPENED_LOCAL',
        task_id=b.TASK,attempt_id=b.ATTEMPT,host='PREPRESS',
        windows_account=r'PREPRESS\Work',package_sha256=b.PACKAGE_SHA,
        jsx_sha256=b.JSX_SHA,runner_sha256=b.EXPECTED_RUNNER_SHA,
        session_id=2,preexisting_illustrator_pid=1012,
        token_limited_verified=True,com_attach_performed=True,
        illustrator_executed=True,native_ai_saved_reopened=True,
        editable_area_text=True,native_ai_sha256=sha256(native).hexdigest(),
        native_ai_bytes=len(native),phase='DONE',error_code='NONE',
        independent_acceptance=False,execution_authority_review_pending=True,
        production_ready=False,accepted=False,client_files_touched=False,
        smb_mutation=False,cleanup_executed=False,automatic_retry=False)
    path_result=folder/'worker_result.json'
    path_result.write_text(json.dumps(result),encoding='utf-8')
    ai_sha=sha256(native).hexdigest()
    result_sha=sha256(path_result.read_bytes()).hexdigest()
    observed=observation(['start_claim','execution_started','jsx','native_ai','worker_result'])
    observed['artifacts']['native_ai']={'present':True,'bytes':len(native),'sha256':ai_sha}
    observed['artifacts']['worker_result']={
       'present':True,'bytes':path_result.stat().st_size,'sha256':result_sha}
    save(cap, observed, 'GDL_W27C3D_LIVE_ATTEMPT='+d.FENCED)
    doc=i.review(cap,p,v,'NONE',result=path_result,native_ai=path_ai,
                 expected_result_sha256=result_sha,expected_native_sha256=ai_sha)
    assert doc['state']=='NATIVE_RETURN_BYTES_VERIFIED_CLOSEOUT_BLOCKED'
    assert doc['local_simulation_only'] is True
    assert doc['native_closeout_completed'] is False
    assert_safety(doc)


def test_source_check_rejects_non_false_boolean_type(tmp_path,monkeypatch):
    config=json.loads(i.CONTRACT.read_text());config['launch_enabled']=0
    tmp=tmp_path/'contract.json';tmp.write_text(json.dumps(config))
    monkeypatch.setattr(i,'CONTRACT',tmp)
    with pytest.raises(i.ReadinessBlocked): i.source_check()

"""Offline fault-injection coverage for C3H: no SSH, COM or local authorization."""
import json
from hashlib import sha256
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import pytest

SCRIPTS = Path(__file__).resolve().parents[2]/'scripts/graphic_design_lab/worker_runtime'
sys.path.insert(0,str(SCRIPTS))
import gdl_w27c3h_worker_return_handoff_v0_1 as h
import gdl_w27c3b_native_worker_review_v0_1 as b
import gdl_w27c3d_live_attempt_inspector_v0_1 as d
import gdl_w27c3g_windows_fence_probe_v0_1 as g


def digest(raw): return sha256(raw).hexdigest()


def observation(present=(), values=None):
    values = values or {}
    items = {}
    for k in d.EVIDENCE:
        is_present = k in present
        size, hash_value = values.get(k,(10,'a'*64))
        items[k]={'present':is_present,
                  'bytes':size if is_present else None,
                  'sha256':hash_value if is_present else None}
    return dict(schema_version=d.REPORT_SCHEMA,
        state=d.FENCED if present else d.INERT,
        task_id=d.TASK,attempt_id=d.ATTEMPT,host='PREPRESS',
        windows_account=r'PREPRESS\Work',
        archive_sha256=d.PACKAGE_SHA, archive_bytes=d.ARCHIVE_BYTES,
        staging_receipt_sha256=d.RECEIPT_SHA,
        artifacts=items,execution_evidence_present=bool(present),
        live_observation=True,no_rerun_authorized=True,
        worker_launch_authorized=False, dispatch_authorized=False,
        production_ready=False, accepted=False, windows_mutation=False,
        jsx_executed_by_inspector=False,com_attach_performed=False,
        scheduler_mutation=False,cleanup_executed=False,
        client_files_touched=False,smb_mutation=False)


def proof(mode,claim='a'*64):
    return dict(schema_version=g.REPORT,mode=mode,state=g.STATES[mode],
        host='PREPRESS',windows_account=r'PREPRESS\Work',task_id=g.TASK,
        attempt_id=g.ATTEMPT,native_task_id=g.NATIVE_TASK,
        native_attempt_id=g.NATIVE_ATTEMPT,native_package_sha256=g.PACKAGE_SHA,
        native_receipt_sha256=g.RECEIPT_SHA,claim_sha256=claim,
        windows_mutation=mode=='probe',duplicate_create_denied=mode!='check',
        com_attach_performed=False,jsx_execution=False,runner_execution=False,
        scheduler_mutated=False,dispatch_authorized=False,
        execution_authorized=False,retry_authorized=False,
        production_ready=False,accepted=False,client_files_touched=False,
        smb_mutation=False,cleanup_executed=False)


def save(path,doc,marker):
    path.write_text(json.dumps(doc,sort_keys=True)+'\n'+marker+'\n',encoding='utf-8')


@pytest.fixture
def evidence():
    # Isolated direct repository tmp, like the actual user evidence directories.
    with TemporaryDirectory(prefix='w27c3h_case_',dir=h.ROOT/'tmp') as loc:
        folder=Path(loc)
        cap=folder/'capture.txt';p=folder/'probe.txt';v=folder/'verify.txt'
        save(cap,observation(),'GDL_W27C3D_LIVE_ATTEMPT='+d.INERT)
        save(p,proof('probe'),'GDL_W27C3G_WINDOWS_FENCE='+h.PROBE_STATE)
        save(v,proof('verify'),'GDL_W27C3G_WINDOWS_FENCE='+h.VERIFY_STATE)
        yield folder,cap,p,v


def result_mock(folder):
    # This is emphatically not a real AI; validates C3B file/schema bindings only.
    native=b'%!PS-Adobe synthetic MOCK NOT AI\n'+b'X'*2048
    result = dict(schema_version=b.RESULT_SCHEMA,state='NATIVE_AI_REOPENED_LOCAL',
        task_id=b.TASK,attempt_id=b.ATTEMPT,host='PREPRESS',
        windows_account=r'PREPRESS\Work',package_sha256=b.PACKAGE_SHA,
        jsx_sha256=b.JSX_SHA,runner_sha256=b.EXPECTED_RUNNER_SHA,
        session_id=2,preexisting_illustrator_pid=1012,
        token_limited_verified=True,com_attach_performed=True,
        illustrator_executed=True,native_ai_saved_reopened=True,
        editable_area_text=True,native_ai_sha256=digest(native),
        native_ai_bytes=len(native),phase='DONE',error_code='NONE',
        independent_acceptance=False,execution_authority_review_pending=True,
        production_ready=False,accepted=False,client_files_touched=False,
        smb_mutation=False,cleanup_executed=False,automatic_retry=False)
    rp=folder/'worker_result.json';ap=folder/'native_result.ai'
    ap.write_bytes(native);rp.write_bytes(json.dumps(result).encode())
    return rp,ap,digest(rp.read_bytes()),digest(native)


def state_flags(output):
    assert output['accepted'] is False
    assert output['execution_authorized'] is False
    assert output['dispatch_authorized'] is False
    assert output['retry_authorized'] is False
    assert output['cleanup_executed'] is False
    assert output['production_ready'] is False
    assert output['closeout_completed'] is False
    assert output['c3g_proof_is_not_worker_execution_fence'] is True
    assert output['com_execution_independently_proven'] is False
    assert output['native_ai_is_editable_independently_proven'] is False


def test_source_check():
    assert h.source_check()['state']=='OFFLINE_WORKER_RETURN_REVIEW_ONLY'


@pytest.mark.parametrize('field,bad', [
  ('task_id','evil'),('attempt_id','a0002'),('package_sha256','0'*64),
  ('staging_receipt_sha256','1'*64),('probe_is_synthetic_only',False),
  ('actual_native_execution_tested',True),('windows_write',True),
  ('ssh_used',True),('dispatch_authorized',True),
  ('execution_authorized',True),('retry_authorized',True),
  ('automatic_acceptance',True),('production_ready',True),
  ('cleanup_allowed',True),('owner_review_pending',False),
  ('blueprint_authority_review_pending',False),
  ('independent_com_execution_proven',True),
  ('independent_illustrator_editability_proven',True),
  ('probe_schema','broken'),('inspector_schema','broken'),
  ('closeout_mode','ACCEPT'),('state','READY')
])
def test_contract_mutations_rejected(tmp_path,monkeypatch,field,bad):
    c=json.loads(h.CONTRACT.read_text())
    c[field]=bad
    path=tmp_path/'contract.json';path.write_text(json.dumps(c))
    monkeypatch.setattr(h,'CONTRACT',path)
    with pytest.raises(h.HandoffBlocked): h.source_check()


def test_extra_contract_field_rejected(tmp_path,monkeypatch):
    c=json.loads(h.CONTRACT.read_text());c['other']='x'
    p=tmp_path/'c.json';p.write_text(json.dumps(c))
    monkeypatch.setattr(h,'CONTRACT',p)
    with pytest.raises(h.HandoffBlocked):h.source_check()


def test_contract_symlink_rejected(tmp_path,monkeypatch):
    path=tmp_path/'link';path.symlink_to(h.CONTRACT)
    monkeypatch.setattr(h,'CONTRACT',path)
    with pytest.raises(h.HandoffBlocked):h.source_check()


def test_current_inert_handoff(evidence):
    _,cap,p,v=evidence
    out=h.review(cap,p,v,'NONE')
    assert out['state']=='INERT_STAGING_NATIVE_RETURN_ABSENT_AUTHORITY_PENDING'
    assert out['worker_return_supplied'] is False
    assert out['worker_result_sha256'] is None
    assert out['c3g_synthetic_claim_sha256']=='a'*64
    assert out['recovery_state']=='INERT_STAGED_SNAPSHOT_NO_EXECUTION_OR_LAUNCH_AUTHORITY'
    state_flags(out)


@pytest.mark.parametrize('incident', [
   'SSH_LOSS','HOST_REBOOT','SCHEDULER_RC0_WITHOUT_VALID_RESULT',
   'PARTIAL_WRITE','WORKER_RC_NONZERO','UNKNOWN_PROCESS_EXIT'
])
def test_incident_never_allows_retry(evidence,incident):
    _,cap,p,v=evidence
    out=h.review(cap,p,v,incident)
    assert out['state']=='INCIDENT_REQUIRES_FRESH_INSPECTION_AND_OWNER_REVIEW'
    state_flags(out)


def test_execution_evidence_without_return_is_fenced(evidence):
    _,cap,p,v=evidence
    save(cap,observation(['start_claim']), 'GDL_W27C3D_LIVE_ATTEMPT='+d.FENCED)
    out=h.review(cap,p,v,'NONE')
    assert out['state']=='EXECUTION_EVIDENCE_PRESENT_RETURN_NOT_VERIFIED'
    state_flags(out)


def test_zero_byte_marker_is_evidence(evidence):
    _,cap,p,v=evidence
    save(cap,observation(['execution_started'],{'execution_started':(0,digest(b''))}),
         'GDL_W27C3D_LIVE_ATTEMPT='+d.FENCED)
    out=h.review(cap,p,v,'PARTIAL_WRITE')
    assert out['state']=='EXECUTION_EVIDENCE_PRESENT_RETURN_NOT_VERIFIED'
    state_flags(out)


def test_mock_native_return_requires_independent_hashes(evidence):
    folder,cap,p,v=evidence
    rp,ai,rs,ahs=result_mock(folder)
    save(cap,observation(['start_claim','execution_started','jsx','native_ai','worker_result'],
        {'native_ai':(ai.stat().st_size,ahs),'worker_result':(rp.stat().st_size,rs)}),
        'GDL_W27C3D_LIVE_ATTEMPT='+d.FENCED)
    out=h.review(cap,p,v,'NONE',rp,ai,rs,ahs)
    assert out['state']=='NATIVE_RETURN_HASH_VERIFIED_NOT_ACCEPTED'
    assert out['worker_report_fields_valid'] is True
    assert out['native_ai_bytes_hash_valid'] is True
    assert out['worker_result_sha256']==rs
    state_flags(out)


def test_return_cannot_be_based_on_inert_snapshot(evidence):
    folder,cap,p,v=evidence
    rp,ai,rs,ahs=result_mock(folder)
    with pytest.raises(h.HandoffBlocked,match='contradict'):
        h.review(cap,p,v,'NONE',rp,ai,rs,ahs)


@pytest.mark.parametrize('badkey', ['worker_result','native_ai'])
def test_windows_snapshot_wrong_sha_rejected(evidence,badkey):
    folder,cap,p,v=evidence
    rp,ai,rs,ahs=result_mock(folder)
    values={'native_ai':(ai.stat().st_size,ahs),'worker_result':(rp.stat().st_size,rs)}
    values[badkey]=(11,'f'*64)
    save(cap,observation(['native_ai','worker_result'],values),
         'GDL_W27C3D_LIVE_ATTEMPT='+d.FENCED)
    with pytest.raises(h.HandoffBlocked,match='SHA'):
        h.review(cap,p,v,'NONE',rp,ai,rs,ahs)


def test_windows_snapshot_wrong_ai_size_rejected(evidence):
    folder,cap,p,v=evidence
    rp,ai,rs,ahs=result_mock(folder)
    save(cap,observation(['native_ai','worker_result'],
       {'native_ai':(ai.stat().st_size+1,ahs), 'worker_result':(rp.stat().st_size,rs)}),
       'GDL_W27C3D_LIVE_ATTEMPT='+d.FENCED)
    with pytest.raises(h.HandoffBlocked,match='byte count'):
        h.review(cap,p,v,'NONE',rp,ai,rs,ahs)


def test_actual_result_hash_mismatch_rejected(evidence):
    folder,cap,p,v=evidence
    rp,ai,rs,ahs=result_mock(folder)
    save(cap,observation(['native_ai','worker_result'],
       {'native_ai':(ai.stat().st_size,ahs),'worker_result':(rp.stat().st_size,rs)}),
       'GDL_W27C3D_LIVE_ATTEMPT='+d.FENCED)
    rp.write_bytes(rp.read_bytes()+b'\n')
    with pytest.raises(h.HandoffBlocked,match='verification refused'):
        h.review(cap,p,v,'NONE',rp,ai,rs,ahs)


@pytest.mark.parametrize('partial', [
    {'result':Path('nowhere')},{'native_ai':Path('no')},
    {'expected_result_sha256':'a'*64}, {'expected_native_sha256':'a'*64}
])
def test_partial_native_return_args_denied(evidence,partial):
    _,cap,p,v=evidence
    with pytest.raises(h.HandoffBlocked,match='all four'):
        h.review(cap,p,v,'NONE',**partial)


@pytest.mark.parametrize('field,value', [
    ('task_id','wrong'),('attempt_id','a002'),('native_task_id','wrong'),
    ('windows_account','OTHER'),('execution_authorized',True),
    ('accepted',True),('windows_mutation',False),('duplicate_create_denied',False),
    ('claim_sha256','0'*64),('native_package_sha256','0'*64),
    ('native_receipt_sha256','0'*64),('runner_execution',True),
])
def test_probe_tampering_blocks(evidence,field,value):
    _,cap,p,v=evidence
    obj=proof('probe');obj[field]=value
    save(p,obj,'GDL_W27C3G_WINDOWS_FENCE='+h.PROBE_STATE)
    with pytest.raises(h.HandoffBlocked):h.review(cap,p,v,'NONE')


@pytest.mark.parametrize('bad', ['','GDL_W27C3G_WINDOWS_FENCE=WRONG',
    'GDL_W27C3G_WINDOWS_FENCE='+h.PROBE_STATE+'\nEXTRA'])
def test_proof_tail_rejected(evidence,bad):
    _,cap,p,v=evidence
    p.write_text(json.dumps(proof('probe'))+'\n'+bad+'\n')
    with pytest.raises(h.HandoffBlocked):h.review(cap,p,v,'NONE')


def test_duplicate_json_key_rejected(evidence):
    _,cap,p,v=evidence
    raw=json.dumps(proof('probe'))
    p.write_text(raw[:-1]+',"state":"hijacked"}'+'\nGDL_W27C3G_WINDOWS_FENCE='+h.PROBE_STATE)
    with pytest.raises(h.HandoffBlocked):h.review(cap,p,v,'NONE')


def test_symlink_evidence_rejected(evidence):
    folder,cap,p,v=evidence
    symlink=folder/'fake.txt';symlink.symlink_to(p)
    with pytest.raises(h.HandoffBlocked):h.review(cap,symlink,v,'NONE')


def test_proof_must_be_under_repo_tmp(evidence,tmp_path):
    _,cap,p,v=evidence
    outside=tmp_path/'outside.txt';outside.write_bytes(p.read_bytes())
    with pytest.raises(h.HandoffBlocked):h.review(cap,outside,v,'NONE')


def test_wrong_proof_type_rejected(evidence):
    folder,cap,p,v=evidence
    with pytest.raises(h.HandoffBlocked):h.review(cap,folder,v,'NONE')


def test_verify_expected_claim_mismatch_rejected(evidence):
    _,cap,p,v=evidence
    save(v,proof('verify',claim='f'*64),
         'GDL_W27C3G_WINDOWS_FENCE='+h.VERIFY_STATE)
    with pytest.raises(h.HandoffBlocked):h.review(cap,p,v,'NONE')


def test_bogus_c3d_report_rejected(evidence):
    _,cap,p,v=evidence
    save(cap,observation(), 'GDL_W27C3D_LIVE_ATTEMPT=EXECUTION_EVIDENCE_PRESENT_RECONCILIATION_REQUIRED')
    with pytest.raises(h.HandoffBlocked):h.review(cap,p,v,'NONE')


def test_main_source_check(capsys):
    assert h.main(['--mode','source-check'])==0
    assert 'SOURCE_CHECK_PASS' in capsys.readouterr().out


def test_main_source_check_extra_refused(capsys):
    assert h.main(['--mode','source-check','--incident','SSH_LOSS'])==2


def test_main_missing_reports_fails(capsys):
    assert h.main(['--mode','review'])==2


def test_main_inert_evidence(evidence,capsys):
    _,cap,p,v=evidence
    assert h.main(['--mode','review','--capture',str(cap),'--probe',str(p),'--verify',str(v)])==0
    output=capsys.readouterr().out
    assert 'GDL_W27C3H_RETURN_HANDOFF=INERT_STAGING_NATIVE_RETURN_ABSENT_AUTHORITY_PENDING' in output
    assert '"closeout_completed": false' in output


def test_no_launcher_or_remote_calls_in_new_module():
    source=Path(h.__file__).read_text()
    for forbidden in ('subprocess.', 'paramiko', 'ssh_command(', 'DoJavaScript(',
                      'Start-ScheduledTask','Register-ScheduledTask','Remove-Item'):
        assert forbidden not in source

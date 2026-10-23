"""Offline W27C3B contract tests. Mocks are NOT Windows/Illustrator runtime proof."""
import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/graphic_design_lab/worker_runtime'))
import gdl_w27c3b_native_worker_review_v0_1 as mod


def digest(data):
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def source():
    config, raw = mod.source_check()
    return config, raw


def test_source_has_review_only_state(source):
    config, raw = source
    assert config['execution_authorized'] is False
    assert config['launch_route_implemented'] is False
    assert config['actual_runtime_execution_tested'] is False
    assert config['entrypoint_mode'] == 'review'
    assert b'DoJavaScript' in raw


@pytest.mark.parametrize('field,bad', [
    ('execution_authorized', True), ('launch_route_implemented', True),
    ('execution_authority_parser_implemented', True), ('automatic_accept', True),
    ('production_publish', True), ('customer_data_allowed', True),
    ('cleanup_allowed', True), ('blueprint_review_pending', False),
    ('actual_runtime_execution_tested', True), ('source_candidate_only', False),
    ('entrypoint_mode', 'execute'),('task_id','different-task'),
    ('attempt_id','a1111'), ('package_sha256','0'*64),
    ('jsx_sha256','1'*64), ('result_schema','changed'),
    ('runner_source_sha256','0'*64), ('windows_mutation_by_review', True),
])
def test_contract_mutation_rejected(tmp_path, monkeypatch, source, field, bad):
    config = dict(source[0]); config[field] = bad
    p = tmp_path/'contract.json';p.write_text(json.dumps(config))
    monkeypatch.setattr(mod,'CONTRACT',p)
    with pytest.raises(mod.ReviewBlocked): mod.source_check()


def test_added_contract_field_rejected(tmp_path, monkeypatch, source):
    config = dict(source[0]);config['unknown']=False
    p=tmp_path/'contract.json';p.write_text(json.dumps(config))
    monkeypatch.setattr(mod,'CONTRACT',p)
    with pytest.raises(mod.ReviewBlocked):mod.source_check()


@pytest.mark.parametrize('replacement',[b'INVALID',b'DoJavaScripx',b'PUBLIC_EXECUTION_NOT_AUTHORIZED!!!'])
def test_source_digest_mutation_rejected(tmp_path, monkeypatch, source, replacement):
    p = tmp_path/'runner.ps1';p.write_bytes(source[1]+replacement)
    monkeypatch.setattr(mod,'RUNNER',p)
    with pytest.raises(mod.ReviewBlocked):mod.source_check()


def test_source_symlink_rejected(tmp_path,monkeypatch,source):
    p=tmp_path/'fake.ps1';p.symlink_to(mod.RUNNER)
    monkeypatch.setattr(mod,'RUNNER',p)
    with pytest.raises(mod.ReviewBlocked):mod.source_check()


def test_source_check_cli(capsys):
    assert mod.main(['--mode','source-check'])==0
    assert 'SOURCE_CHECK_PASS' in capsys.readouterr().out


def test_source_check_cli_extra_rejected():
    assert mod.main(['--mode','source-check','--expected-archive-sha256','0'*64])==2


def test_review_package_cli_requires_sha():
    assert mod.main(['--mode','review-package','--archive','tmp/dummy.zip'])==2


def test_review_package_digest_mismatch(source):
    with pytest.raises(mod.ReviewBlocked):
        mod.review_package(ROOT/'tmp/gdl_w27c1_synthetic_task_package_v0_1.zip', 'f'*64,source[0])


def test_review_package_valid(source):
    p=ROOT/'tmp/gdl_w27c1_synthetic_task_package_v0_1.zip'
    if not p.is_file():
        pytest.skip('fixture native package unavailable in isolated test')
    r=mod.review_package(p,mod.PACKAGE_SHA,source[0])
    assert r['state']==mod.RUNNER_STATE
    assert r['execution_authorized'] is False
    assert r['illustrator_execution'] is False
    assert r['runtime_verified'] is False


def good_result(source,ai):
    return dict(
        schema_version=mod.RESULT_SCHEMA,state='NATIVE_AI_REOPENED_LOCAL',
        task_id=mod.TASK,attempt_id=mod.ATTEMPT,host='PREPRESS',
        windows_account=r'PREPRESS\Work',package_sha256=mod.PACKAGE_SHA,
        jsx_sha256=mod.JSX_SHA,runner_sha256=source[0]['runner_source_sha256'],
        session_id=2,preexisting_illustrator_pid=1012,
        token_limited_verified=True,com_attach_performed=True,
        illustrator_executed=True,native_ai_saved_reopened=True,
        editable_area_text=True,native_ai_sha256=digest(ai),native_ai_bytes=len(ai),
        phase='DONE',error_code='NONE',independent_acceptance=False,
        execution_authority_review_pending=True,production_ready=False,
        accepted=False,client_files_touched=False,smb_mutation=False,
        cleanup_executed=False,automatic_retry=False,
    )


@pytest.fixture
def evidence(tmp_path,monkeypatch,source):
    # Synthetic-only bytes, not a real AI; tests validate binding, not semantics.
    root=tmp_path/'repo';folder=root/'tmp/test_result';folder.mkdir(parents=True)
    monkeypatch.setattr(mod,'ROOT',root)
    ai=b'%!PS-Adobe mock-not-a-real-ai\n'+b'?'*1200
    fp=folder/'native_result.ai';fp.write_bytes(ai)
    result=good_result(source,ai)
    rp=folder/'worker_result.json';rp.write_text(json.dumps(result),encoding='utf-8')
    return source[0],folder,ai,result


def call_verify(evidence):
    config,folder,ai,_=evidence
    rp=folder/'worker_result.json';fp=folder/'native_result.ai'
    return mod.verify_result(rp,fp,digest(rp.read_bytes()),digest(fp.read_bytes()),config)


def test_synthetic_evidence_contract_only(evidence):
    doc=call_verify(evidence)
    assert doc['state']==mod.RESULT_STATE
    assert doc['com_execution_independently_proven'] is False
    assert doc['document_editability_independently_proven'] is False
    assert doc['accepted'] is False


@pytest.mark.parametrize('field,bad',[
    ('task_id','gdl-other'),('attempt_id','a2222'),('state','ACCEPTED'),
    ('host','WRONG'),('windows_account','PREPRESS\\Admin'),
    ('package_sha256','0'*64),('jsx_sha256','1'*64),
    ('runner_sha256','2'*64),('session_id',0),('session_id',True),
    ('preexisting_illustrator_pid',None),('token_limited_verified',False),
    ('com_attach_performed',False),('illustrator_executed',False),
    ('native_ai_saved_reopened',False),('editable_area_text',False),
    ('phase','FAILED'),('error_code','ALERT'),
    ('independent_acceptance',True),('execution_authority_review_pending',False),
    ('production_ready',True),('accepted',True),('client_files_touched',True),
    ('smb_mutation',True),('cleanup_executed',True),('automatic_retry',True),
    ('native_ai_bytes',123),('native_ai_sha256','0'*64),
])
def test_modified_evidence_rejected(evidence,field,bad):
    _,folder,_,obj=evidence
    doc=dict(obj);doc[field]=bad
    (folder/'worker_result.json').write_text(json.dumps(doc),encoding='utf8')
    with pytest.raises(mod.ReviewBlocked):call_verify(evidence)


def test_extra_field_rejected(evidence):
    _,folder,_,obj=evidence
    doc=dict(obj);doc['accepted_by_owner']=True
    (folder/'worker_result.json').write_text(json.dumps(doc))
    with pytest.raises(mod.ReviewBlocked):call_verify(evidence)


def test_missing_field_rejected(evidence):
    _,folder,_,obj=evidence
    doc=dict(obj);doc.pop('phase')
    (folder/'worker_result.json').write_text(json.dumps(doc))
    with pytest.raises(mod.ReviewBlocked):call_verify(evidence)


def test_mismatch_expected_result_hash_rejected(evidence):
    config,folder,_,_=evidence
    with pytest.raises(mod.ReviewBlocked):
        mod.verify_result(folder/'worker_result.json',folder/'native_result.ai','0'*64,
                          digest((folder/'native_result.ai').read_bytes()),config)


def test_mismatch_expected_native_hash_rejected(evidence):
    config,folder,_,_=evidence
    with pytest.raises(mod.ReviewBlocked):
        mod.verify_result(folder/'worker_result.json',folder/'native_result.ai',
                          digest((folder/'worker_result.json').read_bytes()),'0'*64,config)


def test_symlink_evidence_denied(evidence,tmp_path):
    config,folder,ai,_=evidence
    f=folder/'native_result.ai';f.unlink();f.symlink_to(tmp_path/'outside.ai')
    (tmp_path/'outside.ai').write_bytes(ai)
    with pytest.raises(mod.ReviewBlocked):call_verify(evidence)


def test_wrong_result_location_rejected(evidence,tmp_path):
    config,folder,ai,_=evidence
    with pytest.raises(mod.ReviewBlocked):
        mod.verify_result(tmp_path/'worker_result.json',folder/'native_result.ai','0'*64,digest(ai),config)


def test_wrong_file_names_rejected(evidence):
    config,folder,ai,_=evidence
    with pytest.raises(mod.ReviewBlocked):
        mod.verify_result(folder/'result.json',folder/'native_result.ai','0'*64,digest(ai),config)


def test_bad_json_rejected(evidence):
    _,folder,_,_=evidence
    (folder/'worker_result.json').write_text('not-json')
    with pytest.raises(mod.ReviewBlocked):call_verify(evidence)


def test_small_ai_rejected(evidence):
    _,folder,_,_=evidence
    (folder/'native_result.ai').write_bytes(b'AI')
    with pytest.raises(mod.ReviewBlocked):call_verify(evidence)


def test_verify_cli_bad_parameters():
    assert mod.main(['--mode','verify-result'])==2

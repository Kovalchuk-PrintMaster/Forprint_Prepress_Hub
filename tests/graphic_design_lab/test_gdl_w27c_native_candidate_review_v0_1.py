"""Offline tests for W2.7-C1; MUST NEVER launch Illustrator or use SSH."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
import zipfile

import pytest

SOURCE = (Path(__file__).resolve().parents[2] / 'scripts/graphic_design_lab/worker_runtime'
          / 'gdl_w27c_native_candidate_review_v0_1.py')
sys.path.insert(0, str(SOURCE.parent))
spec = importlib.util.spec_from_file_location('gdl_w27c_candidate_under_test',SOURCE)
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
import gdl_w27_illustrator_task_package_v0_1 as pkg


@pytest.fixture
def source(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    c_src = root/'coordination/graphic_design_lab/worker_runtime/gdl_w27c_native_candidate_contract_v0_1.json'
    js_src = root/'tests/fixtures/graphic_design_lab/gdl_w27c/synthetic_native_roundtrip.jsx'
    req_src = root/'tests/fixtures/graphic_design_lab/gdl_w27c/synthetic_native_request.json'
    c, js, req = [tmp_path/p.name for p in (c_src,js_src,req_src)]
    c.write_bytes(c_src.read_bytes());js.write_bytes(js_src.read_bytes());req.write_bytes(req_src.read_bytes())
    monkeypatch.setattr(w,'CONTRACT',c)
    monkeypatch.setattr(w,'FIXTURE',js)
    monkeypatch.setattr(w,'REQUEST',req)
    monkeypatch.setattr(w,'check_static',lambda:None) # existing W2.7-A policy tested in its own suite
    cfg, data=w.source_check()
    return cfg,data,c,js,req


def candidate(source):
    cfg, data, *_=source
    request=json.loads(source[4].read_text())
    m=pkg.manifest_for(request,{'input/main.jsx':data})
    raw=pkg.archive_bytes(m,{'input/main.jsx':data})
    return cfg,data,m,raw,sha256(raw).hexdigest()


def test_source_contract(source):
    cfg, data, *_=source
    assert cfg['launch_authorized'] is False
    assert cfg['runner_implementation']=='NOT_IMPLEMENTED'
    assert cfg['jsx_sha256']==sha256(data).hexdigest()
    assert w.STATE.endswith('NOT_EXECUTABLE_BY_WORKER')


def test_review_candidate(source):
    cfg,js,m,raw,digest=candidate(source)
    report=w.inspect_candidate(raw,digest,cfg,js)
    assert report['state']==w.STATE
    assert report['profile_exact_bytes_verified'] is True
    assert report['package_structurally_verified'] is True
    assert report['worker_launch_authorized'] is False
    assert report['dispatch_authorized'] is False
    assert report['runtime_verified'] is False
    assert report['blueprint_review_pending'] is True
    assert report['illustrator_execution'] is False
    assert report['windows_mutation'] is False


def test_w27a_inspects_candidate(source):
    cfg,js,m,raw,digest=candidate(source)
    checked,got=pkg.inspect_zip(raw)
    assert got==digest and checked==m
    assert len(raw) < 262144


@pytest.mark.parametrize('key,value',[
    ('task_id','other-task'),('attempt_id','a9999'),('data_class','CUSTOMER'),
    ('script_path','input/evil.jsx'),('governance','APPROVED'),
])
def test_binding_attacks(source,key,value):
    cfg,js,manifest,_,_=candidate(source)
    m=deepcopy(manifest);m[key]=value
    raw=pkg.archive_bytes(m,{'input/main.jsx':js})
    with pytest.raises(w.CandidateBlocked):
        w.inspect_candidate(raw,sha256(raw).hexdigest(),cfg,js)


@pytest.mark.parametrize('key,value',[
    ('worker_launch',True),('production_publish',True),('automatic_accept',True),('dispatch_authorized',True),
])
def test_authority_attacks(source,key,value):
    cfg,js,m,_,_=candidate(source)
    m=deepcopy(m);m['authority'][key]=value
    raw=pkg.archive_bytes(m,{'input/main.jsx':js})
    with pytest.raises(w.CandidateBlocked):
        w.inspect_candidate(raw,sha256(raw).hexdigest(),cfg,js)


def test_wrong_expected_sha(source):
    cfg,js,m,raw,digest=candidate(source)
    with pytest.raises(w.CandidateBlocked,match='independent'):
        w.inspect_candidate(raw,'0'*64,cfg,js)


def test_bad_sha_format(source):
    cfg,js,m,raw,digest=candidate(source)
    with pytest.raises(w.CandidateBlocked,match='expected'):
        w.inspect_candidate(raw,'ALMOST',cfg,js)


def test_jsx_tamper_even_when_package_rehashed(source):
    cfg,js,m,raw,digest=candidate(source)
    altered=js.replace(b'W27C SYNTHETIC',b'W27C ALTERED!!')
    assert altered != js
    m=deepcopy(m)
    m['inputs'][0]['sha256']=sha256(altered).hexdigest()
    m['inputs'][0]['bytes']=len(altered)
    raw=pkg.archive_bytes(m,{'input/main.jsx':altered})
    with pytest.raises(w.CandidateBlocked,match='profile'):
        w.inspect_candidate(raw,sha256(raw).hexdigest(),cfg,js)


def test_duplicate_or_missing_member(source):
    cfg,js,m,raw,digest=candidate(source)
    raw=pkg.archive_bytes(m,{})
    with pytest.raises(w.CandidateBlocked):
        w.inspect_candidate(raw,sha256(raw).hexdigest(),cfg,js)


def test_wrong_outputs(source):
    cfg,js,m,raw,digest=candidate(source)
    m=deepcopy(m)
    m['expected_outputs'][0]['path']='export/different.ai'
    raw=pkg.archive_bytes(m,{'input/main.jsx':js})
    with pytest.raises(w.CandidateBlocked):
        w.inspect_candidate(raw,sha256(raw).hexdigest(),cfg,js)


@pytest.mark.parametrize('edit',[
    lambda d:d.pop('cleanup_allowed'),
    lambda d:d.update({'launch_authorized':True}),
    lambda d:d.update({'blueprint_review_pending':False}),
    lambda d:d.update({'runner_implementation':'IMPLEMENTED'}),
    lambda d:d.update({'jsx_sha256':'0'*64}),
    lambda d:d.update({'jsx_bytes':123}),
    lambda d:d.update({'task_id':'different'}),
])
def test_source_contract_rejects_authority_and_tamper(source,edit):
    cfg,js,c,_,_=source
    doc=json.loads(c.read_text());edit(doc)
    c.write_text(json.dumps(doc))
    with pytest.raises(w.CandidateBlocked):w.source_check()


@pytest.mark.parametrize('bad', ['alert(', 'app.quit(', 'File.openDialog'])
def test_source_rejects_forbidden_api(source,bad):
    cfg,js,c,path,request=source
    blob=js+('\n/* '+bad+' */').encode()
    path.write_bytes(blob)
    doc=json.loads(c.read_text());doc['jsx_bytes']=len(blob);doc['jsx_sha256']=sha256(blob).hexdigest()
    c.write_text(json.dumps(doc))
    req=json.loads(request.read_text());req['script']['bytes']=len(blob);req['script']['sha256']=sha256(blob).hexdigest()
    request.write_text(json.dumps(req))
    with pytest.raises(w.CandidateBlocked,match='forbidden'):
        w.source_check()


def test_source_rejects_request_mismatch(source):
    cfg,js,c,path,request=source
    req=json.loads(request.read_text());req['expected_outputs'][0]['path']='export/foo.ai'
    request.write_text(json.dumps(req))
    with pytest.raises(w.CandidateBlocked,match='request'):
        w.source_check()


def test_source_rejects_symlink_fixture(source,tmp_path):
    cfg,js,c,path,request=source
    path.unlink()
    path.symlink_to(tmp_path/'none')
    with pytest.raises(w.CandidateBlocked):w.source_check()


def test_source_check_mode_rejects_archive(source):
    assert w.main(['--mode','source-check'])==0
    assert w.main(['--mode','source-check','--archive','file.zip'])==2


def test_review_requires_explicit_digest(source):
    assert w.main(['--mode','review-package'])==2
    assert w.main(['--mode','review-package','--archive','bogus.zip'])==2


def test_review_exact_file_under_tmp(source, tmp_path, monkeypatch, capsys):
    cfg,js,m,raw,digest=candidate(source)
    path=tmp_path/'fixture.zip';path.write_bytes(raw)
    monkeypatch.setattr(w,'repo_tmp_path',lambda p,**kw:path)
    code=w.main(['--mode','review-package','--archive',str(path),
                 '--expected-archive-sha256',digest])
    assert code==0
    assert 'NOT_EXECUTABLE_BY_WORKER' in capsys.readouterr().out


def test_review_propagates_bad_zip(source):
    cfg,js,m,raw,digest=candidate(source)
    with pytest.raises(w.CandidateBlocked):
        w.inspect_candidate(b'broken zip',sha256(b'broken zip').hexdigest(),cfg,js)


def test_placeholder_from_w27a_rejected(source):
    cfg,js,m,_,_=candidate(source)
    placeholder=b"#target illustrator\n(function(){return 'FORPRINT_W27_PACKAGE_ONLY';})();"
    altered=deepcopy(m)
    altered['inputs'][0]['sha256']=sha256(placeholder).hexdigest()
    altered['inputs'][0]['bytes']=len(placeholder)
    raw=pkg.archive_bytes(altered,{'input/main.jsx':placeholder})
    with pytest.raises(w.CandidateBlocked):
        w.inspect_candidate(raw,sha256(raw).hexdigest(),cfg,js)

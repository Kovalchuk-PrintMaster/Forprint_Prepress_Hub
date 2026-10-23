"""W2.7-C3A offline contract tests; never invoke SSH/PowerShell or Windows."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / 'scripts/graphic_design_lab/worker_runtime'
sys.path.insert(0, str(DIR))
PATH = DIR / 'gdl_w27c3a_runner_source_review_v0_1.py'
spec = importlib.util.spec_from_file_location('gdl_w27c3a_tested', PATH)
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)


def valid_archive():
    from gdl_w27_illustrator_task_package_v0_1 import manifest_for, archive_bytes
    profile, jsx = w.candidate_source_check()
    request = json.loads((ROOT/'tests/fixtures/graphic_design_lab/gdl_w27c/synthetic_native_request.json').read_text())
    return archive_bytes(manifest_for(request, {'input/main.jsx': jsx}), {'input/main.jsx': jsx})


def test_source_check_baseline():
    c,t=w.source_check()
    assert c['runner_launch_implemented'] is False
    assert c['execution_authorized'] is False
    assert '[ValidateSet(\'review\')]' in t


def test_candidate_source_is_inert():
    _, t=w.source_check()
    for forbidden in ('DoJavaScript','GetActiveObject','Register-ScheduledTask',
                      'Start-ScheduledTask', 'CreateDirectory','Start-Process',
                      'Set-Acl','Remove-Item'):
        assert forbidden.lower() not in t.lower()


def test_render_binds_one_identity():
    c, t=w.source_check()
    d=w.render(c,t)
    assert w.TASK.encode() in d and w.ATTEMPT.encode() in d
    assert w.PACKAGE_SHA.encode() in d and w.JSX_SHA.encode() in d
    assert b'__TASK_ID__' not in d
    assert b'$ExecutionAuthorized = $false' in d


def test_review_real_synthetic_archive():
    c,_=w.source_check()
    raw=valid_archive()
    assert w.digest(raw)==w.PACKAGE_SHA
    r=w.review_package(raw,w.PACKAGE_SHA,c)
    assert r['package_verified'] and r['runner_source_verified']
    assert r['execution_authorized'] is False and r['accepted'] is False


@pytest.mark.parametrize('wrong', [
    '0'*64, 'a'*63, '', 'INVALID', 'b'*64,
])
def test_review_rejects_other_digest(wrong):
    c,_=w.source_check()
    with pytest.raises(w.RunnerBlocked):
        w.review_package(valid_archive(), wrong, c)


@pytest.mark.parametrize('substitution', [
    b'RENDEZVOUS', b'\x00', b'BADJSX',
])
def test_review_rejects_tampered_archive(substitution):
    c,_=w.source_check()
    raw=valid_archive() + substitution
    with pytest.raises((w.RunnerBlocked, ValueError)):
        w.review_package(raw,w.PACKAGE_SHA,c)


@pytest.mark.parametrize('key,val', [
    ('runner_launch_implemented',True),
    ('execution_authorized',True),
    ('blueprint_review_pending',False),
    ('automatic_accept',True),
    ('cleanup_allowed',True),
    ('customer_data_allowed',True),
    ('production_publish',True),
    ('state','RUNNER_READY'),
    ('package_sha256','0'*64),
    ('task_id','unrelated'),
    ('write_set','ALL'),
])
def test_contract_authority_fail_closed(tmp_path,monkeypatch,key,val):
    doc=json.loads(w.CONTRACT.read_text())
    doc[key]=val
    file=tmp_path/'contract.json';file.write_text(json.dumps(doc))
    monkeypatch.setattr(w,'CONTRACT',file)
    with pytest.raises(w.RunnerBlocked): w.source_check()


def test_contract_draft_sha_fail_closed(tmp_path,monkeypatch):
    doc=json.loads(w.CONTRACT.read_text())
    doc['template_sha256']='0'*64
    file=tmp_path/'contract.json';file.write_text(json.dumps(doc))
    monkeypatch.setattr(w,'CONTRACT',file)
    with pytest.raises(w.RunnerBlocked): w.source_check()


def test_template_mutation_fail_closed(tmp_path,monkeypatch):
    p=tmp_path/'candidate.ps1';p.write_bytes(w.TEMPLATE.read_bytes()+b'# modified\n')
    monkeypatch.setattr(w,'TEMPLATE',p)
    with pytest.raises(w.RunnerBlocked):w.source_check()


def test_no_source_check_launch(monkeypatch):
    called=[]
    monkeypatch.setattr(subprocess,'run',lambda *a,**k:called.append(1))
    assert w.main(['--mode','source-check'])==0
    assert w.main(['--mode','source-check','--output','x.ps1'])==2
    assert not called


def test_draft_new_only_under_tmp(monkeypatch,tmp_path):
    # Repo root may not be mutated by the test. Override only the well-scoped
    # repo_tmp_path gate, preserving target existence checks.
    _,t=w.source_check()
    b=w.render(json.loads(w.CONTRACT.read_text()),t)
    dest=tmp_path/'draft.ps1'
    def repo_tmp(p,*,must_exist):
        if Path(p) != dest or Path(p).exists() == (not must_exist):
            raise w.PackageBlocked('unsafe')
        return Path(p)
    monkeypatch.setattr(w,'repo_tmp_path',repo_tmp)
    w.write_draft(dest,b)
    assert dest.read_bytes()==b
    assert dest.stat().st_mode & 0o777 == 0o600
    with pytest.raises(w.RunnerBlocked): w.write_draft(dest,b)


def test_render_must_have_exact_markers():
    c,t=w.source_check()
    with pytest.raises(w.RunnerBlocked):w.render(c,t.replace('__TASK_ID__','X'))
    with pytest.raises(w.RunnerBlocked):w.render(c,t+'\n__TASK_ID__')


@pytest.mark.parametrize('filename', ['../../evil.ps1', 'other.txt', '/tmp/f.ps1'])
def test_draft_paths_restricted(filename):
    with pytest.raises(w.RunnerBlocked):w.draft_path(Path(filename), exists=False)


def test_main_rejects_unconfirmed_draft():
    assert w.main(['--mode','build-draft','--output','tmp/unconfirmed.ps1'])==2


def test_main_rejects_fake_package():
    assert w.main(['--mode','review-package','--archive','tmp/unknown.zip',
                   '--expected-archive-sha256',w.PACKAGE_SHA])==2


def test_draft_verifier_requires_independent_digest():
    assert w.main(['--mode','verify-draft','--draft','tmp/x.ps1'])==2


def test_c1_frozen_authority():
    cfg,_=w.source_check()
    assert cfg['expected_outputs']==['export/native_result.ai','export/worker_result.json']
    assert cfg['source_review_only'] is True
    assert cfg['write_set']=='NONE_ON_WINDOWS'


def test_tool_has_no_ssh_or_windows_invocation():
    source=PATH.read_text()
    for text in ('ssh_command(', 'subprocess.run(', 'shell=True', 'os.system(', 'Popen('):
        assert text not in source

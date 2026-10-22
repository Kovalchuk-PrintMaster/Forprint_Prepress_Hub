"""Offline regression tests for W2.6. Does not SSH or modify Windows."""
from __future__ import annotations
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

SOURCE = Path(__file__).resolve().parents[2] / 'scripts/graphic_design_lab/worker_runtime/windows_worker_w2_6_synthetic_artifact_return_v0_1.py'

sys.path.insert(0, str(SOURCE.parent))
# In the actual repository use the real W2 SSH modules. Stand-ins are needed
# only when validating the self-contained distribution outside that repository.
if not (SOURCE.parent / 'windows_worker_w2_host_inspector_v0_1.py').exists():
    host = ModuleType('windows_worker_w2_host_inspector_v0_1')
    host.InspectionBlocked = type('InspectionBlocked', (Exception,), {})
    host.ssh_command = lambda **kw: ['ssh', '-T', 'TEST']
    stdin = ModuleType('windows_worker_w2_3_workspace_initializer_v0_1')
    stdin.PS_STDIN_BRIDGE = '$s=[Console]::In.ReadToEnd(); & ([ScriptBlock]::Create($s))'
    sys.modules.setdefault(host.__name__, host)
    sys.modules.setdefault(stdin.__name__, stdin)
spec=importlib.util.spec_from_file_location('gdl_w26_under_test', SOURCE)
w=importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)


def make_transport(monkeypatch):
    ai=b'hello synthetic proof' * 8
    result={
        'schema_version':'gdl_windows_w2_5_3_native_runner_v0_1',
        'task_id':w.TASK, 'attempt_id':w.ATTEMPT,
        'host':'PREPRESS', 'windows_account':r'PREPRESS\Work',
        'state':'PASS_NATIVE_AI_REOPENED', 'ai_bytes':len(ai),
        'ai_sha256':hashlib.sha256(ai).hexdigest(),
        'jsx_sha256':w.JSX_SHA256, 'runner_sha256':w.RUNNER_SHA256,
        'token_limited_verified':True, 'editable_area_text':True,
        'native_ai_saved_reopened':True, 'production_ready':False,
        'smb_mutation':False, 'client_files_touched':False,
        'cleanup_executed':False, 'phase':'STAGE_DONE', 'error_code':'NONE'}
    rb=json.dumps(result).encode()
    transport={
        'schema_version':w.SCHEMA, 'state':'SOURCE_READ_ONLY_SHA_VERIFIED',
        'host':'PREPRESS', 'account':r'PREPRESS\Work',
        'task_id':w.TASK, 'attempt_id':w.ATTEMPT, 'ai_bytes':len(ai),
        'ai_sha256':hashlib.sha256(ai).hexdigest(),
        'ai_base64':base64.b64encode(ai).decode(),
        'result_bytes':len(rb), 'result_sha256':hashlib.sha256(rb).hexdigest(),
        'result_base64':base64.b64encode(rb).decode(),
        'windows_mutation':False, 'illustrator_execution':False,
        'scheduled_tasks_mutated':False, 'smb_mutation':False,
        'cleanup_executed':False, 'production_ready':False,
    }
    monkeypatch.setattr(w,'AI_SHA256', transport['ai_sha256'])
    monkeypatch.setattr(w,'AI_SIZE',len(ai))
    return ai,rb,transport


def test_remote_script_is_read_only():
    s=w.REMOTE_SCRIPT
    for marker in ('ReadAllBytes', 'AI_SHA256_MISMATCH',
                   'RUNNER_RESULT_BINDING_MISMATCH','SOURCE_READ_ONLY_SHA_VERIFIED',
                   "exit 2", "224636"):
        assert marker in s
    for bad in ('Set-Acl','Remove-Item','Register-ScheduledTask',
                'Start-ScheduledTask','DoJavaScript','WriteAllBytes'):
        assert bad not in s


def test_contract_source_check(tmp_path, monkeypatch):
    import yaml
    p=tmp_path/'policy.yaml'
    p.write_text(yaml.safe_dump({'windows':{'root':w.WIN_ROOT,'access_control':{'policy_id':'gdl_windows_operator_full_control_dev_v0_3'}},'authority':{'worker_launch':False,'production_publish':False},'cleanup':{'no_automatic_deletion':True}}))
    monkeypatch.setattr(w,'CONTRACT',p)
    assert w.source_check() is None
    doc=yaml.safe_load(p.read_text());doc['authority']['production_publish']=True
    p.write_text(yaml.safe_dump(doc))
    with pytest.raises(w.ReturnBlocked):w.source_check()


def test_valid_transport(monkeypatch):
    ai,rb,d=make_transport(monkeypatch)
    assert w.unpack_verified(json.dumps(d))[:2]==(ai,rb)

@pytest.mark.parametrize('k,v', [
 ('state','PUBLISHED'), ('host','OTHER'),('account',r'PREPRESS\someone'),
 ('task_id','unbound'), ('attempt_id','a9999'),
 ('windows_mutation',True),('scheduled_tasks_mutated',True),
 ('production_ready',True),('smb_mutation',True),
 ('ai_bytes',True),('ai_base64','not-b64')])
def test_transport_tampering(monkeypatch,k,v):
    _,_,d=make_transport(monkeypatch)
    d[k]=v
    with pytest.raises(w.ReturnBlocked):w.unpack_verified(json.dumps(d))

@pytest.mark.parametrize('k,v', [('state','BLOCKED_NATIVE_EXECUTION'),('token_limited_verified',False),('production_ready',True),('ai_bytes',False)])
def test_runner_result_tampering(monkeypatch,k,v):
    _,_,d=make_transport(monkeypatch)
    report=json.loads(base64.b64decode(d['result_base64']))
    report[k]=v
    rb=json.dumps(report).encode()
    d['result_bytes']=len(rb)
    d['result_sha256']=hashlib.sha256(rb).hexdigest()
    d['result_base64']=base64.b64encode(rb).decode()
    with pytest.raises(w.ReturnBlocked):w.unpack_verified(json.dumps(d))


def test_write_new_only_private(tmp_path,monkeypatch):
    ai,rb,d=make_transport(monkeypatch)
    dest=tmp_path/'proof'
    m=w.write_local(dest,ai,rb,d)
    assert (dest/'native_probe.ai').read_bytes()==ai
    assert m['accepted'] is False and m['production_ready'] is False
    assert dest.stat().st_mode & 0o777 == 0o700
    assert (dest/'native_probe.ai').stat().st_mode & 0o777 == 0o600
    with pytest.raises(w.ReturnBlocked):w.write_local(dest,ai,rb,d)


def test_source_check_mode_never_ssh(monkeypatch):
    monkeypatch.setattr(w,'source_check',lambda:None)
    monkeypatch.setattr(w,'remote_retrieve',lambda _:(_ for _ in ()).throw(AssertionError('unexpected SSH')))
    assert w.main(['--mode','source-check'])==0
    assert w.main(['--mode','retrieve'])==2


def test_remote_one_ssh_no_retry(monkeypatch):
    # Exercise the transport after the SSH-argument boundary. The real
    # ssh_command correctly rejects these intentionally nonexistent paths;
    # a failure before subprocess.run() does not test the no-retry contract.
    monkeypatch.setattr(w, 'source_check', lambda: None)
    ssh_args = []
    def fake_ssh(**kw):
        ssh_args.append(kw)
        return ['ssh', '-T', 'fake-remote-command']
    monkeypatch.setattr(w, 'ssh_command', fake_ssh)
    calls = []
    def fake(*a, **k):
        calls.append((a, k))
        return SimpleNamespace(returncode=2, stdout='', stderr='PRIVATE_DATA')
    monkeypatch.setattr(w.subprocess, 'run', fake)
    args = SimpleNamespace(host='192.168.50.69', user='work',
                           identity_file=Path('/tmp/key'), known_hosts=Path('/tmp/host'))
    with pytest.raises(w.ReturnBlocked) as err:
        w.remote_retrieve(args)
    assert len(ssh_args) == 1
    assert ssh_args[0]['host'] == '192.168.50.69'
    assert ssh_args[0]['user'] == 'work'
    assert ssh_args[0]['identity_file'] == args.identity_file
    assert ssh_args[0]['known_hosts'] == args.known_hosts
    assert len(calls) == 1
    assert calls[0][0][0] == ['ssh', '-T', 'fake-remote-command']
    assert calls[0][1]['input'] == w.REMOTE_SCRIPT
    assert calls[0][1]['timeout'] == 120
    assert 'PRIVATE_DATA' not in str(err.value)

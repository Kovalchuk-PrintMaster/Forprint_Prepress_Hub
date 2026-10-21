"""W2.3 offline tests: no SSH connections and no Windows/SMB mutations."""
from __future__ import annotations

from copy import deepcopy
from base64 import b64decode
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/graphic_design_lab/worker_runtime/windows_worker_w2_3_workspace_initializer_v0_1.py'
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location('gdl_w2_3_workspace_test_module', SCRIPT)
w = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(w)


def report(mode='check', state='READY_TO_INITIALIZE', mutation=False):
    return {
        'schema_version': w.SCHEMA,
        'mode': mode,
        'state': state,
        'root': w.WINDOWS_ROOT,
        'host': 'PREPRESS',
        'ssh_account': r'PREPRESS\Work',
        'directory_count': 8,
        'windows_mutation': mutation,
        'smb_mutation': False,
        'client_files_touched': False,
        'illustrator_execution': False,
        'cleanup_executed': False,
        'production_ready': False,
    }


def test_project_contract_source_check():
    assert w.source_check().count('__FORPRINT_W2_3_MODE__') == 1


def test_script_has_protected_creation_and_no_cleanup_calls():
    source = w.PROBE.read_text(encoding='utf-8').lower()
    assert 'directory]::createdirectory($shared, (new-strictrootacl))' in source
    assert 'setaccessruleprotection($true, $false)' in source
    assert 'partial_tree_review_required' in source
    for token in ('remove-item ', 'remove-directory', 'delete(', 'set-netfirewall',
                  'new-psdrive', 'new-smb', 'start-process', 'register-scheduledtask'):
        assert token not in source


@pytest.mark.parametrize('mode', ['check', 'initialize'])
def test_encoded_script_mode(mode):
    source = w.source_check()
    decoded = b64decode(w.encode(source, mode)).decode('utf-16le')
    assert f"$Mode = '{mode}'" in decoded
    assert '__FORPRINT_W2_3_MODE__' not in decoded


def test_remote_payload_is_stdin_not_windows_cmdline():
    source = w.source_check()
    assert len(w.encode(source, 'check')) > 8191  # original transport failed
    assert len(w.PS_STDIN_BRIDGE.encode('utf-16le')) < 1000
    assert '[Console]::In.ReadToEnd()' in w.PS_STDIN_BRIDGE
    assert '[ScriptBlock]::Create($s)' in w.PS_STDIN_BRIDGE
    assert 'CreateDirectory' not in w.PS_STDIN_BRIDGE


def test_reject_unsupported_mode():
    with pytest.raises(w.WorkspaceBlocked):
        w.encode(w.source_check(), 'delete')


@pytest.mark.parametrize('mode,state,mutation', [
    ('check', 'READY_TO_INITIALIZE', False),
    ('check', 'ALREADY_INITIALIZED_SAFE', False),
    ('initialize', 'INITIALIZED_SAFE', True),
    ('initialize', 'ALREADY_INITIALIZED_SAFE', False),
])
def test_valid_reports(mode, state, mutation):
    doc = report(mode, state, mutation)
    assert w.validate_report(json.dumps(doc), mode) == doc


@pytest.mark.parametrize('field,value', [
    ('root', r'D:\ForPrint\Automation'),
    ('host', 'MYSTERY'),
    ('ssh_account', 'PREPRESS\\Other'),
    ('directory_count', 7),
    ('schema_version', 'not_a_schema'),
    ('smb_mutation', True),
    ('client_files_touched', True),
    ('illustrator_execution', True),
    ('cleanup_executed', True),
    ('production_ready', True),
    ('windows_mutation', True),
    ('state', 'INITIALIZED_SAFE'),
])
def test_bad_check_report_rejected(field, value):
    d = report()
    d[field] = value
    with pytest.raises(w.WorkspaceBlocked):
        w.validate_report(json.dumps(d), 'check')


def test_forged_success_without_mutation_rejected():
    d = report('initialize', 'INITIALIZED_SAFE', False)
    with pytest.raises(w.WorkspaceBlocked):
        w.validate_report(json.dumps(d), 'initialize')


def test_initialize_cannot_claim_uninitialized():
    d = report('initialize', 'READY_TO_INITIALIZE', False)
    with pytest.raises(w.WorkspaceBlocked):
        w.validate_report(json.dumps(d), 'initialize')


def test_missing_confirmation_blocks_without_ssh(monkeypatch):
    monkeypatch.setattr(w, 'remote_run', lambda a: (_ for _ in ()).throw(AssertionError('unexpected ssh')))
    assert w.main(['--mode', 'initialize']) == 2


def test_check_rejects_confirmation_without_ssh(monkeypatch):
    monkeypatch.setattr(w, 'remote_run', lambda a: (_ for _ in ()).throw(AssertionError('unexpected ssh')))
    assert w.main(['--mode', 'check', '--confirm-local-workspace-creation']) == 2


def test_source_check_does_not_ssh(monkeypatch):
    monkeypatch.setattr(w, 'remote_run', lambda a: (_ for _ in ()).throw(AssertionError('unexpected ssh')))
    assert w.main(['--mode', 'source-check']) == 0


def test_remote_command_reuses_strict_w2_ssh_and_is_bounded(monkeypatch):
    from unittest.mock import Mock
    args = SimpleNamespace(mode='check', host='192.168.50.69', user='work',
                           identity_file=Path('/tmp/identity'), known_hosts=Path('/tmp/hosts'))
    fake = Mock(return_value=['ssh', '-T', 'mocked-command'])
    monkeypatch.setattr(w, 'ssh_command', fake)
    import subprocess
    seen = {}
    def fake_run(*a, **kw):
        seen.update(kw)
        seen['command'] = a[0]
        return SimpleNamespace(returncode=0, stdout=json.dumps(report()), stderr='')
    monkeypatch.setattr(subprocess, 'run', fake_run)
    assert w.remote_run(args)['state'] == 'READY_TO_INITIALIZE'
    assert fake.call_args.kwargs['host'] == '192.168.50.69'
    assert fake.call_args.kwargs['user'] == 'work'
    from base64 import b64decode
    bootstrap = b64decode(fake.call_args.kwargs['encoded']).decode('utf-16le')
    assert bootstrap == w.PS_STDIN_BRIDGE
    assert 'READY_TO_INITIALIZE' not in bootstrap
    assert len(fake.call_args.kwargs['encoded']) < 1024
    assert seen['input'] == w.render(w.source_check(), 'check')
    assert "$Mode = 'check'" in seen['input']
    assert '__FORPRINT_W2_3_MODE__' not in seen['input']
    assert len(seen['command'][-1]) < 1024


def test_failed_ssh_never_claims_success(monkeypatch):
    args = SimpleNamespace(mode='initialize', host='192.168.50.69', user='work',
                           identity_file=Path('/tmp/identity'), known_hosts=Path('/tmp/hosts'))
    monkeypatch.setattr(w, 'ssh_command', lambda **kw: ['ssh'])
    import subprocess
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: SimpleNamespace(
        returncode=2, stdout='', stderr='secret private trace'))
    with pytest.raises(w.WorkspaceBlocked, match='do not retry blindly'):
        w.remote_run(args)


def test_report_without_json_is_blocked():
    with pytest.raises(w.WorkspaceBlocked):
        w.validate_report('GDL=PASS', 'check')


def test_readonly_mode_returns_no_mutation(monkeypatch, capsys):
    monkeypatch.setattr(w, 'remote_run', lambda a: report())
    args = ['--mode', 'check', '--host', '192.168.50.69', '--user', 'work',
            '--identity-file', '/tmp/key', '--known-hosts', '/tmp/hosts']
    assert w.main(args) == 0
    assert 'READY_TO_INITIALIZE' in capsys.readouterr().out


def test_initialize_still_streams_only_confirmed_mode(monkeypatch):
    from unittest.mock import Mock
    args = SimpleNamespace(mode='initialize', host='192.168.50.69', user='work',
                           identity_file=Path('/tmp/identity'), known_hosts=Path('/tmp/hosts'))
    monkeypatch.setattr(w, 'ssh_command', Mock(return_value=['ssh','-T','remote']))
    import subprocess
    sent = []
    def fake_run(*a, **kw):
        sent.append(kw['input'])
        return SimpleNamespace(returncode=0, stdout=json.dumps(report('initialize', 'INITIALIZED_SAFE', True)), stderr='')
    monkeypatch.setattr(subprocess, 'run', fake_run)
    assert w.remote_run(args)['state'] == 'INITIALIZED_SAFE'
    assert len(sent) == 1
    assert "$Mode = 'initialize'" in sent[0]
    assert '__FORPRINT_W2_3_MODE__' not in sent[0]


def test_failed_ssh_does_not_retry_or_echo_remote_stderr(monkeypatch):
    args = SimpleNamespace(mode='check', host='192.168.50.69', user='work',
                           identity_file=Path('/tmp/identity'), known_hosts=Path('/tmp/hosts'))
    monkeypatch.setattr(w, 'ssh_command', lambda **kw: ['ssh','-T','remote'])
    import subprocess
    called = []
    def fake_run(*a, **kw):
        called.append(1)
        return SimpleNamespace(returncode=255, stdout='', stderr='PRIVATE_TOKEN')
    monkeypatch.setattr(subprocess, 'run', fake_run)
    with pytest.raises(w.WorkspaceBlocked, match='rc=255') as exc:
        w.remote_run(args)
    assert 'PRIVATE_TOKEN' not in str(exc.value)
    assert called == [1]

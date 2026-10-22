"""GDL W2 ACL policy migration: offline safety tests. Never contacts PREPRESS."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/graphic_design_lab/worker_runtime/windows_worker_acl_migration_v0_2.py'
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location('gdl_worker_acl_migration', SCRIPT)
w = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(w)


def report(mode='check', state='READY_FOR_LEAST_PRIVILEGE_MIGRATION'):
    prior = 'LEGACY_OPERATOR_FULL_CONTROL' if state == 'READY_FOR_LEAST_PRIVILEGE_MIGRATION' else 'OPERATOR_READ_EXECUTE'
    if mode == 'apply':
        prior = 'LEGACY_OPERATOR_FULL_CONTROL'
    return dict(schema_version=w.SCHEMA, policy_id=w.POLICY, mode=mode,
                state=state, prior_state=prior,
                host='PREPRESS', ssh_account=r'PREPRESS\Work', root=w.WINDOWS_ROOT,
                directories_checked=8, root_inheritance_protected=True,
                operator_sid_verified=True, windows_mutation=(mode == 'apply'),
                client_files_touched=False, scheduled_tasks_mutated=False,
                smb_mutation=False, illustrator_execution=False,
                cleanup_executed=False, production_ready=False)


def test_source_and_contract_match():
    s=w.source_check()
    c=yaml.safe_load(w.CONTRACT.read_text(encoding='utf-8'))
    p=c['windows']['access_control']
    assert w.POLICY == p['policy_id']
    assert w.SID == p['operator_sid']
    assert p['operator_account'] == r'PREPRESS\Work'
    assert p['expected_aces'][w.SID] == 'ReadAndExecute'
    assert p['worker_scheduled_run_level'] == 'Highest'
    assert c['authority']['worker_launch'] is False
    assert c['authority']['production_publish'] is False
    assert s.count('__ACL_MODE__') == 1


def test_migration_source_guards_are_explicit():
    s=w.source_check()
    for x in ('GetOwner([Security.Principal.SecurityIdentifier])',
              'ADMIN_TOKEN_REQUIRED', '$Root', 'RemoveAccessRuleSpecific',
              'Set-Acl -LiteralPath $Shared -AclObject $acl',
              'MIXED_ACL_REVIEW_REQUIRED', 'operator_sid_verified=$true',
              'OWNER_CHANGED', 'REQUIRED_SID_ABSENT', 'SID_UNEXPECTED_OR_DUPLICATED',
              'INHERITANCE_CHANGED', 'POST_MIGRATION_POLICY_NOT_REACHED',
              'MIGRATION_NOT_IN_EXPECTED_LEGACY_STATE',
              'ReadAndExecute', 'FullControl', 'NO_AUTOMATIC_CLEANUP'):
        assert x in s
    assert s.count('Set-Acl -LiteralPath $Shared -AclObject $acl') == 1
    assert 'SetAccessRuleProtection($false' not in s
    for bad in ('Remove-Item', 'icacls /reset', 'Register-ScheduledTask',
                'Start-ScheduledTask', 'Unregister-ScheduledTask',
                'Start-Process', 'Stop-Process', 'DoJavaScript'):
        assert bad not in s


@pytest.mark.parametrize('mode', ['check', 'apply'])
def test_render_exact_mode(mode):
    s=w.render(mode,w.source_check())
    assert f"$Mode = '{mode}'" in s
    assert '__ACL_MODE__' not in s


@pytest.mark.parametrize('mode', ['launch','repair','delete','check;quit','source-check'])
def test_render_rejects_unknown_mode(mode):
    with pytest.raises(w.MigrationBlocked):
        w.render(mode,w.source_check())


@pytest.mark.parametrize('mode,state', [('check','READY_FOR_LEAST_PRIVILEGE_MIGRATION'),
                                       ('check','OPERATOR_READ_EXECUTE_VERIFIED'),
                                       ('apply','OPERATOR_READ_EXECUTE_VERIFIED')])
def test_valid_reports(mode,state):
    doc=report(mode,state)
    assert w.validate_report(json.dumps(doc),mode) == doc


@pytest.mark.parametrize('field,value', [('host','OTHER'), ('root','C:\\'),
                                          ('policy_id','bogus'), ('ssh_account','MYSTERY'),
                                          ('directories_checked',7), ('directories_checked',True),
                                          ('root_inheritance_protected',False),
                                          ('operator_sid_verified',False),
                                          ('windows_mutation',True),
                                          ('client_files_touched',True),
                                          ('scheduled_tasks_mutated',True),
                                          ('smb_mutation',True),('illustrator_execution',True),
                                          ('cleanup_executed',True),('production_ready',True),
                                          ('state','OPERATOR_READ_EXECUTE_VERIFIED')])
def test_readonly_tampering_rejected(field,value):
    d=report();d[field]=value
    with pytest.raises(w.MigrationBlocked):
        w.validate_report(json.dumps(d),'check')


@pytest.mark.parametrize('field,value', [('state','READY_FOR_LEAST_PRIVILEGE_MIGRATION'),
                                          ('prior_state','OPERATOR_READ_EXECUTE'),
                                          ('windows_mutation',False),
                                          ('scheduled_tasks_mutated',True),
                                          ('client_files_touched',True)])
def test_apply_cannot_forge_success(field,value):
    d=report('apply','OPERATOR_READ_EXECUTE_VERIFIED');d[field]=value
    with pytest.raises(w.MigrationBlocked):
        w.validate_report(json.dumps(d),'apply')


def test_bad_json_rejected():
    with pytest.raises(w.MigrationBlocked):
        w.validate_report('Windows Ready','check')


def test_source_check_cannot_contact_ssh(monkeypatch):
    monkeypatch.setattr(w,'remote_run',lambda _ : (_ for _ in ()).throw(AssertionError('SSH')))
    assert w.main(['--mode','source-check']) == 0


def test_missing_or_misplaced_confirmation_blocks(monkeypatch):
    monkeypatch.setattr(w,'remote_run',lambda _ : (_ for _ in ()).throw(AssertionError('SSH')))
    assert w.main(['--mode','apply']) == 2
    assert w.main(['--mode','check','--confirm-operator-rx-migration']) == 2
    assert w.main(['--mode','source-check','--confirm-operator-rx-migration']) == 2


def test_remote_uses_single_pinned_ssh_stdin(monkeypatch):
    from base64 import b64decode
    args=SimpleNamespace(mode='check',host='192.168.50.69',user='work',
                         identity_file=Path('/tmp/worker_key'),known_hosts=Path('/tmp/pinned_hosts'))
    fake_ssh=Mock(return_value=['ssh','-T','powershell -EncodedCommand'])
    monkeypatch.setattr(w,'ssh_command',fake_ssh)
    seen={}
    def fake_run(cmd,**kw):
        seen.update(kw)
        return SimpleNamespace(returncode=0,stdout=json.dumps(report()),stderr='')
    monkeypatch.setattr(w.subprocess,'run',fake_run)
    assert w.remote_run(args)['state']=='READY_FOR_LEAST_PRIVILEGE_MIGRATION'
    assert fake_ssh.call_args.kwargs['host']=='192.168.50.69'
    bridge=b64decode(fake_ssh.call_args.kwargs['encoded']).decode('utf-16le')
    assert 'ReadToEnd()' in bridge
    assert 'Set-Acl' not in bridge
    assert "$Mode = 'check'" in seen['input']
    assert seen['timeout'] == 90


def test_failed_ssh_is_never_retried_and_stderr_is_private(monkeypatch):
    args=SimpleNamespace(mode='apply',host='192.168.50.69',user='work',
                         identity_file=Path('/tmp/worker_key'),known_hosts=Path('/tmp/pinned_hosts'))
    monkeypatch.setattr(w,'ssh_command',lambda **kw:['ssh','-T','remote'])
    calls=[]
    def fake_run(*a,**kw):
        calls.append(1)
        return SimpleNamespace(returncode=2,stdout='',stderr='PERSONAL_DATA')
    monkeypatch.setattr(w.subprocess,'run',fake_run)
    with pytest.raises(w.MigrationBlocked,match='do not retry apply blindly') as e:
        w.remote_run(args)
    assert calls == [1]
    assert 'PERSONAL_DATA' not in str(e.value)


def test_existing_w2_guards_and_w25_native_evidence_unmodified():
    p=SCRIPT.parent
    w24=(p/'windows_worker_w2_4_gui_probe_controller_v0_1.ps1').read_text()
    w25=(p/'windows_worker_w2_5_native_illustrator_controller_v0_1.ps1').read_text()
    w23=(p/'windows_worker_w2_3_workspace_initializer_v0_1.ps1').read_text()
    for content in (w24,w25,w23):
        assert f"$OperatorSid = '{w.SID}'" in content
        assert 'function Assert-ApprovedAcl' in content
        assert 'ReadAndExecute' in content
        assert 'W2_ACL_OPERATOR_NOT_READ_EXECUTE' in content
    assert 'RESUME_START_ALREADY_CLAIMED' in w24
    assert 'SYNTHETIC_GUI_RESULT_REPORTED' in w24
    assert 'TASK_EXISTS_NO_RELAUNCH' in w25
    assert 'NATIVE_AI_REOPENED_VERIFIED' in w25
    assert 'Directory]::CreateDirectory($Shared, (New-StrictRootAcl))' in w23

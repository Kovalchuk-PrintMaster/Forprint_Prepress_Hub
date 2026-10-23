"""C3G: offline tests only; SSH/Windows probe is mocked, NEVER invoked."""
from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

D = Path(__file__).resolve().parents[2]/'scripts/graphic_design_lab/worker_runtime'
sys.path.insert(0,str(D))
m = importlib.import_module('gdl_w27c3g_windows_fence_probe_v0_1')


@pytest.fixture
def source():
    return m.source_check()


def doc(mode='check', **change):
    data={
        'schema_version':m.REPORT,'mode':mode,'state':m.STATES[mode],
        'host':'PREPRESS','windows_account':r'PREPRESS\Work',
        'task_id':m.TASK,'attempt_id':m.ATTEMPT,
        'native_task_id':m.NATIVE_TASK,'native_attempt_id':m.NATIVE_ATTEMPT,
        'native_package_sha256':m.PACKAGE_SHA,'native_receipt_sha256':m.RECEIPT_SHA,
        'claim_sha256':None if mode=='check' else 'a'*64,
        'windows_mutation':mode=='probe','duplicate_create_denied':mode!='check',
        'com_attach_performed':False,'jsx_execution':False,'runner_execution':False,
        'scheduler_mutated':False,'dispatch_authorized':False,
        'execution_authorized':False,'retry_authorized':False,
        'production_ready':False,'accepted':False,'client_files_touched':False,
        'smb_mutation':False,'cleanup_executed':False,
    }
    data.update(change)
    return data


def args(mode='check',sha=None,confirm=False):
    return ['--mode',mode,'--host','192.168.50.69','--user','work',
            '--identity-file','/dummy/key','--known-hosts','/dummy/known'] + (
            ['--expected-probe-sha256',sha] if sha is not None else []) + (
            ['--confirm-synthetic-fence-probe'] if confirm else [])


def fake_remote(monkeypatch,mode='check',remote_doc=None,rc=0):
    monkeypatch.setattr(m,'ssh_command',lambda **k: ['ssh','-T','fake'])
    response=doc(mode) if remote_doc is None else remote_doc
    monkeypatch.setattr(m.subprocess,'run',lambda *a,**k: SimpleNamespace(returncode=rc,
                                  stdout=json.dumps(response),stderr='secret redacted'))


def test_source_check(source):
    assert '$Mode=' in source
    assert m.TASK in source
    assert 'NO_AUTOMATIC_CLEANUP' in source


def test_exact_profile_digests():
    c=json.loads(m.CONTRACT.read_text('utf-8'))
    assert hashlib.sha256(m.SCRIPT.read_bytes()).hexdigest()==c['ps_source_sha256']
    assert c['native_package_sha256']==m.PACKAGE_SHA
    assert c['native_receipt_sha256']==m.RECEIPT_SHA
    assert c['probe_is_not_worker_claim'] is True


@pytest.mark.parametrize('key,value',[
    ('task_id','gdl-other'),('attempt_id','a0002'),
    ('native_task_id','gdl-other'),('native_attempt_id','a0002'),
    ('native_package_sha256','0'*64),('native_receipt_sha256','f'*64),
    ('probe_location','jobs/bad'),('state','READY_TO_EXECUTE'),
    ('one_use_create_new',False),('probe_requires_explicit_confirmation',False),
    ('probe_is_not_worker_claim',False),('runner_launch_implemented',True),
    ('dispatch_authorized',True),('execution_authorized',True),('retry_authorized',True),
    ('automatic_cleanup',True),('production_ready',True),('customer_data_allowed',True),
    ('blueprint_review_pending',False),('ps_source_sha256','0'*64),
])
def test_contract_mutations_fail(monkeypatch,tmp_path,key,value):
    c=json.loads(m.CONTRACT.read_text('utf-8'))
    c[key]=value
    p=tmp_path/'contract.json'
    p.write_text(json.dumps(c))
    monkeypatch.setattr(m,'CONTRACT',p)
    with pytest.raises(m.FenceProbeBlocked): m.source_check()


@pytest.mark.parametrize('append',[b'\n# tampered',b'\nStart-ScheduledTask',b'\nDoJavaScript'])
def test_ps_mutation_fails(monkeypatch,tmp_path,append):
    p=tmp_path/'probe.ps1'
    p.write_bytes(m.SCRIPT.read_bytes()+append)
    monkeypatch.setattr(m,'SCRIPT',p)
    with pytest.raises(m.FenceProbeBlocked):m.source_check()


def test_ps_symlink_rejected(monkeypatch,tmp_path):
    p=tmp_path/'probe.ps1'
    p.symlink_to(m.SCRIPT)
    monkeypatch.setattr(m,'SCRIPT',p)
    with pytest.raises(m.FenceProbeBlocked):m.source_check()


def test_ps_mutators_forbidden(source):
    bad=['Start-ScheduledTask','Register-ScheduledTask','DoJavaScript',
         'GetActiveObject','Remove-Item','Set-Acl','Start-Process','Stop-Process']
    assert all(x.lower() not in source.lower() for x in bad)
    assert source.count('[IO.FileMode]::CreateNew')>=2
    assert 'if(Test-Path -LiteralPath $Task)' in source


@pytest.mark.parametrize('mode',['check','probe','verify'])
def test_render_resolves(source,mode):
    out=m.render(source,mode,'a'*64 if mode=='verify' else None)
    assert '__MODE__' not in out
    assert '__EXPECTED_PROBE_SHA__' not in out
    assert "'$Mode'" not in out
    assert '$Mode=\''+mode+'\'' in out


@pytest.mark.parametrize('sha',[None,'x','A'*64,'a'*63,'a'*65])
def test_render_rejects_untrusted_sha(source,sha):
    if sha is None:
        assert m.render(source,'verify',sha)
    else:
        with pytest.raises(m.FenceProbeBlocked):m.render(source,'verify',sha)


def test_validate_check():
    assert m.validate_report(json.dumps(doc()),'check',None)['claim_sha256'] is None


def test_validate_probe():
    assert m.validate_report(json.dumps(doc('probe')),'probe',None)['claim_sha256']=='a'*64


def test_validate_verify():
    assert m.validate_report(json.dumps(doc('verify')),'verify','a'*64)['claim_sha256']=='a'*64


@pytest.mark.parametrize('key,value',[
    ('schema_version','bad'),('mode','probe'),('state','STARTED'),
    ('host','OTHER'),('windows_account','ADMIN'),('task_id','bad'),('attempt_id','a0002'),
    ('native_task_id','bad'),('native_attempt_id','a0002'),
    ('native_package_sha256','0'*64),('native_receipt_sha256','0'*64),
    ('windows_mutation',True),('duplicate_create_denied',True),
    ('com_attach_performed',True),('jsx_execution',True),('runner_execution',True),
    ('scheduler_mutated',True),('dispatch_authorized',True),
    ('execution_authorized',True),('retry_authorized',True),
    ('production_ready',True),('accepted',True),('client_files_touched',True),
    ('smb_mutation',True),('cleanup_executed',True),('claim_sha256','f'*64),
])
def test_check_report_tampering_fails(key,value):
    with pytest.raises(m.FenceProbeBlocked):
        m.validate_report(json.dumps({**doc('check'),key:value}),'check',None)


@pytest.mark.parametrize('mode,key,value',[
    ('probe','windows_mutation',False),('probe','duplicate_create_denied',False),
    ('probe','claim_sha256',None),('probe','claim_sha256','!'),
    ('verify','windows_mutation',True),('verify','duplicate_create_denied',False),
    ('verify','claim_sha256','b'*64),
])
def test_probe_verify_tampering_fails(mode,key,value):
    with pytest.raises(m.FenceProbeBlocked):
        m.validate_report(json.dumps(doc(mode,**{key:value})),mode,
                          'a'*64 if mode=='verify' else None)


def test_unknown_report_fields_rejected():
    with pytest.raises(m.FenceProbeBlocked):
        m.validate_report(json.dumps(doc(other='hidden')),'check',None)


def test_missing_report_field_rejected():
    report=doc()
    del report['accepted']
    with pytest.raises(m.FenceProbeBlocked):m.validate_report(json.dumps(report),'check',None)


@pytest.mark.parametrize('text',['','not json','[]','{}','{"mode": "check"}\n{}'])
def test_invalid_report_rejected(text):
    with pytest.raises(m.FenceProbeBlocked):m.validate_report(text,'check',None)


def test_source_check_cli(capsys):
    assert m.main(['--mode','source-check'])==0
    assert 'SOURCE_CHECK_PASS' in capsys.readouterr().out


@pytest.mark.parametrize('extra',[['--host','192.168.50.69'],
                                   ['--confirm-synthetic-fence-probe'],
                                   ['--expected-probe-sha256','a'*64]])
def test_source_check_with_other_args_rejected(extra):
    assert m.main(['--mode','source-check']+extra)==2


@pytest.mark.parametrize('mode,more',[
    ('probe',[]),('check',['--confirm-synthetic-fence-probe']),
    ('verify',[]),('verify',['--expected-probe-sha256','A'*64]),
    ('probe',['--expected-probe-sha256','a'*64,'--confirm-synthetic-fence-probe']),
    ('check',['--expected-probe-sha256','a'*64]),
])
def test_authority_args_refused(mode,more):
    assert m.main(args(mode)+more)==2


def test_wrong_host_user_rejected():
    assert m.main(['--mode','check','--host','1.1.1.1','--user','work',
                   '--identity-file','/dummy/key','--known-hosts','/dummy/known'])==2


@pytest.mark.parametrize('mode,confirm,sha',[('check',False,None),
                                              ('probe',True,None),('verify',False,'a'*64)])
def test_cli_remote_mock_success(monkeypatch,capsys,mode,confirm,sha):
    fake_remote(monkeypatch,mode)
    assert m.main(args(mode,sha,confirm))==0
    assert m.STATES[mode] in capsys.readouterr().out


@pytest.mark.parametrize('mode,confirm,sha',[('check',False,None),
                                              ('probe',True,None),('verify',False,'a'*64)])
def test_ssh_failure_blocks(monkeypatch,mode,confirm,sha):
    fake_remote(monkeypatch,mode,rc=255)
    assert m.main(args(mode,sha,confirm))==2


def test_no_remote_probe_on_source_check(monkeypatch):
    monkeypatch.setattr(m,'ssh_command',lambda **k: (_ for _ in ()).throw(AssertionError))
    assert m.main(['--mode','source-check'])==0


def test_remote_returns_only_false_authority_flags(monkeypatch):
    fake_remote(monkeypatch,'probe',remote_doc=doc('probe',execution_authorized=True))
    assert m.main(args('probe',confirm=True))==2


def test_verify_sha_required_and_bound(monkeypatch):
    fake_remote(monkeypatch,'verify',remote_doc=doc('verify',claim_sha256='b'*64))
    assert m.main(args('verify',sha='a'*64))==2


def test_git_footprint_unchanged_for_other_gc_work():
    files=['gdl_w27c3g_windows_fence_probe_contract_v0_1.json',
           'gdl_w27c3g_windows_fence_probe_v0_1.py',
           'gdl_w27c3g_windows_fence_probe_v0_1.ps1',
           'test_gdl_w27c3g_windows_fence_probe_v0_1.py']
    assert all('greeting_cards' not in x and 'Makefile' not in x for x in files)

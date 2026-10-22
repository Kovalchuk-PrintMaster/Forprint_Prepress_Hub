"""Offline W2.5 synthetic Illustrator probe contract/security tests. No Windows calls."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from copy import deepcopy

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/graphic_design_lab/worker_runtime/windows_worker_w2_5_native_illustrator_probe_v0_1.py'
SPEC = importlib.util.spec_from_file_location('gdl_w25_native', SCRIPT)
import sys
sys.path.insert(0, str(SCRIPT.parent))
w = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(w)


def source():
    return w.source_check()


def hashes():
    s, r, j = source()
    _, rh, jh = w.render('check', s, r, j)
    return rh, jh


def fixture(mode='check', state='READY_FOR_NATIVE_PROOF'):
    rh, jh = hashes()
    return {'schema_version': w.SCHEMA, 'mode': mode, 'state': state,
            'host': 'PREPRESS', 'ssh_account': r'PREPRESS\Work',
            'task_name': w.TASK_NAME, 'task_id': w.TASK_ID, 'attempt_id': w.ATTEMPT_ID,
            'jsx_sha256': jh, 'runner_sha256': rh,
            'session_id': 2, 'windows_mutation': mode == 'launch',
            'smb_mutation': False, 'client_files_touched': False,
            'cleanup_executed': False, 'production_ready': False,
            'native_result': None}


def result():
    rh,jh = hashes()
    return {'schema_version':w.RUN_SCHEMA,'state':'PASS_NATIVE_AI_REOPENED',
            'task_id':w.TASK_ID,'attempt_id':w.ATTEMPT_ID,'host':'PREPRESS',
            'windows_account':r'PREPRESS\Work', 'session_id':2,
            'jsx_sha256':jh,'runner_sha256':rh,'font_name':'ZapfChanceryC',
            'illustrator_executed':True, 'native_ai_saved_reopened':True,
            'editable_area_text':True,'production_ready':False,
            'ai_sha256':'c'*64,'ai_bytes':10400,'error_code':'NONE',
            'smb_mutation':False,'client_files_touched':False,'cleanup_executed':False,
            'preexisting_illustrator_pid':9228}


def validate(doc):
    rh, jh = hashes()
    return w.validate_report(json.dumps(doc), doc['mode'], rh, jh)


def test_source_check():
    c,r,j=source()
    assert b'NO_DIALOGS_OR_ALERTS' in j
    assert 'NO_AUTOMATIC_CLEANUP' in c
    assert b'FORPRINT_NATIVE_AI_REOPENED' in j


def test_render_binding_is_verifiable():
    ctrl,runner,jsx=source()
    code,rh,jh=w.render('launch',ctrl,runner,jsx)
    assert '__JSX_SHA__' not in code
    assert '__RUNNER_SHA__' not in code
    assert '__MODE__' not in code
    assert jh == hashlib.sha256(jsx).hexdigest()
    fixed=runner.replace(b'__JSX_SOURCE_SHA__', jh.encode('ascii'))
    assert rh == hashlib.sha256(fixed).hexdigest()


@pytest.mark.parametrize('mode,state', [('check','READY_FOR_NATIVE_PROOF'),
                                        ('launch','NATIVE_PROOF_STARTED_RESULT_PENDING'),
                                        ('verify','WAITING_FOR_NATIVE_RESULT'),
                                        ('verify','NATIVE_RESULT_REQUIRES_REVIEW')])
def test_valid_states(mode,state):
    assert validate(fixture(mode,state))['state'] == state


def test_native_result_success():
    doc=fixture('verify','NATIVE_AI_REOPENED_VERIFIED')
    doc['native_result']=result()
    assert validate(doc)['state']=='NATIVE_AI_REOPENED_VERIFIED'


@pytest.mark.parametrize('key,bad', [('schema_version','foo'),('host','OTHER'),
                                    ('ssh_account','prepress\\other'),('task_id','duplicate'),
                                    ('attempt_id','a0002'),('task_name','WRONG'),
                                    ('runner_sha256','0'*64),('jsx_sha256','0'*64),
                                    ('smb_mutation',True),('cleanup_executed',True),
                                    ('client_files_touched',True),('production_ready',True),
                                    ('windows_mutation',True),('native_result',{})])
def test_invalid_check_rejected(key,bad):
    d=fixture()
    d[key]=bad
    with pytest.raises(w.NativeBlocked):
        validate(d)


@pytest.mark.parametrize('key,bad', [('state','FAKE_PASS'),('session_id',0),
                                    ('windows_mutation',False),('native_result',{})])
def test_invalid_launch_rejected(key,bad):
    d=fixture('launch','NATIVE_PROOF_STARTED_RESULT_PENDING')
    d[key]=bad
    with pytest.raises(w.NativeBlocked):
        validate(d)


@pytest.mark.parametrize('key,bad', [('schema_version','X'),('state','FAILED'),
                                    ('task_id','gdl-w25-other'),('attempt_id','a0002'),
                                    ('host','OTHER'),('windows_account','PREPRESS\\Other'),
                                    ('jsx_sha256','a'*64),('runner_sha256','a'*64),
                                    ('font_name','Arial'),('illustrator_executed',False),
                                    ('native_ai_saved_reopened',False),('editable_area_text',False),
                                    ('production_ready',True),('ai_sha256','no'),('ai_bytes',10),
                                    ('session_id',0),('error_code','FAILED'),('smb_mutation',True),
                                    ('client_files_touched',True),('cleanup_executed',True),
                                    ('preexisting_illustrator_pid',0)])
def test_invalid_native_result_rejected(key,bad):
    doc=fixture('verify','NATIVE_AI_REOPENED_VERIFIED')
    doc['native_result']=result()
    doc['native_result'][key]=bad
    with pytest.raises(w.NativeBlocked):
        validate(doc)


def test_missing_native_result_rejected():
    d=fixture('verify','NATIVE_AI_REOPENED_VERIFIED')
    with pytest.raises(w.NativeBlocked):
        validate(d)


def test_source_check_mode_no_remote(monkeypatch,capsys):
    def fail(*a,**kw):raise AssertionError('external call')
    monkeypatch.setattr(w.subprocess,'run',fail)
    assert w.main(['--mode','source-check'])==0
    assert 'SOURCE_CHECK_PASS' in capsys.readouterr().out


def test_launch_requires_explicit_confirmation():
    assert w.main(['--mode','launch'])==2
    assert w.main(['--mode','check','--confirm-synthetic-native-illustrator'])==2


def test_no_destructive_actions_source():
    js=w.JSX.read_text('ascii')
    ctrl=w.CONTROLLER.read_text('ascii')
    for bad in ('alert(', 'File.openDialog', 'Folder.myDocuments','app.quit(',
                'documents.close(', 'app.activeDocument.close('):
        assert bad not in js
    for bad in ('Unregister-ScheduledTask', 'Remove-Item', 'Clear-Content',
                'Stop-Process', 'Stop-ScheduledTask'):
        assert bad not in ctrl


def test_no_dangerous_asset_permissions():
    c,r,j=source()
    assert 'No customer' in c or 'customer' in c.lower()
    assert b'GetActiveObject' in r
    assert b'New-Object -ComObject' not in r
    assert b'client_files_touched=$false' in r
    assert b'smb_mutation=$false' in r


def test_bad_json_rejected():
    rh,jh=hashes()
    with pytest.raises(w.NativeBlocked):w.validate_report('x','check',rh,jh)


def test_duplicate_source_marker_fails():
    c,r,j=source()
    with pytest.raises(w.NativeBlocked):
        w.render('check',c,r+b'__JSX_SOURCE_SHA__',j)

"""Offline W2 read-only host inspector and SSH safety tests; never connects to Windows."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/graphic_design_lab/worker_runtime/windows_worker_w2_host_inspector_v0_1.py'
SPEC = importlib.util.spec_from_file_location('gdl_w2_host_inspector', SCRIPT)
w2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(w2)


def result():
    return {
        'schema_version': w2.SCHEMA, 'origin': 'WINDOWS_READ_ONLY_SSH_PROBE',
        'host_name': 'PREPRESS', 'ssh_account': r'PREPRESS\work', 'os_build': 19045,
        'drive_d': {'present': True, 'file_system': 'NTFS', 'size_bytes': 320070479872,
                    'free_bytes': 295697117184},
        'worker_root': {'path': w2.WINDOWS_ROOT, 'exists': False},
        'registered_graphics_software': [{'DisplayName': 'Adobe Illustrator 2026',
                                          'DisplayVersion': '30.0'}],
        'registered_relevant_fonts': ['ZapfChanceryC (TrueType)'],
        'zapfchanceryc_registered': True, 'active_quser_session_count': 1,
        'task_scheduler_status': 'Running', 'sshd_status': 'Running',
        'illustrator_font_api_verified': False, 'interactive_gui_execution_verified': False,
        'smb_private_access_verified': False, 'windows_write_requested': False,
    }


def test_project_w2_matches_w1_contract():
    w2.check_sources()


def test_encodecommand_is_utf16le():
    from base64 import b64decode
    assert b64decode(w2.encoded_powershell('Привіт')).decode('utf-16le') == 'Привіт'


def test_verified_remote_readonly_host_not_promoted():
    report = w2.interpret_report(json.dumps(result()))
    assert report['state'] == 'HOST_PREREQUISITES_PRESENT_GUI_NOT_PROVEN'
    assert report['independent_authority_granted'] is False
    assert report['illustrator_executed'] is False
    assert report['gui_execution_verified'] is False


@pytest.mark.parametrize('section,value', [
    ('windows_write_requested', True), ('interactive_gui_execution_verified', True),
    ('illustrator_font_api_verified', True), ('smb_private_access_verified', True),
    ('schema_version', 'different'), ('origin', 'different'),
])
def test_cannot_claim_execution_or_writes(section, value):
    bad = result()
    bad[section] = value
    with pytest.raises(w2.InspectionBlocked):
        w2.interpret_report(json.dumps(bad))


def test_wrong_root_blocked():
    bad = result()
    bad['worker_root']['path'] = r'D:\ForPrint\Automation'
    with pytest.raises(w2.InspectionBlocked):
        w2.interpret_report(json.dumps(bad))


def test_drive_absent_is_not_ready():
    bad = result()
    bad['drive_d'] = {'present': False, 'file_system': None, 'size_bytes': None, 'free_bytes': None}
    assert w2.interpret_report(json.dumps(bad))['state'] == 'HOST_PREREQUISITES_INCOMPLETE'


def test_invalid_json_rejected():
    with pytest.raises(w2.InspectionBlocked):
        w2.interpret_report('not json')


def test_auth_ssh_is_strict_and_no_password(tmp_path):
    key, hostkey = tmp_path / 'key', tmp_path / 'known_hosts'
    key.write_text('synthetic fixture')
    key.chmod(0o600)
    hostkey.write_text('synthetic fixture')
    cmd = w2.ssh_command(host='192.168.50.69', user='work', identity_file=key,
                         known_hosts=hostkey, encoded='UABTAF8A')
    joined = ' '.join(cmd)
    for expected in ('BatchMode=yes', 'PasswordAuthentication=no',
                     'StrictHostKeyChecking=yes', 'IdentitiesOnly=yes'):
        assert expected in joined
    assert 'StrictHostKeyChecking=no' not in joined
    assert '-EncodedCommand UABTAF8A' in cmd[-1]


def test_reject_invalid_ip_username_or_identity_acl(tmp_path):
    key, hostkey = tmp_path / 'key', tmp_path / 'known_hosts'
    key.write_text('synthetic fixture')
    key.chmod(0o644)
    hostkey.write_text('synthetic fixture')
    kwargs = {'host': '192.168.50.69', 'user': 'work', 'identity_file': key,
              'known_hosts': hostkey, 'encoded': 'UAA='}
    with pytest.raises(w2.InspectionBlocked):
        w2.ssh_command(**kwargs)
    key.chmod(0o600)
    for change in ({'host': '-oProxyCommand=x'}, {'user': 'work;whoami'}):
        with pytest.raises(w2.InspectionBlocked):
            w2.ssh_command(**{**kwargs, **change})


def test_check_mode_does_not_execute_remote(monkeypatch, capsys):
    def fail(*a, **kw):
        raise AssertionError('remote executable invoked')
    monkeypatch.setattr(w2.subprocess, 'run', fail)
    assert w2.main(['--mode', 'check']) == 0
    assert 'SOURCE_CHECK_PASS' in capsys.readouterr().out


def test_no_windows_mutation_commands_in_probe():
    source = w2.PROBE.read_text(encoding='utf-8').lower()
    for token in ('new-item ', 'set-content', 'out-file', 'remove-item', 'copy-item',
                  'start-process', 'invoke-expression', 'register-scheduledtask',
                  'set-service ', 'start-service ', 'new-netfirewallrule'):
        assert token not in source

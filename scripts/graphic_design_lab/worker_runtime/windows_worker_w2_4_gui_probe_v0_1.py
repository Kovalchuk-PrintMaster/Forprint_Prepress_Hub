#!/usr/bin/env python3
"""ForPrint GDL W2.4 one-shot synthetic Task Scheduler interactive-session proof.

Uses verified s01 SSH transport and W2.3 protected local Windows workspace.
Only --mode launch --confirm-synthetic-gui-probe can mutate Windows. No Adobe
launch, no client SMB, no cleanup, no worker dispatch or production acceptance.
Never auto-retry a partial/ambiguous scheduler execution.
"""
from __future__ import annotations

import argparse
import base64
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys

import yaml

from windows_worker_w2_host_inspector_v0_1 import InspectionBlocked, ssh_command
from windows_worker_w2_3_workspace_initializer_v0_1 import PS_STDIN_BRIDGE

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / 'coordination/graphic_design_lab/worker_runtime/windows_worker_w1_pilot_contract_v0_1.yaml'
SOURCE = Path(__file__).with_name('windows_worker_w2_4_gui_probe_controller_v0_1.ps1')
PAYLOAD = Path(__file__).with_name('windows_worker_w2_4_gui_probe_payload_v0_1.ps1')
WINDOWS_ROOT = r'D:\ForPrint_Automation\GraficsDesignLab\Automation'
CONTROLLER_SCHEMA = 'gdl_windows_w2_4_controller_report_v0_1'
PAYLOAD_SCHEMA = 'gdl_windows_w2_4_gui_probe_result_v0_1'
TASK_NAME = 'ForPrint-GDL-W2-4-GUI-Probe'
TASK_ID = 'gdl-w24-gui-probe-001'
ATTEMPT_ID = 'a0001'
MODES = ('source-check', 'check', 'launch', 'verify', 'resume-check', 'resume-start')
SHA_RE = re.compile(r'^[a-f0-9]{64}$')


class GuiProbeBlocked(RuntimeError):
    """Blocked action, do not blindly retry especially after launch."""


def source_check() -> tuple[str, bytes]:
    for p in (CONTRACT, SOURCE, PAYLOAD):
        if not p.is_file() or p.is_symlink():
            raise GuiProbeBlocked('W1 contract/W2.4 source missing or symlinked')
    c = yaml.safe_load(CONTRACT.read_text(encoding='utf-8'))
    if (c.get('windows', {}).get('root') != WINDOWS_ROOT
            or c.get('authority', {}).get('worker_launch') is not False
            or c.get('authority', {}).get('production_publish') is not False
            or c.get('cleanup', {}).get('no_automatic_deletion') is not True):
        raise GuiProbeBlocked('W1 pilot contract unsafe or incompatible')
    policy = c.get('windows', {}).get('access_control', {})
    if (policy.get('policy_id') != 'gdl_windows_operator_read_execute_v0_2'
            or policy.get('operator_sid') != 'S-1-5-21-3087849371-1068859030-1179031902-1001'
            or policy.get('expected_aces') != {
                'S-1-5-18': 'FullControl',
                'S-1-5-32-544': 'FullControl',
                'S-1-5-21-3087849371-1068859030-1179031902-1001': 'ReadAndExecute'}
            or policy.get('root_owner') != r'BUILTIN\Administrators'
            or policy.get('root_inheritance_protected') is not True
            or policy.get('child_directories_inherit') is not True):
        raise GuiProbeBlocked('W1 operator ACL policy mismatch')
    ps = SOURCE.read_text(encoding='ascii')
    payload = PAYLOAD.read_bytes()
    if len(payload) > 16000 or len(ps) > 32000:
        raise GuiProbeBlocked('unexpectedly large synthetic probe')
    for marker in ('__MODE__', '__PAYLOAD_B64__', '__PAYLOAD_SHA__'):
        if ps.count(marker) != 1:
            raise GuiProbeBlocked('controller injection marker missing/duplicated')
    if f"$Root = '{WINDOWS_ROOT}'" not in ps:
        raise GuiProbeBlocked('Windows local path mismatch')
    if 'Assert-ApprovedAcl' not in ps or "$OperatorSid = 'S-1-5-21-3087849371-1068859030-1179031902-1001'" not in ps:
        raise GuiProbeBlocked('W2.4 ACL guard missing')
    for marker in (TASK_NAME, TASK_ID, ATTEMPT_ID, 'New-ScheduledTaskPrincipal',
                   '-LogonType Interactive', 'Register-ScheduledTask',
                   'Start-ScheduledTask', 'no automatic cleanup',
                   'SCHEDULED_TASK_OWNER_SID_MISMATCH', 'RESUME_TASK_NOT_PROVEN_NEVER_RUN',
                   'RESUME_START_ALREADY_CLAIMED', 'FileMode]::CreateNew',
                   'READY_TO_RESUME_EXISTING_UNRUN_TASK'):
        if marker not in ps:
            raise GuiProbeBlocked('controller safety/behavior marker missing')
    for marker in (TASK_ID, ATTEMPT_ID, PAYLOAD_SCHEMA,
                   '[Environment]::UserInteractive', 'Get-Process -Name explorer',
                   'FileMode]::CreateNew', 'illustrator_execution = $false'):
        if marker not in payload.decode('ascii'):
            raise GuiProbeBlocked('synthetic result safety marker missing')
    return ps, payload


def render(mode: str, controller: str, payload: bytes) -> tuple[str, str]:
    if mode not in ('check', 'launch', 'verify', 'resume-check', 'resume-start'):
        raise GuiProbeBlocked('invalid remote mode')
    digest = sha256(payload).hexdigest()
    result = (controller.replace('__MODE__', mode)
             .replace('__PAYLOAD_B64__', base64.b64encode(payload).decode('ascii'))
             .replace('__PAYLOAD_SHA__', digest))
    if '__MODE__' in result or '__PAYLOAD_B64__' in result or '__PAYLOAD_SHA__' in result:
        raise GuiProbeBlocked('unresolved source marker')
    return result, digest


def validate_result(raw: object, digest: str) -> dict:
    if not isinstance(raw, dict) or raw.get('schema_version') != PAYLOAD_SCHEMA:
        raise GuiProbeBlocked('invalid synthetic result schema')
    expected = {'task_id': TASK_ID, 'attempt_id': ATTEMPT_ID, 'host': 'PREPRESS',
                'windows_account': r'PREPRESS\Work', 'source_sha256': digest,
                'state': 'PASS_SYNTHETIC_INTERACTIVE'}
    for key, value in expected.items():
        if raw.get(key) != value:
            raise GuiProbeBlocked(f'synthetic result {key} mismatch')
    sid = raw.get('expected_session_id')
    if type(sid) is not int or sid < 1 or type(raw.get('actual_session_id')) is not int or raw['actual_session_id'] != sid:
        raise GuiProbeBlocked('synthetic session identity mismatch')
    if raw.get('user_interactive') is not True or raw.get('explorer_same_session') is not True:
        raise GuiProbeBlocked('synthetic session not interactive')
    for flag in ('illustrator_execution', 'smb_mutation', 'client_files_touched',
                 'production_ready', 'cleanup_executed'):
        if raw.get(flag) is not False:
            raise GuiProbeBlocked(f'forbidden result flag {flag}')
    return raw


def validate_report(output: str, *, mode: str, digest: str) -> dict:
    try:
        doc = json.loads(output.strip())
    except (ValueError, TypeError) as e:
        raise GuiProbeBlocked('remote host did not return single JSON document') from e
    if not isinstance(doc, dict) or doc.get('schema_version') != CONTROLLER_SCHEMA:
        raise GuiProbeBlocked('invalid W2.4 controller result')
    expected = {'mode': mode, 'host': 'PREPRESS', 'ssh_account': r'PREPRESS\Work',
                'task_name': TASK_NAME, 'task_id': TASK_ID, 'attempt_id': ATTEMPT_ID,
                'expected_source_sha256': digest}
    for key, value in expected.items():
        if doc.get(key) != value:
            raise GuiProbeBlocked(f'controller {key} binding mismatch')
    for flag in ('illustrator_execution', 'smb_mutation', 'client_files_touched',
                 'cleanup_executed', 'production_ready'):
        if doc.get(flag) is not False:
            raise GuiProbeBlocked(f'forbidden controller flag {flag}')
    if doc.get('resumed_existing') is not (mode == 'resume-start'):
        raise GuiProbeBlocked('untrusted existing-attempt resume flag')
    if mode in ('check', 'resume-check'):
        required = ('READY_FOR_SYNTHETIC_TASK' if mode == 'check'
                    else 'READY_TO_RESUME_EXISTING_UNRUN_TASK')
        if (doc.get('state') != required
                or doc.get('windows_mutation') is not False
                or doc.get('registered_and_started') is not False
                or doc.get('gui_result') is not None):
            raise GuiProbeBlocked('check mode claimed mutation/execution')
        if type(doc.get('session_id')) is not int or doc['session_id'] < 1:
            raise GuiProbeBlocked('no active interactive session')
    if mode == 'resume-start':
        if (doc.get('state') != 'TASK_RESUMED_RESULT_NOT_YET_VERIFIED'
                or doc.get('windows_mutation') is not True
                or doc.get('registered_and_started') is not False
                or doc.get('gui_result') is not None):
            raise GuiProbeBlocked('untrusted continuation report')
        if type(doc.get('session_id')) is not int or doc['session_id'] < 1:
            raise GuiProbeBlocked('continuation session not verified')
    if mode == 'launch':
        if (doc.get('state') != 'TASK_STARTED_RESULT_NOT_YET_VERIFIED'
                or doc.get('windows_mutation') is not True
                or doc.get('registered_and_started') is not True
                or doc.get('gui_result') is not None):
            raise GuiProbeBlocked('untrusted launch report')
    if mode == 'verify':
        if doc.get('windows_mutation') is not False or doc.get('registered_and_started') is not False:
            raise GuiProbeBlocked('verify mode claimed mutation')
        if doc.get('state') not in ('WAITING_FOR_SYNTHETIC_RESULT',
                                     'SYNTHETIC_GUI_RESULT_REPORTED',
                                     'SYNTHETIC_GUI_RESULT_REQUIRES_REVIEW'):
            raise GuiProbeBlocked('unrecognized verify state')
        if doc['state'] == 'SYNTHETIC_GUI_RESULT_REPORTED':
            validate_result(doc.get('gui_result'), digest)
            if doc.get('session_id') != doc['gui_result']['expected_session_id']:
                raise GuiProbeBlocked('controller/result session mismatch')
        elif doc.get('gui_result') is not None and doc['state'] == 'WAITING_FOR_SYNTHETIC_RESULT':
            raise GuiProbeBlocked('waiting state includes result')
    return doc


def remote_run(args: argparse.Namespace) -> dict:
    controller, payload = source_check()
    code, digest = render(args.mode, controller, payload)
    encoded = base64.b64encode(PS_STDIN_BRIDGE.encode('utf-16le')).decode('ascii')
    try:
        cmd = ssh_command(host=args.host, user=args.user,
                          identity_file=args.identity_file,
                          known_hosts=args.known_hosts, encoded=encoded)
    except InspectionBlocked as e:
        raise GuiProbeBlocked(str(e)) from e
    if len(cmd[-1]) > 1024:
        raise GuiProbeBlocked('SSH bridge unexpectedly long')
    try:
        proc = subprocess.run(cmd, input=code, capture_output=True,
                              text=True, encoding='utf-8', errors='replace',
                              timeout=90, check=False)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise GuiProbeBlocked('SSH timeout/unreachable; read-only inspect before retry') from e
    if proc.returncode:
        raise GuiProbeBlocked(f'Windows refused/failed rc={proc.returncode}; preserve partial task/evidence')
    return validate_report(proc.stdout, mode=args.mode, digest=digest)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=MODES, required=True)
    parser.add_argument('--confirm-synthetic-gui-probe', action='store_true')
    parser.add_argument('--confirm-resume-existing-synthetic-task', action='store_true')
    parser.add_argument('--host')
    parser.add_argument('--user')
    parser.add_argument('--identity-file', type=Path)
    parser.add_argument('--known-hosts', type=Path)
    args = parser.parse_args(argv)
    try:
        source_check()
        if args.mode == 'source-check':
            if args.confirm_synthetic_gui_probe or args.confirm_resume_existing_synthetic_task:
                raise GuiProbeBlocked('confirmation not applicable to source-check')
            print('GDL_WINDOWS_W2_4_GUI_PROBE=SOURCE_CHECK_PASS')
            print('WINDOWS_WRITE=false ILLUSTRATOR_EXECUTION=false SMB_WRITE=false')
            return 0
        if (args.mode == 'launch') != bool(args.confirm_synthetic_gui_probe):
            raise GuiProbeBlocked('launch confirmation required only for new launch')
        if (args.mode == 'resume-start') != bool(args.confirm_resume_existing_synthetic_task):
            raise GuiProbeBlocked('resume-start requires its own explicit confirmation')
        if not all((args.host, args.user, args.identity_file, args.known_hosts)):
            raise GuiProbeBlocked('host/user/SSH paths must be explicit')
        doc = remote_run(args)
        print(json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=2))
        print('GDL_WINDOWS_W2_4_GUI_PROBE=' + doc['state'])
        return 0
    except GuiProbeBlocked as e:
        print('GDL_WINDOWS_W2_4_GUI_PROBE=BLOCKED reason=' + str(e), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

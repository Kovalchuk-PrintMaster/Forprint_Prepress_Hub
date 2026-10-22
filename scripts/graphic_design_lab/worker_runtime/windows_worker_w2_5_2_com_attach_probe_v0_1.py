#!/usr/bin/env python3
"""GDL W2.5.2 single-use READ-ONLY Illustrator COM attach diagnostic.

No JSX, no AI creation, no customer data, no SMB, no cleanup.
Restricted /export write scope for limited token, root stays RX.  One separate
synthetic Task Scheduler attempt under guarded W1 operator ACL. The only
Windows changes when explicitly launching are attempt evidence and one task.
"""
from __future__ import annotations

import argparse
import base64
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

import yaml

from windows_worker_w2_host_inspector_v0_1 import InspectionBlocked, ssh_command
from windows_worker_w2_3_workspace_initializer_v0_1 import PS_STDIN_BRIDGE

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / 'coordination/graphic_design_lab/worker_runtime/windows_worker_w1_pilot_contract_v0_1.yaml'
CTRL = Path(__file__).with_name('windows_worker_w2_5_2_com_attach_controller_v0_1.ps1')
RUNNER = Path(__file__).with_name('windows_worker_w2_5_2_com_attach_runner_v0_1.ps1')
TASK_ID = 'gdl-w252-limited-com-001'
ATTEMPT_ID = 'a0001'
TASK_NAME = 'ForPrint-GDL-W2-5-2-Limited-COM-Attach'
WINDOWS_ROOT = r'D:\ForPrint_Automation\GraficsDesignLab\Automation'
OP_SID = 'S-1-5-21-3087849371-1068859030-1179031902-1001'
SCHEMA = 'gdl_windows_w2_5_2_com_attach_controller_v0_1'
RUN_SCHEMA = 'gdl_windows_w2_5_2_com_attach_runner_v0_1'
MODES = ('source-check', 'check', 'launch', 'verify')


class ComProbeBlocked(RuntimeError):
    pass


def source_check() -> tuple[str, bytes]:
    for path in (CONTRACT, CTRL, RUNNER):
        if not path.is_file() or path.is_symlink():
            raise ComProbeBlocked('W2.5.2 dependency missing or symlink')
    c = yaml.safe_load(CONTRACT.read_text(encoding='utf-8'))
    policy = c.get('windows', {}).get('access_control', {})
    if (c.get('windows', {}).get('root') != WINDOWS_ROOT
            or c.get('authority', {}).get('worker_launch') is not False
            or c.get('authority', {}).get('production_publish') is not False
            or c.get('cleanup', {}).get('no_automatic_deletion') is not True
            or policy.get('policy_id') != 'gdl_windows_operator_full_control_dev_v0_3'
            or policy.get('operator_sid') != OP_SID
            or policy.get('root_owner') != r'BUILTIN\Administrators'
            or policy.get('root_inheritance_protected') is not True
            or policy.get('child_directories_inherit') is not True):
        raise ComProbeBlocked('W1 operator policy/authority mismatch')
    ctrl = CTRL.read_text(encoding='ascii')
    runner = RUNNER.read_bytes()
    if len(ctrl) > 30000 or len(runner) > 16000 or not runner.isascii():
        raise ComProbeBlocked('source too large or non-ascii')
    for marker in ('__MODE__', '__RUNNER_B64__', '__RUNNER_SHA__'):
        if ctrl.count(marker) != 1:
            raise ComProbeBlocked('controller injection marker missing/duplicate: ' + marker)
    for required in (TASK_ID, TASK_NAME, ATTEMPT_ID, OP_SID, WINDOWS_ROOT,
                     'Assert-ApprovedAcl', 'Register-ScheduledTask',
                     'Start-ScheduledTask', 'FileMode]::CreateNew',
                     'TASK_EXISTS_NO_RELAUNCH', 'NO_AUTOMATIC_CLEANUP', '-RunLevel Limited',
                     'Assert-DevExportAcl'):
        if required not in ctrl:
            raise ComProbeBlocked('controller required safety marker missing')
    run = runner.decode('ascii')
    for required in (TASK_ID, ATTEMPT_ID, RUN_SCHEMA, '__RUNNER_SOURCE_SHA__',
                     'GetActiveObject', 'Illustrator.Application', 'STAGE_COM_ROT_LOOKUP',
                     'STAGE_COM_VERSION', 'FileMode]::CreateNew',
                     'TOKEN_NOT_LIMITED', 'STAGE_TOKEN_ELEVATION'):
        if required not in run:
            raise ComProbeBlocked('runner marker missing')
    for forbidden in ('DoJavaScript', 'DoJavaScriptFile', 'New-Object -ComObject',
                      'Start-Process', 'Stop-Process', 'Unregister-ScheduledTask',
                      'Remove-Item', 'app.documents', '.saveAs(', 'app.open('):
        if forbidden.lower() in run.lower() or forbidden.lower() in ctrl.lower():
            raise ComProbeBlocked('unexpected GUI mutation command')
    return ctrl, runner


def render(mode: str, ctrl: str, runner: bytes) -> tuple[str, str]:
    if mode not in ('check', 'launch', 'verify') or runner.count(b'__RUNNER_SOURCE_SHA__') != 1:
        raise ComProbeBlocked('invalid mode or runner SHA binding marker')
    # Runner hash is checked both on s01 and Windows; binding marker in runner
    # is populated with the source-template hash (avoids circular file digest).
    template_sha = sha256(runner).hexdigest()
    bound = runner.replace(b'__RUNNER_SOURCE_SHA__', template_sha.encode('ascii'))
    digest = sha256(bound).hexdigest()
    replacements = {'__MODE__': mode, '__RUNNER_B64__': base64.b64encode(bound).decode('ascii'),
                    '__RUNNER_SHA__': digest}
    for k, v in replacements.items():
        ctrl = ctrl.replace(k, v)
    if any(k in ctrl for k in replacements):
        raise ComProbeBlocked('unresolved controller marker')
    return ctrl, digest


def validate_report(output: str, *, mode: str, runner_sha: str) -> dict:
    try:
        doc = json.loads(output.strip())
    except (ValueError, TypeError) as exc:
        raise ComProbeBlocked('Windows did not return single JSON') from exc
    if not isinstance(doc, dict) or doc.get('schema_version') != SCHEMA:
        raise ComProbeBlocked('controller schema mismatch')
    expected = dict(mode=mode, host='PREPRESS', ssh_account=r'PREPRESS\Work',
                    task_id=TASK_ID, attempt_id=ATTEMPT_ID,
                    task_name=TASK_NAME, runner_sha256=runner_sha)
    for k, val in expected.items():
        if doc.get(k) != val:
            raise ComProbeBlocked('controller binding mismatch: ' + k)
    for flag in ('client_files_touched', 'smb_mutation', 'cleanup_executed',
                 'illustrator_document_mutation', 'production_ready'):
        if doc.get(flag) is not False:
            raise ComProbeBlocked('forbidden controller flag: ' + flag)
    if doc.get('scheduler_run_level') != 'Limited' or doc.get('scoped_export_write') is not False:
        raise ComProbeBlocked('untrusted runlevel/export scope')
    if mode == 'check':
        if (doc.get('state') != 'READY_FOR_LIMITED_COM_PROBE'
                or doc.get('windows_mutation') is not False
                or doc.get('com_result') is not None
                or type(doc.get('session_id')) is not int or doc['session_id'] < 1):
            raise ComProbeBlocked('check result invalid')
    elif mode == 'launch':
        if (doc.get('state') != 'LIMITED_COM_TASK_STARTED_RESULT_PENDING'
                or doc.get('windows_mutation') is not True
                or doc.get('com_result') is not None
                or type(doc.get('session_id')) is not int or doc['session_id'] < 1):
            raise ComProbeBlocked('launch result invalid')
    else:
        if doc.get('windows_mutation') is not False:
            raise ComProbeBlocked('verify claimed mutation')
        if doc.get('state') not in ('WAITING_FOR_LIMITED_COM_RESULT',
                                    'LIMITED_COM_ATTACH_REQUIRES_REVIEW',
                                    'LIMITED_COM_READONLY_ATTACH_VERIFIED'):
            raise ComProbeBlocked('verify state invalid')
        result = doc.get('com_result')
        if doc['state'] == 'WAITING_FOR_LIMITED_COM_RESULT' and result is not None:
            raise ComProbeBlocked('waiting with result')
        if doc['state'] == 'LIMITED_COM_READONLY_ATTACH_VERIFIED':
            if not isinstance(result, dict) or result.get('schema_version') != RUN_SCHEMA:
                raise ComProbeBlocked('runner schema invalid')
            expected_run = dict(task_id=TASK_ID, attempt_id=ATTEMPT_ID,
                                host='PREPRESS', windows_account=r'PREPRESS\Work',
                                state='PASS_COM_READONLY_ATTACH', runner_sha256=runner_sha,
                                phase='STAGE_DONE', error_code='NONE', error_hresult=None,
                                illustrator_document_mutation=False,
                                token_elevated=False, token_elevation_type=3,
                                token_limited_verified=True,
                                production_ready=False, smb_mutation=False,
                                client_files_touched=False, cleanup_executed=False)
            for k, val in expected_run.items():
                if result.get(k) != val:
                    raise ComProbeBlocked('runner binding mismatch: ' + k)
            if type(result.get('session_id')) is not int or result['session_id'] < 1 or doc.get('session_id') != result['session_id']:
                raise ComProbeBlocked('session binding invalid')
            if type(result.get('preexisting_illustrator_pid')) is not int or result['preexisting_illustrator_pid'] < 1:
                raise ComProbeBlocked('Illustrator PID invalid')
            if not isinstance(result.get('illustrator_version'), str) or len(result['illustrator_version']) > 80 or not result['illustrator_version'].strip():
                raise ComProbeBlocked('Illustrator version invalid')
    return doc


def remote_run(args: argparse.Namespace) -> dict:
    ctrl, runner = source_check()
    payload, digest = render(args.mode, ctrl, runner)
    bridge = base64.b64encode(PS_STDIN_BRIDGE.encode('utf-16le')).decode('ascii')
    try:
        cmd = ssh_command(host=args.host, user=args.user,
                          identity_file=args.identity_file, known_hosts=args.known_hosts,
                          encoded=bridge)
    except InspectionBlocked as exc:
        raise ComProbeBlocked(str(exc)) from exc
    if len(cmd[-1]) > 1024:
        raise ComProbeBlocked('SSH bridge too long')
    try:
        proc = subprocess.run(cmd, input=payload, capture_output=True,
                              encoding='utf-8', errors='replace', text=True,
                              timeout=90, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ComProbeBlocked('SSH error/timeout; inspect before any retry') from exc
    if proc.returncode:
        raise ComProbeBlocked(f'Windows refused/failed rc={proc.returncode}; preserve evidence, never retry launch')
    return validate_report(proc.stdout, mode=args.mode, runner_sha=digest)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode', choices=MODES, required=True)
    ap.add_argument('--confirm-limited-com-attach-probe', action='store_true')
    ap.add_argument('--host')
    ap.add_argument('--user')
    ap.add_argument('--identity-file', type=Path)
    ap.add_argument('--known-hosts', type=Path)
    args = ap.parse_args(argv)
    try:
        source_check()
        if args.mode == 'source-check':
            if args.confirm_limited_com_attach_probe:
                raise ComProbeBlocked('confirmation invalid for source-check')
            print('GDL_W2_5_2_LIMITED_COM=SOURCE_CHECK_PASS')
            return 0
        if (args.mode == 'launch') != args.confirm_limited_com_attach_probe:
            raise ComProbeBlocked('launch requires exact one-time confirmation')
        if not all((args.host, args.user, args.identity_file, args.known_hosts)):
            raise ComProbeBlocked('explicit host/user/ssh key and hostfile required')
        result = remote_run(args)
        print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False))
        print('GDL_W2_5_2_LIMITED_COM=' + result['state'])
        return 0
    except ComProbeBlocked as exc:
        print('GDL_W2_5_2_LIMITED_COM=BLOCKED reason=' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

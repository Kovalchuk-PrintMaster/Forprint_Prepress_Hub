#!/usr/bin/env python3
"""W2.5.3 single-attempt *synthetic* Illustrator COM/JSX proof over verified SSH.

W1/W2.3 approved Windows DEV FullControl workspace. New-only Task Scheduler launch (requires
explicit confirmation). No customer data/SMB/cleanup. No auto retry.
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
CONTROLLER = Path(__file__).with_name('windows_worker_w2_5_3_limited_native_illustrator_controller_v0_1.ps1')
RUNNER = Path(__file__).with_name('windows_worker_w2_5_3_limited_native_illustrator_runner_v0_1.ps1')
JSX = Path(__file__).with_name('windows_worker_w2_5_3_limited_native_illustrator_proof_v0_1.jsx')
WINDOWS_ROOT = r'D:\ForPrint_Automation\GraficsDesignLab\Automation'
TASK_ID = 'gdl-w253-limited-native-001'
ATTEMPT_ID = 'a0001'
TASK_NAME = 'ForPrint-GDL-W2-5-3-Limited-Native-Proof'
SCHEMA = 'gdl_windows_w2_5_3_native_controller_v0_1'
RUN_SCHEMA = 'gdl_windows_w2_5_3_native_runner_v0_1'
MODES = ('source-check', 'check', 'launch', 'verify')
SHA = re.compile(r'^[0-9a-f]{64}$')


class NativeBlocked(RuntimeError):
    pass


def source_check() -> tuple[str, bytes, bytes]:
    for p in (CONTRACT, CONTROLLER, RUNNER, JSX):
        if not p.is_file() or p.is_symlink():
            raise NativeBlocked('W2.5.3 source missing or symlinked')
    c = yaml.safe_load(CONTRACT.read_text(encoding='utf-8'))
    if (c.get('windows', {}).get('root') != WINDOWS_ROOT or
            c.get('authority', {}).get('worker_launch') is not False or
            c.get('authority', {}).get('production_publish') is not False or
            c.get('cleanup', {}).get('no_automatic_deletion') is not True):
        raise NativeBlocked('W1 contract grants unexpected authority')
    policy = c.get('windows', {}).get('access_control', {})
    if (policy.get('policy_id') != 'gdl_windows_operator_full_control_dev_v0_3'
            or policy.get('operator_sid') != 'S-1-5-21-3087849371-1068859030-1179031902-1001'
            or policy.get('expected_aces') != {
                'S-1-5-18': 'FullControl',
                'S-1-5-32-544': 'FullControl',
                'S-1-5-21-3087849371-1068859030-1179031902-1001': 'FullControl'}
            or policy.get('root_owner') != r'BUILTIN\Administrators'
            or policy.get('root_inheritance_protected') is not True
            or policy.get('child_directories_inherit') is not True):
        raise NativeBlocked('W1 operator ACL policy mismatch')
    ctrl = CONTROLLER.read_text(encoding='ascii')
    runner, jsx = RUNNER.read_bytes(), JSX.read_bytes()
    if any(len(x) > 24000 for x in (ctrl.encode('ascii'), runner, jsx)):
        raise NativeBlocked('unexpectedly large W2.5.3 source')
    for marker in ('__MODE__', '__RUNNER_B64__', '__JSX_B64__', '__RUNNER_SHA__', '__JSX_SHA__'):
        if ctrl.count(marker) != 1:
            raise NativeBlocked('controller injection marker missing or duplicated')
    if 'Assert-ApprovedAcl' not in ctrl or "$OperatorSid = 'S-1-5-21-3087849371-1068859030-1179031902-1001'" not in ctrl:
        raise NativeBlocked('W2.5.3 ACL guard missing')
    for mark in (TASK_NAME, TASK_ID, ATTEMPT_ID, WINDOWS_ROOT,
                 'Start-ScheduledTask', 'Register-ScheduledTask', 'FileMode]::CreateNew', '-RunLevel Limited',
                 'TASK_EXISTS_NO_RELAUNCH', 'NO_AUTOMATIC_CLEANUP'):
        if mark not in ctrl:
            raise NativeBlocked('controller safety marker missing')
    runtext = runner.decode('ascii')
    for mark in (TASK_ID, ATTEMPT_ID, RUN_SCHEMA, '__JSX_SOURCE_SHA__', 'DoJavaScript',
                 'Illustrator.Application', 'GetActiveObject', 'Get-FileHash', 'FileMode]::CreateNew',
                 'token_limited_verified', 'STAGE_COM_ROT_LOOKUP'):
        if mark not in runtext:
            raise NativeBlocked('runner proof marker missing')
    js = jsx.decode('ascii')
    for mark in (TASK_ID, 'ZapfChanceryC', 'saveAs', 'app.open',
                 'TextType.AREATEXT', 'DONOTSAVECHANGES',
                 'FORPRINT_NATIVE_AI_REOPENED', 'NO_DIALOGS_OR_ALERTS'):
        if mark not in js:
            raise NativeBlocked('JSX native proof marker missing')
    for bad in ('alert(', 'confirm(', 'prompt(', 'Folder.myDocuments', 'File.openDialog'):
        if bad in js:
            raise NativeBlocked('JSX must not request user interaction')
    return ctrl, runner, jsx


def render(mode: str, controller: str, runner: bytes, jsx: bytes) -> tuple[str, str, str]:
    if mode not in ('check', 'launch', 'verify'):
        raise NativeBlocked('invalid remote mode')
    jsx_sha = sha256(jsx).hexdigest()
    if runner.count(b'__JSX_SOURCE_SHA__') != 1:
        raise NativeBlocked('runner JSX binding marker invalid')
    runner = runner.replace(b'__JSX_SOURCE_SHA__', jsx_sha.encode('ascii'))
    runner_sha = sha256(runner).hexdigest()
    args = {'__MODE__': mode, '__RUNNER_B64__': base64.b64encode(runner).decode('ascii'),
            '__JSX_B64__': base64.b64encode(jsx).decode('ascii'),
            '__RUNNER_SHA__': runner_sha, '__JSX_SHA__': jsx_sha}
    for key, value in args.items():
        controller = controller.replace(key, value)
    if any(mark in controller for mark in args):
        raise NativeBlocked('unresolved template marker')
    return controller, runner_sha, jsx_sha


def validate_report(output: str, mode: str, runner_sha: str, jsx_sha: str) -> dict:
    try:
        doc = json.loads(output.strip())
    except (TypeError, ValueError) as exc:
        raise NativeBlocked('Windows returned no single JSON report') from exc
    if not isinstance(doc, dict) or doc.get('schema_version') != SCHEMA:
        raise NativeBlocked('Windows native controller schema mismatch')
    expected = {'mode': mode, 'host': 'PREPRESS', 'ssh_account': r'PREPRESS\Work',
                'task_id': TASK_ID, 'attempt_id': ATTEMPT_ID, 'task_name': TASK_NAME,
                'jsx_sha256': jsx_sha, 'runner_sha256': runner_sha}
    for k, val in expected.items():
        if doc.get(k) != val:
            raise NativeBlocked('Windows native controller binding mismatch: ' + k)
    if doc.get('scheduler_run_level') != 'Limited':
        raise NativeBlocked('unexpected scheduler run level')
    if doc.get('smb_mutation') is not False or doc.get('client_files_touched') is not False or doc.get('cleanup_executed') is not False or doc.get('production_ready') is not False:
        raise NativeBlocked('Forbidden native controller side effect claimed')
    if mode == 'check':
        if (doc.get('state') != 'READY_FOR_LIMITED_NATIVE_PROOF' or
                doc.get('windows_mutation') is not False or
                doc.get('native_result') is not None):
            raise NativeBlocked('read-only preflight invalid')
        if type(doc.get('session_id')) is not int or doc['session_id'] < 1:
            raise NativeBlocked('missing interactive session')
    elif mode == 'launch':
        if (doc.get('state') != 'LIMITED_NATIVE_PROOF_STARTED_RESULT_PENDING' or
                doc.get('windows_mutation') is not True or
                doc.get('native_result') is not None or
                type(doc.get('session_id')) is not int or doc['session_id'] < 1):
            raise NativeBlocked('launch not proven')
    else:
        if doc.get('windows_mutation') is not False:
            raise NativeBlocked('verification must be read-only')
        if doc.get('state') not in ('WAITING_FOR_LIMITED_NATIVE_RESULT',
                                    'LIMITED_NATIVE_RESULT_REQUIRES_REVIEW',
                                    'LIMITED_NATIVE_AI_REOPENED_VERIFIED'):
            raise NativeBlocked('unexpected native verification state')
        if doc['state'] == 'LIMITED_NATIVE_AI_REOPENED_VERIFIED':
            r = doc.get('native_result')
            if not isinstance(r, dict) or r.get('schema_version') != RUN_SCHEMA:
                raise NativeBlocked('native runner result malformed')
            for key, val in ({'state': 'PASS_NATIVE_AI_REOPENED', 'task_id': TASK_ID,
                              'attempt_id': ATTEMPT_ID, 'host': 'PREPRESS',
                              'windows_account': r'PREPRESS\Work',
                              'jsx_sha256': jsx_sha, 'runner_sha256': runner_sha,
                              'font_name': 'ZapfChanceryC',
                              'token_elevated': False, 'token_elevation_type': 3,
                              'token_limited_verified': True,
                              'illustrator_executed': True,
                              'native_ai_saved_reopened': True,
                              'editable_area_text': True,
                              'production_ready': False,
                              'smb_mutation': False, 'client_files_touched': False,
                              'cleanup_executed': False, 'error_code': 'NONE',
                              'phase': 'STAGE_DONE'}).items():
                if r.get(key) != val:
                    raise NativeBlocked('native runner evidence mismatch: ' + key)
            if type(r.get('session_id')) is not int or r['session_id'] < 1 or doc.get('session_id') != r['session_id']:
                raise NativeBlocked('native session mismatch')
            if type(r.get('preexisting_illustrator_pid')) is not int or r['preexisting_illustrator_pid'] < 1:
                raise NativeBlocked('preexisting Illustrator identity missing')
            if not SHA.fullmatch(str(r.get('ai_sha256'))) or type(r.get('ai_bytes')) is not int or r['ai_bytes'] < 1000:
                raise NativeBlocked('native artifact digest/size missing')
        elif doc.get('native_result') is not None and doc['state'] == 'WAITING_FOR_LIMITED_NATIVE_RESULT':
            raise NativeBlocked('waiting result contradiction')
    return doc


def remote_run(args: argparse.Namespace) -> dict:
    controller, runner, jsx = source_check()
    content, runner_sha, jsx_sha = render(args.mode, controller, runner, jsx)
    bridge = base64.b64encode(PS_STDIN_BRIDGE.encode('utf-16le')).decode('ascii')
    try:
        command = ssh_command(host=args.host, user=args.user,
                              identity_file=args.identity_file,
                              known_hosts=args.known_hosts, encoded=bridge)
    except InspectionBlocked as e:
        raise NativeBlocked(str(e)) from e
    if len(command[-1]) > 1024:
        raise NativeBlocked('SSH command unexpectedly long')
    try:
        result = subprocess.run(command, input=content, capture_output=True,
                                encoding='utf-8', errors='replace', text=True,
                                timeout=100, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise NativeBlocked('SSH failed or timed out; inspect before further action') from exc
    if result.returncode != 0:
        raise NativeBlocked('Windows refused/failed operation rc=' + str(result.returncode) + '; do not retry launch')
    return validate_report(result.stdout, args.mode, runner_sha, jsx_sha)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode', choices=MODES, required=True)
    ap.add_argument('--confirm-limited-native-illustrator', action='store_true')
    ap.add_argument('--host')
    ap.add_argument('--user')
    ap.add_argument('--identity-file', type=Path)
    ap.add_argument('--known-hosts', type=Path)
    a = ap.parse_args(argv)
    try:
        source_check()
        if a.mode == 'source-check':
            if a.confirm_limited_native_illustrator:
                raise NativeBlocked('confirmation forbidden for source-check')
            print('GDL_W2_5_3_LIMITED_NATIVE=SOURCE_CHECK_PASS')
            print('WINDOWS_WRITE=false SMB_WRITE=false ILLUSTRATOR_EXECUTION=false')
            return 0
        if (a.mode == 'launch') != a.confirm_limited_native_illustrator:
            raise NativeBlocked('launch requires separate exact confirmation')
        if not all((a.host, a.user, a.identity_file, a.known_hosts)):
            raise NativeBlocked('explicit SSH arguments required')
        doc = remote_run(a)
        print(json.dumps(doc, sort_keys=True, ensure_ascii=False, indent=2))
        print('GDL_W2_5_3_LIMITED_NATIVE=' + doc['state'])
        return 0
    except NativeBlocked as exc:
        print('GDL_W2_5_3_LIMITED_NATIVE=BLOCKED reason=' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""W2.7-C2: read-only Windows staged native candidate execution prerequisites.

Does NOT extract, start a task, attach COM, execute JSX, or authorize dispatch.
W2.7-B independently stages/verifies the exact W2.7-C1 synthetic package.
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

from gdl_w27_illustrator_task_package_v0_1 import PackageBlocked, read_regular, repo_tmp_path
from gdl_w27c_native_candidate_review_v0_1 import (
    CandidateBlocked, inspect_candidate, source_check as native_source_check,
    TASK, ATTEMPT,
)
from gdl_w27b_windows_package_staging_v0_1 import (
    StageBlocked, source_check as stage_source_check,
)
from windows_worker_w2_host_inspector_v0_1 import InspectionBlocked, ssh_command
from windows_worker_w2_3_workspace_initializer_v0_1 import PS_STDIN_BRIDGE

ROOT = Path(__file__).resolve().parents[3]
CONTROLLER = Path(__file__).with_suffix('.ps1')
SCHEMA = 'gdl_w27c2_native_execution_preflight_v0_1'
JSX_SHA = '98780bcd7939df58f16aa0e123ced5efc4956ed43cc6438d0516b43d4d819902'
JSX_BYTES = 3791
ARCHIVE_SHA = 'd1949844b3ab2d68936facf8012e6b8fba1ecd1134597f2e6f4139ef1449b3e7'
ARCHIVE_BYTES = 5120
SHA_RE = re.compile(r'^[0-9a-f]{64}$')
STATES = {
    'STAGED_NATIVE_HOST_PREREQUISITES_PRESENT_AUTHORITY_PENDING',
    'WAITING_FOR_INTERACTIVE_SESSION_NOT_AUTHORIZED',
    'WAITING_FOR_ILLUSTRATOR_OR_DESKTOP_NOT_AUTHORIZED',
}
MARKERS = ('__TASK_ID__', '__ATTEMPT_ID__', '__ARCHIVE_SHA__',
           '__ARCHIVE_BYTES__', '__JSX_SHA__', '__JSX_BYTES__')


class PreflightBlocked(RuntimeError):
    pass


def source_check() -> str:
    """Fail closed on source and authority changes; never changes Windows."""
    try:
        stage_source_check()
        profile, script = native_source_check()
    except (StageBlocked, CandidateBlocked, PackageBlocked, OSError) as exc:
        raise PreflightBlocked('W2.7-B or W2.7-C1 prerequisite invalid') from exc
    if (profile['launch_authorized'] is not False or
            profile['blueprint_review_pending'] is not True or
            profile['runner_implementation'] != 'NOT_IMPLEMENTED' or
            profile['jsx_sha256'] != JSX_SHA or profile['jsx_bytes'] != JSX_BYTES or
            sha256(script).hexdigest() != JSX_SHA):
        raise PreflightBlocked('profile authority or digest changed')
    if not CONTROLLER.is_file() or CONTROLLER.is_symlink():
        raise PreflightBlocked('PowerShell controller absent/unsafe')
    raw = CONTROLLER.read_bytes()
    if not raw.isascii() or not 150 < len(raw) <= 24000:
        raise PreflightBlocked('PowerShell source size/encoding invalid')
    ps = raw.decode('ascii')
    for marker in MARKERS:
        if ps.count(marker) != 1:
            raise PreflightBlocked('controller template marker missing/duplicated')
    for expected in ('STAGED_NATIVE_HOST_PREREQUISITES_PRESENT_AUTHORITY_PENDING',
                     'WAITING_FOR_INTERACTIVE_SESSION_NOT_AUTHORIZED',
                     'WAITING_FOR_ILLUSTRATOR_OR_DESKTOP_NOT_AUTHORIZED',
                     'STAGED_ZIP_DIGEST_MISMATCH', 'JSX_DIGEST_MISMATCH',
                     'ARCHIVE_MANIFEST_BINDING_CHANGED', 'STAGING_RECEIPT_BINDING_MISMATCH',
                     'EXISTING_EXECUTION_OR_OUTPUT_EVIDENCE',
                     'NO_AUTOMATIC_CLEANUP', 'NO_COM_EXECUTION', 'NO_TASK_SCHEDULER_MUTATION'):
        if expected not in ps:
            raise PreflightBlocked('read-only controller guard absent')
    for forbidden in ('Start-ScheduledTask', 'Register-ScheduledTask', 'DoJavaScript',
                      'GetActiveObject', 'Remove-Item', 'Set-Acl', 'Start-Process',
                      'Stop-Process', 'WriteAllBytes', 'CreateDirectory',
                      'ExtractToDirectory', 'Expand-Archive'):
        if forbidden.lower() in ps.lower():
            raise PreflightBlocked('potentially mutating or executing controller source')
    return ps


def check_archive(path: Path, expected: str) -> bytes:
    if expected != ARCHIVE_SHA or not SHA_RE.fullmatch(expected):
        raise PreflightBlocked('expected candidate digest not pinned to W2.7-C1')
    try:
        safe_path = repo_tmp_path(path, must_exist=True)
        if safe_path.suffix != '.zip':
            raise PreflightBlocked('expected ZIP in repository tmp')
        raw = read_regular(safe_path, 262144)
        profile, jsx = native_source_check()
        result = inspect_candidate(raw, expected, profile, jsx)
    except (PackageBlocked, CandidateBlocked, OSError) as exc:
        raise PreflightBlocked('native candidate package verification failed') from exc
    if (len(raw) != ARCHIVE_BYTES or sha256(raw).hexdigest() != ARCHIVE_SHA or
            result.get('state') != 'SYNTHETIC_NATIVE_CANDIDATE_VERIFIED_NOT_EXECUTABLE_BY_WORKER' or
            result.get('worker_launch_authorized') is not False):
        raise PreflightBlocked('package bytes or forbidden authority changed')
    return raw


def render(ps: str) -> str:
    args = {'__TASK_ID__': TASK, '__ATTEMPT_ID__': ATTEMPT,
            '__ARCHIVE_SHA__': ARCHIVE_SHA, '__ARCHIVE_BYTES__': str(ARCHIVE_BYTES),
            '__JSX_SHA__': JSX_SHA, '__JSX_BYTES__': str(JSX_BYTES)}
    for key, val in args.items():
        if ps.count(key) != 1:
            raise PreflightBlocked('unexpected template marker')
        ps = ps.replace(key, val)
    if any(key in ps for key in args):
        raise PreflightBlocked('unresolved template marker')
    return ps


def validate_report(text: str) -> dict:
    try:
        r = json.loads(text.strip())
    except (TypeError, ValueError) as exc:
        raise PreflightBlocked('Windows did not return single JSON result') from exc
    if not isinstance(r, dict):
        raise PreflightBlocked('Windows result not an object')
    expect = {'schema_version': SCHEMA, 'task_id': TASK, 'attempt_id': ATTEMPT,
              'host': 'PREPRESS', 'windows_account': r'PREPRESS\Work',
              'archive_sha256': ARCHIVE_SHA, 'archive_bytes': ARCHIVE_BYTES,
              'jsx_sha256': JSX_SHA, 'jsx_bytes': JSX_BYTES}
    for k, value in expect.items():
        if r.get(k) != value or (type(value) is int and type(r.get(k)) is not int):
            raise PreflightBlocked('Windows result binding mismatch')
    if r.get('state') not in STATES:
        raise PreflightBlocked('invalid readiness state')
    for k in ('windows_mutation', 'payload_extracted', 'illustrator_execution',
              'com_attach_performed', 'scheduled_tasks_mutated', 'worker_launch_authorized',
              'dispatch_authorized', 'production_ready', 'accepted', 'cleanup_executed',
              'client_files_touched', 'smb_mutation'):
        if r.get(k) is not False:
            raise PreflightBlocked('forbidden Windows side effect or authority')
    if not isinstance(r.get('staging_receipt_sha256'), str) or not SHA_RE.fullmatch(r['staging_receipt_sha256']):
        raise PreflightBlocked('staging evidence digest missing')
    session, pid = r.get('session_id'), r.get('preexisting_illustrator_pid')
    if r['state'] == 'STAGED_NATIVE_HOST_PREREQUISITES_PRESENT_AUTHORITY_PENDING':
        if type(session) is not int or session <= 0 or type(pid) is not int or pid <= 0:
            raise PreflightBlocked('native desktop/Illustrator identity absent')
    elif pid is not None or (session is not None and (type(session) is not int or session < 1)):
        raise PreflightBlocked('waiting state contains inconsistent process evidence')
    return r


def remote_check(args: argparse.Namespace, ps: str) -> dict:
    encoded = base64.b64encode(PS_STDIN_BRIDGE.encode('utf-16le')).decode('ascii')
    try:
        cmd = ssh_command(host=args.host, user=args.user, identity_file=args.identity_file,
                          known_hosts=args.known_hosts, encoded=encoded)
    except InspectionBlocked as exc:
        raise PreflightBlocked('SSH binding blocked') from exc
    if len(cmd[-1]) > 1024:
        raise PreflightBlocked('SSH bridge command unexpectedly long')
    try:
        p = subprocess.run(cmd, input=render(ps), capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=90, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PreflightBlocked('SSH failed/timed out; do not blindly retry') from exc
    if p.returncode:
        raise PreflightBlocked(f'Windows read-only preflight refused rc={p.returncode}')
    return validate_report(p.stdout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('source-check', 'check'), required=True)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--expected-archive-sha256')
    parser.add_argument('--host')
    parser.add_argument('--user')
    parser.add_argument('--identity-file', type=Path)
    parser.add_argument('--known-hosts', type=Path)
    a = parser.parse_args(argv)
    try:
        ps = source_check()
        if a.mode == 'source-check':
            if any((a.archive,a.expected_archive_sha256,a.host,a.user,a.identity_file,a.known_hosts)):
                raise PreflightBlocked('source-check accepts no remote arguments')
            print('GDL_W27C2_NATIVE_PREFLIGHT=SOURCE_CHECK_PASS')
            print('WINDOWS_WRITE=false JSX_EXECUTION=false LAUNCH_AUTHORITY=false')
            return 0
        if (not a.archive or not a.expected_archive_sha256 or
                not all((a.host,a.user,a.identity_file,a.known_hosts)) or
                a.host != '192.168.50.69' or a.user != 'work'):
            raise PreflightBlocked('explicit pinned synthetic-only input and SSH binding required')
        check_archive(a.archive,a.expected_archive_sha256)
        doc = remote_check(a,ps)
        print(json.dumps(doc,ensure_ascii=False,sort_keys=True,indent=2))
        print('GDL_W27C2_NATIVE_PREFLIGHT='+doc['state'])
        return 0
    except (PreflightBlocked, OSError, ValueError) as exc:
        print('GDL_W27C2_NATIVE_PREFLIGHT=BLOCKED reason='+str(exc),file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

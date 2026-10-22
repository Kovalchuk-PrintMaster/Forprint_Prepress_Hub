#!/usr/bin/env python3
"""ForPrint GDL W2.7-B: explicitly confirmed *synthetic-only opaque ZIP staging*.

Input is a W2.7-A independently verified archive, direct child of repo tmp/.
Windows stores exact bytes once under a fresh attempt (no unpack/no JSX/no Task Scheduler).
Staging is NOT dispatch, execution, acceptance, or production authority.
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

from gdl_w27_illustrator_task_package_v0_1 import (
    MAX_ARCHIVE, PackageBlocked, check_static, inspect_zip, repo_tmp_path,
)
from windows_worker_w2_host_inspector_v0_1 import InspectionBlocked, ssh_command
from windows_worker_w2_3_workspace_initializer_v0_1 import PS_STDIN_BRIDGE

ROOT = Path(__file__).resolve().parents[3]
CONTROLLER = Path(__file__).with_suffix('.ps1')
SCHEMA = 'gdl_w27b_windows_stage_controller_v0_1'
RECEIPT_SCHEMA = 'gdl_w27b_windows_stage_receipt_v0_1'
SHA = re.compile(r'^[0-9a-f]{64}$')
MAX_STAGE = 262144  # W2.7-B pilot; future large-asset transport is separate.
REMOTE_MODES = {'check', 'stage', 'verify'}


class StageBlocked(RuntimeError):
    pass


def source_check() -> str:
    try:
        check_static()
    except (PackageBlocked, OSError) as exc:
        raise StageBlocked('W2.7-A source/authority not verified') from exc
    if not CONTROLLER.is_file() or CONTROLLER.is_symlink():
        raise StageBlocked('W2.7-B PowerShell source missing/unsafe')
    raw = CONTROLLER.read_bytes()
    if len(raw) > 24000 or not raw.isascii():
        raise StageBlocked('W2.7-B PowerShell source size/encoding invalid')
    s = raw.decode('ascii')
    for name in ('__MODE__', '__ARCHIVE_B64__', '__ARCHIVE_SHA__',
                 '__ARCHIVE_BYTES__', '__TASK_ID__', '__ATTEMPT_ID__'):
        if s.count(name) != 1:
            raise StageBlocked('source template binding invalid: ' + name)
    required = ('SYNTHETIC_PACKAGE_STAGED_NOT_EXECUTED',
                'SYNTHETIC_STAGE_SHA_VERIFIED_NOT_EXECUTED',
                'TASK_EXISTS_NO_RESTAGE', 'CreateNew', 'SafeDir', 'STAGED_ARCHIVE_CHANGED',
                'NO_AUTOMATIC_CLEANUP', 'NO_TASK_SCHEDULER', 'NO_JSX_EXECUTION')
    if any(x not in s for x in required):
        raise StageBlocked('Windows stage safety guard absent')
    for forbidden in ('Start-ScheduledTask', 'Register-ScheduledTask', 'DoJavaScript',
                      'Remove-Item', 'Set-Acl', 'Start-Process', 'Stop-Process',
                      'Unregister-ScheduledTask', 'Expand-Archive', 'ExtractToDirectory'):
        if forbidden.lower() in s.lower():
            raise StageBlocked('Windows stage contains forbidden operation')
    return s


def load_archive(path: Path, expected_sha: str) -> tuple[dict, bytes, str]:
    if not SHA.fullmatch(expected_sha):
        raise StageBlocked('expected archive digest invalid')
    try:
        path = repo_tmp_path(path, must_exist=True)
        if path.suffix != '.zip' or path.stat().st_size > MAX_STAGE or path.stat().st_size < 200:
            raise StageBlocked('staging pilot accepts only ZIP up to 256 KiB')
        raw = path.read_bytes()
        manifest, digest = inspect_zip(raw)
    except (PackageBlocked, OSError) as exc:
        raise StageBlocked('W2.7-A archive structural verification failed') from exc
    if digest != expected_sha or sha256(raw).hexdigest() != expected_sha:
        raise StageBlocked('independent archive SHA256 mismatch')
    if manifest['authority']['worker_launch'] is not False or manifest['data_class'] != 'SYNTHETIC_ONLY':
        raise StageBlocked('package scope or execution authority invalid')
    return manifest, raw, digest


def render(mode: str, script: str, manifest: dict, archive: bytes, digest: str) -> str:
    if mode not in REMOTE_MODES:
        raise StageBlocked('remote mode invalid')
    replacements = {
        '__MODE__': mode,
        '__ARCHIVE_B64__': base64.b64encode(archive).decode('ascii'),
        '__ARCHIVE_SHA__': digest,
        '__ARCHIVE_BYTES__': str(len(archive)),
        '__TASK_ID__': manifest['task_id'],
        '__ATTEMPT_ID__': manifest['attempt_id'],
    }
    for key, value in replacements.items():
        if script.count(key) != 1:
            raise StageBlocked('missing or duplicated template key')
        script = script.replace(key, value)
    if any(key in script for key in replacements):
        raise StageBlocked('unresolved remote template key')
    return script


def validate_report(raw: str, mode: str, manifest: dict, digest: str, length: int) -> dict:
    try:
        doc = json.loads(raw.strip())
    except (TypeError, ValueError) as exc:
        raise StageBlocked('Windows response not single JSON') from exc
    if not isinstance(doc, dict):
        raise StageBlocked('Windows response not an object')
    expected = {
        'schema_version': SCHEMA, 'mode': mode, 'host': 'PREPRESS',
        'ssh_account': r'PREPRESS\Work',
        'task_id': manifest['task_id'], 'attempt_id': manifest['attempt_id'],
        'archive_sha256': digest, 'archive_bytes': length,
    }
    for key, value in expected.items():
        if doc.get(key) != value or (type(value) is int and type(doc.get(key)) is not int):
            raise StageBlocked('Windows stage binding mismatch: ' + key)
    for k in ('payload_extracted', 'illustrator_execution', 'worker_launch_authorized',
              'production_ready', 'accepted', 'scheduled_tasks_mutated',
              'client_files_touched', 'smb_mutation', 'cleanup_executed'):
        if doc.get(k) is not False:
            raise StageBlocked('forbidden stage side effect reported: ' + k)
    states = {
        'check': 'READY_FOR_SYNTHETIC_STAGE',
        'stage': 'SYNTHETIC_PACKAGE_STAGED_NOT_EXECUTED',
        'verify': 'SYNTHETIC_STAGE_SHA_VERIFIED_NOT_EXECUTED',
    }
    if doc.get('state') != states[mode] or doc.get('windows_mutation') is not (mode == 'stage'):
        raise StageBlocked('Windows staging state invalid')
    rsha = doc.get('staging_receipt_sha256')
    if mode == 'check':
        if rsha is not None:
            raise StageBlocked('check must not contain staging receipt')
    elif not isinstance(rsha, str) or not SHA.fullmatch(rsha):
        raise StageBlocked('staging receipt digest absent/invalid')
    return doc


def remote_run(args: argparse.Namespace, manifest: dict, archive: bytes, digest: str) -> dict:
    script = render(args.mode, source_check(), manifest, archive, digest)
    bridge = base64.b64encode(PS_STDIN_BRIDGE.encode('utf-16le')).decode('ascii')
    try:
        command = ssh_command(host=args.host, user=args.user, identity_file=args.identity_file,
                              known_hosts=args.known_hosts, encoded=bridge)
    except InspectionBlocked as exc:
        raise StageBlocked('SSH binding blocked') from exc
    if len(command[-1]) > 1024:
        raise StageBlocked('SSH bridge unexpectedly long')
    try:
        proc = subprocess.run(command, input=script, capture_output=True,
                              text=True, encoding='utf-8', errors='replace',
                              timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise StageBlocked('SSH failed/timed out; inspect stage before retry') from exc
    if proc.returncode != 0:
        raise StageBlocked(f'Windows stage refused rc={proc.returncode}; no blind retry')
    return validate_report(proc.stdout, args.mode, manifest, digest, len(archive))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('source-check', 'check', 'stage', 'verify'), required=True)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--expected-archive-sha256')
    parser.add_argument('--confirm-synthetic-stage', action='store_true')
    parser.add_argument('--host')
    parser.add_argument('--user')
    parser.add_argument('--identity-file', type=Path)
    parser.add_argument('--known-hosts', type=Path)
    args = parser.parse_args(argv)
    try:
        source_check()
        if args.mode == 'source-check':
            if any((args.archive, args.expected_archive_sha256, args.confirm_synthetic_stage,
                    args.host, args.user, args.identity_file, args.known_hosts)):
                raise StageBlocked('source-check requires no remote arguments')
            print('GDL_W27B_WINDOWS_STAGE=SOURCE_CHECK_PASS')
            print('WINDOWS_WRITE=false ILLUSTRATOR_EXECUTION=false DISPATCH_ALLOWED=false')
            return 0
        if not args.archive or not args.expected_archive_sha256:
            raise StageBlocked('exact source package and independently known SHA256 required')
        if (args.mode == 'stage') != args.confirm_synthetic_stage:
            raise StageBlocked('confirmation is required only for new-only stage')
        if not all((args.host, args.user, args.identity_file, args.known_hosts)):
            raise StageBlocked('explicit pinned SSH host/user/key/known-hosts required')
        if args.host != '192.168.50.69' or args.user != 'work':
            raise StageBlocked('unexpected PREPRESS host/user')
        manifest, archive, digest = load_archive(args.archive, args.expected_archive_sha256)
        doc = remote_run(args, manifest, archive, digest)
        print(json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=2))
        print('GDL_W27B_WINDOWS_STAGE=' + doc['state'])
        return 0
    except (StageBlocked, OSError, ValueError) as exc:
        print('GDL_W27B_WINDOWS_STAGE=BLOCKED reason=' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

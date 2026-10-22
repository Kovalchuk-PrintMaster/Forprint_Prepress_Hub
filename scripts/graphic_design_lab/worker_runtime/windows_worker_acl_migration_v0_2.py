#!/usr/bin/env python3
"""ForPrint W2 pilot: guarded operator ACL FullControl -> ReadAndExecute migration.

Changes ONLY D:\\ForPrint_Automation DACL on explicit --mode apply + approval.
Windows operations are transported from s01 over pinned SSH stdin. No Adobe.
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import subprocess
import sys

import yaml

from windows_worker_w2_host_inspector_v0_1 import InspectionBlocked, ssh_command
from windows_worker_w2_3_workspace_initializer_v0_1 import PS_STDIN_BRIDGE

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / 'coordination/graphic_design_lab/worker_runtime/windows_worker_w1_pilot_contract_v0_1.yaml'
SOURCE = Path(__file__).with_suffix('.ps1')
POLICY = 'gdl_windows_operator_read_execute_v0_2'
SID = 'S-1-5-21-3087849371-1068859030-1179031902-1001'
WINDOWS_ROOT = r'D:\ForPrint_Automation\GraficsDesignLab\Automation'
SCHEMA = 'gdl_windows_worker_acl_migration_v0_2'
MODES = ('source-check', 'check', 'apply')


class MigrationBlocked(RuntimeError):
    pass


def source_check() -> str:
    if any(not p.is_file() or p.is_symlink() for p in (CONTRACT, SOURCE)):
        raise MigrationBlocked('ACL contract/script absent or unsafe')
    c = yaml.safe_load(CONTRACT.read_text(encoding='utf-8'))
    p = c.get('windows', {}).get('access_control', {})
    if (c.get('windows', {}).get('root') != WINDOWS_ROOT
            or p.get('policy_id') != POLICY
            or p.get('approval_scope') != 'GDL_W2_LOCAL_PILOT_ONLY'
            or p.get('operator_sid') != SID
            or p.get('operator_account') != r'PREPRESS\Work'
            or p.get('expected_aces') != {'S-1-5-18': 'FullControl',
                                           'S-1-5-32-544': 'FullControl',
                                           SID: 'ReadAndExecute'}
            or p.get('root_inheritance_protected') is not True
            or p.get('child_directories_inherit') is not True
            or p.get('no_automatic_deletion') is not True
            or c.get('authority', {}).get('worker_launch') is not False
            or c.get('authority', {}).get('production_publish') is not False):
        raise MigrationBlocked('W1 ACL policy mismatched')
    script = SOURCE.read_text(encoding='ascii')
    for x in ('__ACL_MODE__', 'LEGACY_OPERATOR_FULL_CONTROL',
              'READY_FOR_LEAST_PRIVILEGE_MIGRATION', 'OPERATOR_READ_EXECUTE_VERIFIED',
              f"$OperatorSid = '{SID}'", 'RemoveAccessRuleSpecific',
              'Set-Acl -LiteralPath $Shared', 'NO_AUTOMATIC_CLEANUP'):
        if x not in script:
            raise MigrationBlocked(f'ACL migration safety marker missing/duplicated: {x}')
    if len(script) > 20000:
        raise MigrationBlocked('ACL migration script too large')
    return script


def render(mode: str, script: str) -> str:
    if mode not in ('check', 'apply') or script.count('__ACL_MODE__') != 1:
        raise MigrationBlocked('ACL mode or source marker invalid')
    return script.replace('__ACL_MODE__', mode)


def validate_report(raw: str, mode: str) -> dict:
    try:
        data = json.loads(raw.strip())
    except (ValueError, TypeError) as e:
        raise MigrationBlocked('Windows returned no single JSON document') from e
    if not isinstance(data, dict):
        raise MigrationBlocked('ACL result not an object')
    expected = {'schema_version': SCHEMA, 'policy_id': POLICY, 'mode': mode,
                'host': 'PREPRESS', 'ssh_account': r'PREPRESS\Work',
                'root': WINDOWS_ROOT, 'directories_checked': 8,
                'root_inheritance_protected': True, 'operator_sid_verified': True}
    for k, v in expected.items():
        if data.get(k) != v or (type(v) is int and type(data.get(k)) is not int):
            raise MigrationBlocked(f'ACL report binding mismatch: {k}')
    for flag in ('client_files_touched', 'scheduled_tasks_mutated', 'smb_mutation',
                 'illustrator_execution', 'cleanup_executed', 'production_ready'):
        if data.get(flag) is not False:
            raise MigrationBlocked(f'Forbidden ACL side effect: {flag}')
    if mode == 'check':
        if (data.get('windows_mutation') is not False or
            (data.get('state'), data.get('prior_state')) not in (
                ('READY_FOR_LEAST_PRIVILEGE_MIGRATION', 'LEGACY_OPERATOR_FULL_CONTROL'),
                ('OPERATOR_READ_EXECUTE_VERIFIED', 'OPERATOR_READ_EXECUTE'))):
            raise MigrationBlocked('Read-only ACL check inconsistent')
    else:
        if (data.get('windows_mutation') is not True or
                data.get('state') != 'OPERATOR_READ_EXECUTE_VERIFIED' or
                data.get('prior_state') != 'LEGACY_OPERATOR_FULL_CONTROL'):
            raise MigrationBlocked('ACL mutation not independently verified')
    return data


def remote_run(args: argparse.Namespace) -> dict:
    script = render(args.mode, source_check())
    bridge = base64.b64encode(PS_STDIN_BRIDGE.encode('utf-16le')).decode('ascii')
    try:
        command = ssh_command(host=args.host, user=args.user,
                              identity_file=args.identity_file,
                              known_hosts=args.known_hosts, encoded=bridge)
    except InspectionBlocked as e:
        raise MigrationBlocked(str(e)) from e
    if len(command[-1]) > 1024:
        raise MigrationBlocked('SSH bridge too long')
    try:
        result = subprocess.run(command, input=script, capture_output=True,
                                text=True, encoding='utf-8', errors='replace',
                                timeout=90, check=False)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise MigrationBlocked('SSH failed/timed out; inspect before mutation retry') from e
    if result.returncode:
        raise MigrationBlocked(f'Windows refused ACL operation rc={result.returncode}; do not retry apply blindly')
    return validate_report(result.stdout, args.mode)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode', choices=MODES, required=True)
    ap.add_argument('--confirm-operator-rx-migration', action='store_true')
    ap.add_argument('--host')
    ap.add_argument('--user')
    ap.add_argument('--identity-file', type=Path)
    ap.add_argument('--known-hosts', type=Path)
    a = ap.parse_args(argv)
    try:
        source_check()
        if a.mode == 'source-check':
            if a.confirm_operator_rx_migration:
                raise MigrationBlocked('No confirmation in source-check')
            print('GDL_WINDOWS_ACL_MIGRATION=SOURCE_CHECK_PASS')
            return 0
        if (a.mode == 'apply') != a.confirm_operator_rx_migration:
            raise MigrationBlocked('Explicit confirmation only for apply')
        if not all((a.host, a.user, a.identity_file, a.known_hosts)):
            raise MigrationBlocked('Explicit SSH host/user/identity/known-hosts required')
        doc = remote_run(a)
        print(json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=2))
        print('GDL_WINDOWS_ACL_MIGRATION=' + doc['state'])
        return 0
    except MigrationBlocked as e:
        print('GDL_WINDOWS_ACL_MIGRATION=BLOCKED reason=' + str(e), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

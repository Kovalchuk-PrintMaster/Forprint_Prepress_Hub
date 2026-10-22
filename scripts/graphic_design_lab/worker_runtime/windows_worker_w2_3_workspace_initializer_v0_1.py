#!/usr/bin/env python3
"""Guarded s01 -> PREPRESS local workspace initialization, W2.3 pilot.

No SMB, no client content, no worker launch. Changes only the new protected
local D: tree, when --mode initialize --confirm-local-workspace-creation is given.
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import sys

import yaml

# Import W2 SSH security policy instead of maintaining a second copy.
from windows_worker_w2_host_inspector_v0_1 import InspectionBlocked, ssh_command

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / 'coordination/graphic_design_lab/worker_runtime/windows_worker_w1_pilot_contract_v0_1.yaml'
PROBE = Path(__file__).with_suffix('.ps1')
WINDOWS_ROOT = r'D:\ForPrint_Automation\GraficsDesignLab\Automation'
SCHEMA = 'gdl_windows_w2_3_workspace_report_v0_1'
MODES = {'check', 'initialize'}

# Windows OpenSSH often invokes the configured shell via cmd.exe, whose
# command-line length limit is ~8191 chars. The full PowerShell source needs
# ~15K chars when encoded as UTF-16LE Base64, and SSH exits 255 before it runs.
# Pass only this small, fixed bootstrap as an argument; stream project-owned
# checked PowerShell source over SSH stdin (no Windows file is written).
PS_STDIN_BRIDGE = (
    "$ErrorActionPreference='Stop';"
    "$s=[Console]::In.ReadToEnd();"
    "if([string]::IsNullOrWhiteSpace($s)){throw 'W2_3_EMPTY_STDIN'};"
    "& ([ScriptBlock]::Create($s))"
)


class WorkspaceBlocked(RuntimeError):
    pass


def source_check() -> str:
    if not CONTRACT.is_file() or CONTRACT.is_symlink():
        raise WorkspaceBlocked('W1 contract missing/unsafe')
    if not PROBE.is_file() or PROBE.is_symlink():
        raise WorkspaceBlocked('PowerShell initializer missing/unsafe')
    contract = yaml.safe_load(CONTRACT.read_text(encoding='utf-8'))
    if contract.get('windows', {}).get('root') != WINDOWS_ROOT:
        raise WorkspaceBlocked('W1 root mismatch')
    authority = contract.get('authority', {})
    if authority.get('worker_launch') is not False or authority.get('production_publish') is not False:
        raise WorkspaceBlocked('Pilot authority has changed')
    if contract.get('windows', {}).get('windows_host_initialized') is not False:
        raise WorkspaceBlocked('W1 description must not claim initialization')
    policy = contract.get('windows', {}).get('access_control', {})
    if (policy.get('policy_id') != 'gdl_windows_operator_full_control_dev_v0_3'
            or policy.get('operator_sid') != 'S-1-5-21-3087849371-1068859030-1179031902-1001'
            or policy.get('operator_access') != 'FullControl'
            or policy.get('expected_aces', {}).get(policy['operator_sid']) != 'FullControl'
            or policy.get('expected_aces', {}).get('S-1-5-18') != 'FullControl'
            or policy.get('expected_aces', {}).get('S-1-5-32-544') != 'FullControl'
            or len(policy.get('expected_aces', {})) != 3
            or policy.get('root_owner') != r'BUILTIN\Administrators'
            or policy.get('root_inheritance_protected') is not True
            or policy.get('child_directories_inherit') is not True):
        raise WorkspaceBlocked('W1 operator ACL policy mismatch')
    source = PROBE.read_text(encoding='utf-8')
    if source.count('__FORPRINT_W2_3_MODE__') != 1 or f"$Root = '{WINDOWS_ROOT}'" not in source:
        raise WorkspaceBlocked('PowerShell W1 root / mode marker mismatch')
    if ('$OperatorSid = ' not in source or 'Assert-ApprovedAcl' not in source or 'ReadAndExecute' not in source):
        raise WorkspaceBlocked('W2.3 ACL guard missing')
    required = ('SetAccessRuleProtection($true, $false)',
                'Directory]::CreateDirectory($Shared, (New-StrictRootAcl))',
                "'S-1-5-18'", "'S-1-5-32-544'", "'PARTIAL_TREE_REVIEW_REQUIRED'",
                'NO_AUTOMATIC_DELETE_SENTINEL')
    # The sentinel is a comment marker guarding against accidental broad refactors.
    for marker in required:
        if marker not in source:
            raise WorkspaceBlocked('PowerShell safety marker missing')
    return source


def render(script: str, mode: str) -> str:
    if mode not in MODES:
        raise WorkspaceBlocked('Invalid mode')
    if script.count('__FORPRINT_W2_3_MODE__') != 1:
        raise WorkspaceBlocked('Mode marker mismatch')
    return script.replace('__FORPRINT_W2_3_MODE__', mode)


def encode(script: str, mode: str) -> str:
    """Legacy encoder retained for source/transport regression tests only."""
    return base64.b64encode(render(script, mode).encode('utf-16le')).decode('ascii')


def validate_report(text: str, mode: str) -> dict:
    try:
        doc = json.loads(text.strip())
    except (TypeError, ValueError) as exc:
        raise WorkspaceBlocked('Windows did not return a single JSON report') from exc
    if not isinstance(doc, dict) or doc.get('schema_version') != SCHEMA:
        raise WorkspaceBlocked('Unsupported W2.3 schema')
    if doc.get('mode') != mode or doc.get('root') != WINDOWS_ROOT:
        raise WorkspaceBlocked('Mode/root mismatch')
    if doc.get('host', '').upper() != 'PREPRESS' or doc.get('ssh_account', '').lower() != r'prepress\work':
        raise WorkspaceBlocked('Host/account mismatch')
    if doc.get('directory_count') != 8 or doc.get('state') not in {
        'READY_TO_INITIALIZE', 'ALREADY_INITIALIZED_SAFE', 'INITIALIZED_SAFE'
    }:
        raise WorkspaceBlocked('Invalid workspace state')
    if type(doc.get('windows_mutation')) is not bool:
        raise WorkspaceBlocked('Missing mutation evidence')
    if mode == 'check' and doc['windows_mutation'] is not False:
        raise WorkspaceBlocked('Read-only check claimed Windows mutation')
    if mode == 'initialize' and doc['state'] == 'READY_TO_INITIALIZE':
        raise WorkspaceBlocked('Initialize returned no initial state')
    if mode == 'check' and doc['state'] == 'INITIALIZED_SAFE':
        raise WorkspaceBlocked('Read-only check claims creation')
    if (doc['windows_mutation'] is True) != (doc['state'] == 'INITIALIZED_SAFE'):
        raise WorkspaceBlocked('Mutation and state mismatch')
    for flag in ('smb_mutation', 'client_files_touched', 'illustrator_execution',
                 'cleanup_executed', 'production_ready'):
        if doc.get(flag) is not False:
            raise WorkspaceBlocked(f'Forbidden {flag} claim')
    return doc


def remote_run(args: argparse.Namespace) -> dict:
    import subprocess
    source = source_check()
    payload = render(source, args.mode)
    bridge = base64.b64encode(PS_STDIN_BRIDGE.encode('utf-16le')).decode('ascii')
    try:
        command = ssh_command(host=args.host, user=args.user,
                              identity_file=args.identity_file,
                              known_hosts=args.known_hosts, encoded=bridge)
    except InspectionBlocked as exc:
        raise WorkspaceBlocked(str(exc)) from exc
    if len(command[-1]) > 1024:
        raise WorkspaceBlocked('Short SSH command length bound exceeded')
    try:
        result = subprocess.run(command, input=payload, capture_output=True,
                                text=True, encoding='utf-8', errors='replace',
                                timeout=90, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkspaceBlocked('Windows SSH failed or timed out; check for partial tree') from exc
    if result.returncode:
        raise WorkspaceBlocked(f'Windows refused/failed operation rc={result.returncode}; do not retry blindly')
    return validate_report(result.stdout, args.mode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['source-check', 'check', 'initialize'], required=True)
    parser.add_argument('--confirm-local-workspace-creation', action='store_true')
    parser.add_argument('--host')
    parser.add_argument('--user')
    parser.add_argument('--identity-file', type=Path)
    parser.add_argument('--known-hosts', type=Path)
    args = parser.parse_args(argv)
    try:
        source_check()
        if args.mode == 'source-check':
            if args.confirm_local_workspace_creation:
                raise WorkspaceBlocked('No confirmation flag in source-check')
            print('GDL_WINDOWS_W2_3_WORKSPACE=SOURCE_CHECK_PASS')
            return 0
        if args.mode == 'initialize' and not args.confirm_local_workspace_creation:
            raise WorkspaceBlocked('Explicit confirmation required for initialize')
        if args.mode == 'check' and args.confirm_local_workspace_creation:
            raise WorkspaceBlocked('Confirmation flag not valid for read-only check')
        if not all((args.host, args.user, args.identity_file, args.known_hosts)):
            raise WorkspaceBlocked('Explicit SSH host/user/identity-file/known-hosts required')
        doc = remote_run(args)
        print(json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=2))
        print('GDL_WINDOWS_W2_3_WORKSPACE=' + doc['state'])
        return 0
    except WorkspaceBlocked as exc:
        print(f'GDL_WINDOWS_W2_3_WORKSPACE=BLOCKED reason={exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())

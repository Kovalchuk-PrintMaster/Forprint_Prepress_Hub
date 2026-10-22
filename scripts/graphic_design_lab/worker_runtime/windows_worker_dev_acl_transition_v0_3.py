#!/usr/bin/env python3
"""Bounded temporary DEV ACL transition for PREPRESS local test root only.

Only a confirmed apply can modify one parent DACL. This is not production authorization.
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
SCRIPT = Path(__file__).with_suffix('.ps1')
POLICY = 'gdl_windows_operator_full_control_dev_v0_3'
SCHEMA = 'gdl_windows_worker_dev_acl_transition_v0_3'
SID = 'S-1-5-21-3087849371-1068859030-1179031902-1001'
SHARED = r'D:\ForPrint_Automation'
GDL_ROOT = SHARED + r'\GraficsDesignLab\Automation'

class DevAclBlocked(RuntimeError):
    pass

def source_check() -> str:
    for path in (CONTRACT, SCRIPT):
        if not path.is_file() or path.is_symlink():
            raise DevAclBlocked('Missing or unsafe project source')
    doc = yaml.safe_load(CONTRACT.read_text(encoding='utf-8'))
    a = doc.get('windows', {}).get('access_control', {})
    if (doc.get('windows', {}).get('root') != GDL_ROOT
            or doc.get('authority', {}).get('worker_launch') is not False
            or doc.get('authority', {}).get('production_publish') is not False
            or doc.get('cleanup', {}).get('no_automatic_deletion') is not True
            or a.get('policy_id') != POLICY or a.get('operator_sid') != SID
            or a.get('operator_access') != 'FullControl'
            or a.get('dev_profile') is not True or a.get('dev_scope') != SHARED
            or a.get('expected_aces') != {
                'S-1-5-18': 'FullControl', 'S-1-5-32-544': 'FullControl', SID: 'FullControl'
            }
            or a.get('root_owner') != r'BUILTIN\Administrators'
            or a.get('root_inheritance_protected') is not True):
        raise DevAclBlocked('DEV policy/authority not as reviewed')
    src = SCRIPT.read_text(encoding='ascii')
    if src.count('__DEV_ACL_MODE__') != 1:
        raise DevAclBlocked('PowerShell mode marker invalid')
    for sentinel in ('Set-Acl -LiteralPath $Shared', 'Inspect-Tree',
                     'NO_AUTOMATIC_CLEANUP', 'OPERATION_FAILED_INSPECT_BEFORE_RETRY',
                     SID, 'FileSystemRights]::FullControl'):
        if sentinel not in src:
            raise DevAclBlocked('PowerShell migration guard missing')
    return src

def validate_report(output: str, mode: str) -> dict:
    try:
        r = json.loads(output.strip())
    except (ValueError, TypeError) as e:
        raise DevAclBlocked('Windows returned no single JSON report') from e
    if not isinstance(r, dict) or r.get('schema_version') != SCHEMA or r.get('policy_id') != POLICY:
        raise DevAclBlocked('Invalid DEV ACL report schema')
    expected = {'mode': mode, 'host': 'PREPRESS', 'ssh_account': r'PREPRESS\Work',
                'boundary': SHARED, 'gdl_root': GDL_ROOT, 'directories_checked': 8,
                'operator_sid_verified': True, 'root_inheritance_protected': True,
                'scheduled_tasks_mutated': False, 'client_files_touched': False,
                'smb_mutation': False, 'illustrator_execution': False,
                'cleanup_executed': False, 'production_ready': False}
    for k, v in expected.items():
        if r.get(k) != v:
            raise DevAclBlocked('Invalid DEV ACL report field ' + k)
    if mode == 'check':
        if r.get('windows_mutation') is not False:
            raise DevAclBlocked('Check claimed mutation')
        if (r.get('state'), r.get('previous_state')) not in (
            ('READY_FOR_DEV_FULL_CONTROL', 'CURRENT_RX'),
            ('DEV_FULL_CONTROL_VERIFIED', 'DEV_FULL')):
            raise DevAclBlocked('Unexpected check state')
    elif mode == 'apply':
        if (r.get('windows_mutation') is not True
                or r.get('state') != 'DEV_FULL_CONTROL_VERIFIED'
                or r.get('previous_state') != 'CURRENT_RX'):
            raise DevAclBlocked('Apply did not confirm expected transition')
    else:
        raise DevAclBlocked('Invalid mode')
    return r

def remote_run(args: argparse.Namespace) -> dict:
    text = source_check().replace('__DEV_ACL_MODE__', args.mode)
    bridge = base64.b64encode(PS_STDIN_BRIDGE.encode('utf-16le')).decode('ascii')
    try:
        cmd = ssh_command(host=args.host, user=args.user,
                          identity_file=args.identity_file, known_hosts=args.known_hosts,
                          encoded=bridge)
    except InspectionBlocked as e:
        raise DevAclBlocked(str(e)) from e
    if len(cmd[-1]) > 1024:
        raise DevAclBlocked('SSH command too long')
    try:
        p = subprocess.run(cmd, input=text, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=90, check=False)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise DevAclBlocked('SSH failed; inspect Windows before further action') from e
    if p.returncode != 0:
        raise DevAclBlocked(f'Windows refused rc={p.returncode}; no automatic retry')
    return validate_report(p.stdout, args.mode)

def main(argv: list[str] | None = None) -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode', choices=('source-check','check','apply'), required=True)
    ap.add_argument('--confirm-dev-full-control', action='store_true')
    ap.add_argument('--host'); ap.add_argument('--user')
    ap.add_argument('--identity-file', type=Path); ap.add_argument('--known-hosts', type=Path)
    a=ap.parse_args(argv)
    try:
        source_check()
        if a.mode == 'source-check':
            if a.confirm_dev_full_control:
                raise DevAclBlocked('Confirmation invalid in source-check')
            print('GDL_W2_DEV_ACL=SOURCE_CHECK_PASS')
            return 0
        if (a.mode == 'apply') != a.confirm_dev_full_control:
            raise DevAclBlocked('Apply requires exact confirmation')
        if not all((a.host,a.user,a.identity_file,a.known_hosts)):
            raise DevAclBlocked('Explicit SSH parameters required')
        r=remote_run(a)
        print(json.dumps(r,ensure_ascii=False,sort_keys=True,indent=2))
        print('GDL_W2_DEV_ACL=' + r['state'])
        return 0
    except DevAclBlocked as e:
        print('GDL_W2_DEV_ACL=BLOCKED reason=' + str(e),file=sys.stderr)
        return 2

if __name__=='__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""Read-only Windows GDL host inspection over verified public-key SSH.

Runs the project-owned PS 5.1 probe via -EncodedCommand without copying any
files to Windows. No SMB, GUI execution, Windows directory creation or cleanup.
Windows GUI suitability is *not* asserted by quser or an SSH session.
"""
from __future__ import annotations

import argparse
import base64
import ipaddress
import json
from pathlib import Path
import re
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / 'coordination/graphic_design_lab/worker_runtime/windows_worker_w1_pilot_contract_v0_1.yaml'
PROBE = Path(__file__).with_name('windows_worker_w2_host_probe_v0_1.ps1')
SCHEMA = 'gdl_windows_w2_host_inspection_v0_1'
WINDOWS_ROOT = r'D:\ForPrint_Automation\GraficsDesignLab\Automation'
USER_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9_.-]{0,63}$')


class InspectionBlocked(RuntimeError):
    """Fail-closed inspector error."""


def check_sources() -> None:
    if not CONTRACT.is_file() or not PROBE.is_file() or PROBE.is_symlink():
        raise InspectionBlocked('W1 contract or W2 probe missing or unsafe')
    contract = yaml.safe_load(CONTRACT.read_text(encoding='utf-8'))
    if contract.get('windows', {}).get('root') != WINDOWS_ROOT:
        raise InspectionBlocked('W1 Windows root does not match approved pilot')
    if contract.get('authority', {}).get('worker_launch') is not False:
        raise InspectionBlocked('W1 worker authority has changed')
    script = PROBE.read_text(encoding='utf-8')
    if f"$root = '{WINDOWS_ROOT}'" not in script:
        raise InspectionBlocked('Windows probe root does not match W1')
    if "windows_write_requested = $false" not in script:
        raise InspectionBlocked('Windows probe is not marked read-only')


def encoded_powershell(script: str) -> str:
    return base64.b64encode(script.encode('utf-16le')).decode('ascii')


def ssh_command(*, host: str, user: str, identity_file: Path,
                known_hosts: Path, encoded: str) -> list[str]:
    try:
        if not isinstance(ipaddress.ip_address(host), ipaddress.IPv4Address):
            raise ValueError('IPv4 required')
    except ValueError as ex:
        raise InspectionBlocked('Host must be a specific IPv4 address') from ex
    if not USER_RE.fullmatch(user):
        raise InspectionBlocked('Invalid SSH username')
    for label, path in [('identity', identity_file), ('known_hosts', known_hosts)]:
        if not path.is_file() or path.is_symlink():
            raise InspectionBlocked(f'{label} is missing or symlinked')
    if identity_file.stat().st_mode & 0o077:
        raise InspectionBlocked('Identity file must be owner-only')
    return [
        'ssh', '-T', '-i', str(identity_file), '-l', user,
        '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
        '-o', 'PreferredAuthentications=publickey',
        '-o', 'PasswordAuthentication=no', '-o', 'KbdInteractiveAuthentication=no',
        '-o', 'StrictHostKeyChecking=yes', '-o', 'UpdateHostKeys=no',
        '-o', f'UserKnownHostsFile={known_hosts}',
        '-o', 'GlobalKnownHostsFile=/dev/null',
        '-o', 'ConnectTimeout=10', host,
        f'powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand {encoded}',
    ]


def interpret_report(output: str, *, expected_root: str = WINDOWS_ROOT) -> dict:
    try:
        report = json.loads(output.strip())
    except (ValueError, TypeError) as ex:
        raise InspectionBlocked('Windows did not return a single JSON object') from ex
    if not isinstance(report, dict) or report.get('schema_version') != SCHEMA:
        raise InspectionBlocked('Missing or unsupported W2 inspection schema')
    if report.get('origin') != 'WINDOWS_READ_ONLY_SSH_PROBE':
        raise InspectionBlocked('Report origin mismatch')
    if report.get('windows_write_requested') is not False:
        raise InspectionBlocked('Windows write was not excluded')
    if (report.get('interactive_gui_execution_verified') is not False or
            report.get('illustrator_font_api_verified') is not False or
            report.get('smb_private_access_verified') is not False):
        raise InspectionBlocked('Unsupported verification claim')
    disk, root = report.get('drive_d'), report.get('worker_root')
    if not isinstance(disk, dict) or not isinstance(root, dict):
        raise InspectionBlocked('Missing drive/root section')
    if root.get('path') != expected_root or type(root.get('exists')) is not bool:
        raise InspectionBlocked('Invalid Windows root evidence')
    if type(disk.get('present')) is not bool:
        raise InspectionBlocked('Drive presence evidence invalid')
    if disk['present']:
        if (disk.get('file_system') != 'NTFS'
                or not isinstance(disk.get('free_bytes'), int)
                or disk.get('free_bytes', -1) < 0
                or not isinstance(disk.get('size_bytes'), int)
                or disk['size_bytes'] < disk['free_bytes']):
            raise InspectionBlocked('Drive D disk evidence inconsistent')
    if not isinstance(report.get('registered_graphics_software'), list):
        raise InspectionBlocked('Graphics software inventory missing')
    if not isinstance(report.get('registered_relevant_fonts'), list):
        raise InspectionBlocked('Font inventory missing')
    if not isinstance(report.get('active_quser_session_count'), int):
        raise InspectionBlocked('Session evidence invalid')
    if not isinstance(report.get('host_name'), str) or not report['host_name']:
        raise InspectionBlocked('Windows hostname missing')
    if not isinstance(report.get('ssh_account'), str) or not report['ssh_account']:
        raise InspectionBlocked('Windows SSH identity missing')
    if (disk['present'] and disk['file_system'] == 'NTFS'
            and report['active_quser_session_count'] >= 1):
        readiness = 'HOST_PREREQUISITES_PRESENT_GUI_NOT_PROVEN'
    else:
        readiness = 'HOST_PREREQUISITES_INCOMPLETE'
    return {
        'schema_version': 'gdl_windows_w2_s01_inspection_result_v0_1',
        'state': readiness,
        'independent_authority_granted': False,
        'windows_write': False,
        'smb_write': False,
        'illustrator_executed': False,
        'gui_execution_verified': False,
        'host_inspection': report,
    }


def run_inspection(args: argparse.Namespace) -> dict:
    check_sources()
    encoded = encoded_powershell(PROBE.read_text(encoding='utf-8'))
    command = ssh_command(host=args.host, user=args.user,
                          identity_file=args.identity_file, known_hosts=args.known_hosts,
                          encoded=encoded)
    try:
        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, encoding='utf-8', errors='replace',
                                 timeout=75, check=False)
    except (OSError, subprocess.TimeoutExpired) as ex:
        raise InspectionBlocked('SSH inspector unreachable or timed out') from ex
    if process.returncode:
        # Do not echo unexpected remote diagnostic streams into logs.
        raise InspectionBlocked(f'Windows SSH inspection failed rc={process.returncode}')
    return interpret_report(process.stdout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['check', 'inspect'], required=True)
    parser.add_argument('--host', default=None, help='PREPRESS IPv4; required for inspect')
    parser.add_argument('--user', default=None, help='Windows SSH user; required for inspect')
    parser.add_argument('--identity-file', type=Path)
    parser.add_argument('--known-hosts', type=Path)
    a = parser.parse_args(argv)
    try:
        if a.mode == 'check':
            check_sources()
            print('GDL_WINDOWS_W2_HOST_INSPECTOR=SOURCE_CHECK_PASS')
            print('WINDOWS_WRITE=false SMB_WRITE=false ILLUSTRATOR_EXECUTION=false')
            return 0
        if not all((a.host, a.user, a.identity_file, a.known_hosts)):
            raise InspectionBlocked('inspect requires --host, --user, --identity-file and --known-hosts')
        report = run_inspection(a)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
        print('GDL_WINDOWS_W2_HOST_INSPECTOR=REMOTE_READ_ONLY_COMPLETE')
        return 0
    except InspectionBlocked as ex:
        print(f'GDL_WINDOWS_W2_HOST_INSPECTOR=BLOCKED reason={ex}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())

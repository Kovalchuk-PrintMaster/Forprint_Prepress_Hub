#!/usr/bin/env python3
"""W2.6: bounded *read-only* retrieval of W2.5.3's proven synthetic .ai.

No Windows mutation, Illustrator execution, scheduled-task operation, SMB use,
customer file access, automatic retry, or source repository change. Writes only
new private files under an explicitly named s01 repository tmp/ directory.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import yaml

from windows_worker_w2_host_inspector_v0_1 import InspectionBlocked, ssh_command
from windows_worker_w2_3_workspace_initializer_v0_1 import PS_STDIN_BRIDGE

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / 'coordination/graphic_design_lab/worker_runtime/windows_worker_w1_pilot_contract_v0_1.yaml'
WIN_ROOT = r'D:\ForPrint_Automation\GraficsDesignLab\Automation'
TASK = 'gdl-w253-limited-native-001'
ATTEMPT = 'a0001'
AI_SHA256 = 'da12062420b01e20521f1e47365abbe1719ad787a831a55070528b1d11e82b7d'
AI_SIZE = 224636
JSX_SHA256 = '2f586907039e0b9ae1562df361aeb02db8dc88262b9cce3bf9a25c181a7982bb'
RUNNER_SHA256 = '05344c201b81dd185b61bbb576157f27ad456e746e8b2645c187e32b8eb38aa1'
SCHEMA = 'gdl_w2_6_artifact_return_transport_v0_1'
OUT_SUBDIR = 'tmp/gdl_w26_w253_a0001_artifact_return_v0_1'
SHA = re.compile(r'^[0-9a-f]{64}$')

class ReturnBlocked(RuntimeError):
    pass

REMOTE_SCRIPT = r'''$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try {
    $task = 'gdl-w253-limited-native-001'
    $attempt = 'a0001'
    $root = 'D:\ForPrint_Automation\GraficsDesignLab\Automation'
    if ($env:COMPUTERNAME -ine 'PREPRESS' -or
      [Security.Principal.WindowsIdentity]::GetCurrent().Name -ine 'PREPRESS\Work') {
        throw 'HOST_USER_MISMATCH'
    }
    $basedir = Join-Path (Join-Path (Join-Path $root 'jobs') $task) $attempt
    $export = Join-Path $basedir 'export'
    $ai = Join-Path $export 'native_probe.ai'
    $result = Join-Path $export 'native_runner_result.json'
    foreach ($d in @('D:\ForPrint_Automation', $root, (Join-Path $root 'jobs'),
                     (Join-Path (Join-Path $root 'jobs') $task), $basedir, $export)) {
        $item = Get-Item -LiteralPath $d -Force -ErrorAction Stop
        if (-not $item.PSIsContainer -or
            ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'UNSAFE_DIRECTORY'
        }
    }
    foreach ($f in @($ai,$result)) {
        $item = Get-Item -LiteralPath $f -Force -ErrorAction Stop
        if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'UNSAFE_FILE'
        }
    }
    $aiLength = (Get-Item -LiteralPath $ai).Length
    if ($aiLength -ne 224636) { throw 'AI_LENGTH_UNEXPECTED' }
    $reportLength = (Get-Item -LiteralPath $result).Length
    if ($reportLength -le 80 -or $reportLength -gt 32768) { throw 'RESULT_LENGTH_UNEXPECTED' }
    $aiBytes = [IO.File]::ReadAllBytes($ai)
    $reportBytes = [IO.File]::ReadAllBytes($result)
    $hashProvider = [Security.Cryptography.SHA256]::Create()
    try {
        $sha = [BitConverter]::ToString($hashProvider.ComputeHash($aiBytes)).Replace('-','').ToLowerInvariant()
        $resultSha = [BitConverter]::ToString($hashProvider.ComputeHash($reportBytes)).Replace('-','').ToLowerInvariant()
    } finally { $hashProvider.Dispose() }
    if ($sha -ne 'da12062420b01e20521f1e47365abbe1719ad787a831a55070528b1d11e82b7d') {
        throw 'AI_SHA256_MISMATCH'
    }
    $r = [Text.Encoding]::UTF8.GetString($reportBytes) | ConvertFrom-Json
    if ($r.task_id -ne $task -or $r.attempt_id -ne $attempt -or
        $r.state -ne 'PASS_NATIVE_AI_REOPENED' -or
        $r.ai_sha256 -ne $sha -or $r.ai_bytes -ne 224636 -or
        $r.jsx_sha256 -ne '2f586907039e0b9ae1562df361aeb02db8dc88262b9cce3bf9a25c181a7982bb' -or
        $r.runner_sha256 -ne '05344c201b81dd185b61bbb576157f27ad456e746e8b2645c187e32b8eb38aa1' -or
        $r.token_limited_verified -ne $true -or $r.production_ready -ne $false) {
        throw 'RUNNER_RESULT_BINDING_MISMATCH'
    }
    $out = [ordered]@{
        schema_version = 'gdl_w2_6_artifact_return_transport_v0_1'
        state = 'SOURCE_READ_ONLY_SHA_VERIFIED'
        host = $env:COMPUTERNAME
        account = [Security.Principal.WindowsIdentity]::GetCurrent().Name
        task_id = $task
        attempt_id = $attempt
        ai_bytes = $aiBytes.Length
        ai_sha256 = $sha
        ai_base64 = [Convert]::ToBase64String($aiBytes)
        result_bytes = $reportBytes.Length
        result_sha256 = $resultSha
        result_base64 = [Convert]::ToBase64String($reportBytes)
        windows_mutation = $false
        illustrator_execution = $false
        scheduled_tasks_mutated = $false
        smb_mutation = $false
        cleanup_executed = $false
        production_ready = $false
    }
    [Console]::Out.WriteLine((ConvertTo-Json -InputObject $out -Compress -Depth 4))
    exit 0
} catch {
    [Console]::Error.WriteLine('W26_BLOCKED:REMOTE_READ_ONLY_VERIFICATION_FAILED')
    exit 2
}
'''


def source_check() -> None:
    if not CONTRACT.is_file() or CONTRACT.is_symlink():
        raise ReturnBlocked('W1 contract missing or unsafe')
    contract = yaml.safe_load(CONTRACT.read_text(encoding='utf-8'))
    if (contract.get('windows', {}).get('root') != WIN_ROOT
            or contract.get('windows', {}).get('access_control', {}).get('policy_id') != 'gdl_windows_operator_full_control_dev_v0_3'
            or contract.get('authority', {}).get('worker_launch') is not False
            or contract.get('authority', {}).get('production_publish') is not False
            or contract.get('cleanup', {}).get('no_automatic_deletion') is not True):
        raise ReturnBlocked('W1 root, DEV policy or authority mismatch')
    for marker in ('[IO.File]::ReadAllBytes', 'SOURCE_READ_ONLY_SHA_VERIFIED', 'AI_SHA256_MISMATCH', 'exit 2'):
        # The stage/state marker is an intentional exact-literal source guard.
        if marker.lower() not in REMOTE_SCRIPT.lower():
            raise ReturnBlocked('W2.6 remote safety marker missing')
    for forbidden in ('Set-Acl', 'Remove-Item', 'Register-ScheduledTask',
                      'Start-ScheduledTask', 'DoJavaScript', 'WriteAllBytes', 'CreateDirectory'):
        if forbidden.lower() in REMOTE_SCRIPT.lower():
            raise ReturnBlocked('W2.6 remote script unexpectedly mutating')


def _sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def unpack_verified(raw: str) -> tuple[bytes, bytes, dict]:
    try:
        doc = json.loads(raw.strip())
    except (ValueError, TypeError) as exc:
        raise ReturnBlocked('Remote returned no single JSON document') from exc
    if not isinstance(doc, dict):
        raise ReturnBlocked('Remote transport was not an object')
    expected = {'schema_version': SCHEMA, 'state': 'SOURCE_READ_ONLY_SHA_VERIFIED',
                'host': 'PREPRESS', 'account': r'PREPRESS\Work',
                'task_id': TASK, 'attempt_id': ATTEMPT, 'ai_bytes': AI_SIZE,
                'ai_sha256': AI_SHA256}
    for key, val in expected.items():
        if doc.get(key) != val or (type(val) is int and type(doc.get(key)) is not int):
            raise ReturnBlocked('Remote transport binding mismatch: ' + key)
    for flag in ('windows_mutation', 'illustrator_execution', 'scheduled_tasks_mutated',
                 'smb_mutation', 'cleanup_executed', 'production_ready'):
        if doc.get(flag) is not False:
            raise ReturnBlocked('Remote reported forbidden side effect: ' + flag)
    try:
        ai = base64.b64decode(doc['ai_base64'], validate=True)
        result = base64.b64decode(doc['result_base64'], validate=True)
        r = json.loads(result.decode('utf-8-sig'))
    except (KeyError, ValueError, UnicodeError) as exc:
        raise ReturnBlocked('Remote returned malformed artifact bytes') from exc
    if len(ai) != AI_SIZE or _sha(ai) != AI_SHA256:
        raise ReturnBlocked('AI bytes do not match independently expected evidence')
    if (type(doc.get('result_bytes')) is not int or doc['result_bytes'] != len(result)
            or not 80 < len(result) <= 32768
            or not SHA.fullmatch(str(doc.get('result_sha256')))
            or _sha(result) != doc['result_sha256']):
        raise ReturnBlocked('Runner result digest / size mismatch')
    if not isinstance(r, dict):
        raise ReturnBlocked('Runner result not an object')
    required = {'schema_version': 'gdl_windows_w2_5_3_native_runner_v0_1',
                'task_id': TASK, 'attempt_id': ATTEMPT,
                'host': 'PREPRESS', 'windows_account': r'PREPRESS\Work',
                'state': 'PASS_NATIVE_AI_REOPENED', 'ai_bytes': AI_SIZE,
                'ai_sha256': AI_SHA256, 'jsx_sha256': JSX_SHA256,
                'runner_sha256': RUNNER_SHA256, 'token_limited_verified': True,
                'editable_area_text': True, 'native_ai_saved_reopened': True,
                'production_ready': False, 'smb_mutation': False,
                'client_files_touched': False, 'cleanup_executed': False,
                'phase': 'STAGE_DONE', 'error_code': 'NONE'}
    for key, val in required.items():
        if r.get(key) != val or (type(val) is int and type(r.get(key)) is not int):
            raise ReturnBlocked('Runner result content mismatch: ' + key)
    return ai, result, doc


def remote_retrieve(args: argparse.Namespace) -> tuple[bytes, bytes, dict]:
    bridge = base64.b64encode(PS_STDIN_BRIDGE.encode('utf-16le')).decode('ascii')
    try:
        cmd = ssh_command(host=args.host, user=args.user,
                          identity_file=args.identity_file, known_hosts=args.known_hosts,
                          encoded=bridge)
    except InspectionBlocked as exc:
        raise ReturnBlocked(str(exc)) from exc
    if len(cmd[-1]) > 1024:
        raise ReturnBlocked('SSH command unexpectedly long')
    try:
        p = subprocess.run(cmd, input=REMOTE_SCRIPT, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReturnBlocked('SSH failed or timed out; no automatic retry') from exc
    if p.returncode != 0:
        raise ReturnBlocked(f'Windows read-only retrieval failed rc={p.returncode}; no automatic retry')
    return unpack_verified(p.stdout)


def write_local(outdir: Path, ai: bytes, result: bytes, transport: dict) -> dict:
    if outdir.exists() or outdir.is_symlink():
        raise ReturnBlocked('Local destination already exists; never overwrite evidence')
    manifest = {
        'schema_version': 'gdl_w2_6_synthetic_artifact_return_manifest_v0_1',
        'state': 'SYNTHETIC_ARTIFACT_RETURNED_SHA_VERIFIED',
        'task_id': TASK, 'attempt_id': ATTEMPT, 'source_host': 'PREPRESS',
        'source_path': WIN_ROOT + rf'\jobs\{TASK}\{ATTEMPT}\export\native_probe.ai',
        'artifact_file': 'native_probe.ai', 'artifact_bytes': len(ai),
        'artifact_sha256': _sha(ai), 'worker_result_file': 'native_runner_result.json',
        'worker_result_sha256': _sha(result),
        'ssh_host_key_pinned': True, 'windows_mutation': False,
        'illustrator_execution': False, 'smb_mutation': False,
        'client_files_touched': False, 'cleanup_executed': False,
        'production_ready': False, 'accepted': False,
        'scope': 'W2.5.3_SYNTHETIC_RETURN_ONLY',
    }
    try:
        outdir.mkdir(mode=0o700)
        for name, blob in (
                ('native_probe.ai', ai),
                ('native_runner_result.json', result),
                ('retrieval_manifest.json', (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode('utf-8'))):
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
            fd = os.open(outdir / name, flags, 0o600)
            with os.fdopen(fd, 'wb') as handle:
                handle.write(blob)
                handle.flush()
                os.fsync(handle.fileno())
        return manifest
    except (OSError, ValueError) as exc:
        raise ReturnBlocked('Local evidence write failed; preserve partial directory for review') from exc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode', required=True, choices=('source-check', 'retrieve'))
    ap.add_argument('--confirm-synthetic-artifact-return', action='store_true')
    ap.add_argument('--host')
    ap.add_argument('--user')
    ap.add_argument('--identity-file', type=Path)
    ap.add_argument('--known-hosts', type=Path)
    args = ap.parse_args(argv)
    try:
        source_check()
        if args.mode == 'source-check':
            if args.confirm_synthetic_artifact_return:
                raise ReturnBlocked('Confirmation not allowed for source-check')
            print('GDL_W2_6_ARTIFACT_RETURN=SOURCE_CHECK_PASS')
            return 0
        if not args.confirm_synthetic_artifact_return:
            raise ReturnBlocked('Explicit confirmation required for retrieval')
        if not all((args.host, args.user, args.identity_file, args.known_hosts)):
            raise ReturnBlocked('Explicit SSH host, user, key and pinned known_hosts required')
        if args.host != '192.168.50.69' or args.user != 'work':
            raise ReturnBlocked('Unexpected W2.6 host/user')
        outdir = ROOT / OUT_SUBDIR
        tmp = ROOT / 'tmp'
        if not tmp.is_dir() or tmp.is_symlink() or outdir.exists() or outdir.is_symlink():
            raise ReturnBlocked('Unsafe or occupied local tmp destination')
        ai, result, data = remote_retrieve(args)
        manifest = write_local(outdir, ai, result, data)
        print(json.dumps(manifest, indent=2, sort_keys=True))
        print('GDL_W2_6_ARTIFACT_RETURN=SYNTHETIC_ARTIFACT_RETURNED_SHA_VERIFIED')
        return 0
    except ReturnBlocked as exc:
        print('GDL_W2_6_ARTIFACT_RETURN=BLOCKED reason=' + str(exc), file=sys.stderr)
        return 2

if __name__ == '__main__':
    sys.exit(main())

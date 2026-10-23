#!/usr/bin/env python3
"""GDL W2.7-C3D: inspect existing Windows attempt evidence WITHOUT mutation.

Fail-closed SSH PowerShell read-only snapshot, bound to C3C historical contract.
A successful observation NEVER grants launch, dispatch, acceptance, or rerun.
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

from gdl_w27c3c_attempt_snapshot_reconciler_v0_1 import (
    SnapshotBlocked, check_source as c3c_source_check,
    TASK, ATTEMPT, PACKAGE_SHA, RECEIPT_SHA,
)
from windows_worker_w2_host_inspector_v0_1 import InspectionBlocked, ssh_command
from windows_worker_w2_3_workspace_initializer_v0_1 import PS_STDIN_BRIDGE

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / 'coordination/graphic_design_lab/worker_runtime/gdl_w27c3d_live_attempt_inspection_contract_v0_1.json'
CONTROLLER = Path(__file__).with_suffix('.ps1')
SCHEMA = 'gdl_w27c3d_live_attempt_inspection_contract_v0_1'
REPORT_SCHEMA = 'gdl_w27c3d_live_attempt_inspection_v0_1'
ARCHIVE_BYTES = 5120
HEX = re.compile(r'^[a-f0-9]{64}$')
MARKERS = ('__TASK_ID__', '__ATTEMPT_ID__', '__ARCHIVE_SHA__', '__ARCHIVE_BYTES__', '__RECEIPT_SHA__')
EVIDENCE = ('start_claim', 'execution_started', 'jsx', 'native_ai', 'worker_result')
MAX_EVIDENCE_BYTES = {'start_claim':32768,'execution_started':32768,
                      'jsx':262144,'native_ai':104857600,'worker_result':65536}
INERT = 'STAGED_ATTEMPT_INERT_NO_EXECUTION_EVIDENCE'
FENCED = 'EXECUTION_EVIDENCE_PRESENT_RECONCILIATION_REQUIRED'


class InspectionFailure(RuntimeError):
    pass


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise InspectionFailure(reason)


def source_check() -> tuple[dict, str]:
    try:
        c3c_source_check()
        require(CONTRACT.is_file() and not CONTRACT.is_symlink(), 'C3D contract unsafe')
        require(CONTROLLER.is_file() and not CONTROLLER.is_symlink(), 'C3D script unsafe')
        contract = json.loads(CONTRACT.read_text('utf-8'))
        data = CONTROLLER.read_bytes()
    except (OSError, ValueError, SnapshotBlocked, UnicodeError) as exc:
        raise InspectionFailure('C3C dependency or C3D source unavailable') from exc
    expected = {
        'schema_version':SCHEMA,
        'state':'READ_ONLY_CURRENT_ATTEMPT_INSPECTION_AUTHORITY_PENDING',
        'task_id':TASK,'attempt_id':ATTEMPT,'package_sha256':PACKAGE_SHA,
        'staging_receipt_sha256':RECEIPT_SHA,
        'evidence_names':list(EVIDENCE),'windows_write':False,
        'execution_authorized':False,'dispatch_authorized':False,
        'automatic_retry':False,'automatic_acceptance':False,
        'synthetic_only':True,'blueprint_review_pending':True,
    }
    require(isinstance(contract,dict) and set(contract)==set(expected)|{'ps_source_sha256'},
            'C3D contract fields changed')
    for key,value in expected.items():
        require(type(contract[key]) is type(value) and contract[key]==value,
                'C3D binding/authority invalid: '+key)
    require(isinstance(contract['ps_source_sha256'],str) and
            HEX.fullmatch(contract['ps_source_sha256']) is not None,
            'source digest missing')
    require(data.isascii() and 1500 < len(data) <= 15000 and
            sha256(data).hexdigest()==contract['ps_source_sha256'],
            'C3D PowerShell source differs from pinned contract')
    source = data.decode('ascii')
    require(all(source.count(x)==1 for x in MARKERS), 'C3D template binding invalid')
    for required in ('STAGED_ATTEMPT_INERT_NO_EXECUTION_EVIDENCE',
                     'EXECUTION_EVIDENCE_PRESENT_RECONCILIATION_REQUIRED',
                     'READ_ONLY_ATTEMPT_INSPECTION_FAILED_PRESERVE_EVIDENCE'):
        require(required in source, 'C3D denied-state marker absent')
    return contract, source


def render(script: str) -> str:
    substitutions={
        '__TASK_ID__':TASK,'__ATTEMPT_ID__':ATTEMPT,
        '__ARCHIVE_SHA__':PACKAGE_SHA,'__ARCHIVE_BYTES__':str(ARCHIVE_BYTES),
        '__RECEIPT_SHA__':RECEIPT_SHA,
    }
    for key,value in substitutions.items():
        require(script.count(key)==1, 'C3D template variable mismatch')
        script=script.replace(key,value)
    require(not any(key in script for key in substitutions), 'C3D unresolved template')
    return script


def equal(obj: dict, key: str, value: object) -> None:
    require(obj.get(key)==value and type(obj.get(key)) is type(value),
            'Windows inspector report binding invalid: '+key)


def validate_report(text: str) -> dict:
    try:
        report=json.loads(text.strip())
    except (ValueError, TypeError) as exc:
        raise InspectionFailure('remote report is not a single JSON object') from exc
    require(type(report) is dict, 'report must be a dict')
    expected = {
        'schema_version':REPORT_SCHEMA,'task_id':TASK,'attempt_id':ATTEMPT,
        'host':'PREPRESS','windows_account':r'PREPRESS\Work',
        'archive_sha256':PACKAGE_SHA,'archive_bytes':ARCHIVE_BYTES,
        'staging_receipt_sha256':RECEIPT_SHA,
        'live_observation':True,'no_rerun_authorized':True,
        'worker_launch_authorized':False,'dispatch_authorized':False,
        'production_ready':False,'accepted':False,'windows_mutation':False,
        'jsx_executed_by_inspector':False,'com_attach_performed':False,
        'scheduler_mutation':False,'cleanup_executed':False,
        'client_files_touched':False,'smb_mutation':False,
    }
    require(set(report)==set(expected)|{'artifacts','state','execution_evidence_present'},
            'report fields changed')
    for k,v in expected.items(): equal(report,k,v)
    require(type(report['artifacts']) is dict and set(report['artifacts'])==set(EVIDENCE),
            'artifact inventory invalid')
    found=False
    for k in EVIDENCE:
        item=report['artifacts'][k]
        require(type(item) is dict and set(item)=={'present','bytes','sha256'},
                'artifact metadata invalid: '+k)
        present=item['present']
        require(type(present) is bool,'artifact presence invalid: '+k)
        if present:
            found=True
            require(type(item['bytes']) is int and 0<=item['bytes']<=MAX_EVIDENCE_BYTES[k],
                    'artifact size invalid: '+k)
            require(type(item['sha256']) is str and bool(HEX.fullmatch(item['sha256'])),
                    'artifact digest invalid: '+k)
        else:
            require(item['bytes'] is None and item['sha256'] is None,
                    'missing artifact metadata must be null')
    equal(report,'execution_evidence_present',found)
    equal(report,'state',FENCED if found else INERT)
    return report


def remote_inspect(args: argparse.Namespace, script: str) -> dict:
    encoded = base64.b64encode(PS_STDIN_BRIDGE.encode('utf-16le')).decode('ascii')
    try:
        command = ssh_command(host=args.host,user=args.user,
                              identity_file=args.identity_file,
                              known_hosts=args.known_hosts,encoded=encoded)
    except InspectionBlocked as exc:
        raise InspectionFailure('pinned SSH configuration refused') from exc
    require(len(command[-1])<=1024, 'unexpected SSH command size')
    try:
        result=subprocess.run(command,input=render(script),capture_output=True,text=True,
                              encoding='utf-8',errors='replace',timeout=90,check=False)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise InspectionFailure('SSH unavailable; preserve evidence and do not retry execution') from exc
    require(result.returncode==0,
            f'Windows inspector refused rc={result.returncode}; preserve attempt evidence')
    return validate_report(result.stdout)


def main(argv: list[str]|None=None) -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode',required=True,choices=('source-check','check'))
    ap.add_argument('--host')
    ap.add_argument('--user')
    ap.add_argument('--identity-file',type=Path)
    ap.add_argument('--known-hosts',type=Path)
    a=ap.parse_args(argv)
    try:
        _,script=source_check()
        if a.mode=='source-check':
            require(not any((a.host,a.user,a.identity_file,a.known_hosts)),
                    'source-check forbids remote arguments')
            print('GDL_W27C3D_LIVE_ATTEMPT=SOURCE_CHECK_PASS')
            print('WINDOWS_WRITE=false EXECUTION=false DISPATCH_ALLOWED=false')
            return 0
        require(a.host=='192.168.50.69' and a.user=='work' and
                a.identity_file is not None and a.known_hosts is not None,
                'explicit PREPRESS SSH host/account/key/known-hosts required')
        doc=remote_inspect(a,script)
        print(json.dumps(doc,ensure_ascii=False,sort_keys=True,indent=2))
        print('GDL_W27C3D_LIVE_ATTEMPT='+doc['state'])
        return 0
    except (InspectionFailure,OSError,ValueError) as exc:
        print('GDL_W27C3D_LIVE_ATTEMPT=BLOCKED reason='+str(exc),file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())

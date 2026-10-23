#!/usr/bin/env python3
"""GDL W2.7-C3G: synthetic Windows filesystem one-use fence probe.

Strictly isolated from real staged attempt. check/verify are read-only.
probe writes one fresh synthetic directory and CreateNew marker only. NO retry.
NO Illustrator, COM, JSX, Task Scheduler, dispatcher, acceptance or customer data.
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

from gdl_w27c3d_live_attempt_inspector_v0_1 import (InspectionFailure,
                                                     source_check as c3d_source_check)
from gdl_w27c3f_one_use_fence_simulator_v0_1 import (FenceBlocked,
                                                      source_check as c3f_source_check)
from windows_worker_w2_host_inspector_v0_1 import InspectionBlocked, ssh_command
from windows_worker_w2_3_workspace_initializer_v0_1 import PS_STDIN_BRIDGE

ROOT=Path(__file__).resolve().parents[3]
CONTRACT=ROOT/'coordination/graphic_design_lab/worker_runtime/gdl_w27c3g_windows_fence_probe_contract_v0_1.json'
SCRIPT=Path(__file__).with_suffix('.ps1')
SCHEMA='gdl_w27c3g_windows_fence_probe_contract_v0_1'
REPORT='gdl_w27c3g_windows_fence_probe_report_v0_1'
TASK='gdl-w27g-synthetic-fence-001'
ATTEMPT='a0001'
NATIVE_TASK='gdl-w27c-native-001'
NATIVE_ATTEMPT='a0001'
PACKAGE_SHA='d1949844b3ab2d68936facf8012e6b8fba1ecd1134597f2e6f4139ef1449b3e7'
RECEIPT_SHA='0c025e0132795c7f0e7011fbe52fdf17c44f9f19fc01dcd34f77684e4b11e827'
HEX=re.compile(r'^[0-9a-f]{64}$')
MODES=('check','probe','verify')
STATES={
 'check':'READY_FOR_ISOLATED_SYNTHETIC_FENCE_PROBE',
 'probe':'ISOLATED_FENCE_PROBE_WRITTEN_DUPLICATE_DENIED',
 'verify':'ISOLATED_FENCE_PROBE_SHA_VERIFIED_NOT_EXECUTED',
}
MARKERS=('__MODE__','__EXPECTED_PROBE_SHA__')

class FenceProbeBlocked(RuntimeError):
    pass


def require(test:bool,reason:str)->None:
    if not test:
        raise FenceProbeBlocked(reason)


def source_check()->str:
    try:
        c3d_source_check()
        c3f_source_check()
        require(CONTRACT.is_file() and not CONTRACT.is_symlink(), 'C3G contract unsafe')
        require(SCRIPT.is_file() and not SCRIPT.is_symlink(), 'C3G PowerShell unsafe')
        contract=json.loads(CONTRACT.read_text('utf-8'))
        raw=SCRIPT.read_bytes()
    except (InspectionFailure, FenceBlocked, OSError, UnicodeError, ValueError) as exc:
        raise FenceProbeBlocked('C3D/C3F dependencies or C3G source unavailable') from exc
    expect={
        'schema_version':SCHEMA,
        'state':'WINDOWS_ISOLATED_SYNTHETIC_FENCE_PROBE_REVIEW_ONLY',
        'task_id':TASK,'attempt_id':ATTEMPT,
        'native_task_id':NATIVE_TASK,'native_attempt_id':NATIVE_ATTEMPT,
        'native_package_sha256':PACKAGE_SHA,
        'native_receipt_sha256':RECEIPT_SHA,
        'probe_location':'jobs/gdl-w27g-synthetic-fence-001/a0001/work/fence_probe.json',
        'one_use_create_new':True,'probe_requires_explicit_confirmation':True,
        'probe_is_not_worker_claim':True,
        'runner_launch_implemented':False,'dispatch_authorized':False,
        'execution_authorized':False,'retry_authorized':False,
        'automatic_cleanup':False,'production_ready':False,
        'customer_data_allowed':False,'blueprint_review_pending':True,
    }
    require(isinstance(contract,dict) and set(contract)==set(expect)|{'ps_source_sha256'},
            'C3G contract shape changed')
    for key,value in expect.items():
        require(type(contract[key]) is type(value) and contract[key]==value,
                'C3G source authority or binding changed: '+key)
    require(type(contract['ps_source_sha256']) is str and
            HEX.fullmatch(contract['ps_source_sha256']) is not None,
            'C3G script sha missing')
    require(1500<len(raw)<20000 and raw.isascii() and
            sha256(raw).hexdigest()==contract['ps_source_sha256'],
            'C3G Windows source differs from pinned contract')
    ps=raw.decode('ascii')
    require(all(ps.count(marker)==1 for marker in MARKERS),
            'C3G template marker missing or duplicate')
    for marker in ('FileMode]::CreateNew','PROBE_TASK_ALREADY_EXISTS_NO_RETRY',
                   'DUPLICATE_CREATE_UNEXPECTEDLY_SUCCEEDED',
                   'INDEPENDENT_CLAIM_SHA_MISMATCH',
                   'ISOLATED_FENCE_PROBE_WRITTEN_DUPLICATE_DENIED',
                   'ISOLATED_FENCE_PROBE_SHA_VERIFIED_NOT_EXECUTED',
                   'NO_AUTOMATIC_CLEANUP','NO_TASK_SCHEDULER','NO_COM','NO_JSX'):
        require(marker in ps,'C3G source guard missing')
    for forbidden in ('Start-ScheduledTask','Register-ScheduledTask','DoJavaScript',
                      'GetActiveObject','Invoke-Expression','Remove-Item','Set-Acl',
                      'Start-Process','Stop-Process','Unregister-ScheduledTask',
                      'Expand-Archive','ExtractToDirectory'):
        require(forbidden.lower() not in ps.lower(),'C3G contains forbidden operation')
    return ps


def render(source:str,mode:str,expected_probe_sha:str|None)->str:
    require(mode in MODES,'invalid remote mode')
    token='0'*64 if expected_probe_sha is None else expected_probe_sha
    require(HEX.fullmatch(token) is not None,'invalid expected SHA')
    args={'__MODE__':mode,'__EXPECTED_PROBE_SHA__':token}
    for mark,value in args.items():
        require(source.count(mark)==1,'template marker changed')
        source=source.replace(mark,value)
    require(not any(m in source for m in args),'unresolved template marker')
    return source


def validate_report(raw:str,mode:str,expected_probe_sha:str|None)->dict:
    try:
        report=json.loads(raw.strip())
    except (TypeError,ValueError) as exc:
        raise FenceProbeBlocked('Windows output not one JSON') from exc
    require(type(report) is dict,'Windows report type invalid')
    fields={
        'schema_version':REPORT,'mode':mode,'state':STATES[mode],
        'host':'PREPRESS','windows_account':r'PREPRESS\Work',
        'task_id':TASK,'attempt_id':ATTEMPT,
        'native_task_id':NATIVE_TASK,'native_attempt_id':NATIVE_ATTEMPT,
        'native_package_sha256':PACKAGE_SHA,'native_receipt_sha256':RECEIPT_SHA,
        'windows_mutation':mode=='probe','duplicate_create_denied':mode!='check',
        'com_attach_performed':False,'jsx_execution':False,'runner_execution':False,
        'scheduler_mutated':False,'dispatch_authorized':False,
        'execution_authorized':False,'retry_authorized':False,
        'production_ready':False,'accepted':False,
        'client_files_touched':False,'smb_mutation':False,'cleanup_executed':False,
    }
    require(set(report)==set(fields)|{'claim_sha256'},'Windows result keys changed')
    for key,value in fields.items():
        require(type(report[key]) is type(value) and report[key]==value,
                'Windows result authority/binding mismatch: '+key)
    claim=report.get('claim_sha256')
    if mode=='check':
        require(claim is None,'check unexpectedly has a claim')
    else:
        require(type(claim) is str and HEX.fullmatch(claim) is not None,
                'probe claim digest invalid')
        if mode=='verify':
            require(claim==expected_probe_sha,'independent claim SHA changed')
    return report


def remote_run(args:argparse.Namespace,source:str)->dict:
    bridge=base64.b64encode(PS_STDIN_BRIDGE.encode('utf-16le')).decode('ascii')
    try:
        command=ssh_command(host=args.host,user=args.user,identity_file=args.identity_file,
                            known_hosts=args.known_hosts,encoded=bridge)
    except InspectionBlocked as exc:
        raise FenceProbeBlocked('pinned SSH binding refused') from exc
    require(len(command[-1])<1024,'unexpectedly long SSH bridge')
    try:
        p=subprocess.run(command,input=render(source,args.mode,args.expected_probe_sha256),
                         capture_output=True,text=True,encoding='utf-8',errors='replace',
                         timeout=120,check=False)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise FenceProbeBlocked('SSH unavailable/timed out; DO NOT RETRY probe, verify state first') from exc
    if p.returncode:
        raise FenceProbeBlocked(f'Windows refused rc={p.returncode}; preserve evidence, DO NOT RETRY probe')
    return validate_report(p.stdout,args.mode,args.expected_probe_sha256)


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',required=True,choices=('source-check',*MODES))
    p.add_argument('--host')
    p.add_argument('--user')
    p.add_argument('--identity-file',type=Path)
    p.add_argument('--known-hosts',type=Path)
    p.add_argument('--expected-probe-sha256')
    p.add_argument('--confirm-synthetic-fence-probe',action='store_true')
    a=p.parse_args(argv)
    try:
        source=source_check()
        if a.mode=='source-check':
            require(not any((a.host,a.user,a.identity_file,a.known_hosts,
                             a.expected_probe_sha256,a.confirm_synthetic_fence_probe)),
                    'source-check accepts no remote options')
            print('GDL_W27C3G_WINDOWS_FENCE=SOURCE_CHECK_PASS')
            print('WINDOWS_WRITE=false WORKER_EXECUTION=false DISPATCH=false')
            return 0
        require(all((a.host,a.user,a.identity_file,a.known_hosts)) and
                a.host=='192.168.50.69' and a.user=='work',
                'expected pinned PREPRESS SSH target required')
        require((a.mode=='probe')==a.confirm_synthetic_fence_probe,
                'explicit synthetic probe confirmation required ONLY for probe')
        if a.mode=='verify':
            require(type(a.expected_probe_sha256) is str and
                    HEX.fullmatch(a.expected_probe_sha256) is not None,
                    'verify requires independently copied probe SHA')
        else:
            require(a.expected_probe_sha256 is None,
                    'expected SHA only valid for verify')
        doc=remote_run(a,source)
        print(json.dumps(doc,sort_keys=True,ensure_ascii=False,indent=2))
        print('GDL_W27C3G_WINDOWS_FENCE='+doc['state'])
        return 0
    except (FenceProbeBlocked,InspectionFailure,FenceBlocked,OSError,ValueError) as exc:
        print('GDL_W27C3G_WINDOWS_FENCE=BLOCKED reason='+str(exc),file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())

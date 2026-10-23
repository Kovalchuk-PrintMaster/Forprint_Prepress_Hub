#!/usr/bin/env python3
"""ForPrint W2.7-C3H: OFFLINE native worker-result handoff, not a closeout.

Consumes previously captured C3D read-only evidence and independent C3G
synthetic Windows CreateNew proof. If actual native return files are provided,
reuses the existing C3B byte/hash verifier; it never grants execution, retry,
acceptance, publishing or production readiness. No SSH/PowerShell execution.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import sys

from gdl_w27c3b_native_worker_review_v0_1 import (
    ReviewBlocked, source_check as c3b_source_check, verify_result,
)
from gdl_w27c3e_recovery_decision_engine_v0_1 import (
    RecoveryBlocked, source_check as c3e_source_check, read_capture,
    decide, INCIDENTS,
)
from gdl_w27c3g_windows_fence_probe_v0_1 import (
    FenceProbeBlocked, source_check as c3g_source_check,
    validate_report as c3g_validate,
)

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT/'coordination/graphic_design_lab/worker_runtime/gdl_w27c3h_worker_return_handoff_contract_v0_1.json'
SCHEMA = 'gdl_w27c3h_worker_return_handoff_contract_v0_1'
REPORT = 'gdl_w27c3h_worker_return_handoff_v0_1'
TASK = 'gdl-w27c-native-001'
ATTEMPT = 'a0001'
PACKAGE_SHA = 'd1949844b3ab2d68936facf8012e6b8fba1ecd1134597f2e6f4139ef1449b3e7'
RECEIPT_SHA = '0c025e0132795c7f0e7011fbe52fdf17c44f9f19fc01dcd34f77684e4b11e827'
HEX = re.compile(r'[0-9a-f]{64}\Z')
MARKER = 'GDL_W27C3G_WINDOWS_FENCE='
PROBE_STATE = 'ISOLATED_FENCE_PROBE_WRITTEN_DUPLICATE_DENIED'
VERIFY_STATE = 'ISOLATED_FENCE_PROBE_SHA_VERIFIED_NOT_EXECUTED'

class HandoffBlocked(RuntimeError):
    pass


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise HandoffBlocked(reason)


def source_check() -> dict:
    try:
        c3b_source_check()
        c3e_source_check()
        c3g_source_check()
        require(CONTRACT.is_file() and not CONTRACT.is_symlink(), 'unsafe C3H contract')
        obj = json.loads(CONTRACT.read_text('utf-8'))
    except (ReviewBlocked, RecoveryBlocked, FenceProbeBlocked, OSError, ValueError,
            UnicodeError) as exc:
        raise HandoffBlocked('C3B/C3E/C3G prerequisite source or C3H contract unavailable') from exc
    expect = {
        'schema_version':SCHEMA, 'state':'OFFLINE_WORKER_RETURN_REVIEW_ONLY',
        'task_id':TASK,'attempt_id':ATTEMPT,'package_sha256':PACKAGE_SHA,
        'staging_receipt_sha256':RECEIPT_SHA,
        'expected_native_result_schema':'gdl_w27c3b_native_worker_result_v0_1',
        'inspector_schema':'gdl_w27c3d_live_attempt_inspection_v0_1',
        'probe_schema':'gdl_w27c3g_windows_fence_probe_report_v0_1',
        'probe_is_synthetic_only':True,
        'closeout_mode':'REVIEW_ONLY_NO_ACCEPTANCE',
        'actual_native_execution_tested':False,
        'independent_com_execution_proven':False,
        'independent_illustrator_editability_proven':False,
        'windows_write':False,'ssh_used':False,'dispatch_authorized':False,
        'execution_authorized':False,'retry_authorized':False,
        'automatic_acceptance':False,'production_ready':False,
        'cleanup_allowed':False,'owner_review_pending':True,
        'blueprint_authority_review_pending':True,
    }
    require(type(obj) is dict and set(obj)==set(expect), 'C3H contract shape changed')
    for key, val in expect.items():
        require(type(obj[key]) is type(val) and obj[key]==val,
                'C3H source authority/binding changed: '+key)
    return obj


def read_proof(path: Path, mode: str, expected_sha: str | None = None) -> tuple[dict,str]:
    """Strict tmp/<one-folder>/<name>.txt, bounded, O_NOFOLLOW read."""
    rawpath = Path(path)
    if not rawpath.is_absolute():
        rawpath = ROOT/rawpath
    path = Path(os.path.normpath(str(rawpath)))
    tmp = ROOT/'tmp'
    try:
        parts = path.relative_to(tmp).parts
    except ValueError as exc:
        raise HandoffBlocked('C3G report outside repository tmp') from exc
    require(len(parts)==2 and parts[1].endswith('.txt') and
            parts[0] not in ('.','..') and parts[1] not in ('.','..'),
            'C3G report path must be tmp/<folder>/<report>.txt')
    try:
        require(stat.S_ISDIR(tmp.lstat().st_mode) and
                stat.S_ISDIR((tmp/parts[0]).lstat().st_mode),
                'unsafe tmp or evidence folder')
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        with os.fdopen(fd,'rb') as handle:
            info = os.fstat(handle.fileno())
            require(stat.S_ISREG(info.st_mode) and 40<=info.st_size<=16384,
                    'unsafe C3G report type or size')
            data = handle.read(16385)
        require(len(data)==info.st_size, 'C3G evidence modified during read')
        text = data.decode('utf-8').strip()
        def unique(pairs: list[tuple[str,object]]) -> dict:
            d = {}
            for k,v in pairs:
                if k in d:
                    raise HandoffBlocked('duplicate JSON key in C3G capture')
                d[k] = v
            return d
        parsed, offset = json.JSONDecoder(object_pairs_hook=unique).raw_decode(text)
        require(type(parsed) is dict,'C3G evidence JSON object required')
        tail = text[offset:].strip()
        require(tail == MARKER + (PROBE_STATE if mode=='probe' else VERIFY_STATE),
                'C3G evidence missing/extraneous or mismatched marker')
        validated = c3g_validate(json.dumps(parsed, ensure_ascii=False),mode,expected_sha)
    except (OSError,ValueError,UnicodeError,FenceProbeBlocked) as exc:
        raise HandoffBlocked('C3G evidence read or schema validation failed') from exc
    return validated,sha256(data).hexdigest()


def review(capture:Path,probe:Path,verification:Path,incident:str,
           result:Path|None=None,native_ai:Path|None=None,
           expected_result_sha256:str|None=None,
           expected_native_sha256:str|None=None) -> dict:
    require(incident in INCIDENTS, 'unrecognized incident')
    try:
        observed,capture_digest = read_capture(capture)
    except RecoveryBlocked as exc:
        raise HandoffBlocked('C3D capture invalid') from exc
    p,p_digest = read_proof(probe,'probe')
    v,v_digest = read_proof(verification,'verify',p['claim_sha256'])
    require(p['claim_sha256']==v['claim_sha256'] and
            p['duplicate_create_denied'] is True and
            v['duplicate_create_denied'] is True,
            'one-use synthetic Windows fence proof mismatch')
    recovery=decide(incident,observed,capture_digest)
    require(recovery['retry_authorized'] is False and
            recovery['dispatch_authorized'] is False and
            recovery['accepted'] is False and
            recovery['fencing_released'] is False,
            'upstream recovery grants unexpected authority')
    provided = [result,native_ai,expected_result_sha256,expected_native_sha256]
    require(all(x is not None for x in provided) or all(x is None for x in provided),
            'actual native return requires all four independent inputs or none')
    positive = all(x is not None for x in provided)
    doc = None
    if positive:
        require(type(expected_result_sha256) is str and HEX.fullmatch(expected_result_sha256) is not None and
                type(expected_native_sha256) is str and HEX.fullmatch(expected_native_sha256) is not None,
                'expected result/AI SHA256 must be independently supplied')
        require(observed['execution_evidence_present'] is True,
                'returned bytes contradict inert C3D observation')
        for key, digest in [('worker_result',expected_result_sha256),
                            ('native_ai',expected_native_sha256)]:
            info=observed['artifacts'][key]
            require(info['present'] is True and info['sha256']==digest,
                    'Windows-side evidence SHA missing/mismatched: '+key)
        try:
            contract,_ = c3b_source_check()
            doc=verify_result(result,native_ai,expected_result_sha256,
                              expected_native_sha256,contract)
        except (ReviewBlocked,OSError,ValueError) as exc:
            raise HandoffBlocked('independent C3B byte/hash verification refused') from exc
        require(observed['artifacts']['native_ai']['bytes']==doc['native_ai_bytes'],
                'Windows-side AI byte count differs from returned bytes')
        state='NATIVE_RETURN_HASH_VERIFIED_NOT_ACCEPTED'
        action='INDEPENDENT_ILLUSTRATOR_OPEN_EDIT_PROOF_AND_OWNER_AUTHORITY_REVIEW'
    elif observed['execution_evidence_present']:
        state='EXECUTION_EVIDENCE_PRESENT_RETURN_NOT_VERIFIED'
        action='PRESERVE_ATTEMPT_RECONCILE_RETURN_NO_RERUN'
    elif incident!='NONE':
        state='INCIDENT_REQUIRES_FRESH_INSPECTION_AND_OWNER_REVIEW'
        action='FRESH_READ_ONLY_INSPECTION_THEN_MANUAL_RECONCILIATION'
    else:
        state='INERT_STAGING_NATIVE_RETURN_ABSENT_AUTHORITY_PENDING'
        action='PRESERVE_STAGING_AWAIT_EXTERNAL_EXECUTION_AUTHORITY'
    return {
        'schema_version':REPORT,'state':state,'task_id':TASK,'attempt_id':ATTEMPT,
        'package_sha256':PACKAGE_SHA,'staging_receipt_sha256':RECEIPT_SHA,
        'c3d_capture_sha256':capture_digest,'c3g_probe_output_sha256':p_digest,
        'c3g_verify_output_sha256':v_digest,'c3g_synthetic_claim_sha256':p['claim_sha256'],
        'c3g_proof_is_not_worker_execution_fence':True,
        'observed_c3d_state':observed['state'],
        'recovery_state':recovery['state'],
        'incident':incident,'worker_return_supplied':positive,
        'worker_result_sha256': doc['worker_result_sha256'] if doc else None,
        'native_ai_sha256': doc['native_ai_sha256'] if doc else None,
        'worker_report_fields_valid': bool(doc),
        'native_ai_bytes_hash_valid': bool(doc),
        'native_ai_is_editable_independently_proven':False,
        'com_execution_independently_proven':False,
        'freshness_for_next_execution_proven':False,
        'closeout_completed':False,'owner_approval_recorded':False,
        'blueprint_authority_review_pending':True,
        'execution_authorized':False,'dispatch_authorized':False,
        'retry_authorized':False,'accepted':False,
        'production_ready':False,'windows_mutation':False,
        'cleanup_executed':False,'operator_next_action':action,
    }


def main(argv:list[str]|None=None) -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode',required=True,choices=('source-check','review'))
    ap.add_argument('--capture',type=Path)
    ap.add_argument('--probe',type=Path)
    ap.add_argument('--verify',type=Path)
    ap.add_argument('--incident',choices=INCIDENTS,default='NONE')
    ap.add_argument('--result',type=Path)
    ap.add_argument('--native-ai',type=Path)
    ap.add_argument('--expected-result-sha256')
    ap.add_argument('--expected-native-sha256')
    a=ap.parse_args(argv)
    try:
        source_check()
        if a.mode=='source-check':
            require(not any((a.capture,a.probe,a.verify,a.result,a.native_ai,
                             a.expected_result_sha256,a.expected_native_sha256)) and
                    a.incident=='NONE','source-check accepts no report or incident options')
            print('GDL_W27C3H_RETURN_HANDOFF=SOURCE_CHECK_PASS')
            print('WINDOWS_WRITE=false DISPATCH=false ACCEPTANCE=false')
            return 0
        require(all((a.capture,a.probe,a.verify)),
                'review requires C3D capture and C3G probe/verify reports')
        doc=review(a.capture,a.probe,a.verify,a.incident,a.result,a.native_ai,
                   a.expected_result_sha256,a.expected_native_sha256)
        print(json.dumps(doc,sort_keys=True,indent=2,ensure_ascii=False))
        print('GDL_W27C3H_RETURN_HANDOFF='+doc['state'])
        return 0
    except (HandoffBlocked,RecoveryBlocked,FenceProbeBlocked,ReviewBlocked,
            ValueError,OSError) as exc:
        print('GDL_W27C3H_RETURN_HANDOFF=BLOCKED reason='+str(exc),file=sys.stderr)
        return 2

if __name__=='__main__':
    raise SystemExit(main())

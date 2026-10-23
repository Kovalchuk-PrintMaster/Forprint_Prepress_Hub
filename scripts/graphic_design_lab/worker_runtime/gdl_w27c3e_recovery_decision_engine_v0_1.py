#!/usr/bin/env python3
"""W2.7-C3E: deterministic OFFLINE recovery triage of bounded Windows evidence.

No SSH, Task Scheduler, Windows filesystem, COM/JSX execution, retry, cleanup,
acceptance, dispatch, or permission changes. Input is a captured, validated C3D
observation, not a persistent fresh state or an execution authorization.
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

from gdl_w27c3d_live_attempt_inspector_v0_1 import (
    InspectionFailure, validate_report as c3d_validate_report,
    source_check as c3d_source_check, FENCED, INERT,
)
from gdl_w27c3c_attempt_snapshot_reconciler_v0_1 import (
    SnapshotBlocked, TASK, ATTEMPT, PACKAGE_SHA, RECEIPT_SHA,
)

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / 'coordination/graphic_design_lab/worker_runtime/gdl_w27c3e_recovery_decision_contract_v0_1.json'
SCHEMA = 'gdl_w27c3e_recovery_decision_contract_v0_1'
REPORT_SCHEMA = 'gdl_w27c3e_recovery_decision_v0_1'
INCIDENTS = (
    'NONE', 'SSH_LOSS', 'HOST_REBOOT',
    'SCHEDULER_RC0_WITHOUT_VALID_RESULT', 'PARTIAL_WRITE',
    'WORKER_RC_NONZERO', 'UNKNOWN_PROCESS_EXIT',
)
TAIL = re.compile(r'GDL_W27C3D_LIVE_ATTEMPT=(STAGED_ATTEMPT_INERT_NO_EXECUTION_EVIDENCE|EXECUTION_EVIDENCE_PRESENT_RECONCILIATION_REQUIRED)')

class RecoveryBlocked(RuntimeError):
    pass


def require(value: bool, reason: str) -> None:
    if not value:
        raise RecoveryBlocked(reason)


def source_check() -> dict:
    try:
        c3d_source_check()
        require(CONTRACT.is_file() and not CONTRACT.is_symlink(), 'C3E contract missing/symlinked')
        obj = json.loads(CONTRACT.read_text('utf-8'))
    except (InspectionFailure, SnapshotBlocked, OSError, ValueError, UnicodeError) as exc:
        raise RecoveryBlocked('C3D prerequisite or C3E contract unavailable') from exc
    expected = {
        'schema_version':SCHEMA, 'state':'OFFLINE_RECOVERY_TRIAGE_ONLY_NO_DISPATCH',
        'task_id':TASK, 'attempt_id':ATTEMPT, 'package_sha256':PACKAGE_SHA,
        'staging_receipt_sha256':RECEIPT_SHA,
        'inspector_schema':'gdl_w27c3d_live_attempt_inspection_v0_1',
        'incidents':list(INCIDENTS),
        'capture_root':'tmp/<one-existing-dir>/<capture>.txt',
        'read_only':True, 'windows_write':False, 'execution_authorized':False,
        'dispatch_authorized':False, 'retry_authorized':False,
        'automatic_acceptance':False, 'cleanup_allowed':False,
        'production_publish':False, 'synthetic_only':True,
        'observation_freshness_proven_for_action':False,
        'handoff_scope':'PREPRESS_HUB_LOCAL_ONLY_BLUEPRINT_DECISION_PENDING',
    }
    require(type(obj) is dict and set(obj) == set(expected), 'C3E contract shape changed')
    for key,val in expected.items():
        require(type(obj[key]) is type(val) and obj[key] == val,
                'C3E contract identity, policy or authority changed: ' + key)
    return obj


def capture_path(path: Path) -> Path:
    """Only direct tmp/<run-folder>/<capture>.txt files, never a symlink."""
    tmp = ROOT / 'tmp'
    raw = Path(path)
    if not raw.is_absolute():
        raw = ROOT / raw
    normalized = Path(os.path.normpath(str(raw)))
    try:
        parts = normalized.relative_to(tmp).parts
    except ValueError as exc:
        raise RecoveryBlocked('capture path outside repository tmp') from exc
    require(len(parts)==2 and parts[1].endswith('.txt') and
            parts[0] not in ('.','..') and parts[1] not in ('.','..'),
            'capture must be tmp/<one-existing-dir>/<name>.txt')
    try:
        d = (tmp / parts[0]).lstat()
        t = tmp.lstat()
        f = normalized.lstat()
    except OSError as exc:
        raise RecoveryBlocked('capture path missing') from exc
    require(stat.S_ISDIR(t.st_mode) and stat.S_ISDIR(d.st_mode) and
            stat.S_ISREG(f.st_mode) and 40 <= f.st_size <= 32768,
            'unsafe capture type, symlink or size')
    return normalized


def read_capture(path: Path) -> tuple[dict,str]:
    p = capture_path(path)
    try:
        flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
        fd = os.open(p, flags)
        with os.fdopen(fd, 'rb') as f:
            metadata = os.fstat(f.fileno())
            require(stat.S_ISREG(metadata.st_mode) and 40 <= metadata.st_size <= 32768,
                    'capture changed type or size')
            raw = f.read(32769)
        require(len(raw) == metadata.st_size, 'capture changed during read')
        text = raw.decode('utf-8').strip()
        def unique_pairs(pairs: list[tuple[str, object]]) -> dict:
            result = {}
            for key, value in pairs:
                if key in result:
                    raise RecoveryBlocked('duplicate JSON field')
                result[key] = value
            return result
        doc, offset = json.JSONDecoder(object_pairs_hook=unique_pairs).raw_decode(text)
    except (ValueError, UnicodeError, OSError) as exc:
        raise RecoveryBlocked('capture not a UTF8 JSON report') from exc
    require(type(doc) is dict, 'capture must start with JSON object')
    tail = text[offset:].strip()
    require(not tail or TAIL.fullmatch(tail) is not None,
            'capture contains unexpected trailing text')
    # The C3D validator requires a single exact schema and independently pinned
    # task/attempt/archive/receipt. No ad-hoc interpretation of a JSON object.
    try:
        validated = c3d_validate_report(json.dumps(doc,ensure_ascii=False))
    except InspectionFailure as exc:
        raise RecoveryBlocked('C3D evidence binding invalid') from exc
    if tail:
        require(tail == 'GDL_W27C3D_LIVE_ATTEMPT=' + validated['state'],
                'capture state/status marker mismatch')
    return validated, sha256(raw).hexdigest()


def decide(incident: str, observation: dict | None, digest: str | None = None) -> dict:
    require(incident in INCIDENTS, 'incident category not supported')
    require((observation is None) == (digest is None), 'capture and SHA evidence inconsistent')
    if observation is None:
        require(incident != 'NONE', 'unobserved state requires explicit incident')
        state = 'STATE_UNOBSERVED_RECONCILIATION_REQUIRED'
        action = 'RESTORE_CONNECTIVITY_THEN_NEW_READ_ONLY_INSPECTION'
        decision = 'MANUAL_REVIEW'
        observed = None
        present = None
    else:
        # Revalidate even if invoked programmatically, not only from CLI.
        try:
            obs = c3d_validate_report(json.dumps(observation,ensure_ascii=False))
        except (InspectionFailure,TypeError,ValueError) as exc:
            raise RecoveryBlocked('untrusted C3D observation invalid') from exc
        require(type(digest) is str and re.fullmatch(r'[0-9a-f]{64}',digest) is not None,
                'capture digest invalid')
        observed = obs['state']
        present = obs['execution_evidence_present']
        if present:
            state = 'EXISTING_EXECUTION_EVIDENCE_RECONCILIATION_REQUIRED'
            action = 'PRESERVE_ALL_FILES_VERIFY_WITH_INDEPENDENT_RESULT_GATE'
            decision = 'MANUAL_REVIEW'
        elif incident == 'NONE':
            state = 'INERT_STAGED_SNAPSHOT_NO_EXECUTION_OR_LAUNCH_AUTHORITY'
            action = 'PRESERVE_STAGING_AWAIT_EXPLICIT_OWNER_REVIEW'
            decision = 'DO_NOT_RERUN'
        elif incident == 'SSH_LOSS':
            state = 'TRANSPORT_INTERRUPTION_REQUIRES_NEW_LIVE_OBSERVATION'
            action = 'VERIFY_NETWORK_THEN_REPEAT_READ_ONLY_INSPECTION'
            decision = 'MANUAL_REVIEW'
        elif incident == 'HOST_REBOOT':
            state = 'HOST_REBOOT_RECONCILIATION_REQUIRED'
            action = 'REINSPECT_ATTEMPT_AND_INTERACTIVE_SESSION'
            decision = 'MANUAL_REVIEW'
        elif incident == 'SCHEDULER_RC0_WITHOUT_VALID_RESULT':
            state = 'RC0_WITHOUT_VALID_RESULT_RECONCILIATION_REQUIRED'
            action = 'PRESERVE_EVIDENCE_VALIDATE_RESULT_AND_SCHEDULER_RECORD'
            decision = 'MANUAL_REVIEW'
        else:
            state = 'UNCERTAIN_EXECUTION_RECONCILIATION_REQUIRED'
            action = 'PRESERVE_PARTIAL_EVIDENCE_MANUAL_REVIEW'
            decision = 'MANUAL_REVIEW'
    return {
        'schema_version':REPORT_SCHEMA,'state':state,'task_id':TASK,'attempt_id':ATTEMPT,
        'incident':incident, 'package_sha256':PACKAGE_SHA,
        'staging_receipt_sha256':RECEIPT_SHA,
        'capture_sha256':digest,'observed_c3d_state':observed,
        'execution_evidence_present':present,
        'source_snapshot_not_current_authority':True,
        'observation_freshness_proven_now':False,
        'recovery_decision':decision, 'operator_next_action':action,
        'next_boundary':'PRESERVE_EVIDENCE_THEN_INDEPENDENT_OWNER_REVIEW',
        'fencing_released':False,'new_attempt_authorized':False,
        'retry_authorized':False,'worker_launch_authorized':False,
        'dispatch_authorized':False,'accepted':False,'production_ready':False,
        'windows_mutation':False,'smb_mutation':False,'cleanup_executed':False,
        'illustrator_execution':False,'network_probe_performed':False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('source-check','evaluate','incident'), required=True)
    parser.add_argument('--capture', type=Path)
    parser.add_argument('--incident', choices=INCIDENTS, default='NONE')
    a=parser.parse_args(argv)
    try:
        source_check()
        if a.mode=='source-check':
            require(a.capture is None and a.incident == 'NONE',
                    'source-check takes no capture/incident')
            print('GDL_W27C3E_RECOVERY=SOURCE_CHECK_PASS')
            print('WINDOWS_WRITE=false RETRY_AUTHORIZED=false DISPATCH_ALLOWED=false')
            return 0
        if a.mode=='incident':
            require(a.capture is None and a.incident!='NONE',
                    'incident mode requires category without a capture')
            out=decide(a.incident,None)
        else:
            require(a.capture is not None, 'evaluate requires one evidence capture')
            obs,digest=read_capture(a.capture)
            out=decide(a.incident,obs,digest)
        print(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True))
        print('GDL_W27C3E_RECOVERY=' + out['state'])
        return 0
    except (RecoveryBlocked,InspectionFailure,SnapshotBlocked,OSError,ValueError) as exc:
        print('GDL_W27C3E_RECOVERY=BLOCKED reason='+str(exc),file=sys.stderr)
        return 2

if __name__=='__main__':
    raise SystemExit(main())

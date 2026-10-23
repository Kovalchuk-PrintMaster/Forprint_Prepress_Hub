#!/usr/bin/env python3
"""C3F: local ONLY one-use fence simulation, never a dispatch/launch authorization.

A real Windows start_claim.json is NOT made by this module. The only write action
is an explicitly requested new-only tmp/<run>/fence_simulation.json on s01.
The module reuses C3E recovery triage, not an ad-hoc reading of C3D evidence.
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

from gdl_w27c3e_recovery_decision_engine_v0_1 import (
    RecoveryBlocked, ROOT, TASK, ATTEMPT, PACKAGE_SHA, RECEIPT_SHA,
    INCIDENTS, read_capture, decide, source_check as c3e_source_check,
)
from gdl_w27c3a_runner_source_review_v0_1 import (
    RunnerBlocked, JSX_SHA, source_check as c3a_source_check,
)

CONTRACT = ROOT / 'coordination/graphic_design_lab/worker_runtime/gdl_w27c3f_one_use_fence_contract_v0_1.json'
SCHEMA = 'gdl_w27c3f_one_use_fence_contract_v0_1'
CLAIM_SCHEMA = 'gdl_w27c3f_local_fence_simulation_v0_1'
REPORT_SCHEMA = 'gdl_w27c3f_one_use_fence_report_v0_1'
HEX = re.compile(r'^[0-9a-f]{64}$')
NAME = 'fence_simulation.json'

class FenceBlocked(RuntimeError):
    pass


def require(ok: bool, message: str) -> None:
    if not ok:
        raise FenceBlocked(message)


def source_check() -> dict:
    try:
        c3e_source_check()
        c3a_source_check()
        require(CONTRACT.is_file() and not CONTRACT.is_symlink(), 'C3F contract missing/unsafe')
        c = json.loads(CONTRACT.read_text('utf-8'), object_pairs_hook=_unique)
    except (RecoveryBlocked, RunnerBlocked, ValueError, UnicodeError, OSError) as exc:
        raise FenceBlocked('C3E/C3A prerequisite or C3F source unavailable') from exc
    expected = {
        'schema_version':SCHEMA,'state':'OFFLINE_ATOMIC_FENCE_SIMULATION_ONLY',
        'task_id':TASK,'attempt_id':ATTEMPT,'package_sha256':PACKAGE_SHA,
        'jsx_sha256':JSX_SHA,'staging_receipt_sha256':RECEIPT_SHA,
        'recovery_schema':'gdl_w27c3e_recovery_decision_v0_1',
        'claim_schema':CLAIM_SCHEMA,'claim_basename':NAME,
        'claim_location':'tmp/<existing-non-symlink-run-dir>/fence_simulation.json',
        'create_mode':'O_CREAT_O_EXCL_NOFOLLOW_MODE_0600_FSYNC',
        'simulation_only':True,'uses_windows_claim_path':False,
        'windows_write':False,'ssh_or_com':False,'execution_authorized':False,
        'dispatch_authorized':False,'retry_authorized':False,
        'fencing_released':False,'production_ready':False,'accepted':False,
        'automatic_cleanup':False,'synthetic_only':True,
        'blueprint_review_pending':True,
    }
    require(type(c) is dict and set(c)==set(expected), 'C3F contract shape changed')
    for k,v in expected.items():
        require(type(c[k]) is type(v) and c[k]==v, 'C3F policy/authority mismatch: '+k)
    return c


def _unique(pairs):
    obj={}
    for k,v in pairs:
        if k in obj:
            raise FenceBlocked('duplicate JSON key')
        obj[k]=v
    return obj


def canonical(doc: dict) -> bytes:
    return (json.dumps(doc,ensure_ascii=True,sort_keys=True,separators=(',',':'))+'\n').encode('ascii')


def location(path: Path, *, must_exist: bool) -> Path:
    """Only an exact file in one already existing repo tmp child directory."""
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    # Reject dot segments even when normpath would hide a traversal attempt.
    require('..' not in candidate.parts and candidate.name==NAME,
            'claim path must use simulation basename and no traversal')
    tmp = ROOT / 'tmp'
    try:
        parts = candidate.relative_to(tmp).parts
    except ValueError as exc:
        raise FenceBlocked('simulation must remain under project tmp') from exc
    require(len(parts)==2 and re.fullmatch(r'[a-z][a-z0-9_-]{2,63}',parts[0]) is not None,
            'simulation must be a direct child of an existing named run dir')
    for p in (tmp,tmp/parts[0]):
        try: mode=p.lstat().st_mode
        except OSError as exc: raise FenceBlocked('simulation parent absent') from exc
        require(stat.S_ISDIR(mode), 'simulation parent not a regular directory')
    if must_exist:
        try: mode=candidate.lstat().st_mode
        except OSError as exc: raise FenceBlocked('claim missing') from exc
        require(stat.S_ISREG(mode), 'claim is not a regular file')
    else:
        require(not candidate.exists() and not candidate.is_symlink(),
                'claim already exists or unsafe; preserve and never repeat')
    return candidate


def build_claim(capture_digest: str) -> dict:
    require(type(capture_digest) is str and HEX.fullmatch(capture_digest) is not None,
            'capture sha256 missing')
    return {'schema_version':CLAIM_SCHEMA,'state':'SIMULATED_FENCE_HELD_NO_EXECUTION_AUTHORITY',
            'task_id':TASK,'attempt_id':ATTEMPT,'package_sha256':PACKAGE_SHA,
            'jsx_sha256':JSX_SHA,'staging_receipt_sha256':RECEIPT_SHA,
            'source_capture_sha256':capture_digest,'simulation_only':True,
            'windows_write':False,'worker_launch_authorized':False,
            'dispatch_authorized':False,'retry_authorized':False,
            'accepted':False,'production_ready':False,'cleanup_executed':False}


def create_once(path: Path, doc: dict) -> str:
    """Atomic local simulation: even interrupted/zero-byte output fences reuse."""
    dest=location(path,must_exist=False)
    require(doc==build_claim(doc.get('source_capture_sha256')), 'claim content not pinned')
    data=canonical(doc)
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0)
    try:
        fd=os.open(dest, flags, 0o600)
    except OSError as exc:
        raise FenceBlocked('simulation claim exists/unsafe/unwritable; no retry') from exc
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        # Best-effort durability of the new directory entry on POSIX Linux s01.
        dfd=os.open(dest.parent,os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
        try: os.fsync(dfd)
        finally: os.close(dfd)
    except OSError as exc:
        # NEVER unlink a partial claim. Presence is a fence even on fsync failure.
        raise FenceBlocked('simulation write interrupted; preserve claim and review') from exc
    return sha256(data).hexdigest()


def inspect(path: Path) -> tuple[dict,str]:
    dest=location(path,must_exist=True)
    try:
        fd=os.open(dest,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
        with os.fdopen(fd,'rb') as stream:
            info=os.fstat(stream.fileno())
            require(stat.S_ISREG(info.st_mode) and 50<=info.st_size<=8192,
                    'partial, empty or oversized claim: preserve for reconciliation')
            raw=stream.read(8193)
        require(len(raw)==info.st_size, 'claim changed during read')
        obj=json.loads(raw.decode('ascii'),object_pairs_hook=_unique)
        require(type(obj) is dict and canonical(obj)==raw,
                'claim not canonical; preservation required')
        require(obj==build_claim(obj.get('source_capture_sha256')),
                'claim binding/authority changed; preservation required')
        return obj,sha256(raw).hexdigest()
    except (OSError,UnicodeError,ValueError) as exc:
        raise FenceBlocked('cannot verify claim; preserve for reconciliation') from exc


def projection(incident: str, obs: dict|None, digest: str|None, claim: dict|None=None,
               claim_digest: str|None=None) -> dict:
    try: recovery=decide(incident,obs,digest)
    except RecoveryBlocked as exc: raise FenceBlocked('C3E reconciliation failed') from exc
    if claim is not None:
        require(type(claim_digest) is str and HEX.fullmatch(claim_digest) is not None,
                'claim digest missing')
        require(claim==build_claim(claim.get('source_capture_sha256')) and
                claim['source_capture_sha256']==digest and
                sha256(canonical(claim)).hexdigest()==claim_digest,
                'simulation claim corrupted or unbound')
        state='SIMULATED_CLAIM_EXISTS_FENCED_MANUAL_REVIEW'
        next_action='PRESERVE_SIMULATION_AND_SOURCE_EVIDENCE'
    elif recovery['state']=='INERT_STAGED_SNAPSHOT_NO_EXECUTION_OR_LAUNCH_AUTHORITY':
        state='INERT_SNAPSHOT_SIMULATION_ELIGIBLE_ONLY'
        next_action='OPTIONAL_LOCAL_SIMULATION_ONLY_NOT_EXECUTION'
    else:
        state='RECOVERY_INCIDENT_BLOCKS_FENCE_SIMULATION'
        next_action='PRESERVE_EVIDENCE_AND_RECONCILE'
    return {'schema_version':REPORT_SCHEMA,'state':state,'task_id':TASK,
            'attempt_id':ATTEMPT,'incident':incident,'package_sha256':PACKAGE_SHA,
            'staging_receipt_sha256':RECEIPT_SHA,'source_capture_sha256':digest,
            'simulated_claim_sha256':claim_digest,'source_recovery_state':recovery['state'],
            'operator_next_action':next_action,'simulation_only':True,
            'simulation_claim_present':claim is not None,
            'live_freshness_proven':False,'windows_write':False,
            'execution_authorized':False,'dispatch_authorized':False,
            'retry_authorized':False,'fencing_released':False,
            'accepted':False,'production_ready':False,'cleanup_executed':False}


def output(doc:dict):
    print(json.dumps(doc,indent=2,ensure_ascii=False,sort_keys=True))
    print('GDL_W27C3F_ONE_USE_FENCE='+doc['state'])


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',required=True,choices=('source-check','assess','simulate-create','inspect-simulation'))
    p.add_argument('--capture',type=Path)
    p.add_argument('--incident',choices=INCIDENTS,default='NONE')
    p.add_argument('--simulation',type=Path)
    p.add_argument('--confirm-local-simulation',action='store_true')
    a=p.parse_args(argv)
    try:
        source_check()
        if a.mode=='source-check':
            require(not any((a.capture,a.simulation,a.confirm_local_simulation)) and a.incident=='NONE',
                    'source-check needs no arguments')
            print('GDL_W27C3F_ONE_USE_FENCE=SOURCE_CHECK_PASS')
            print('WINDOWS_WRITE=false DISPATCH=false EXECUTION=false CLAIM_LOCAL_SIMULATION_ONLY=true')
            return 0
        require(a.capture is not None,'C3E/C3D captured evidence required')
        obs,digest=read_capture(a.capture)
        if a.mode=='assess':
            require(a.simulation is None and not a.confirm_local_simulation,'assess is read-only')
            output(projection(a.incident,obs,digest))
        elif a.mode=='simulate-create':
            require(a.simulation is not None and a.confirm_local_simulation and a.incident=='NONE',
                    'explicit local simulation only, incident NONE required')
            decision=projection(a.incident,obs,digest)
            require(decision['state']=='INERT_SNAPSHOT_SIMULATION_ELIGIBLE_ONLY',
                    'recovery incident/evidence prohibits even local simulation')
            doc=build_claim(digest)
            claim_sha=create_once(a.simulation,doc)
            result=projection(a.incident,obs,digest,doc,claim_sha)
            output(result)
        else:
            require(a.simulation is not None and not a.confirm_local_simulation,
                    'inspect requires a path and no confirmation')
            claim,claim_sha=inspect(a.simulation)
            output(projection(a.incident,obs,digest,claim,claim_sha))
        return 0
    except (FenceBlocked,RecoveryBlocked,OSError,ValueError) as exc:
        print('GDL_W27C3F_ONE_USE_FENCE=BLOCKED reason='+str(exc),file=sys.stderr)
        return 2

if __name__=='__main__':
    raise SystemExit(main())

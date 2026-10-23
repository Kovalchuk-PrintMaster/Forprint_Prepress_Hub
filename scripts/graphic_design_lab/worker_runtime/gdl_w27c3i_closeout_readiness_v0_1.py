#!/usr/bin/env python3
"""C3I: read-only native synthetic worker lifecycle gate atlas.

Reuses C3H independent evidence/recovery review and C3F local simulation
verification. No SSH, Windows writes, COM, Task Scheduler, execution or
acceptance. Source/staged/historical evidence MUST NOT grant authority.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

from gdl_w27c3h_worker_return_handoff_v0_1 import (
    HandoffBlocked, source_check as h_source_check, review as h_review,
)
from gdl_w27c3f_one_use_fence_simulator_v0_1 import (
    FenceBlocked, source_check as f_source_check,
    inspect as f_inspect, projection as f_projection,
)
from gdl_w27c3e_recovery_decision_engine_v0_1 import (
    INCIDENTS, RecoveryBlocked, read_capture,
)

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / 'coordination/graphic_design_lab/worker_runtime/gdl_w27c3i_closeout_readiness_contract_v0_1.json'
SCHEMA = 'gdl_w27c3i_closeout_readiness_contract_v0_1'
REPORT = 'gdl_w27c3i_closeout_readiness_report_v0_1'
TASK = 'gdl-w27c-native-001'
ATTEMPT = 'a0001'
PACKAGE = 'd1949844b3ab2d68936facf8012e6b8fba1ecd1134597f2e6f4139ef1449b3e7'
RECEIPT = '0c025e0132795c7f0e7011fbe52fdf17c44f9f19fc01dcd34f77684e4b11e827'


class ReadinessBlocked(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ReadinessBlocked(message)


def unique(pairs):
    output = {}
    for key, value in pairs:
        if key in output:
            raise ReadinessBlocked('duplicate contract JSON key')
        output[key] = value
    return output


def source_check() -> dict:
    try:
        h_source_check()  # Includes C3B/C3E/C3G and upstream C1/C3A provenance
        f_source_check()  # Includes C3A and C3E, no actual runner or claim
        require(CONTRACT.is_file() and not CONTRACT.is_symlink(), 'unsafe C3I contract')
        contract = json.loads(CONTRACT.read_text('utf-8'), object_pairs_hook=unique)
    except (HandoffBlocked, FenceBlocked, OSError, UnicodeError, ValueError) as exc:
        raise ReadinessBlocked('missing or invalid C3I/upstream source contract') from exc
    expect = {
        'schema_version': SCHEMA,
        'state': 'OFFLINE_NATIVE_CYCLE_GATE_ATLAS_REVIEW_ONLY',
        'task_id': TASK, 'attempt_id': ATTEMPT,
        'package_sha256': PACKAGE, 'staging_receipt_sha256': RECEIPT,
        'source_handoff_schema': 'gdl_w27c3h_worker_return_handoff_v0_1',
        'source_local_fence_schema': 'gdl_w27c3f_local_fence_simulation_v0_1',
        'mode': 'INDEPENDENT_READ_ONLY_GATE_ATLAS',
        'pilot_scope': 'SYNTHETIC_ONLY',
        'authority_issued': False, 'dispatcher_owner_approved': False,
        'real_attempt_claim_created': False,
        'native_execution_independently_proven': False,
        'editability_independently_proven': False,
        'operator_acceptance_recorded': False,
        'realtime_readiness_proven': False,
        'launch_enabled': False, 'retry_enabled': False,
        'cleanup_enabled': False, 'production_ready': False,
        'windows_write': False, 'ssh_used': False,
        'blueprint_review_deferred_not_waived': True,
    }
    require(type(contract) is dict and set(contract) == set(expect),
            'C3I contract shape mismatch')
    for key, wanted in expect.items():
        require(type(contract[key]) is type(wanted) and contract[key] == wanted,
                'C3I authority/identity binding mismatch: ' + key)
    return contract


def gate(gate_id: str, group: str, status: str, evidence: str, required: bool = True) -> dict:
    return {'id': gate_id, 'group': group, 'status': status,
            'evidence': evidence, 'required_for_native_closeout': required}


def atlas(h: dict, *, local_claim: dict | None = None,
          local_claim_sha: str | None = None) -> dict:
    """Only validated upstream projections. No acceptance or launch flags imported."""
    require(type(h) is dict and h.get('schema_version') == 'gdl_w27c3h_worker_return_handoff_v0_1',
            'C3H projection missing')
    require(h.get('task_id') == TASK and h.get('attempt_id') == ATTEMPT and
            h.get('package_sha256') == PACKAGE and
            h.get('staging_receipt_sha256') == RECEIPT,
            'C3H task / attempt / source mismatch')
    for key in ('execution_authorized', 'dispatch_authorized', 'retry_authorized',
                'accepted', 'production_ready', 'closeout_completed',
                'com_execution_independently_proven',
                'native_ai_is_editable_independently_proven'):
        require(h.get(key) is False, 'unsafe C3H gate: ' + key)
    require(h.get('c3g_proof_is_not_worker_execution_fence') is True,
            'synthetic Windows fence promoted to native authority')
    require(h.get('blueprint_authority_review_pending') is True and
            h.get('owner_approval_recorded') is False,
            'independent approval boundary unexpectedly modified')
    require((local_claim is None) == (local_claim_sha is None),
            'local simulation evidence incomplete')
    if local_claim is not None:
        require(local_claim.get('simulation_only') is True and
                local_claim.get('source_capture_sha256') == h['c3d_capture_sha256'] and
                local_claim.get('task_id') == TASK and
                local_claim.get('attempt_id') == ATTEMPT,
                'C3F simulation is unbound or has authority flags')
    state_map = {
        'INERT_STAGING_NATIVE_RETURN_ABSENT_AUTHORITY_PENDING':
            'TECHNICAL_FOUNDATIONS_RECONCILED_AUTHORITY_BLOCKED',
        'EXECUTION_EVIDENCE_PRESENT_RETURN_NOT_VERIFIED':
            'EXECUTION_EVIDENCE_PRESENT_MANUAL_RECONCILIATION',
        'INCIDENT_REQUIRES_FRESH_INSPECTION_AND_OWNER_REVIEW':
            'INCIDENT_STATE_STALE_REINSPECTION_REQUIRED',
        'NATIVE_RETURN_HASH_VERIFIED_NOT_ACCEPTED':
            'NATIVE_RETURN_BYTES_VERIFIED_CLOSEOUT_BLOCKED',
    }
    require(h['state'] in state_map, 'unknown C3H review state')
    gates = [
        gate('C1_C2_STAGED_IDENTITY', 'source', 'PRIOR_EVIDENCE_RECONCILED',
             'Pinned archive + staged receipt identity in C3H and C3D'),
        gate('C3B_RUNNER_ADAPTER', 'source', 'REVIEW_SOURCE_ONLY',
             'PowerShell candidate public entrypoint is review-only'),
        gate('C3D_WINDOWS_OBSERVATION', 'observation', 'HISTORICAL_SNAPSHOT_VALIDATED',
             'C3D capture SHA256 validated; not live freshness at dispatch'),
        gate('C3E_RECOVERY', 'recovery', 'FAIL_CLOSED_RECONCILED',
             'C3H reused C3E; no automatic retry'),
        gate('C3F_LINUX_ATOMIC_CLAIM', 'fencing',
             'OFFLINE_SIMULATION_VERIFIED' if local_claim else 'SOURCE_CONTRACT_ONLY',
             'Simulation cannot create native Windows execution authority'),
        gate('C3G_WINDOWS_ATOMIC_CLAIM', 'fencing', 'ISOLATED_SYNTHETIC_PROOF_VALIDATED',
             'CreateNew marker only in separate synthetic Windows probe'),
        gate('INDEPENDENT_EXECUTION_AUTHORITY', 'authority', 'NOT_GRANTED',
             'Owner-issued expiring bounded proof must be independently verified'),
        gate('SINGLE_DISPATCH_OWNER_AND_ACTION', 'authority', 'NOT_APPROVED',
             'One dispatcher, schedule/action/token policy and review pending'),
        gate('FRESH_DISPATCH_PREFLIGHT', 'authority', 'NOT_PROVEN',
             'Historical session / PID / SSH check cannot authorize new execution'),
        gate('NATIVE_PRECLAIM_AND_EXECUTION_FENCE', 'execution', 'NOT_EXECUTED',
             'C3F/C3G synthetic claims not a real native task start claim'),
        gate('LIMITED_INTERACTIVE_NATIVE_EXECUTION', 'execution', 'NOT_EXECUTED_FOR_TASK',
             'W2.5.3 proof belongs to a different historical task'),
        gate('NATIVE_RESULT_AND_AI_RETURN', 'return',
             'HASHES_ONLY_NOT_ACCEPTED' if h['worker_return_supplied'] else 'ABSENT',
             'Actual returned bytes require independent checks; C3H never accepts'),
        gate('NATIVE_AI_EDITABILITY', 'acceptance', 'NOT_INDEPENDENTLY_PROVEN',
             'Independent Illustrator open/edit/reopen evidence still required'),
        gate('OWNER_TECHNICAL_CLOSEOUT', 'acceptance', 'NOT_GRANTED',
             'Worker result and technical acceptance are separate authority'),
        gate('PRODUCTION_OR_CUSTOMER_ACCESS', 'production', 'OUT_OF_SCOPE',
             'DEV FullControl/SMB not approved for real customer data', False),
    ]
    must = [x for x in gates if x['required_for_native_closeout']]
    missing = [x['id'] for x in must if x['status'] in {
        'NOT_GRANTED', 'NOT_APPROVED', 'NOT_PROVEN', 'NOT_EXECUTED',
        'NOT_EXECUTED_FOR_TASK', 'ABSENT', 'HASHES_ONLY_NOT_ACCEPTED',
        'NOT_INDEPENDENTLY_PROVEN', 'REVIEW_SOURCE_ONLY',
    }]
    require('INDEPENDENT_EXECUTION_AUTHORITY' in missing and
            'OWNER_TECHNICAL_CLOSEOUT' in missing,
            'C3I may not report readiness without independent authority')
    return {
        'schema_version': REPORT, 'state': state_map[h['state']],
        'task_id': TASK, 'attempt_id': ATTEMPT,
        'package_sha256': PACKAGE, 'staging_receipt_sha256': RECEIPT,
        'c3h_state': h['state'],
        'c3d_capture_sha256': h['c3d_capture_sha256'],
        'c3g_synthetic_claim_sha256': h['c3g_synthetic_claim_sha256'],
        'local_simulation_claim_sha256': local_claim_sha,
        'local_simulation_only': True,
        'source_handoff_review_only': True,
        'gate_count': len(gates), 'blocking_gate_count': len(missing),
        'blocking_gate_ids': missing, 'gates': gates,
        'next_boundary': 'PRESERVE_EVIDENCE_INDEPENDENT_OWNER_AND_BLUEPRINT_AUTHORITY_REVIEW'
             if h['state'] == 'INERT_STAGING_NATIVE_RETURN_ABSENT_AUTHORITY_PENDING'
             else 'PRESERVE_EVIDENCE_MANUAL_RECONCILIATION',
        'real_execution_fence_verified': False, 'fresh_dispatch_readiness_proven': False,
        'owner_approval_recorded': False, 'blueprint_review_deferred_not_waived': True,
        'worker_launch_authorized': False, 'dispatch_authorized': False,
        'retry_authorized': False, 'native_closeout_completed': False,
        'accepted': False, 'production_ready': False,
        'windows_write': False, 'ssh_used': False, 'cleanup_executed': False,
    }


def review(capture: Path, probe: Path, verification: Path, incident: str,
           simulation: Path | None = None,
           result: Path | None = None, native_ai: Path | None = None,
           expected_result_sha256: str | None = None,
           expected_native_sha256: str | None = None) -> dict:
    require(incident in INCIDENTS, 'unknown incident')
    h = h_review(capture, probe, verification, incident, result, native_ai,
                 expected_result_sha256, expected_native_sha256)
    claim = digest = None
    if simulation is not None:
        claim, digest = f_inspect(simulation)
        observed, observed_digest = read_capture(capture)
        proof = f_projection(incident, observed, observed_digest, claim, digest)
        require(proof['state'] == 'SIMULATED_CLAIM_EXISTS_FENCED_MANUAL_REVIEW'
                and proof['source_capture_sha256'] == h['c3d_capture_sha256'],
                'C3F simulation inconsistent with C3H evidence')
    return atlas(h, local_claim=claim, local_claim_sha=digest)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode', required=True, choices=('source-check', 'review'))
    ap.add_argument('--capture', type=Path)
    ap.add_argument('--probe', type=Path)
    ap.add_argument('--verify', type=Path)
    ap.add_argument('--simulation', type=Path)
    ap.add_argument('--incident', choices=INCIDENTS, default='NONE')
    ap.add_argument('--result', type=Path)
    ap.add_argument('--native-ai', type=Path)
    ap.add_argument('--expected-result-sha256')
    ap.add_argument('--expected-native-sha256')
    args = ap.parse_args(argv)
    try:
        source_check()
        if args.mode == 'source-check':
            require(not any((args.capture,args.probe,args.verify,args.simulation,
                             args.result,args.native_ai,args.expected_result_sha256,
                             args.expected_native_sha256)) and args.incident == 'NONE',
                    'source-check does not take evidence/incident arguments')
            print('GDL_W27C3I_CLOSEOUT_READINESS=SOURCE_CHECK_PASS')
            print('WINDOWS_WRITE=false SSH=false DISPATCH=false CLOSEOUT=false')
            return 0
        require(all((args.capture,args.probe,args.verify)),
                'review requires C3D capture and C3G probe/verify files')
        output = review(args.capture, args.probe, args.verify, args.incident,
                        args.simulation, args.result, args.native_ai,
                        args.expected_result_sha256, args.expected_native_sha256)
        print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
        print('GDL_W27C3I_CLOSEOUT_READINESS=' + output['state'])
        return 0
    except (ReadinessBlocked, HandoffBlocked, FenceBlocked, RecoveryBlocked,
            ValueError, OSError, UnicodeError) as exc:
        print('GDL_W27C3I_CLOSEOUT_READINESS=BLOCKED reason=' + str(exc), file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())

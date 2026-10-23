#!/usr/bin/env python3
"""GDL W2.7-C3C: evidence snapshot reconciliation, NOT dispatch or live authority.

Strictly compares W2.7-B verified-stage, W2.7-C2 read-only desktop evidence,
and W2.7-C3B source-review projections. Inputs are snapshot JSON captures; even
valid snapshots NEVER imply current readiness, permission, COM proof, or rerun.
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
    ReviewBlocked, source_check as c3b_source_check,
)

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / 'coordination/graphic_design_lab/worker_runtime/gdl_w27c3c_snapshot_contract_v0_1.json'
TASK = 'gdl-w27c-native-001'
ATTEMPT = 'a0001'
PACKAGE_SHA = 'd1949844b3ab2d68936facf8012e6b8fba1ecd1134597f2e6f4139ef1449b3e7'
JSX_SHA = '98780bcd7939df58f16aa0e123ced5efc4956ed43cc6438d0516b43d4d819902'
RUNNER_SHA = '8ef7a0298646295c24d2d091ce433ac0cfcdbb4831b05469c493ff6d3ce8b934'
RECEIPT_SHA = '0c025e0132795c7f0e7011fbe52fdf17c44f9f19fc01dcd34f77684e4b11e827'
ARCHIVE_BYTES = 5120
JSX_BYTES = 3791
SCHEMA = 'gdl_w27c3c_snapshot_contract_v0_1'
STAGE = 'SYNTHETIC_STAGE_SHA_VERIFIED_NOT_EXECUTED'
HOST_READY = 'STAGED_NATIVE_HOST_PREREQUISITES_PRESENT_AUTHORITY_PENDING'
RUNNER_REVIEW = 'EXECUTION_ADAPTER_SOURCE_REVIEW_ONLY_AUTHORITY_PENDING'
HEX = re.compile(r'^[0-9a-f]{64}$')

class SnapshotBlocked(RuntimeError):
    pass

def reject(reason: str) -> None:
    raise SnapshotBlocked(reason)

def check_source() -> dict:
    try:
        c3b, _ = c3b_source_check()
        if not CONTRACT.is_file() or CONTRACT.is_symlink():
            reject('contract missing or symlinked')
        contract = json.loads(CONTRACT.read_text('utf-8'))
    except (ReviewBlocked, OSError, ValueError, UnicodeError) as exc:
        raise SnapshotBlocked('C3B dependency or C3C contract unavailable') from exc
    expected = {
        'schema_version': SCHEMA,
        'state': 'SNAPSHOT_RECONCILIATION_ONLY_NO_DISPATCH',
        'task_id': TASK, 'attempt_id': ATTEMPT,
        'package_sha256': PACKAGE_SHA, 'jsx_sha256': JSX_SHA,
        'runner_sha256': RUNNER_SHA, 'staging_receipt_sha256': RECEIPT_SHA,
        'authoritative_for_launch': False, 'independent_acceptance': False,
        'synthetic_only': True, 'windows_write': False,
        'automatic_retry': False, 'production_publish': False,
        'requires_fresh_pre_execution_recheck': True,
    }
    if not isinstance(contract, dict) or set(contract) != set(expected):
        reject('snapshot contract shape changed')
    for k, v in expected.items():
        if type(contract[k]) is not type(v) or contract[k] != v:
            reject('snapshot contract altered: ' + k)
    if (c3b['execution_authorized'] is not False or
            c3b['runner_source_sha256'] != RUNNER_SHA or
            c3b['launch_route_implemented'] is not False):
        reject('C3B source review no longer matches')
    return contract


def read_capture(path: Path, root: Path = ROOT) -> dict:
    """Accept one JSON object, optionally followed by the single expected status line.

    No arbitrary directory traversal, symlinks, broad file reads, or log parsing.
    """
    p = Path(path)
    if not p.is_absolute():
        p = root / p
    normalized = Path(os.path.normpath(str(p)))
    allowed = root / 'tmp'
    try:
        rel = normalized.relative_to(allowed)
    except ValueError as exc:
        raise SnapshotBlocked('capture must be inside repository tmp') from exc
    if len(rel.parts) != 2 or not rel.parts[1].endswith('.txt'):
        reject('capture must be tmp/<capture-dir>/<name>.txt')
    folder = allowed / rel.parts[0]
    try:
        for item, is_dir in ((allowed, True), (folder, True), (normalized, False)):
            meta = item.lstat()
            if is_dir and not stat.S_ISDIR(meta.st_mode):
                reject('unsafe capture directory')
            if not is_dir and (not stat.S_ISREG(meta.st_mode) or meta.st_size > 32768 or meta.st_size < 32):
                reject('unsafe capture file')
        content = normalized.read_text('utf-8')
    except (OSError, UnicodeError) as exc:
        raise SnapshotBlocked('capture inaccessible/invalid') from exc
    content = content.strip()
    try:
        obj, offset = json.JSONDecoder().raw_decode(content)
    except ValueError as exc:
        raise SnapshotBlocked('capture must begin with JSON object') from exc
    if not isinstance(obj, dict):
        reject('capture must contain object')
    tail = content[offset:].strip()
    if tail and not re.fullmatch(r'GDL_W27(?:B_WINDOWS_STAGE|C2_NATIVE_PREFLIGHT|C3B_NATIVE_WORKER)=[A-Z0-9_]+', tail):
        reject('capture trailing output invalid')
    return obj


def equal(doc: dict, key: str, value: object) -> None:
    if doc.get(key) != value or type(doc.get(key)) is not type(value):
        reject('snapshot binding mismatch: ' + key)


def false_keys(doc: dict, keys: tuple[str, ...]) -> None:
    for name in keys:
        equal(doc, name, False)


def reconcile(stage: dict, host: dict, runner: dict) -> dict:
    """Three *historical* observations, not a current run command or approval."""
    for title, obj in [('stage', stage), ('host', host), ('runner', runner)]:
        if not isinstance(obj, dict):
            reject(title + ' snapshot is not a JSON object')
        equal(obj, 'task_id', TASK)
        equal(obj, 'attempt_id', ATTEMPT)
    for doc in (stage, host):
        equal(doc, 'archive_sha256', PACKAGE_SHA)
        equal(doc, 'archive_bytes', ARCHIVE_BYTES)
        equal(doc, 'staging_receipt_sha256', RECEIPT_SHA)
    equal(stage, 'schema_version', 'gdl_w27b_windows_stage_controller_v0_1')
    equal(stage, 'mode', 'verify')
    equal(stage, 'state', STAGE)
    equal(stage, 'host', 'PREPRESS')
    equal(stage, 'ssh_account', r'PREPRESS\Work')
    false_keys(stage, ('windows_mutation','payload_extracted','illustrator_execution',
                       'worker_launch_authorized','production_ready','accepted',
                       'scheduled_tasks_mutated','client_files_touched','smb_mutation','cleanup_executed'))
    equal(host, 'schema_version', 'gdl_w27c2_native_execution_preflight_v0_1')
    equal(host, 'host', 'PREPRESS')
    equal(host, 'windows_account', r'PREPRESS\Work')
    equal(host, 'jsx_sha256', JSX_SHA)
    equal(host, 'jsx_bytes', JSX_BYTES)
    false_keys(host, ('windows_mutation','payload_extracted','illustrator_execution',
                      'com_attach_performed','scheduled_tasks_mutated','worker_launch_authorized',
                      'dispatch_authorized','production_ready','accepted','cleanup_executed',
                      'client_files_touched','smb_mutation'))
    state = host.get('state')
    if state not in (HOST_READY, 'WAITING_FOR_INTERACTIVE_SESSION_NOT_AUTHORIZED',
                     'WAITING_FOR_ILLUSTRATOR_OR_DESKTOP_NOT_AUTHORIZED'):
        reject('unexpected host readiness state')
    if state == HOST_READY:
        for k in ('session_id','preexisting_illustrator_pid'):
            if type(host.get(k)) is not int or host[k] <= 0:
                reject('invalid observed interactive process')
    elif host.get('preexisting_illustrator_pid') is not None:
        reject('waiting state contains Illustrator PID')
    equal(runner, 'schema_version', 'gdl_w27c3b_native_source_review_v0_1')
    equal(runner, 'state', RUNNER_REVIEW)
    equal(runner, 'package_sha256', PACKAGE_SHA)
    equal(runner, 'jsx_sha256', JSX_SHA)
    equal(runner, 'runner_source_sha256', RUNNER_SHA)
    equal(runner, 'source_reviewed', True)
    equal(runner, 'runtime_verified', False)
    false_keys(runner, ('runner_launch_implemented','execution_authorized','windows_mutation',
                        'com_attach_performed','illustrator_execution','accepted','production_ready'))
    return {
        'schema_version': 'gdl_w27c3c_snapshot_reconciliation_v0_1',
        'state': ('HISTORICAL_PREREQUISITES_RECONCILED_AUTHORITY_PENDING'
                  if state == HOST_READY else 'HISTORICAL_HOST_WAITING_NO_DISPATCH'),
        'task_id': TASK, 'attempt_id': ATTEMPT,
        'package_sha256': PACKAGE_SHA, 'jsx_sha256': JSX_SHA,
        'runner_sha256': RUNNER_SHA,
        'staging_receipt_sha256': RECEIPT_SHA,
        'host_readiness_observed': state == HOST_READY,
        'readiness_observation_session_id': host.get('session_id'),
        'readiness_observation_illustrator_pid': host.get('preexisting_illustrator_pid'),
        'snapshots_not_live': True, 'fresh_recheck_required_before_any_execution': True,
        'attempt_claim_independently_checked': False,
        'worker_launch_authorized': False, 'dispatch_authorized': False,
        'automatic_accept': False, 'production_ready': False,
        'windows_mutation': False, 'illustrator_executed': False,
        'retry_authorized': False, 'next_boundary': 'ONE_USE_ATTEMPT_FENCING_AND_AUTHORITY_REVIEW',
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode', choices=('source-check', 'reconcile'), required=True)
    ap.add_argument('--stage-capture', type=Path)
    ap.add_argument('--readiness-capture', type=Path)
    ap.add_argument('--runner-capture', type=Path)
    a = ap.parse_args(argv)
    try:
        check_source()
        if a.mode == 'source-check':
            if any((a.stage_capture, a.readiness_capture, a.runner_capture)):
                reject('source-check requires no captures')
            print('GDL_W27C3C_SNAPSHOT=SOURCE_CHECK_PASS')
            print('WINDOWS_WRITE=false DISPATCH_ALLOWED=false FRESHNESS_PROVEN=false')
            return 0
        if not all((a.stage_capture, a.readiness_capture, a.runner_capture)):
            reject('three explicit evidence snapshots required')
        report = reconcile(read_capture(a.stage_capture), read_capture(a.readiness_capture),
                           read_capture(a.runner_capture))
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
        print('GDL_W27C3C_SNAPSHOT=' + report['state'])
        return 0
    except (SnapshotBlocked, ReviewBlocked, OSError, ValueError) as exc:
        print('GDL_W27C3C_SNAPSHOT=BLOCKED reason=' + str(exc), file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())

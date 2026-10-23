#!/usr/bin/env python3
"""ForPrint W2.7-C3B: OFFLINE source and evidence review, never worker launch.

PowerShell contains a *private, uncallable* native execution candidate; its
public entrypoint only emits a review projection. This CLI performs no SSH,
Windows write, Task Scheduler, COM, JSX, or production operation. A source
SHA and markers are *not* a security code audit or runtime proof.
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

from gdl_w27c3a_runner_source_review_v0_1 import (
    RunnerBlocked as PreviousBlocked,
    source_check as previous_source_check,
)
from gdl_w27c_native_candidate_review_v0_1 import (
    CandidateBlocked, inspect_candidate, source_check as native_source_check,
)
from gdl_w27_illustrator_task_package_v0_1 import PackageBlocked, read_regular, repo_tmp_path

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / 'coordination/graphic_design_lab/worker_runtime/gdl_w27c3b_native_worker_contract_v0_1.json'
RUNNER = Path(__file__).with_name('gdl_w27c3b_native_limited_runner_candidate_v0_1.ps1')
PACKAGE_SHA = 'd1949844b3ab2d68936facf8012e6b8fba1ecd1134597f2e6f4139ef1449b3e7'
JSX_SHA = '98780bcd7939df58f16aa0e123ced5efc4956ed43cc6438d0516b43d4d819902'
EXPECTED_RUNNER_SHA = '8ef7a0298646295c24d2d091ce433ac0cfcdbb4831b05469c493ff6d3ce8b934'
TASK, ATTEMPT = 'gdl-w27c-native-001', 'a0001'
CONTRACT_SCHEMA = 'gdl_w27c3b_native_worker_contract_v0_1'
RESULT_SCHEMA = 'gdl_w27c3b_native_worker_result_v0_1'
RUNNER_STATE = 'EXECUTION_ADAPTER_SOURCE_REVIEW_ONLY_AUTHORITY_PENDING'
RESULT_STATE = 'RESULT_BYTES_HASH_VERIFIED_AUTHORITY_PENDING'
HEX = re.compile(r'^[0-9a-f]{64}$')


class ReviewBlocked(RuntimeError):
    pass


def sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def fail(message: str) -> None:
    raise ReviewBlocked(message)


def source_check() -> tuple[dict, bytes]:
    try:
        prior, _ = previous_source_check()
        profile, jsx = native_source_check()
        if not CONTRACT.is_file() or CONTRACT.is_symlink() or not RUNNER.is_file() or RUNNER.is_symlink():
            fail('contract or candidate missing/symlinked')
        contract = json.loads(CONTRACT.read_text('utf-8'))
        raw = RUNNER.read_bytes()
    except (PreviousBlocked, CandidateBlocked, OSError, ValueError, UnicodeError) as exc:
        raise ReviewBlocked('C3A/C1 provenance or C3B sources unavailable') from exc
    expected = {
        'schema_version': CONTRACT_SCHEMA,
        'state': RUNNER_STATE,
        'task_id': TASK,
        'attempt_id': ATTEMPT,
        'package_sha256': PACKAGE_SHA,
        'jsx_sha256': JSX_SHA,
        'result_schema': RESULT_SCHEMA,
        'entrypoint_mode': 'review',
        'source_candidate_only': True,
        'actual_runtime_execution_tested': False,
        'launch_route_implemented': False,
        'execution_authority_parser_implemented': False,
        'execution_authorized': False,
        'blueprint_review_pending': True,
        'automatic_accept': False,
        'production_publish': False,
        'customer_data_allowed': False,
        'cleanup_allowed': False,
        'windows_mutation_by_review': False,
        'runner_source_sha256': contract.get('runner_source_sha256') if isinstance(contract, dict) else None,
    }
    if not isinstance(contract, dict) or set(contract) != set(expected):
        fail('contract fields changed')
    if any(type(contract[k]) is not type(v) or contract[k] != v for k, v in expected.items()):
        fail('contract scope/authority mismatch')
    if (contract['runner_source_sha256'] != EXPECTED_RUNNER_SHA or
            not isinstance(contract['runner_source_sha256'], str) or
            not HEX.fullmatch(contract['runner_source_sha256'])):
        fail('runner digest malformed')
    if not (2000 <= len(raw) <= 35000 and raw.isascii() and
            sha(raw) == EXPECTED_RUNNER_SHA):
        fail('candidate source digest/size/encoding mismatch')
    ps = raw.decode('ascii')
    guard = (
        "param([ValidateSet('review')][string]$Mode='review')",
        '$ReviewedExecutionAuthorityImplemented=$false',
        "if(-not $ReviewedExecutionAuthorityImplemented) { Fail 'BLUEPRINT_EXECUTION_GATE_NOT_IMPLEMENTED' }",
        "Fail 'PUBLIC_EXECUTION_NOT_AUTHORIZED'",
        'function Invoke-NativeCandidate(', 'function ProveLimitedInteractive(',
        'function SourceBindings {', 'function WriteOnce(',
        '[IO.FileMode]::CreateNew', 'GetTokenInformation(',
        'TOKEN_NOT_LIMITED', 'EXISTING_ATTEMPT_EVIDENCE_NO_RERUN',
        'GetActiveObject(', '.DoJavaScript(', 'FORPRINT_W27C_SYNTHETIC_NATIVE_REOPENED',
        'worker_result.json', 'native_result.ai', 'NO_DISPATCH',
    )
    if any(x not in ps for x in guard):
        fail('candidate security/review marker missing')
    if (ps.count('Invoke-NativeCandidate') != 1 or
        ps.count('BLUEPRINT_EXECUTION_GATE_NOT_IMPLEMENTED') != 1 or
        ps.count("[ValidateSet('review')]") != 1):
        fail('entrypoint or authority gate changed')
    if ('Start-ScheduledTask' in ps or 'Register-ScheduledTask' in ps or
        'Invoke-Expression' in ps or 'Remove-Item' in ps or
        'Set-Acl' in ps or 'app.quit' in ps):
        fail('unexpected launcher or destructive API')
    if (prior['execution_authorized'] is not False or
        prior['runner_launch_implemented'] is not False or
        profile['launch_authorized'] is not False or
        sha(jsx) != JSX_SHA):
        fail('predecessor execution authority changed')
    return contract, raw


def review_package(path: Path, expected_sha: str, contract: dict) -> dict:
    if expected_sha != PACKAGE_SHA:
        fail('expected archive digest is not pinned to C1')
    try:
        raw = read_regular(repo_tmp_path(path, must_exist=True), 262144)
        config, jsx = native_source_check()
        result = inspect_candidate(raw, expected_sha, config, jsx)
    except (CandidateBlocked, PackageBlocked, OSError) as exc:
        raise ReviewBlocked('C1 immutable package invalid') from exc
    if (sha(raw) != PACKAGE_SHA or result['task_id'] != TASK or
        result['attempt_id'] != ATTEMPT or result['worker_launch_authorized'] is not False):
        fail('native package identity or authority changed')
    return {
        'schema_version': 'gdl_w27c3b_native_source_review_v0_1',
        'state': RUNNER_STATE,
        'task_id': TASK, 'attempt_id': ATTEMPT,
        'package_sha256': PACKAGE_SHA, 'jsx_sha256': JSX_SHA,
        'runner_source_sha256': contract['runner_source_sha256'],
        'source_reviewed': True, 'runtime_verified': False,
        'runner_launch_implemented': False, 'execution_authorized': False,
        'windows_mutation': False, 'com_attach_performed': False,
        'illustrator_execution': False, 'accepted': False, 'production_ready': False,
        'next_boundary': 'BLUEPRINT_AUTHORITY_AND_ONE_USE_DISPATCHER_REVIEW',
    }


def safe_evidence(path: Path, maximum: int) -> bytes:
    """No links/escape; result and AI must be returned together below repo/tmp."""
    tmp = ROOT / 'tmp'
    given = Path(path)
    if not given.is_absolute():
        given = ROOT / given
    # Lexical parent comparison precedes any filesystem resolution.
    rel = Path(os.path.normpath(str(given)))
    try:
        parts = rel.relative_to(tmp).parts
    except ValueError as exc:
        raise ReviewBlocked('evidence must be inside repository tmp') from exc
    if len(parts) != 2 or parts[0] in ('.', '..') or parts[1] in ('.', '..'):
        fail('evidence must be in one isolated tmp/return_dir/')
    folder = tmp / parts[0]
    try:
        if not stat.S_ISDIR(tmp.lstat().st_mode):
            fail('unsafe tmp directory')
        t = folder.lstat()
        f = rel.lstat()
    except OSError as exc:
        raise ReviewBlocked('evidence or return directory missing') from exc
    if not stat.S_ISDIR(t.st_mode) or not stat.S_ISREG(f.st_mode):
        fail('symlink or special evidence path denied')
    if f.st_size <= 0 or f.st_size > maximum:
        fail('evidence file size invalid')
    return rel.read_bytes()


def verify_result(result_path: Path, ai_path: Path, expected_result_sha: str,
                  expected_ai_sha: str, contract: dict) -> dict:
    if any(not isinstance(x, str) or not HEX.fullmatch(x)
           for x in (expected_result_sha, expected_ai_sha)):
        fail('independently known result and AI SHA256 required')
    # Never accept local fake evidence outside a single sandbox return directory.
    if Path(result_path).parent != Path(ai_path).parent:
        fail('result and AI must share the same return directory')
    if Path(result_path).name != 'worker_result.json' or Path(ai_path).name != 'native_result.ai':
        fail('unexpected evidence filenames')
    rb = safe_evidence(result_path, 16384)
    ai = safe_evidence(ai_path, 64 * 1024 * 1024)
    if sha(rb) != expected_result_sha or sha(ai) != expected_ai_sha:
        fail('independent evidence digest mismatch')
    try:
        doc = json.loads(rb.decode('utf-8'))
    except (ValueError, UnicodeError) as exc:
        raise ReviewBlocked('worker result not valid UTF8 JSON') from exc
    if not isinstance(doc, dict):
        fail('worker result not an object')
    expected_fields = {
        'schema_version','state','task_id','attempt_id','host','windows_account',
        'package_sha256','jsx_sha256','runner_sha256','session_id',
        'preexisting_illustrator_pid','token_limited_verified','com_attach_performed',
        'illustrator_executed','native_ai_saved_reopened','editable_area_text',
        'native_ai_sha256','native_ai_bytes','phase','error_code',
        'independent_acceptance','execution_authority_review_pending',
        'production_ready','accepted','client_files_touched','smb_mutation',
        'cleanup_executed','automatic_retry',
    }
    if set(doc) != expected_fields:
        fail('worker result schema fields mismatch')
    expected = {
        'schema_version': RESULT_SCHEMA,
        'state': 'NATIVE_AI_REOPENED_LOCAL',
        'task_id': TASK, 'attempt_id': ATTEMPT,
        'host': 'PREPRESS', 'windows_account': r'PREPRESS\Work',
        'package_sha256': PACKAGE_SHA,'jsx_sha256': JSX_SHA,
        'runner_sha256': contract['runner_source_sha256'],
        'token_limited_verified': True, 'com_attach_performed': True,
        'illustrator_executed': True, 'native_ai_saved_reopened': True,
        'editable_area_text': True, 'native_ai_sha256': expected_ai_sha,
        'native_ai_bytes': len(ai), 'phase': 'DONE','error_code': 'NONE',
        'independent_acceptance': False, 'execution_authority_review_pending': True,
        'production_ready': False, 'accepted': False,
        'client_files_touched': False,'smb_mutation': False,
        'cleanup_executed': False,'automatic_retry': False,
    }
    if any(doc[k] != v or type(doc[k]) is not type(v) for k, v in expected.items()):
        fail('machine evidence identity/flags/artifact binding invalid')
    if any(type(doc[k]) is not int or doc[k] <= 0 for k in
           ('session_id','preexisting_illustrator_pid')):
        fail('session/Illustrator PID invalid')
    if len(ai) < 1000:
        fail('native evidence implausibly small')
    return {
        'schema_version':'gdl_w27c3b_native_evidence_verification_v0_1',
        'state': RESULT_STATE, 'task_id': TASK, 'attempt_id': ATTEMPT,
        'worker_result_sha256': expected_result_sha, 'native_ai_sha256': expected_ai_sha,
        'native_ai_bytes': len(ai), 'machine_report_fields_valid': True,
        'independent_file_hashes_valid': True,
        'com_execution_independently_proven': False,
        'document_editability_independently_proven': False,
        'execution_authorized': False, 'accepted': False, 'production_ready': False,
        'next_boundary':'PROVENANCE_BLUEPRINT_AUTHORITY_AND_HUMAN_ACCEPTANCE_REVIEW',
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode', required=True, choices=('source-check','review-package','verify-result'))
    ap.add_argument('--archive', type=Path)
    ap.add_argument('--expected-archive-sha256')
    ap.add_argument('--result', type=Path)
    ap.add_argument('--native-ai', type=Path)
    ap.add_argument('--expected-result-sha256')
    ap.add_argument('--expected-native-sha256')
    a = ap.parse_args(argv)
    try:
        config, _ = source_check()
        if a.mode == 'source-check':
            if any((a.archive,a.expected_archive_sha256,a.result,a.native_ai,
                    a.expected_result_sha256,a.expected_native_sha256)):
                fail('source-check arguments invalid')
            print('GDL_W27C3B_NATIVE_WORKER=SOURCE_CHECK_PASS')
            print('WINDOWS_WRITE=false COM_EXECUTION=false LAUNCH_AUTHORIZED=false')
            return 0
        if a.mode == 'review-package':
            if not (a.archive and a.expected_archive_sha256) or any((
                a.result,a.native_ai,a.expected_result_sha256,a.expected_native_sha256)):
                fail('review-package arguments invalid')
            doc = review_package(a.archive, a.expected_archive_sha256, config)
        else:
            if not all((a.result,a.native_ai,a.expected_result_sha256,a.expected_native_sha256)) or any((
                a.archive,a.expected_archive_sha256)):
                fail('verify-result arguments invalid')
            doc = verify_result(a.result,a.native_ai,a.expected_result_sha256,
                                a.expected_native_sha256,config)
        print(json.dumps(doc,ensure_ascii=False,sort_keys=True,indent=2))
        print('GDL_W27C3B_NATIVE_WORKER=' + doc['state'])
        return 0
    except (ReviewBlocked,PreviousBlocked,CandidateBlocked,PackageBlocked,OSError,ValueError) as exc:
        print('GDL_W27C3B_NATIVE_WORKER=BLOCKED reason='+str(exc),file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())

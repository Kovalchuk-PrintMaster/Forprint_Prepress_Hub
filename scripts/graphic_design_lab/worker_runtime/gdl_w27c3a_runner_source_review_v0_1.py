#!/usr/bin/env python3
"""W2.7-C3A: offline, non-executable Limited Token Runner source candidate.

This intentionally has NO SSH, COM, PowerShell invocation, Task Scheduler action,
Windows write, launch/dispatch authority, acceptance, or production operations.
Use it to bind a reviewed runner *design* to the immutable C1 package. Actual
execution belongs to a separately authorized/implemented later work boundary.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys

from gdl_w27_illustrator_task_package_v0_1 import PackageBlocked, read_regular, repo_tmp_path
from gdl_w27c_native_candidate_review_v0_1 import (
    CandidateBlocked, inspect_candidate, source_check as candidate_source_check,
    TASK, ATTEMPT,
)

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / 'coordination/graphic_design_lab/worker_runtime/gdl_w27c3a_runner_source_contract_v0_1.json'
TEMPLATE = Path(__file__).with_name('gdl_w27c3a_limited_runner_source_v0_1.ps1')
SCHEMA = 'gdl_w27c3a_runner_source_contract_v0_1'
PACKAGE_SHA = 'd1949844b3ab2d68936facf8012e6b8fba1ecd1134597f2e6f4139ef1449b3e7'
JSX_SHA = '98780bcd7939df58f16aa0e123ced5efc4956ed43cc6438d0516b43d4d819902'
RESULT_SCHEMA = 'gdl_w27c3_worker_result_contract_v0_1'
STATE = 'RUNNER_SOURCE_DRAFT_AUTHORITY_PENDING'
HEX = re.compile(r'^[a-f0-9]{64}$')
PLACEHOLDERS = ('__TASK_ID__', '__ATTEMPT_ID__', '__ARCHIVE_SHA__', '__JSX_SHA__')
EXPECTED = ['export/native_result.ai', 'export/worker_result.json']


class RunnerBlocked(RuntimeError):
    pass


def fail(reason: str) -> None:
    raise RunnerBlocked(reason)


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def source_check() -> tuple[dict, str]:
    try:
        profile, jsx = candidate_source_check()
        if any(not x.is_file() or x.is_symlink() for x in (CONTRACT, TEMPLATE)):
            fail('source contract/template missing or symlinked')
        config = json.loads(CONTRACT.read_text('utf-8'))
        raw = TEMPLATE.read_bytes()
    except (CandidateBlocked, PackageBlocked, OSError, UnicodeError, ValueError) as exc:
        raise RunnerBlocked('W27C1 profile or C3A source unavailable') from exc
    fields = {
        'schema_version', 'state', 'task_id', 'attempt_id', 'package_sha256',
        'jsx_sha256', 'expected_outputs', 'worker_result_schema', 'template_sha256',
        'source_review_only', 'runner_launch_implemented', 'execution_authorized',
        'blueprint_review_pending', 'automatic_accept', 'production_publish',
        'customer_data_allowed', 'cleanup_allowed', 'write_set',
    }
    if not isinstance(config, dict) or set(config) != fields:
        fail('C3A contract shape changed')
    expected = {
        'schema_version': SCHEMA, 'state': STATE, 'task_id': TASK,
        'attempt_id': ATTEMPT, 'package_sha256': PACKAGE_SHA,
        'jsx_sha256': JSX_SHA, 'expected_outputs': EXPECTED,
        'worker_result_schema': RESULT_SCHEMA, 'source_review_only': True,
        'runner_launch_implemented': False, 'execution_authorized': False,
        'blueprint_review_pending': True, 'automatic_accept': False,
        'production_publish': False, 'customer_data_allowed': False,
        'cleanup_allowed': False, 'write_set': 'NONE_ON_WINDOWS',
    }
    if any(config.get(k) != value or type(config.get(k)) is not type(value)
           for k, value in expected.items()):
        fail('C3A scope/authority/identity mismatch')
    if profile['launch_authorized'] is not False or profile['jsx_sha256'] != JSX_SHA:
        fail('C1 profile no longer pinned or authorization changed')
    if digest(jsx) != JSX_SHA:
        fail('C1 JSX digest changed')
    if (not isinstance(config['template_sha256'], str)
            or not HEX.fullmatch(config['template_sha256'])
            or digest(raw) != config['template_sha256']):
        fail('runner template SHA256 differs from contract')
    if not raw.isascii() or len(raw) > 12000 or len(raw) < 500:
        fail('runner template encoding or size invalid')
    template = raw.decode('ascii')
    if any(template.count(p) != 1 for p in PLACEHOLDERS):
        fail('runner template placeholders absent or duplicated')
    required = (
        "[ValidateSet('review')]", "if ($Mode -ne 'review' -or $ExecutionAuthorized -or $LaunchImplemented)",
        '$ExecutionAuthorized = $false', '$LaunchImplemented = $false',
        'W27C3A_AUTHORITY_OR_IMPLEMENTATION_CHANGED',
        'RUNNER_SOURCE_DRAFT_AUTHORITY_PENDING', 'no_rerun_if_claim_exists',
        'no_overwrite_result', 'limited_token_required',
        'independent_artifact_sha_required', 'no_customer_files',
        'scheduled_tasks_mutated = $false', 'windows_mutation = $false',
    )
    if any(part not in template for part in required):
        fail('runner denial/contract markers missing')
    # This slice contains deliberately no executable path. Later runner cannot
    # be enabled by renaming a CLI argument or toggling a boolean here.
    forbidden = (
        'Start-ScheduledTask', 'Register-ScheduledTask', 'DoJavaScript',
        'GetActiveObject', 'CreateDirectory', 'FileMode]::CreateNew',
        'SaveAs(', 'Remove-Item', 'Set-Acl', 'Start-Process',
        'Stop-Process', 'Unregister-ScheduledTask', 'Expand-Archive',
        'ExtractToDirectory', '[IO.File]::Write', 'Invoke-Expression',
    )
    if any(part.lower() in template.lower() for part in forbidden):
        fail('candidate contains executable/Windows-mutating API')
    return config, template


def render(config: dict, template: str) -> bytes:
    substitutions = {
        '__TASK_ID__': config['task_id'], '__ATTEMPT_ID__': config['attempt_id'],
        '__ARCHIVE_SHA__': config['package_sha256'],
        '__JSX_SHA__': config['jsx_sha256'],
    }
    for mark, value in substitutions.items():
        if template.count(mark) != 1:
            fail('draft placeholder mismatch')
        template = template.replace(mark, value)
    if any(mark in template for mark in substitutions):
        fail('unresolved candidate placeholder')
    return template.encode('ascii')


def review_package(raw: bytes, expected_sha: str, config: dict) -> dict:
    if expected_sha != PACKAGE_SHA:
        fail('package digest must be independently C1-pinned')
    try:
        profile, script = candidate_source_check()
        result = inspect_candidate(raw, expected_sha, profile, script)
    except (PackageBlocked, CandidateBlocked) as exc:
        raise RunnerBlocked('W27C1 package/profile verification failed') from exc
    if (result['state'] != 'SYNTHETIC_NATIVE_CANDIDATE_VERIFIED_NOT_EXECUTABLE_BY_WORKER'
            or result['task_id'] != TASK or result['attempt_id'] != ATTEMPT
            or result['jsx_sha256'] != JSX_SHA
            or result['worker_launch_authorized'] is not False):
        fail('candidate report authority/identity mismatch')
    return {
        'schema_version': 'gdl_w27c3a_runner_source_review_v0_1',
        'state': STATE, 'task_id': TASK, 'attempt_id': ATTEMPT,
        'package_sha256': digest(raw), 'jsx_sha256': JSX_SHA,
        'runner_source_sha256': config['template_sha256'],
        'package_verified': True, 'runner_source_verified': True,
        'runner_launch_implemented': False, 'execution_authorized': False,
        'windows_mutation': False, 'illustrator_execution': False,
        'accepted': False, 'production_ready': False,
        'next_boundary': 'BLUEPRINT_AUTHORITY_REVIEW_AND_EXECUTABLE_RUNNER_IMPLEMENTATION',
    }


def draft_path(path: Path, *, exists: bool) -> Path:
    try:
        p = repo_tmp_path(path, must_exist=exists) if exists else repo_tmp_path(path, must_exist=False)
    except PackageBlocked as exc:
        raise RunnerBlocked('draft path must be safe direct child of repository tmp') from exc
    if p.suffix.lower() != '.ps1':
        fail('runner draft must be .ps1')
    return p


def write_draft(path: Path, raw: bytes) -> None:
    path = draft_path(path, exists=False)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
    try:
        fd = os.open(path, flags, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise RunnerBlocked('new-only draft write failed; preserve partial file') from exc


def print_result(doc: dict) -> None:
    print(json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True))
    print('GDL_W27C3A_RUNNER_SOURCE=' + doc['state'])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode', required=True,
                    choices=('source-check', 'review-package', 'build-draft', 'verify-draft'))
    ap.add_argument('--archive', type=Path)
    ap.add_argument('--expected-archive-sha256')
    ap.add_argument('--output', type=Path)
    ap.add_argument('--draft', type=Path)
    ap.add_argument('--expected-draft-sha256')
    ap.add_argument('--confirm-local-draft', action='store_true')
    a = ap.parse_args(argv)
    try:
        config, template = source_check()
        if a.mode == 'source-check':
            if any((a.archive, a.expected_archive_sha256, a.output,
                    a.draft, a.expected_draft_sha256, a.confirm_local_draft)):
                fail('source-check accepts no other arguments')
            print('GDL_W27C3A_RUNNER_SOURCE=SOURCE_CHECK_PASS')
            print('WINDOWS_WRITE=false COM_EXECUTION=false RUNNER_LAUNCH_IMPLEMENTED=false')
            return 0
        if a.mode == 'review-package':
            if (not a.archive or not a.expected_archive_sha256 or a.output or
                    a.draft or a.expected_draft_sha256 or a.confirm_local_draft):
                fail('review-package arguments invalid')
            path = repo_tmp_path(a.archive, must_exist=True)
            raw = read_regular(path, 262144)
            print_result(review_package(raw, a.expected_archive_sha256, config))
            return 0
        expected = render(config, template)
        if a.mode == 'build-draft':
            if (not a.output or not a.confirm_local_draft or a.archive or
                    a.expected_archive_sha256 or a.draft or a.expected_draft_sha256):
                fail('build-draft arguments or explicit local confirmation invalid')
            write_draft(a.output, expected)
        else:
            if (not a.draft or a.output or a.archive or a.expected_archive_sha256 or
                    a.confirm_local_draft or a.expected_draft_sha256 is None or
                    not HEX.fullmatch(a.expected_draft_sha256)):
                fail('verify-draft arguments invalid')
            path = draft_path(a.draft, exists=True)
            stored = read_regular(path, 12000)
            if stored != expected or digest(stored) != a.expected_draft_sha256:
                fail('draft content or independent SHA256 mismatch')
        print_result({
            'schema_version': 'gdl_w27c3a_runner_source_receipt_v0_1',
            'state': 'RUNNER_DRAFT_NEW_ONLY_NOT_EXECUTABLE' if a.mode == 'build-draft'
            else 'RUNNER_DRAFT_SHA_VERIFIED_NOT_EXECUTABLE',
            'task_id': TASK, 'attempt_id': ATTEMPT,
            'draft_sha256': digest(expected), 'draft_bytes': len(expected),
            'local_draft_write': a.mode == 'build-draft',
            'windows_mutation': False, 'com_attach_performed': False,
            'illustrator_execution': False, 'runner_launch_implemented': False,
            'execution_authorized': False, 'accepted': False,
            'production_ready': False,
        })
        return 0
    except (RunnerBlocked, CandidateBlocked, PackageBlocked, OSError, ValueError) as exc:
        print('GDL_W27C3A_RUNNER_SOURCE=BLOCKED reason=' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

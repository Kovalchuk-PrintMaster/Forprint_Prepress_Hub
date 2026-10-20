#!/usr/bin/env python3
"""W1 candidate: universal Windows Worker contract + ephemeral *synthetic* smoke.

NO client SMB access, Windows access, provider startup, queue registration,
production authority, approval, real cleanup, or mutation of existing GDL.
Blueprint must review portfolio runtime ownership before enabling anything.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
from typing import Any

import yaml

CONTRACT = Path('coordination/graphic_design_lab/worker_runtime/windows_worker_w1_pilot_contract_v0_1.yaml')
SCHEMA = 'gdl_windows_worker_w1_pilot_contract_v0_1'
RESULT_SCHEMA = 'gdl_windows_worker_w1_synthetic_result_v0_1'
REQUIRED_STATES = frozenset(('QUEUED', 'CLAIMED', 'RUNNING', 'RESULT_LOCAL_COMPLETE',
                             'RESULT_UPLOADED', 'VERIFIED', 'ACCEPTED', 'RETRY_REQUIRED',
                             'WAITING_FOR_WORKER', 'WAITING_FOR_INTERACTIVE_SESSION',
                             'NEEDS_RECONCILIATION', 'BLOCKED'))
TASK = re.compile(r'^[a-z][a-z0-9-]{3,63}$')
ATTEMPT = re.compile(r'^a[0-9]{4}$')
ADAPTER = re.compile(r'^[a-z][a-z0-9_]{1,47}$')
HEX = re.compile(r'^[a-f0-9]{64}$')
WINDOWS_DIRS = ('runtime', 'jobs', 'cache', 'logs', 'config')
PROOF_ARTIFACTS = frozenset(('editable_ai', 'review_pdf', 'page_png'))


class W1Blocked(ValueError):
    pass


def _dir(path: Path) -> bool:
    return path.is_dir() and not path.is_symlink() and stat.S_ISDIR(path.stat().st_mode)


def _file(path: Path) -> bool:
    return path.is_file() and not path.is_symlink() and stat.S_ISREG(path.stat().st_mode)


def _sha(path: Path) -> str:
    h = sha256()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def _mapping(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise W1Blocked('contract_mapping_required')
    return raw


def check_contract(raw: dict[str, Any]) -> dict[str, Any]:
    c = _mapping(raw)
    if c.get('schema_version') != SCHEMA or c.get('status') != 'PILOT_PROPOSAL_PENDING_BLUEPRINT_REVIEW':
        raise W1Blocked('contract_unapproved_or_incompatible')
    if c.get('scope') != 'GDL_SYNTHETIC_FOUNDATION_ONLY':
        raise W1Blocked('contract_scope_unsafe')
    authority = _mapping(c.get('authority'))
    if (authority.get('portfolio_worker_owner') != 'BLUEPRINT_DECISION_PENDING'
            or authority.get('dispatcher') != 'NOT_IMPLEMENTED'
            or authority.get('planning') != 'NOT_IMPLEMENTED'
            or authority.get('client_smb_2777_private_data_safe') is not False
            or authority.get('git_commit_push') != 'NEVER_WORKER_AUTOMATIC'):
        raise W1Blocked('portfolio_authority_not_resolved')
    for key in ('automatic_acceptance', 'production_publish', 'client_workspace_mutation', 'worker_launch'):
        if authority.get(key) is not False:
            raise W1Blocked('contract_grants_forbidden_authority')
    ws = _mapping(c.get('workspace'))
    if (ws.get('client_existing_input') != 'input'
            or ws.get('client_existing_output') != 'output'
            or ws.get('service_root_candidate') != '.forprint'
            or ws.get('service_root_status') != 'NOT_CREATED_PENDING_SAMBA_ACCESS_AND_GC14_MIGRATION'
            or ws.get('gc14_migration_state') != 'NOT_STARTED'
            or ws.get('cleaning_client_output') != 'FORBIDDEN_UNTIL_HISTORY_DECOUPLED'):
        raise W1Blocked('workspace_migration_or_privacy_unresolved')
    windows = _mapping(c.get('windows'))
    if windows.get('root') != 'D:\\ForPrint\\Automation':
        raise W1Blocked('windows_local_root_unexpected')
    if any(windows.get(key) != key for key in WINDOWS_DIRS):
        raise W1Blocked('windows_layout_invalid')
    if windows.get('job_structure') != ['input', 'work', 'export']:
        raise W1Blocked('attempt_layout_invalid')
    if windows.get('work_dir_pattern') != 'jobs/<task-id>/<attempt-id>/{input,work,export}':
        raise W1Blocked('attempt_isolation_not_declared')
    for k in ('one_active_attempt_per_worker', 'interactive_user_session_required_for_gui',
              'network_copy_uses_sha256', 'local_staging_before_execution'):
        if windows.get(k) is not True:
            raise W1Blocked('windows_worker_invariant_missing')
    for k in ('windows_host_initialized', 'sessions_supported_proven', 'live_smb_execution'):
        if windows.get(k) is not False:
            raise W1Blocked('windows_unverified_capability')
    if (windows.get('recovery_policy') != 'RESTART_INCOMPLETE_ATTEMPTS_FROM_SCRATCH'
            or windows.get('local_complete_unuploaded') != 'VERIFY_THEN_REUPLOAD_WITHOUT_RERENDER'
            or windows.get('after_reboot_without_logon') != 'WAITING_FOR_INTERACTIVE_SESSION'
            or windows.get('adapters_implemented') != []):
        raise W1Blocked('recovery_or_provider_state_invalid')
    ids = _mapping(c.get('identity'))
    for name, expected in [('task_id_pattern', TASK.pattern), ('attempt_id_pattern', ATTEMPT.pattern),
                           ('adapter_id_pattern', ADAPTER.pattern), ('source_sha256_pattern', HEX.pattern)]:
        if ids.get(name) != expected:
            raise W1Blocked('identity_pattern_changed')
    if ids.get('attempt_fencing_required_before_retry') is not True:
        raise W1Blocked('retry_fencing_missing')
    if not REQUIRED_STATES.issubset(c.get('states', [])):
        raise W1Blocked('task_states_incomplete')
    term = _mapping(c.get('terminal_acceptance'))
    if not all(term.get(x) is True for x in (
            'worker_rc_zero_not_sufficient', 'requires_independent_verification',
            'requires_expected_artifact_sha', 'requires_task_and_attempt_binding',
            'requires_explicit_human_authority_after_verification')):
        raise W1Blocked('terminal_acceptance_unsafe')
    clean = _mapping(c.get('cleanup'))
    if clean.get('policy') != 'REPORT_ONLY_NOT_IMPLEMENTED' or clean.get('no_automatic_deletion') is not True:
        raise W1Blocked('cleanup_authority_unsafe')
    for x in ('avoid_deleting_unuploaded_local_results', 'avoid_deleting_inflight_or_ambiguous_attempts',
              'avoid_deleting_unverified_or_blocked_evidence',
              'server_independent_terminal_ledger_required', 'never_delete_canonical_resources_on_age'):
        if clean.get(x) is not True:
            raise W1Blocked('cleanup_invariant_missing')
    pilot = _mapping(c.get('pilot'))
    if (not HEX.fullmatch(str(pilot.get('gc18_source_sha256')))
            or not TASK.fullmatch(str(pilot.get('task_id')))
            or pilot.get('native_page4_scope') != 'P04_BODY_ONLY'
            or pilot.get('private_jsx_stays_outside_git') is not True
            or pilot.get('next_boundary') != 'BLUEPRINT_REVIEW_AND_WINDOWS_CAPABILITY_PROOF'):
        raise W1Blocked('pilot_identity_or_boundary_invalid')
    return c


def load_contract(repo: Path) -> dict[str, Any]:
    root = repo.resolve(strict=True)
    p = root / CONTRACT
    if not _file(p) or p.stat().st_size > 64_000:
        raise W1Blocked('contract_missing_or_unsafe')
    return check_contract(yaml.safe_load(p.read_text(encoding='utf-8')))


def windows_attempt_relative(task: str, attempt: str) -> PurePosixPath:
    if not TASK.fullmatch(task) or not ATTEMPT.fullmatch(attempt):
        raise W1Blocked('task_or_attempt_id_invalid')
    return PurePosixPath('jobs') / task / attempt


def recovery_decision(*, server_state: str, current_owner_fenced: bool,
                      local_result_verified: bool, old_attempt_finished: bool) -> str:
    """A decision *only*. Never execute/retry/upload based on this projection."""
    if server_state not in REQUIRED_STATES:
        raise W1Blocked('unknown_server_state')
    if not all(type(v) is bool for v in
               (current_owner_fenced, local_result_verified, old_attempt_finished)):
        raise W1Blocked('recovery_boolean_required')
    if server_state in ('VERIFIED', 'ACCEPTED'):
        return 'DO_NOT_RERUN'
    if server_state in ('BLOCKED', 'NEEDS_RECONCILIATION'):
        return 'MANUAL_REVIEW'
    if not current_owner_fenced:
        return 'WAIT_FOR_FENCING'
    if local_result_verified:
        if old_attempt_finished and server_state in ('RESULT_LOCAL_COMPLETE',
                                                      'RESULT_UPLOADED', 'RETRY_REQUIRED'):
            return 'VERIFY_AND_REUPLOAD'
        return 'MANUAL_REVIEW'
    if old_attempt_finished:
        return 'START_NEW_ATTEMPT'
    return 'WAIT_FOR_FENCING'


def _relative_artifact(rel: Any) -> PurePosixPath:
    if not isinstance(rel, str) or not rel or '\\' in rel or '\x00' in rel:
        raise W1Blocked('artifact_path_invalid')
    p = PurePosixPath(rel)
    if p.is_absolute() or any(part in ('.', '..') for part in rel.split('/')) or len(p.parts) != 1:
        raise W1Blocked('artifact_path_outside_export')
    return p


def verify_synthetic_result(export: Path, result: dict[str, Any], *,
                            task: str, attempt: str, source_sha: str) -> dict[str, Any]:
    """Independent *synthetic* evidence validator. Never grants production acceptance."""
    if (not _dir(export) or not TASK.fullmatch(task) or not ATTEMPT.fullmatch(attempt)
            or not HEX.fullmatch(source_sha)):
        raise W1Blocked('result_scope_invalid')
    if not isinstance(result, dict) or result.get('schema_version') != RESULT_SCHEMA:
        raise W1Blocked('result_schema_invalid')
    if (result.get('task_id') != task or result.get('attempt_id') != attempt
            or result.get('source_sha256') != source_sha
            or not ADAPTER.fullmatch(str(result.get('adapter_id', '')))):
        raise W1Blocked('result_identity_mismatch')
    if (result.get('worker_rc') != 0 or result.get('worker_state') != 'LOCAL_COMPLETE'
            or result.get('production_ready') is not False
            or result.get('dispatch_authorized') is not False):
        raise W1Blocked('worker_result_not_local_complete_or_unsafe')
    artifacts = result.get('artifacts')
    if not isinstance(artifacts, list) or not artifacts or len(artifacts) > 16:
        raise W1Blocked('artifact_manifest_missing')
    seen: set[str] = set()
    kinds: set[str] = set()
    for a in artifacts:
        if not isinstance(a, dict) or a.get('kind') not in PROOF_ARTIFACTS:
            raise W1Blocked('artifact_kind_invalid')
        relative = _relative_artifact(a.get('filename'))
        if relative.name in seen or a['kind'] in kinds:
            raise W1Blocked('artifact_duplicate')
        seen.add(relative.name)
        kinds.add(a['kind'])
        path = export / relative.name
        if not _file(path) or path.stat().st_size <= 0 or path.stat().st_size > 100_000_000:
            raise W1Blocked('artifact_missing_or_unsafe')
        if type(a.get('size_bytes')) is not int or path.stat().st_size != a['size_bytes']:
            raise W1Blocked('artifact_size_mismatch')
        if not isinstance(a.get('sha256'), str) or not HEX.fullmatch(a['sha256']) or _sha(path) != a['sha256']:
            raise W1Blocked('artifact_sha256_mismatch')
    return {'state': 'SYNTHETIC_LOCAL_EVIDENCE_VERIFIED_REVIEW_ONLY',
            'artifact_count': len(artifacts), 'task_id': task, 'attempt_id': attempt,
            'windows_execution': False, 'production_ready': False,
            'human_accepted': False}


def synthetic_smoke(repo: Path, contract: dict[str, Any]) -> dict[str, str]:
    root = repo.resolve(strict=True)
    tmp = root / 'tmp'
    if not _dir(tmp):
        raise W1Blocked('repo_tmp_unsafe_or_missing')
    task = contract['pilot']['task_id']
    source_sha = contract['pilot']['gc18_source_sha256']
    attempt = 'a0001'
    # Create and delete ONLY a fresh synthetic scratch under this project's tmp/.
    with tempfile.TemporaryDirectory(prefix='gdl-w1-synthetic-', dir=tmp) as scratch:
        workspace = Path(scratch) / 'D_ForPrint_Automation_SIMULATED'
        for d in WINDOWS_DIRS:
            (workspace / d).mkdir(parents=True)
        local = workspace.joinpath(*windows_attempt_relative(task, attempt).parts)
        for d in ('input', 'work', 'export'):
            (local / d).mkdir(parents=True)
        target = local / 'export' / 'synthetic_document.ai'
        target.write_bytes(b'SYNTHETIC_W1_NON_ILLUSTRATOR_PROOF\n')
        result = {'schema_version': RESULT_SCHEMA, 'task_id': task,
                  'attempt_id': attempt, 'source_sha256': source_sha,
                  'adapter_id': 'illustrator', 'worker_rc': 0,
                  'worker_state': 'LOCAL_COMPLETE', 'production_ready': False,
                  'dispatch_authorized': False,
                  'artifacts': [{'kind': 'editable_ai', 'filename': target.name,
                                 'size_bytes': target.stat().st_size, 'sha256': _sha(target)}]}
        verified = verify_synthetic_result(local / 'export', result, task=task,
                                           attempt=attempt, source_sha=source_sha)
        crash = recovery_decision(server_state='RUNNING', current_owner_fenced=False,
                                  local_result_verified=False, old_attempt_finished=True)
        rerun = recovery_decision(server_state='RETRY_REQUIRED', current_owner_fenced=True,
                                  local_result_verified=False, old_attempt_finished=True)
        reupload = recovery_decision(server_state='RESULT_LOCAL_COMPLETE', current_owner_fenced=True,
                                     local_result_verified=True, old_attempt_finished=True)
        skip = recovery_decision(server_state='ACCEPTED', current_owner_fenced=False,
                                 local_result_verified=True, old_attempt_finished=False)
        if (crash, rerun, reupload, skip) != ('WAIT_FOR_FENCING', 'START_NEW_ATTEMPT',
                                             'VERIFY_AND_REUPLOAD', 'DO_NOT_RERUN'):
            raise W1Blocked('synthetic_recovery_assertions_failed')
        if verified['artifact_count'] != 1:
            raise W1Blocked('synthetic_artifact_count_invalid')
    # tmp/<scratch> self-deleted, not even a persistent synthetic fixture is created.
    return {'state': 'SYNTHETIC_SMOKE_PASS', 'crash': crash, 'rerun': rerun,
            'unuploaded': reupload, 'accepted': skip}


def main() -> int:
    p = argparse.ArgumentParser(description='GDL Windows W1 candidate, read-only + ephemeral synthetic tests only')
    p.add_argument('--repo', type=Path, default=Path('.'))
    p.add_argument('--mode', choices=('check', 'smoke'), required=True)
    args = p.parse_args()
    try:
        c = load_contract(args.repo)
        if args.mode == 'smoke':
            s = synthetic_smoke(args.repo, c)
            print('GDL_WINDOWS_WORKER_W1=' + s['state'])
            for k in ('crash', 'rerun', 'unuploaded', 'accepted'):
                print('DECISION_' + k.upper() + '=' + s[k])
        else:
            print('GDL_WINDOWS_WORKER_W1=CONTRACT_CHECK_PASS')
        print('BLUEPRINT_REVIEW_REQUIRED=true')
        print('WINDOWS_WORKER_IMPLEMENTED=false')
        print('WINDOWS_SESSION_VERIFIED=false')
        print('SMB_WRITE=false')
        print('GC14_MUTATED=false')
        print('WINDOWS_EXECUTION=false')
        print('AUTOMATIC_CLEANUP=false')
        print('PRODUCTION_READY=false')
        return 0
    except (W1Blocked, OSError, TypeError, KeyError, ValueError, yaml.YAMLError) as exc:
        # No private text or file paths in logs.
        print('GDL_WINDOWS_WORKER_W1=BLOCKED')
        print('ERROR_CLASS=' + (str(exc) if isinstance(exc, W1Blocked) else type(exc).__name__))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

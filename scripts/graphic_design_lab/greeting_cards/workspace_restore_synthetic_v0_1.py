#!/usr/bin/env python3
"""GDL D09/D12: fail-closed *synthetic-only* client workspace skeleton proof.

Do not use this command to restore real client files, resources, or production
workspace state. No PDF/Illustrator invocation. No external network access.

This is a bounded first stage toward a real client workspace initializer.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any
from zipfile import ZipFile, BadZipFile

import yaml

SCRIPT_ID = 'gdl_workspace_restore_synthetic_v0_1'
WORKSPACE = '_forprint_automation'
CONTRACT = 'coordination/graphic_design_lab/client_workflows/client_workspace_architecture_v0_1.yaml'
PROOF = '.forprint_synthetic_restore_proof.json'
SCRATCH = 'gdl_workspace_restore_scratch'
CASE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$')
SYNTHETIC_MEMBER = 'SYNTHETIC_NOT_AN_ACCEPTED_HANDOFF.txt'
SYNTHETIC_INPUTS = (('synthetic_invalid_01.zip', b'synthetic-only-one'),
                    ('synthetic_invalid_02.zip', b'synthetic-only-two'))


class RestoreBlocked(ValueError):
    pass


def sha_path(path: Path) -> str:
    h = sha256()
    with path.open('rb') as stream:
        for piece in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(piece)
    return h.hexdigest()


def regular_directory(path: Path) -> bool:
    return not path.is_symlink() and path.is_dir() and stat.S_ISDIR(path.stat().st_mode)


def get_source(repo: Path) -> tuple[dict[str, Any], str]:
    source = repo / CONTRACT
    if source.is_symlink() or not source.is_file():
        raise RestoreBlocked('workspace_contract_missing_or_unsafe')
    raw = source.read_bytes()
    value = yaml.safe_load(raw)
    if not isinstance(value, dict) or value.get('schema_version') != 'gdl_client_workspace_architecture_v0_1':
        raise RestoreBlocked('workspace_contract_schema_invalid')
    if value.get('status') != 'ACTIVE_EMPIRICAL_ARCHITECTURE' or value.get('workspace_dir_name') != WORKSPACE:
        raise RestoreBlocked('workspace_contract_not_active')
    tree = value.get('tree')
    if not isinstance(tree, dict) or any(x not in tree for x in ('jobs', 'previews', 'archive')):
        raise RestoreBlocked('workspace_contract_tree_invalid')
    return value, sha256(raw).hexdigest()


def get_locations(repo: Path, case_id: str) -> tuple[Path, Path, Path]:
    # Never expand to arbitrary SMB/client paths. This first slice is strictly in repo/tmp.
    if not CASE.fullmatch(case_id) or case_id in ('.', '..'):
        raise RestoreBlocked('invalid_synthetic_case_id')
    repo = repo.resolve(strict=True)
    tmp = repo / 'tmp'
    if not regular_directory(tmp):
        raise RestoreBlocked('repository_tmp_not_regular')
    scratch = tmp / SCRATCH
    if scratch.is_symlink() or (scratch.exists() and not regular_directory(scratch)):
        raise RestoreBlocked('scratch_root_unsafe')
    case_dir = scratch / case_id
    if case_dir.is_symlink() or case_dir.exists() and not regular_directory(case_dir):
        raise RestoreBlocked('case_dir_unsafe')
    workspace = case_dir / WORKSPACE
    if workspace.is_symlink():
        raise RestoreBlocked('workspace_symlink_forbidden')
    return scratch, case_dir, workspace


def create(repo: Path, case_id: str) -> Path:
    _, contract_sha = get_source(repo)
    scratch, case_dir, workspace = get_locations(repo, case_id)
    if case_dir.exists():
        raise RestoreBlocked('case_already_exists_no_overwrite')
    scratch.mkdir(mode=0o750, exist_ok=True)
    # Recheck parent: creation intentionally exclusive; no cleanup on unexpected I/O error.
    case_dir.mkdir(mode=0o750, exist_ok=False)
    workspace.mkdir(mode=0o750, exist_ok=False)
    (workspace / 'input').mkdir(mode=0o750, exist_ok=False)
    (workspace / 'output').mkdir(mode=0o750, exist_ok=False)
    receipt = {
        'schema_version': SCRIPT_ID,
        'status': 'SYNTHETIC_SKELETON_CREATED_NOT_CLIENT_RESTORE',
        'case_id': case_id,
        'contract_sha256': contract_sha,
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'created_dirs': ['input', 'output'],
        'source': 'PROJECT_ARCHITECTURE_CONTRACT_ONLY',
        'copied_real_client_assets': False,
        'server_private_resource_restore': False,
        'windows_worker_verified': False,
        'pdf_builder_invoked': False,
        'production_authority': False,
    }
    with (workspace / PROOF).open('x', encoding='utf-8') as output:
        json.dump(receipt, output, ensure_ascii=False, sort_keys=True, indent=2)
        output.write('\n')
    return workspace


def verify(repo: Path, case_id: str, *, expect_empty: bool = False) -> dict[str, Any]:
    _, contract_sha = get_source(repo)
    _, _, workspace = get_locations(repo, case_id)
    if not regular_directory(workspace):
        raise RestoreBlocked('workspace_missing_or_unsafe')
    for folder in ('input', 'output'):
        path = workspace / folder
        if not regular_directory(path):
            raise RestoreBlocked('operational_directory_missing_or_unsafe')
    proof = workspace / PROOF
    if proof.is_symlink() or not proof.is_file():
        raise RestoreBlocked('restore_receipt_missing_or_unsafe')
    try:
        data = json.loads(proof.read_text(encoding='utf-8'))
    except (ValueError, OSError) as exc:
        raise RestoreBlocked('restore_receipt_invalid') from exc
    if (data.get('schema_version') != SCRIPT_ID
            or data.get('status') != 'SYNTHETIC_SKELETON_CREATED_NOT_CLIENT_RESTORE'
            or data.get('case_id') != case_id
            or data.get('contract_sha256') != contract_sha
            or data.get('created_dirs') != ['input', 'output']
            or data.get('copied_real_client_assets') is not False
            or data.get('production_authority') is not False):
        raise RestoreBlocked('restore_receipt_identity_mismatch')
    counts = {}
    for folder in ('input', 'output'):
        items = list((workspace / folder).iterdir())
        if any(p.is_symlink() for p in items):
            raise RestoreBlocked('workspace_top_level_symlink_forbidden')
        counts[folder] = len(items)
    if expect_empty and any(counts.values()):
        raise RestoreBlocked('expected_empty_skeleton')
    return {'status': 'SYNTHETIC_SKELETON_VERIFIED', 'case_id': case_id,
            'contract_sha256': contract_sha, 'entry_counts': counts,
            'real_client_recovery_proven': False}


def _verify_smoke_evidence(workspace: Path, expected_sha: dict[str, str]) -> int:
    """Check the recorded GC14 outcome without regenerating or deleting files."""
    outputs = sorted((workspace / 'output').iterdir())
    if len(outputs) != len(expected_sha):
        raise RestoreBlocked('gc14_synthetic_result_count_invalid')
    seen: set[str] = set()
    for index in outputs:
        if not regular_directory(index):
            raise RestoreBlocked('unsafe_queue_output')
        source_path, report_path = index / 'source_info.json', index / 'report.json'
        if (any(p.is_symlink() or not p.is_file() for p in (source_path, report_path))
                or any(not regular_directory(index / sub) for sub in ('pdf', 'png'))):
            raise RestoreBlocked('gc14_synthetic_evidence_structure_invalid')
        source = json.loads(source_path.read_text(encoding='utf-8'))
        report = json.loads(report_path.read_text(encoding='utf-8'))
        filename = source.get('source_archive')
        if (filename not in expected_sha or filename in seen
                or source.get('source_sha256') != expected_sha[filename]
                or report.get('source_sha256') != expected_sha[filename]
                or report.get('source_archive') != filename
                or report.get('reason') != 'UNSUPPORTED_ARCHIVE_ENVELOPE'
                or report.get('status') != 'BLOCKED'
                or report.get('production_approved') is not False
                or report.get('client_published') is not False
                or any(any((index / sub).iterdir()) for sub in ('pdf', 'png'))):
            raise RestoreBlocked('gc14_synthetic_evidence_invalid')
        seen.add(filename)
    if seen != set(expected_sha):
        raise RestoreBlocked('gc14_synthetic_result_count_invalid')
    return len(seen)


def _verify_and_replay(repo: Path, workspace: Path,
                       expected_sha: dict[str, str]) -> dict[str, Any]:
    """The queue must recognize the terminal BLOCKED records on replay."""
    from scripts.graphic_design_lab.greeting_cards import smb_workspace_queue_v0_1 as queue
    total = _verify_smoke_evidence(workspace, expected_sha)
    again = queue.run(workspace)
    if again != {'SKIPPED_ALREADY_REPORTED': total}:
        raise RestoreBlocked('gc14_synthetic_idempotency_invalid')
    return {'status': 'GC14_SYNTHETIC_QUEUE_SMOKE_PASS', 'processed': total,
            'blocked_as_expected': total, 'idempotent_replay_skipped': total,
            'illustrator_worker_verified': False, 'real_intake_verified': False,
            'pdf_builder_invoked': False}


def smoke(repo: Path, case_id: str) -> dict[str, Any]:
    """First execution: two unsupported synthetic ZIPs and GC14 proof."""
    verify(repo, case_id, expect_empty=True)
    _, _, workspace = get_locations(repo, case_id)
    if str(repo.resolve()) not in sys.path:
        sys.path.insert(0, str(repo.resolve()))
    from scripts.graphic_design_lab.greeting_cards import smb_workspace_queue_v0_1 as queue
    expected_sha: dict[str, str] = {}
    for name, payload in SYNTHETIC_INPUTS:
        path = workspace / 'input' / name
        with ZipFile(path, mode='x') as z:
            z.writestr(SYNTHETIC_MEMBER, payload)
        expected_sha[name] = sha_path(path)
    outcomes = queue.run(workspace)
    if outcomes != {'BLOCKED': len(SYNTHETIC_INPUTS)}:
        raise RestoreBlocked('gc14_synthetic_fail_closed_outcome_mismatch')
    return _verify_and_replay(repo, workspace, expected_sha)


def resume_smoke(repo: Path, case_id: str) -> dict[str, Any]:
    """Resume only the evidence/replay gate after a failed first smoke check.

    Never regenerate synthetic inputs and never delete the existing reports.
    """
    verify(repo, case_id)
    _, _, workspace = get_locations(repo, case_id)
    actual = {p.name for p in (workspace / 'input').iterdir()}
    expected_names = {name for name, _ in SYNTHETIC_INPUTS}
    if actual != expected_names:
        raise RestoreBlocked('gc14_synthetic_resume_input_set_mismatch')
    expected_sha: dict[str, str] = {}
    for name, payload in SYNTHETIC_INPUTS:
        path = workspace / 'input' / name
        if path.is_symlink() or not path.is_file():
            raise RestoreBlocked('gc14_synthetic_resume_input_unsafe')
        try:
            with ZipFile(path) as z:
                if z.namelist() != [SYNTHETIC_MEMBER] or z.read(SYNTHETIC_MEMBER) != payload:
                    raise RestoreBlocked('gc14_synthetic_resume_input_identity_invalid')
        except (BadZipFile, KeyError, OSError) as exc:
            raise RestoreBlocked('gc14_synthetic_resume_input_identity_invalid') from exc
        expected_sha[name] = sha_path(path)
    if str(repo.resolve()) not in sys.path:
        sys.path.insert(0, str(repo.resolve()))
    return _verify_and_replay(repo, workspace, expected_sha)

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument('--case-id', required=True)
    parser.add_argument('--mode', choices=('check', 'create-synthetic', 'verify', 'smoke', 'resume-smoke'), required=True)
    parser.add_argument('--confirm-synthetic', action='store_true')
    args = parser.parse_args()
    try:
        repo = args.repo.resolve(strict=True)
        if args.mode == 'check':
            _, fingerprint = get_source(repo)
            _, case, _ = get_locations(repo, args.case_id)
            if case.exists():
                raise RestoreBlocked('case_already_exists_no_overwrite')
            result = {'status': 'SYNTHETIC_RESTORE_PREFLIGHT_PASS',
                      'contract_sha256': fingerprint, 'case_id': args.case_id}
        elif args.mode == 'create-synthetic':
            if not args.confirm_synthetic:
                raise RestoreBlocked('explicit_synthetic_confirmation_required')
            create(repo, args.case_id)
            result = verify(repo, args.case_id, expect_empty=True)
        elif args.mode == 'verify':
            result = verify(repo, args.case_id)
        elif args.mode == 'smoke':
            result = smoke(repo, args.case_id)
        else:
            result = resume_smoke(repo, args.case_id)
        print('GDL_WORKSPACE_RESTORE=' + result['status'])
        for key, value in result.items():
            if key != 'status':
                print(key.upper() + '=' + (str(value).lower() if isinstance(value, bool) else json.dumps(value, ensure_ascii=False)))
        print('REAL_CLIENT_WORKSPACE_MUTATED=false')
        print('WINDOWS_WORKER_DISPATCH=false')
        return 0
    except (RestoreBlocked, OSError, yaml.YAMLError, ImportError, KeyError, ValueError) as exc:
        if isinstance(exc, RestoreBlocked):
            code = str(exc)
        else:
            code = type(exc).__name__
        print('GDL_WORKSPACE_RESTORE=BLOCKED')
        print('ERROR_CODE=' + code)
        print('REAL_CLIENT_WORKSPACE_MUTATED=false')
        return 2


if __name__ == '__main__':
    sys.exit(main())

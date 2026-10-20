#!/usr/bin/env python3
"""GC18 pre-dispatch candidate inventory: GC14 1..N ZIP -> immutable receipts.

No GC10/PDF Builder, Adobe/Windows dispatch, SMB write or production authority.
An archive envelope is NOT acceptance. Native-worker authorization is deferred.
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
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.graphic_design_lab.greeting_cards import smb_workspace_queue_v0_1 as gc14  # noqa: E402

SCHEMA = 'gdl_gc18_illustrator_task_candidate_v0_1'
RECEIPTS = 'gdl_gc18_illustrator_task_candidates_v0_1'
NATIVE_PLAN_DIR = 'gdl_gc18_illustrator_native_task_plans_v0_1'
NATIVE_PLAN_SCHEMA = 'gdl_gc18_illustrator_native_task_plan_v0_1'
HEX64 = re.compile(r'^[0-9a-f]{64}$')

class CandidateBlocked(ValueError):
    pass


def _dir(path: Path) -> bool:
    return path.is_dir() and not path.is_symlink() and stat.S_ISDIR(path.stat().st_mode)


def _sha(path: Path) -> str:
    h = sha256()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def _json(data: dict[str, Any]) -> bytes:
    return (json.dumps(data, sort_keys=True, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def _source_list(workspace: Path) -> list[Path]:
    if not _dir(workspace) or workspace.name != '_forprint_automation':
        raise CandidateBlocked('workspace_invalid')
    source = workspace / 'input'
    if not _dir(source):
        raise CandidateBlocked('input_missing_or_unsafe')
    return [p for p in sorted(source.iterdir(), key=lambda v: v.name.casefold())
            if p.suffix.lower() == '.zip']


def inventory(workspace: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for file in _source_list(workspace):
        if file.is_symlink() or not file.is_file() or not stat.S_ISREG(file.stat().st_mode):
            # Do not follow links or treat them as accepted sources.
            records.append({'status': 'UNSAFE_ENTRY', 'source_sha256': None,
                            'source_name': file.name, 'kind': 'UNINSPECTED'})
            continue
        if file.stat().st_size > gc14.MAX_ZIP_BYTES:
            records.append({'status': 'BLOCKED', 'source_sha256': None,
                            'source_name': file.name, 'kind': 'OVER_SIZE'})
            continue
        original = _sha(file)
        if original in seen:
            status, kind = 'DUPLICATE_SOURCE_SHA', 'DUPLICATE'
        else:
            seen.add(original)
            try:
                kind, _metadata = gc14.inspect_archive(file)
                status = ('CANDIDATE_AWAITING_DEEP_ACCEPTANCE'
                          if kind == 'ACCEPTED_HANDOFF_CANDIDATE'
                          else 'BLOCKED')
            except (Exception) as exc:  # fail closed; never dump private exceptions
                status, kind = 'BLOCKED', 'INSPECTION_FAILED_' + type(exc).__name__
        if _sha(file) != original:
            raise CandidateBlocked('input_changed_during_inventory')
        records.append({'status': status, 'source_sha256': original,
                        'source_name': file.name, 'kind': kind})
    return records


def deep_preflight(repo: Path, workspace: Path, record: dict[str, Any], config: Path,
                   *, include_job_keys: bool = False) -> dict[str, Any]:
    """Reuse the GC10 Intake *inspector* without invoking GC10/Builder runtime.

    The legacy validator requires a canonical basename; an ephemeral, SHA-pinned
    staging copy is automatically removed. Never create a second client ZIP.
    """
    from scripts.graphic_design_lab.greeting_cards import intake_handoff_runner_v0_1 as handoff

    if record.get('status') != 'CANDIDATE_AWAITING_DEEP_ACCEPTANCE':
        raise CandidateBlocked('deep_check_requires_structural_candidate')
    repo_tmp = repo.resolve(strict=True) / 'tmp'
    if not _dir(repo_tmp):
        raise CandidateBlocked('repo_tmp_missing_or_unsafe')
    if config.is_symlink() or not config.is_file():
        raise CandidateBlocked('deep_intake_config_missing_or_unsafe')
    source = workspace / 'input' / record['source_name']
    if source.is_symlink() or not source.is_file():
        raise CandidateBlocked('deep_intake_source_missing_or_unsafe')
    expected = record['source_sha256']
    if _sha(source) != expected:
        raise CandidateBlocked('deep_intake_source_identity_changed')
    with tempfile.TemporaryDirectory(prefix='gc18-deep-intake-', dir=repo_tmp) as temp:
        target = Path(temp) / handoff.HANDOFF_FILENAME
        # O_NOFOLLOW also protects against a symlink swap after inventory().
        fd = os.open(source, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise CandidateBlocked('deep_intake_source_not_regular')
            copied = 0
            with os.fdopen(fd, 'rb') as src, target.open('xb') as dst:
                fd = -1
                while chunk := src.read(1024 * 1024):
                    copied += len(chunk)
                    if copied > gc14.MAX_ZIP_BYTES:
                        raise CandidateBlocked('deep_intake_source_too_large')
                    dst.write(chunk)
        finally:
            if fd >= 0:
                os.close(fd)
        if _sha(target) != expected or _sha(source) != expected:
            raise CandidateBlocked('deep_intake_source_identity_changed')
        # inspect_zip validates provenance, manifests, accepted bundle, assets.
        # It DOES NOT generate PDF, use Illustrator, or grant dispatch authority.
        inspection = handoff.inspect_zip(target, config)
        if inspection['archive_sha256'] != expected:
            raise CandidateBlocked('deep_intake_validation_identity_mismatch')
        if inspection.get('jobs', 0) < 1:
            raise CandidateBlocked('deep_intake_job_count_invalid')
        result = {
            'jobs': inspection['jobs'], 'assets': inspection['assets'],
            'synthetic': bool(inspection.get('synthetic', False)),
        }
        if include_job_keys:
            raw_jobs = (inspection.get('bundle') or {}).get('jobs')
            if not isinstance(raw_jobs, list) or len(raw_jobs) != result['jobs']:
                raise CandidateBlocked('native_job_manifest_count_mismatch')
            keys = set()
            descriptors = []
            for item in raw_jobs:
                if not isinstance(item, dict) or not isinstance(item.get('job_id'), str):
                    raise CandidateBlocked('native_job_identity_invalid')
                job_id = item['job_id']
                builder = item.get('builder_v1')
                revision = builder.get('revision') if isinstance(builder, dict) else None
                if (not job_id or len(job_id) > 256 or not isinstance(revision, str)
                        or not revision or len(revision) > 80):
                    raise CandidateBlocked('native_job_identity_invalid')
                if (job_id, revision) in keys:
                    raise CandidateBlocked('native_job_identity_duplicate')
                keys.add((job_id, revision))
                # No customer names, greeting text, or source filenames in the plan.
                job_key = sha256(_json({'source_sha256': expected, 'job_id': job_id,
                                       'revision': revision})).hexdigest()
                descriptors.append({'task_id': 'gc18-' + job_key[:24],
                                    'job_binding_sha256': job_key,
                                    'expected_outputs': ['editable_ai', 'review_pdf',
                                                         'page_png', 'worker_result'],
                                    'worker_authorized': False})
            if len(descriptors) != result['jobs']:
                raise CandidateBlocked('native_job_manifest_count_mismatch')
            result['job_descriptors'] = sorted(descriptors, key=lambda item: item['task_id'])
    if _sha(source) != expected:
        raise CandidateBlocked('deep_intake_source_changed_after_validation')
    return result


def candidate_payload(record: dict[str, Any]) -> dict[str, Any]:
    digest = record.get('source_sha256')
    if not isinstance(digest, str) or not HEX64.fullmatch(digest):
        raise CandidateBlocked('source_digest_not_available')
    # Machine identity deliberately does not contain customer names or filesystem paths.
    identity = sha256((SCHEMA + ':' + digest).encode('ascii')).hexdigest()
    return {
        'schema_version': SCHEMA,
        'task_candidate_id': identity,
        'source_sha256': digest,
        'source_zip_basename': record['source_name'],
        'gc14_envelope_kind': record['kind'],
        'state': record['status'],
        'admission_evidence': 'GC14_ARCHIVE_ENVELOPE_ONLY',
        'deep_intake_validated': False,
        'windows_worker_acked': False,
        'windows_worker_executed': False,
        'worker_dispatch_authorized': False,
        'production_approved': False,
        'customer_approved': False,
        'pdf_builder_invoked': False,
        'expected_artifact_kinds_future': ['editable_ai', 'review_pdf', 'page_png', 'worker_result'],
        'next_boundary': 'DEEP_INTAKE_VALIDATION_AND_NATIVE_WORKER_CONTRACT',
    }


def _root(repo: Path, *, create: bool) -> Path:
    repo = repo.resolve(strict=True)
    tmp = repo / 'tmp'
    if not _dir(tmp):
        raise CandidateBlocked('repo_tmp_missing_or_unsafe')
    path = tmp / RECEIPTS
    if path.is_symlink() or path.exists() and not _dir(path):
        raise CandidateBlocked('receipt_directory_unsafe')
    if create and not path.exists():
        path.mkdir(mode=0o700)
    return path


def _write_once(directory: Path, record: dict[str, Any]) -> str:
    payload = candidate_payload(record)
    target = directory / (record['source_sha256'] + '.json')
    data = _json(payload)
    if target.is_symlink():
        raise CandidateBlocked('receipt_symlink_forbidden')
    if target.exists():
        if not target.is_file() or target.read_bytes() != data:
            raise CandidateBlocked('existing_receipt_identity_conflict')
        return 'REUSED'
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(target, flags, 0o600)
    with os.fdopen(fd, 'wb') as output:
        output.write(data)
    return 'CREATED'


def _write_native_plan(repo: Path, record: dict[str, Any], proof: dict[str, Any]) -> str:
    """An immutable *non-dispatchable* planning receipt, scoped to one source ZIP."""
    if proof['synthetic'] or proof['jobs'] < 1:
        raise CandidateBlocked('native_plan_requires_real_accepted_intake')
    digest = record['source_sha256']
    payload = {
        'schema_version': NATIVE_PLAN_SCHEMA,
        'state': 'DEEP_INTAKE_VERIFIED_NATIVE_CONTRACT_PENDING',
        'source_sha256': digest,
        'source_job_count': proof['jobs'],
        'source_asset_count': proof['assets'],
        'tasks': proof['job_descriptors'],
        'admission': {'strict_intake_inspector': 'PASS',
                      'illustrator_script_pinned': False,
                      'windows_capability_verified': False,
                      'windows_session_verified': False,
                      'worker_ack_received': False},
        'dispatch_authorized': False,
        'pdf_builder_invoked': False,
        'production_approved': False,
        'next_boundary': 'PIN_NATIVE_JSX_AND_WORKER_CAPABILITY_THEN_AUTHORIZED_HANDOFF',
    }
    target_dir = _root(repo, create=False).parent / NATIVE_PLAN_DIR
    if target_dir.is_symlink() or (target_dir.exists() and not _dir(target_dir)):
        raise CandidateBlocked('native_plan_directory_unsafe')
    target_dir.mkdir(mode=0o700, exist_ok=True)
    target = target_dir / (digest + '.json')
    data = _json(payload)
    if target.is_symlink():
        raise CandidateBlocked('native_plan_symlink_forbidden')
    if target.exists():
        if not target.is_file() or target.read_bytes() != data:
            raise CandidateBlocked('native_plan_existing_identity_conflict')
        return 'NATIVE_PLAN_REUSED'
    fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY |
                 getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(data)
    return 'NATIVE_PLAN_CREATED'


def run(repo: Path, workspace: Path, *, mode: str, confirm: bool = False,
        config: Path | None = None) -> dict[str, int]:
    if mode not in ('check', 'prepare', 'deep-check', 'plan-native'):
        raise CandidateBlocked('unsupported_mode')
    if mode in ('prepare', 'plan-native') and not confirm:
        raise CandidateBlocked('explicit_candidate_confirmation_required')
    if mode in ('deep-check', 'plan-native') and config is None:
        raise CandidateBlocked('deep_intake_config_required')
    rows = inventory(workspace)
    directory = _root(repo, create=(mode == 'prepare'))
    counts: dict[str, int] = {}
    for record in rows:
        status = record['status']
        if mode in ('deep-check', 'plan-native') and status == 'CANDIDATE_AWAITING_DEEP_ACCEPTANCE':
            try:
                proof = deep_preflight(repo, workspace, record, config,
                                       include_job_keys=(mode == 'plan-native'))
                status = ('DEEP_INTAKE_SYNTHETIC_REVIEW_ONLY' if proof['synthetic']
                          else 'DEEP_INTAKE_PASS_NATIVE_CONTRACT_PENDING')
                print('VALIDATED_JOB_COUNT=' + str(proof['jobs']))
                print('VALIDATED_ASSET_COUNT=' + str(proof['assets']))
                if mode == 'plan-native' and not proof['synthetic']:
                    written = _write_native_plan(repo, record, proof)
                    counts[written] = counts.get(written, 0) + 1
                    status = 'NATIVE_TASK_PLAN_REVIEW_ONLY'
            except Exception as exc:
                # Do not print customer data, private paths, or exception payloads.
                status = 'DEEP_INTAKE_BLOCKED'
                print('DEEP_BLOCK_REASON_CLASS=' + type(exc).__name__)
        counts[status] = counts.get(status, 0) + 1
        if mode == 'prepare' and record['source_sha256'] and status != 'DUPLICATE_SOURCE_SHA':
            result = _write_once(directory, record)
            counts[result] = counts.get(result, 0) + 1
        print('SOURCE_SHA12=' + ((record['source_sha256'] or 'UNAVAILABLE')[:12]))
        print('SOURCE_STATE=' + status)
    print('GDL_GC18_TASK_CANDIDATE=' + ('PREPARED' if mode == 'prepare' else 'NATIVE_PLAN_COMPLETE' if mode == 'plan-native' else 'DEEP_CHECK_COMPLETE' if mode == 'deep-check' else 'CHECK_PASS'))
    print('SOURCE_COUNT=' + str(len(rows)))
    print('WINDOWS_DISPATCH=false')
    print('NATIVE_WORKER_ADMISSION=false')
    print('PDF_BUILDER_INVOKED=false')
    print('CLIENT_WORKSPACE_MUTATED=false')
    for key, value in sorted(counts.items()):
        print(key + '=' + str(value))
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('--mode', required=True, choices=('check', 'prepare', 'deep-check', 'plan-native'))
    parser.add_argument('--config', type=Path)
    parser.add_argument('--confirm-candidate', action='store_true')
    args = parser.parse_args()
    try:
        run(args.repo, args.workspace, mode=args.mode, confirm=args.confirm_candidate,
            config=args.config)
        return 0
    except (CandidateBlocked, OSError, ValueError) as exc:
        code = str(exc) if isinstance(exc, CandidateBlocked) else type(exc).__name__
        print('GDL_GC18_TASK_CANDIDATE=BLOCKED')
        print('ERROR_CODE=' + (code if re.fullmatch('[A-Za-z0-9_]+', code) else 'UNEXPECTED_ERROR'))
        print('WINDOWS_DISPATCH=false')
        print('CLIENT_WORKSPACE_MUTATED=false')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

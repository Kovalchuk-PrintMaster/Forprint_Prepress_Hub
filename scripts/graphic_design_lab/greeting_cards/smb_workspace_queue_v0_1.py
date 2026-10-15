#!/usr/bin/env python3
"""GC14: single-operator SMB input queue and PDF/PNG-only output projection.

No creator/provider, intake approval, printing or customer publication authority.
Inputs are never changed/deleted. Refuses ambiguous, unverified or unsafe sources.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
from datetime import datetime
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
from typing import Any
from zipfile import ZipFile, BadZipFile

import yaml

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SHARE_ROOTS = {'In_Progress': Path('/srv/smb/In_Progress/data')}
SCHEMA = 'gdl_gc14_smb_workspace_queue_v0_1'
GC10_NAME = 'gdl_intake_handoff.zip'
GC10_REQUIRED = frozenset({'accepted_constructor_bundle.yaml', 'artifact_manifest.yaml', 'handoff_manifest.json'})
STAGING_REQUIRED = frozenset({'packet_manifest.json', 'SERVER_INGEST_STAGING.yaml', 'BLOCKERS.yaml'})
SHA_PATTERN = re.compile(r'^[a-f0-9]{64}$')
SAFE_FILE = re.compile(r'^[A-Za-z0-9_.-]+$')
MAX_ZIP_BYTES = 250_000_000
MAX_UNCOMPRESSED = 500_000_000

class QueueBlocked(ValueError):
    pass


def sha_file(p: Path) -> str:
    h = sha256()
    with p.open('rb') as f:
        for part in iter(lambda: f.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def token_to_relative(value: str) -> PurePosixPath:
    try:
        raw = base64.urlsafe_b64decode(value + '=' * (-len(value) % 4)).decode('utf-8')
    except (ValueError, UnicodeError) as exc:
        raise QueueBlocked('workspace_token_invalid') from exc
    if not raw or '\x00' in raw or '\\' in raw:
        raise QueueBlocked('workspace_token_invalid')
    # Reject dot segments before PurePosixPath normalizes them away.
    if raw.startswith('/') or any(p in ('', '.', '..') for p in raw.split('/')):
        raise QueueBlocked('workspace_path_unsafe')
    return PurePosixPath(raw)


def workspace_path(share: str, token: str, *, roots: dict[str, Path] | None = None) -> Path:
    shared = SHARE_ROOTS if roots is None else roots
    if share not in shared:
        raise QueueBlocked('unsupported_share')
    root = shared[share].resolve(strict=True)
    parts = token_to_relative(token).parts
    if len(parts) != 2 or parts[-1] != '_forprint_automation':
        raise QueueBlocked('workspace_layout_not_supported')
    path = (root / Path(*parts)).resolve(strict=True)
    if path.parent.parent != root or path.name != '_forprint_automation':
        raise QueueBlocked('workspace_escape')
    if not path.is_dir():
        raise QueueBlocked('workspace_missing')
    return path


def _assert_regular(path: Path) -> None:
    if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        raise QueueBlocked('source_not_regular')
    if path.stat().st_size > MAX_ZIP_BYTES:
        raise QueueBlocked('source_archive_too_large')


def inspect_archive(path: Path) -> tuple[str, dict[str, Any]]:
    _assert_regular(path)
    try:
        with ZipFile(path) as z:
            infos = z.infolist()
            names = [i.filename for i in infos]
            if len(names) != len(set(names)) or len(names) > 300 or not names:
                raise QueueBlocked('archive_members_invalid')
            if sum(i.file_size for i in infos) > MAX_UNCOMPRESSED:
                raise QueueBlocked('archive_expansion_too_large')
            for info in infos:
                name = info.filename
                if (not name or name.startswith('/') or '\\' in name or '\x00' in name
                        or any(c in ('', '.', '..') for c in name.split('/'))
                        or (info.external_attr >> 16) & 0o170000 == 0o120000):
                    raise QueueBlocked('archive_member_unsafe')
            members = set(names)
            if STAGING_REQUIRED <= members:
                if GC10_REQUIRED & members:
                    raise QueueBlocked('conflicting_archive_envelopes')
                manifest = json.loads(z.read('packet_manifest.json'))
                routing = yaml.safe_load(z.read('SERVER_INGEST_STAGING.yaml'))
                blockers = yaml.safe_load(z.read('BLOCKERS.yaml'))
                if (manifest.get('schema_version') != 'gdl_intake_staging_packet_manifest_v0_1'
                        or routing.get('packet_kind') != 'STRUCTURED_INTAKE_STAGING_NOT_ACCEPTED_BUNDLE'
                        or blockers.get('final_handoff_allowed') is not False):
                    raise QueueBlocked('staging_authority_invalid')
                entries = manifest.get('entries')
                if not isinstance(entries, list) or set(names) != {x.get('path') for x in entries} | {'packet_manifest.json'}:
                    raise QueueBlocked('staging_manifest_mismatch')
                for item in entries:
                    n = item['path']
                    if not isinstance(item.get('sha256'), str) or not SHA_PATTERN.fullmatch(item['sha256']):
                        raise QueueBlocked('staging_digest_invalid')
                    if z.getinfo(n).file_size != item['bytes'] or sha256(z.read(n)).hexdigest() != item['sha256']:
                        raise QueueBlocked('staging_file_digest_mismatch')
                issues = blockers.get('blockers') or []
                codes = [x['code'] for x in issues if isinstance(x, dict) and isinstance(x.get('code'), str)]
                return 'STAGING_BLOCKED', {'blocker_codes': codes, 'job_count': len(routing.get('asset_selection_rule', {}).get('all_job_ids', []))}
            if GC10_REQUIRED <= members and not (STAGING_REQUIRED & members):
                # Full semantic validation deliberately delegated to established GC10.
                return 'ACCEPTED_HANDOFF_CANDIDATE', {}
            return 'UNSUPPORTED', {}
    except (BadZipFile, KeyError, ValueError, TypeError, yaml.YAMLError) as exc:
        if isinstance(exc, QueueBlocked):
            raise
        raise QueueBlocked('archive_parse_invalid') from exc


def _json_exclusive(path: Path, data: dict[str, Any]) -> None:
    with path.open('x', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, sort_keys=True, indent=2)
        f.write('\n')


def _safe_name(stem: str) -> str:
    value = re.sub(r'[^\w.-]+', '_', stem, flags=re.UNICODE).strip('._')[:56]
    return value or 'unnamed_source'


def reports_for_source(out: Path, source_sha: str) -> tuple[str | None, bool]:
    """Prefer a verified terminal result; any unfinished record is a hard stop."""
    last_state: str | None = None
    has_incomplete = False
    for p in sorted(out.glob('*/source_info.json')):
        if p.is_symlink() or p.parent.is_symlink() or p.stat().st_size > 4096:
            raise QueueBlocked('unsafe_existing_source_index')
        data = json.loads(p.read_text(encoding='utf-8'))
        if data.get('source_sha256') != source_sha:
            continue
        report_path = p.parent / 'report.json'
        if not report_path.is_file() or report_path.is_symlink():
            has_incomplete = True
            continue
        if report_path.stat().st_size > 1024 * 1024:
            raise QueueBlocked('unsafe_existing_result')
        report = json.loads(report_path.read_text(encoding='utf-8'))
        if report.get('source_sha256') != source_sha or report.get('schema_version') != SCHEMA:
            raise QueueBlocked('existing_result_identity_mismatch')
        status = report.get('status')
        if status != 'BLOCKED':
            last_state = status
        elif last_state is None:
            last_state = 'BLOCKED'
    return last_state, has_incomplete


def new_output_dir(out: Path, name: str, source_sha: str) -> Path:
    today = datetime.now().astimezone().strftime('%Y-%m-%d')
    for index in range(1, 10000):
        path = out / f'{today}_{index:04d}_{_safe_name(name)}__{source_sha[:10]}'
        try:
            path.mkdir(mode=0o750)
            (path / 'pdf').mkdir()
            (path / 'png').mkdir()
            return path
        except FileExistsError:
            continue
    raise QueueBlocked('daily_output_index_exhausted')


def gc10_module():
    from scripts.graphic_design_lab.greeting_cards import unified_private_cycle_v0_1
    return unified_private_cycle_v0_1


def _existing_or_new_private_result(source: Path, source_sha: str, gc: Any) -> tuple[Path, bool]:
    # GC12 reconciliation first: never bypass uncertain finalization.
    previous = gc.prior_successful_cycles(source_sha)
    if previous:
        rows = sorted((gc.OUTPUT_ROOT / 'runs').glob('*/unified_cycle_result.json'))
        for path in reversed(rows):
            item = json.loads(path.read_text(encoding='utf-8'))
            if item.get('source_zip_sha256') == source_sha and item.get('status') == 'PRIVATE_CYCLE_PASS_REQUIRES_VISUAL_REVIEW':
                gc._verified_prior_success(path, source_sha)
                return path, True
        raise QueueBlocked('prior_success_not_recoverable')
    # Existing GC10 requires exact handoff basename. Keep source untouched.
    staging = ROOT / 'tmp/gdl_gc14_smb_workspace_queue_v0_1/copies' / source_sha
    staging.mkdir(parents=True, exist_ok=True)
    copied = staging / GC10_NAME
    if not copied.exists():
        with source.open('rb') as s, copied.open('xb') as d:
            shutil.copyfileobj(s, d, length=1024 * 1024)
    if gc.file_sha(copied) != source_sha or sha_file(source) != source_sha:
        raise QueueBlocked('source_copy_digest_mismatch')
    cfg = ROOT / 'tmp/gdl_intake_handoff_runtime_v0_1/local_config.json'
    result = gc.run_private(copied, cfg, allow_repeat=False)
    path = ROOT / result['report']
    if result['summary']['source_zip_sha256'] != source_sha or not path.is_file():
        raise QueueBlocked('gc10_cycle_identity_invalid')
    return path, False


def _export_review(run_report: Path, dest: Path, source_sha: str, gc: Any) -> dict[str, Any]:
    gc._verified_prior_success(run_report, source_sha)
    report = json.loads(run_report.read_text(encoding='utf-8'))
    review_path = gc.inside_tmp(ROOT / report['private_review_report'])
    review = json.loads(review_path.read_text(encoding='utf-8'))
    archive = review_path.parent.parent / 'full_card_review_PRIVATE.zip'
    if (review.get('review_state') != 'READY_FOR_INTERNAL_VISUAL_REVIEW'
            or review.get('synthetic_fixture') is not False
            or review.get('pdf_preview_pixel_replay') != 'PASS'
            or review.get('job_count') != report['job_count']
            or review.get('pdf_count') != report['pdf_count']
            or review.get('png_preview_count') != report['png_preview_count']
            or len(review.get('jobs', [])) != report['job_count']):
        raise QueueBlocked('review_evidence_invalid')
    pdfs, previews, outputs = 0, 0, []
    with ZipFile(archive) as z:
        infos = z.infolist()
        if len({x.filename for x in infos}) != len(infos):
            raise QueueBlocked('review_zip_duplicate_members')
        names = {x.filename for x in infos}
        for job in review['jobs']:
            job_id, revision = job['job_id'], job['revision']
            if not SAFE_FILE.fullmatch(job_id) or not SAFE_FILE.fullmatch(revision):
                raise QueueBlocked('review_job_path_unsafe')
            wanted = [job['pdf']] + [f'builder_outputs_PRIVATE/preview/{job_id}__{revision}__{i:02}.png' for i in range(1, 5)]
            if (wanted[0] != f'builder_outputs_PRIVATE/completed/{job_id}__{revision}.pdf'
                    or set(wanted) - names
                    or job.get('page_count') != 4 or job.get('preview_count') != 4
                    or job.get('preview_pixel_replay') != 'PASS'):
                raise QueueBlocked('review_job_evidence_invalid')
            for idx, member in enumerate(wanted):
                target_folder = 'pdf' if idx == 0 else 'png'
                target = dest / target_folder / Path(member).name
                if target.exists() or z.getinfo(member).file_size > MAX_ZIP_BYTES:
                    raise QueueBlocked('review_artifact_invalid')
                with z.open(member) as src, target.open('xb') as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
                digest = sha_file(target)
                if idx == 0 and digest != job['pdf_sha256']:
                    raise QueueBlocked('exported_pdf_digest_mismatch')
                outputs.append({'path': f'{target_folder}/{target.name}', 'sha256': digest})
                if idx == 0:
                    pdfs += 1
                else:
                    previews += 1
    if pdfs != report['pdf_count'] or previews != report['png_preview_count']:
        raise QueueBlocked('exported_artifact_count_mismatch')
    return {'job_count': report['job_count'], 'pdf_count': pdfs, 'png_count': previews,
            'files': outputs, 'gc10_cycle_report': str(run_report.relative_to(ROOT)),
            'closeout_receipt': report['closeout_receipt'],
            'closeout_receipt_sha256': report['closeout_receipt_sha256']}


@contextmanager
def workspace_lock(workspace: Path):
    key = sha256(str(workspace).encode('utf-8')).hexdigest()[:20]
    home = ROOT / 'tmp/gdl_gc14_smb_workspace_queue_v0_1/locks'
    home.mkdir(parents=True, exist_ok=True)
    fd = os.open(home / (key + '.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise QueueBlocked('workspace_lock_unsafe')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise QueueBlocked('workspace_queue_already_running') from exc
        yield
    finally:
        os.close(fd)


def process_one(source: Path, out: Path, *, retry_blocked: bool = False) -> str:
    source_sha = sha_file(source)
    prior, incomplete = reports_for_source(out, source_sha)
    if incomplete:
        return 'NEEDS_RECONCILIATION'
    if prior and (prior != 'BLOCKED' or not retry_blocked):
        return 'SKIPPED_ALREADY_REPORTED'
    dest = new_output_dir(out, source.stem, source_sha)
    record = {'schema_version': SCHEMA, 'source_archive': source.name,
              'source_sha256': source_sha, 'created_at': datetime.now().astimezone().isoformat(),
              'production_approved': False, 'customer_approved': False, 'client_published': False}
    _json_exclusive(dest / 'source_info.json', record)
    status = 'BLOCKED'
    details: dict[str, Any] = {}
    try:
        kind, metadata = inspect_archive(source)
        if kind == 'STAGING_BLOCKED':
            details = {'reason': 'INTAKE_STAGING_NOT_FINAL_HANDOFF', **metadata}
        elif kind == 'ACCEPTED_HANDOFF_CANDIDATE':
            gc = gc10_module()
            result_path, reused = _existing_or_new_private_result(source, source_sha, gc)
            details = _export_review(result_path, dest, source_sha, gc)
            details['reused_verified_gc10_cycle'] = reused
            status = 'READY_FOR_VISUAL_REVIEW'
        else:
            details = {'reason': 'UNSUPPORTED_ARCHIVE_ENVELOPE'}
        if sha_file(source) != source_sha:
            raise QueueBlocked('source_changed_during_processing')
    except (QueueBlocked, ValueError, OSError, KeyError, TypeError) as exc:
        # Report safe fixed error names, never private raw exception strings.
        reason = str(exc) if re.fullmatch(r'[A-Za-z0-9_]+', str(exc)) else type(exc).__name__
        details = {'reason': reason if re.fullmatch(r'[A-Za-z0-9_]+', reason) else 'INTERNAL_PROCESS_ERROR'}
        status = 'BLOCKED'
    final = {**record, 'status': status, **details, 'source_unchanged': sha_file(source) == source_sha}
    _json_exclusive(dest / 'report.json', final)
    return status


def run(workspace: Path, *, retry_blocked: bool = False,
        retry_blocked_sha256: str | None = None) -> dict[str, int]:
    if retry_blocked_sha256 is not None:
        if (retry_blocked or not SHA_PATTERN.fullmatch(retry_blocked_sha256)):
            raise QueueBlocked('scoped_retry_arguments_invalid')
    if workspace.name != '_forprint_automation':
        raise QueueBlocked('invalid_workspace_root')
    inp, out = workspace / 'input', workspace / 'output'
    if any(p.is_symlink() or not p.is_dir() for p in (inp, out)):
        raise QueueBlocked('workspace_input_output_missing')
    counts: dict[str, int] = {}
    with workspace_lock(workspace):
        sources = sorted(inp.iterdir(), key=lambda p: p.name.casefold())
        if retry_blocked_sha256 is not None:
            # Exact one-archive reentry: reject a missing or duplicate pinned source.
            matches = [p for p in sources
                       if p.suffix.lower() == '.zip'
                       and not p.is_symlink() and p.is_file()
                       and sha_file(p) == retry_blocked_sha256]
            if len(matches) != 1:
                raise QueueBlocked('scoped_retry_source_not_unique')
        for candidate in sources:
            if candidate.suffix.lower() != '.zip':
                continue
            if candidate.is_symlink() or not candidate.is_file():
                outcome = 'SKIPPED_UNSAFE_ENTRY'
            else:
                try:
                    allow_retry = retry_blocked or (
                        retry_blocked_sha256 is not None
                        and sha_file(candidate) == retry_blocked_sha256
                    )
                    outcome = process_one(candidate, out, retry_blocked=allow_retry)
                except Exception:
                    # Uncertain incomplete run cannot silently continue as success.
                    outcome = 'NEEDS_RECONCILIATION'
            counts[outcome] = counts.get(outcome, 0) + 1
            print('SOURCE=' + candidate.name)
            print('RESULT=' + outcome)
    print('GC14_SMB_QUEUE=COMPLETE')
    print('PDF_ONLY_OUTPUT=true')
    print('CLIENT_PUBLISHED=false')
    print('SOURCE_FILES_DELETED=false')
    for status, count in sorted(counts.items()):
        print(f'{status}={count}')
    return counts


def main() -> int:
    a = argparse.ArgumentParser()
    a.add_argument('--share', required=True)
    a.add_argument('--workspace-relative-b64', required=True)
    a.add_argument('--mode', choices=('check', 'run'), required=True)
    a.add_argument('--retry-blocked', action='store_true')
    a.add_argument('--retry-blocked-sha256')
    args = a.parse_args()
    try:
        workspace = workspace_path(args.share, args.workspace_relative_b64)
        if args.mode == 'check':
            print('GC14_WORKSPACE_CHECK=PASS')
            print('INPUT_EXISTS=' + str((workspace / 'input').is_dir()).lower())
            print('OUTPUT_EXISTS=' + str((workspace / 'output').is_dir()).lower())
            print('INTAKE_EXISTS=' + str((workspace / 'intake').is_dir()).lower())
        else:
            result = run(workspace, retry_blocked=args.retry_blocked,
                         retry_blocked_sha256=args.retry_blocked_sha256)
            if result.get('NEEDS_RECONCILIATION') or result.get('SKIPPED_UNSAFE_ENTRY'):
                return 2
        return 0
    except Exception as exc:
        code = str(exc) if isinstance(exc, QueueBlocked) else type(exc).__name__
        print('GC14_SMB_QUEUE=BLOCKED')
        print('ERROR_CODE=' + (code if re.fullmatch(r'[A-Za-z0-9_]+', code) else 'UNEXPECTED_ERROR'))
        print('CLIENT_PUBLISHED=false')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

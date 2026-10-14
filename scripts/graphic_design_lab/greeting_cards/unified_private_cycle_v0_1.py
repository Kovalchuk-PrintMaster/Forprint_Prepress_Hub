#!/usr/bin/env python3
"""GC-E2E-10: one operator-invoked private Handoff -> Builder -> formal closeout.

Reuses existing inspected Intake ZIP, Constructor ingest, Builder, review and
cycle_closeout machinery. Never sends to a client, authorizes printing, mutates
customer source, accepts synthetic jobs, or enables candidate-only DUAL runtime.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.graphic_design_lab.greeting_cards import (  # noqa: E402
    intake_handoff_runner_v0_1 as handoff,
    cycle_closeout_v0_1 as closeout,
)

SCHEMA = 'gdl_gc10_unified_private_cycle_v0_1'
OUTPUT_ROOT = ROOT / 'tmp/gdl_gc10_unified_private_cycle_v0_1'
RECEIPT_CLI = ROOT / 'scripts/graphic_design_lab/greeting_cards/cycle_closeout_v0_1.py'
FIRST_LOOP_SIGNATURES = frozenset(('GRIGO', 'HERASYMENKO'))
SHA_RE = re.compile(r'^[0-9a-f]{64}$')
SAFE_CODE = re.compile(r'^[a-z0-9_]+$')


class UnifiedBlocked(ValueError):
    """Bounded failure without customer content or private absolute paths."""


def file_sha(path: Path) -> str:
    h = sha256()
    with path.open('rb') as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def inside_tmp(path: Path) -> Path:
    candidate = path.expanduser().resolve()
    top = (ROOT / 'tmp').resolve()
    if candidate == top or top not in candidate.parents:
        raise UnifiedBlocked('path_outside_project_tmp')
    return candidate


def relative_tmp(path: Path) -> str:
    return str(inside_tmp(path).relative_to(ROOT.resolve()))


def atomic_json_exclusive(path: Path, content: dict[str, Any]) -> None:
    # Never overwrite a terminal report from an earlier execution.
    with path.open('x', encoding='utf-8') as f:
        json.dump(content, f, ensure_ascii=False, sort_keys=True, indent=2)
        f.write('\n')


def source_preflight(package: Path, config: Path) -> dict[str, Any]:
    if package.name != handoff.HANDOFF_FILENAME or not package.is_file() or package.is_symlink():
        raise UnifiedBlocked('source_package_invalid')
    # Do not infer any Intake approval or guess resource bindings.
    inspection = handoff.inspect_zip(package, config)
    if inspection.get('synthetic') is not False:
        raise UnifiedBlocked('synthetic_package_not_formal_evidence')
    if not isinstance(inspection.get('jobs'), int) or inspection['jobs'] < 1:
        raise UnifiedBlocked('source_job_count_invalid')
    checksum = inspection.get('archive_sha256')
    if not isinstance(checksum, str) or not SHA_RE.fullmatch(checksum):
        raise UnifiedBlocked('source_checksum_invalid')
    if file_sha(package) != checksum:
        raise UnifiedBlocked('source_changed_during_preflight')
    # Candidate-only DUAL must not leak into the ordinary first-loop runtime.
    from app.graphic_design_lab.greeting_card_builder_renderer import (
        SUPPORTED_SIGNATURE_VARIANTS, SUPPORTED_FRONT_FAMILIES,
        SUPPORTED_IMAGE_MODES,
    )
    bundle = inspection.get('bundle')
    jobs = bundle.get('jobs') if isinstance(bundle, dict) else None
    if not isinstance(jobs, list) or len(jobs) != inspection['jobs']:
        raise UnifiedBlocked('source_bundle_job_count_invalid')
    for job in jobs:
        if not isinstance(job, dict):
            raise UnifiedBlocked('source_job_invalid')
        signature = job.get('signature_selection') or {}
        payload = job.get('builder_v1') or {}
        sender = payload.get('sender_text') or {}
        variant = signature.get('variant_id')
        if (variant not in FIRST_LOOP_SIGNATURES
                or variant not in SUPPORTED_SIGNATURE_VARIANTS
                or sender.get('signature_variant_id') != variant):
            raise UnifiedBlocked('signature_variant_not_in_first_loop')
        if ((payload.get('front') or {}).get('family') not in SUPPORTED_FRONT_FAMILIES
                or (payload.get('inside_image') or {}).get('mode') not in SUPPORTED_IMAGE_MODES):
            raise UnifiedBlocked('layout_not_in_first_loop')
        if str(job.get('job_id', '')).startswith('gdl-synthetic-'):
            raise UnifiedBlocked('synthetic_job_not_formal_evidence')
    return inspection


def copy_source_to_private_tmp(source: Path, private_root: Path, expected_sha: str) -> Path:
    private_root = inside_tmp(private_root)
    path = private_root / 'source' / handoff.HANDOFF_FILENAME
    path.parent.mkdir(parents=True, exist_ok=False)
    with source.open('rb') as src, path.open('xb') as dst:
        shutil.copyfileobj(src, dst, length=1024 * 1024)
    if file_sha(path) != expected_sha or file_sha(source) != expected_sha:
        raise UnifiedBlocked('private_package_copy_digest_mismatch')
    return path


def new_handoff_run(before: set[str], expected_source_sha: str) -> Path:
    folder = handoff.RUNTIME / 'runs'
    after = {p.name for p in folder.iterdir() if p.is_dir()} if folder.is_dir() else set()
    new = sorted(after - before)
    if len(new) != 1 or not new[0].endswith('-' + expected_source_sha[:10]):
        raise UnifiedBlocked('handoff_run_identity_ambiguous')
    return inside_tmp(folder / new[0])


def make_manifest(run: Path, result: dict[str, Any], source: Path, path: Path) -> dict[str, str]:
    if (result.get('status') != 'PASS_REQUIRES_VISUAL_APPROVAL'
            or result.get('client_review_published') is not False
            or result.get('client_output_subdir') is not None
            or result.get('customer_approved') is not False
            or result.get('production_approved') is not False
            or result.get('source_zip_unchanged') is not True):
        raise UnifiedBlocked('handoff_not_private_review_only')
    location = result.get('private_review_dir')
    if not isinstance(location, str) or not location:
        raise UnifiedBlocked('private_review_location_missing')
    review_root = inside_tmp(ROOT / location)
    review = review_root / 'review/review_summary.json'
    archive = review_root / 'full_card_review_PRIVATE.zip'
    ingest = run / 'input_PRIVATE/output/report/job_result.json'
    handoff_result = run / 'handoff_result.json'
    if not all(p.is_file() for p in (review, archive, ingest, handoff_result)):
        raise UnifiedBlocked('formal_closeout_inputs_incomplete')
    document = {
        'schema_version': closeout.SCHEMA,
        'sources': [{
            'kind': 'STANDARD_REVIEW',
            'report': relative_tmp(review),
            'constructor_ingest_report': relative_tmp(ingest),
            'handoff_report': relative_tmp(handoff_result),
            'handoff_package': relative_tmp(source),
        }],
    }
    with path.open('x', encoding='utf-8') as f:
        yaml.safe_dump(document, f, allow_unicode=True, sort_keys=False)
    return {'review': relative_tmp(review), 'handoff': relative_tmp(handoff_result),
            'ingest': relative_tmp(ingest), 'manifest': relative_tmp(path)}


def require_closeout(record: dict[str, Any], job_count: int) -> None:
    if (record.get('status') != 'INTERNAL_LAYOUT_CYCLE_VERIFIED_NOT_FOR_PRINT'
            or record.get('formal_constructor_acceptance_for_all_jobs') is not True
            or record.get('job_count') != job_count
            or record.get('pdf_count') != job_count
            or record.get('page_count') != 4 * job_count
            or record.get('production_approvals') != 0
            or record.get('customer_approvals') != 0
            or record.get('client_published') is not False):
        raise UnifiedBlocked('formal_constructor_closeout_not_verified')


def record_closeout(manifest: Path, checked: dict[str, Any], job_count: int) -> Path:
    # Invoke the established CLI for its canonical immutable receipt semantics.
    proc = subprocess.run(
        [sys.executable, str(RECEIPT_CLI), '--mode', 'record', '--manifest', str(manifest)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        raise UnifiedBlocked('formal_closeout_record_blocked')
    keys = [line.split('=', 1)[1] for line in proc.stdout.splitlines()
            if line.startswith('GDL_GC_CYCLE_RECORD=')]
    if len(keys) != 1:
        raise UnifiedBlocked('formal_closeout_receipt_missing')
    receipt = inside_tmp(ROOT / keys[0])
    if not receipt.is_file():
        raise UnifiedBlocked('formal_closeout_receipt_file_missing')
    report = json.loads(receipt.read_text(encoding='utf-8'))
    require_closeout(report, job_count)
    if report.get('manifest_sha256') != file_sha(manifest):
        raise UnifiedBlocked('formal_closeout_receipt_manifest_mismatch')
    if report != checked:
        raise UnifiedBlocked('formal_closeout_check_record_mismatch')
    return receipt


def run_private(package: Path, config: Path) -> dict[str, Any]:
    stage = 'PREFLIGHT'
    root: Path | None = None
    try:
        inspection = source_preflight(package, config)
        source_sha = inspection['archive_sha256']
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        root = inside_tmp(OUTPUT_ROOT / 'runs' / (stamp + '-' + source_sha[:10]))
        root.mkdir(parents=True, exist_ok=False)
        stage = 'COPY_SOURCE'
        local = copy_source_to_private_tmp(package, root, source_sha)
        stage = 'PREFLIGHT_PRIVATE_COPY'
        rebound = source_preflight(local, config)
        if rebound['archive_sha256'] != source_sha or rebound['jobs'] != inspection['jobs']:
            raise UnifiedBlocked('source_copy_preflight_changed')
        folder = handoff.RUNTIME / 'runs'
        before = {p.name for p in folder.iterdir() if p.is_dir()} if folder.is_dir() else set()
        stage = 'PRIVATE_HANDOFF_BUILDER'
        # Existing handoff prints internal job details; not echoing into the operator log.
        with redirect_stdout(io.StringIO()):
            result = handoff.materialize_and_run(rebound, config, publish_client=False)
        if result.get('source_zip_sha256') != source_sha or result.get('job_count') != inspection['jobs']:
            raise UnifiedBlocked('handoff_output_identity_mismatch')
        existing_run = new_handoff_run(before, source_sha)
        stage = 'FORMAL_CLOSEOUT_CHECK'
        manifest_path = root / 'formal_closeout_manifest.yaml'
        evidence = make_manifest(existing_run, result, local, manifest_path)
        checked = closeout.compile_closeout(manifest_path)
        require_closeout(checked, inspection['jobs'])
        stage = 'FORMAL_CLOSEOUT_RECORD'
        receipt = record_closeout(manifest_path, checked, inspection['jobs'])
        stage = 'FINAL_SOURCE_CHECK'
        if file_sha(local) != source_sha or file_sha(package) != source_sha:
            raise UnifiedBlocked('source_changed_during_cycle')
        output = {
            'schema_version': SCHEMA,
            'status': 'PRIVATE_CYCLE_PASS_REQUIRES_VISUAL_REVIEW',
            'job_count': checked['job_count'],
            'pdf_count': checked['pdf_count'],
            'page_count': checked['page_count'],
            'png_preview_count': checked['job_count'] * 4,
            'formal_constructor_evidence_verified_for_all_jobs': True,
            'source_zip_sha256': source_sha,
            'formal_closeout_manifest': evidence['manifest'],
            'constructor_ingest_report': evidence['ingest'],
            'handoff_report': evidence['handoff'],
            'private_review_report': evidence['review'],
            'closeout_receipt': relative_tmp(receipt),
            'closeout_receipt_sha256': file_sha(receipt),
            'production_approved': False,
            'customer_approved': False,
            'client_published': False,
            'dual_runtime_enabled': False,
            'next_action': 'OPERATOR_VISUAL_REVIEW_AND_PRINT_PREFLIGHT',
        }
        atomic_json_exclusive(root / 'unified_cycle_result.json', output)
        return {'summary': output, 'report': relative_tmp(root / 'unified_cycle_result.json')}
    except Exception as error:
        code = str(error) if isinstance(error, UnifiedBlocked) else type(error).__name__
        if not SAFE_CODE.fullmatch(code):
            code = type(error).__name__
        action = {
            'PREFLIGHT': 'CHECK_ACCEPTED_HANDOFF_ZIP_AND_PRIVATE_RESOURCE_CONFIG',
            'COPY_SOURCE': 'CHECK_PRIVATE_TMP_AND_SOURCE_INTEGRITY',
            'PREFLIGHT_PRIVATE_COPY': 'CHECK_SOURCE_ARCHIVE_DIGEST',
            'PRIVATE_HANDOFF_BUILDER': 'INSPECT_HANDOFF_BUILDER_BLOCKER_PRIVATELY',
            'FORMAL_CLOSEOUT_CHECK': 'INSPECT_CONSTRUCTOR_HANDOFF_REVIEW_EVIDENCE',
            'FORMAL_CLOSEOUT_RECORD': 'INSPECT_CLOSEOUT_RECEIPT_BLOCKER',
            'FINAL_SOURCE_CHECK': 'CHECK_SOURCE_MUTATION_OR_INTEGRITY',
        }.get(stage, 'OPERATOR_INVESTIGATE')
        if root is not None and root.is_dir():
            try:
                atomic_json_exclusive(root / 'unified_cycle_result.json', {
                    'schema_version': SCHEMA, 'status': 'BLOCKED',
                    'blocked_stage': stage, 'error_code': code,
                    'next_action': action, 'production_approved': False,
                    'customer_approved': False, 'client_published': False,
                })
            except (OSError, ValueError):
                pass
        raise UnifiedBlocked(stage.lower() + '_blocked') from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', required=True, choices=('preflight', 'run'))
    parser.add_argument('--package', required=True, type=Path)
    parser.add_argument('--config', type=Path, default=handoff.CONFIG)
    args = parser.parse_args()
    try:
        if args.mode == 'preflight':
            inspection = source_preflight(args.package, args.config)
            print('GDL_GC10_UNIFIED_PREFLIGHT=PASS')
            print('JOB_COUNT=' + str(inspection['jobs']))
            print('CLIENT_PUBLISHED=false')
        else:
            result = run_private(args.package, args.config)
            report = result['summary']
            print('GDL_GC10_UNIFIED_PRIVATE_CYCLE=PASS_REQUIRES_VISUAL_REVIEW')
            print('JOB_COUNT=' + str(report['job_count']))
            print('PDF_COUNT=' + str(report['pdf_count']))
            print('PNG_COUNT=' + str(report['png_preview_count']))
            print('FORMAL_CONSTRUCTOR_EVIDENCE=PASS')
            print('CYCLE_REPORT=' + result['report'])
            print('CLOSEOUT_RECEIPT=' + report['closeout_receipt'])
            print('PRODUCTION_APPROVED=false')
            print('CLIENT_PUBLISHED=false')
        return 0
    except Exception as error:
        # Do not expose private source paths, contents or raw lower-layer errors.
        code = str(error) if isinstance(error, UnifiedBlocked) else type(error).__name__
        if not SAFE_CODE.fullmatch(code):
            code = type(error).__name__
        print('GDL_GC10_UNIFIED_PRIVATE_CYCLE=BLOCKED')
        print('ERROR_CODE=' + code)
        print('CLIENT_PUBLISHED=false')
        print('PRODUCTION_APPROVED=false')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

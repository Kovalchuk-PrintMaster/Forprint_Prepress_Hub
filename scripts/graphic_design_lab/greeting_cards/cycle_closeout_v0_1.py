#!/usr/bin/env python3
"""Generic, project-owned review-only greeting-card cycle closeout.

The manifest names existing immutable review *reports*, not original customer
materials or PDFs. No Builder run, no customer publishing, no acceptance.
The CLI verifies each PDF against its own report and records a private receipt
inside repository tmp/, preserving failed production gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pymupdf
import yaml

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = 'gdl_gc_review_cycle_manifest_v0_1'
RECEIPT_SCHEMA = 'gdl_gc_review_cycle_closeout_v0_1'
VALID_KINDS = {'STANDARD_REVIEW', 'CREATOR_LAYOUT_PROOF', 'BRANDED_LAYOUT_PROOF'}
HEX = re.compile(r'^[a-f0-9]{64}$')
ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$')


class CycleBlocked(ValueError):
    pass


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def inside_tmp(path: Path, *, root: Path) -> Path:
    candidate = (root / path).resolve() if not path.is_absolute() else path.resolve()
    permitted = (root / 'tmp').resolve()
    if candidate == permitted or permitted not in candidate.parents:
        raise CycleBlocked('path_outside_repository_tmp')
    return candidate


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise CycleBlocked('report_missing')
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise CycleBlocked('report_not_mapping')
    return data


def require_exact_bool(data: dict[str, Any], key: str, value: bool) -> None:
    if data.get(key) is not value:
        raise CycleBlocked('report_authority_mismatch_' + key)


def verified_pdf(report_path: Path, relative: str, expected_sha: str, *, root: Path) -> tuple[str, int]:
    if not isinstance(relative, str) or not relative or not HEX.fullmatch(str(expected_sha)):
        raise CycleBlocked('pdf_path_or_digest_invalid')
    rel = Path(relative)
    if rel.is_absolute() or '..' in rel.parts or '\\' in relative:
        raise CycleBlocked('pdf_path_unsafe')
    # Reports live in <run>/review/*.json, PDFs are in the corresponding <run>.
    run_dir = report_path.parent.parent
    pdf = inside_tmp(run_dir / rel, root=root)
    if not pdf.is_file() or sha_file(pdf) != expected_sha:
        raise CycleBlocked('pdf_missing_or_digest_mismatch')
    with pymupdf.open(pdf) as document:
        count = document.page_count
        if count != 4:
            raise CycleBlocked('pdf_must_have_four_pages')
    return expected_sha, count


def validate_standard(report_path: Path, data: dict[str, Any], *, root: Path) -> list[dict[str, Any]]:
    if (data.get('schema_version') != 'gdl_gc09_full_card_review_v0_1'
            or data.get('pdf_preview_pixel_replay') != 'PASS'
            or data.get('synthetic_fixture') is not False):
        raise CycleBlocked('standard_review_contract_invalid')
    require_exact_bool(data, 'customer_approved', False)
    require_exact_bool(data, 'production_approved', False)
    require_exact_bool(data, 'dual_runtime_activated_by_this_runner', False)
    require_exact_bool(data, 'git_or_source_modified_by_this_runner', False)
    raw_jobs = data.get('jobs')
    if not isinstance(raw_jobs, list) or not raw_jobs or data.get('job_count') != len(raw_jobs):
        raise CycleBlocked('standard_job_count_mismatch')
    if data.get('pdf_count') != len(raw_jobs) or data.get('png_preview_count') != 4 * len(raw_jobs):
        raise CycleBlocked('standard_artifact_count_mismatch')
    jobs: list[dict[str, Any]] = []
    for item in raw_jobs:
        if not isinstance(item, dict) or item.get('page_count') != 4 or item.get('preview_count') != 4:
            raise CycleBlocked('standard_job_invalid')
        if item.get('preview_pixel_replay') != 'PASS':
            raise CycleBlocked('standard_preview_not_verified')
        digest, pages = verified_pdf(report_path, item.get('pdf'), item.get('pdf_sha256'), root=root)
        jobs.append(dict(job_id=item.get('job_id'), status='REVIEW_PDF_NEEDS_VISUAL_APPROVAL',
                         pdf_sha256=digest, page_count=pages, production_ready=False))
    return jobs


def validate_creator(report_path: Path, data: dict[str, Any], *, root: Path) -> list[dict[str, Any]]:
    if (data.get('schema_version') != 'gdl_creator_blocked_layout_proof_v0_1'
            or data.get('creator_result_state') != 'BLOCKED_LOW_SOURCE_RESOLUTION'
            or data.get('print_quality_state') != 'BLOCKED_INSUFFICIENT_NATIVE_RESOLUTION'
            or data.get('pdf_preview_pixel_replay') != 'PASS'
            or data.get('pdf_page_count') != 4):
        raise CycleBlocked('creator_proof_contract_invalid')
    for key in ('accepted_constructor_bundle_created', 'production_ready', 'customer_published',
                'customer_approved', 'smb_modified', 'git_mutated',
                'creator_asset_accepted_for_constructor'):
        require_exact_bool(data, key, False)
    digest, pages = verified_pdf(report_path, data.get('final_pdf_path'), data.get('pdf_sha256'), root=root)
    return [dict(job_id=data.get('job_id'), status='INTERNAL_LAYOUT_PROOF_LOW_PPI_BLOCKED',
                 pdf_sha256=digest, page_count=pages, production_ready=False,
                 outstanding_gates=['LOW_NATIVE_PORTRAIT_RESOLUTION'],
                 proof_font_pt=data.get('temporary_font_pt'),
                 proof_font_evidence='SOURCE_REPORT' if isinstance(data.get('temporary_font_pt'), (float, int)) else 'NOT_IN_SOURCE_REPORT')]


def validate_branded(report_path: Path, data: dict[str, Any], *, root: Path) -> list[dict[str, Any]]:
    if (data.get('schema_version') != 'gdl_gc_bas_branded_layout_proof_v0_1'
            or data.get('front_variant') != 'RECIPIENT_BRANDING_OVERLAY_CANDIDATE'
            or data.get('preview_pixel_replay') != 'PASS'
            or data.get('pages_2_to_4_pixel_identity_vs_base') != 'PASS'
            or data.get('pdf_page_count') != 4):
        raise CycleBlocked('branded_proof_contract_invalid')
    for key in ('accepted_constructor_bundle_created', 'production_ready', 'client_published',
                'client_approved', 'git_mutated', 'smb_mutated'):
        require_exact_bool(data, key, False)
    if data.get('sender_content_authority') != 'PROJECT_CANONICAL_ONLY':
        raise CycleBlocked('branded_sender_authority_not_canonical')
    if data.get('canonical_signature_exact_private_source_used') is not True:
        raise CycleBlocked('branded_signature_not_authenticated')
    # The legacy proof report omits a PDF relative filename. Resolve one and
    # only one candidate matching its job ID and revision pattern.
    jobid = data.get('job_id')
    if not isinstance(jobid, str) or ID.fullmatch(jobid) is None:
        raise CycleBlocked('branded_job_id_invalid')
    matches = list((report_path.parent.parent / 'completed').glob(
        f'{jobid}__r[0-9][0-9][0-9]__BRANDED_LAYOUT_PROOF_NOT_FOR_PRINT.pdf'
    ))
    if len(matches) != 1:
        raise CycleBlocked('branded_pdf_unique_revision_missing')
    relative_pdf = str(matches[0].relative_to(report_path.parent.parent))
    digest, pages = verified_pdf(report_path, relative_pdf, data.get('pdf_sha256'), root=root)
    return [dict(job_id=jobid, status='RECIPIENT_BRANDING_PROOF_NOT_APPROVED',
                 pdf_sha256=digest, page_count=pages, production_ready=False,
                 outstanding_gates=['BRANDED_FRONT_PERMANENT_RENDERER_NOT_VERIFIED'],
                 proof_font_pt=data.get('temporary_font_pt'))]


HANDLERS = {'STANDARD_REVIEW': validate_standard,
            'CREATOR_LAYOUT_PROOF': validate_creator,
            'BRANDED_LAYOUT_PROOF': validate_branded}


def compile_closeout(manifest: Path, *, root: Path = ROOT) -> dict[str, Any]:
    manifest = inside_tmp(manifest, root=root)
    if not manifest.is_file():
        raise CycleBlocked('manifest_missing')
    raw = yaml.safe_load(manifest.read_text(encoding='utf-8'))
    if (not isinstance(raw, dict) or raw.get('schema_version') != SCHEMA
            or set(raw) != {'schema_version', 'sources'}):
        raise CycleBlocked('manifest_schema_invalid')
    sources = raw['sources']
    if not isinstance(sources, list) or not sources or len(sources) > 100:
        raise CycleBlocked('manifest_sources_invalid')
    jobs: list[dict[str, Any]] = []
    evidence: list[dict[str, str]] = []
    seen_reports: set[str] = set()
    for entry in sources:
        if not isinstance(entry, dict) or set(entry) != {'kind', 'report'}:
            raise CycleBlocked('manifest_source_invalid')
        kind = entry['kind']
        if kind not in VALID_KINDS:
            raise CycleBlocked('manifest_kind_unknown')
        if not isinstance(entry['report'], str):
            raise CycleBlocked('manifest_report_path_invalid')
        report_path = inside_tmp(Path(entry['report']), root=root)
        if str(report_path) in seen_reports:
            raise CycleBlocked('report_duplicate')
        seen_reports.add(str(report_path))
        data = read_json(report_path)
        jobs.extend(HANDLERS[kind](report_path, data, root=root))
        evidence.append(dict(kind=kind, report_sha256=sha_file(report_path),
                             report_relative_path=str(report_path.relative_to(root))))
    ids = [x.get('job_id') for x in jobs]
    if any(not isinstance(v, str) or not ID.fullmatch(v) for v in ids) or len(set(ids)) != len(ids):
        raise CycleBlocked('job_ids_missing_or_duplicate')
    jobs = sorted(jobs, key=lambda x: x['job_id'])
    return {'schema_version': RECEIPT_SCHEMA, 'status': 'INTERNAL_LAYOUT_CYCLE_VERIFIED_NOT_FOR_PRINT',
            'job_count': len(jobs), 'pdf_count': len(jobs), 'page_count': sum(x['page_count'] for x in jobs),
            'production_approvals': 0, 'customer_approvals': 0, 'client_published': False,
            'formal_constructor_acceptance_for_all_jobs': False,
            'manifest_sha256': sha_file(manifest), 'source_reports': evidence,
            'jobs': jobs,
            'outstanding_gates': sorted({gate for j in jobs for gate in j.get('outstanding_gates', [])} | {'VISUAL_REVIEW_AND_PRINT_PREFLIGHT'}),
            'tracked_code_modified': False}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', choices=('check', 'record'), required=True)
    p.add_argument('--manifest', type=Path, required=True)
    args = p.parse_args()
    try:
        record = compile_closeout(args.manifest)
        print('GDL_GC_CYCLE_CLOSEOUT=CHECK_PASS')
        print('JOB_COUNT=' + str(record['job_count']))
        print('PDF_COUNT=' + str(record['pdf_count']))
        print('PAGE_COUNT=' + str(record['page_count']))
        print('PRODUCTION_APPROVALS=0')
        print('CLIENT_PUBLISHED=false')
        if args.mode == 'record':
            root = (ROOT / 'tmp/gdl_gc_cycle_closeout_v0_1/records').resolve()
            root.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            target = root / (stamp + '-' + record['manifest_sha256'][:10] + '.json')
            with target.open('x', encoding='utf-8') as f:
                json.dump(record, f, ensure_ascii=False, indent=2)
                f.write('\n')
            print('GDL_GC_CYCLE_RECORD=' + str(target.relative_to(ROOT)))
        return 0
    except (CycleBlocked, ValueError, OSError, KeyError, TypeError, json.JSONDecodeError, yaml.YAMLError, pymupdf.FileDataError) as e:
        code = str(e).split(':')[0]
        if not re.fullmatch('[a-z0-9_]+', code):
            code = type(e).__name__
        print('GDL_GC_CYCLE_CLOSEOUT=BLOCKED')
        print('ERROR_CODE=' + code)
        print('CLIENT_PUBLISHED=false')
        return 2


if __name__ == '__main__':
    sys.exit(main())

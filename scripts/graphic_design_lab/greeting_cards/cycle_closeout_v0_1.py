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
import zipfile
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


def verify_constructor_chain(entry: dict[str, Any], report_path: Path,
                             review: dict[str, Any], jobs: list[dict[str, Any]],
                             *, root: Path) -> dict[str, str]:
    """Correlate a real review with immutable Intake/Constructor/Handoff evidence.

    All paths are local to repository tmp. This does not grant printing, customer
    release or any additional authority beyond operator-reviewed constructor input.
    """
    from app.graphic_design_lab.greeting_card_constructor_bundle import compute_bundle_sha256

    ingest_path = inside_tmp(Path(entry['constructor_ingest_report']), root=root)
    handoff_path = inside_tmp(Path(entry['handoff_report']), root=root)
    package_path = inside_tmp(Path(entry['handoff_package']), root=root)
    if (ingest_path.name != 'job_result.json' or ingest_path.parent.name != 'report'
            or ingest_path.parent.parent.name != 'output'
            or ingest_path.parents[2].name != 'input_PRIVATE'
            or handoff_path.name != 'handoff_result.json'
            or handoff_path.parent != ingest_path.parents[3]
            or package_path.name != 'gdl_intake_handoff.zip'):
        raise CycleBlocked('constructor_evidence_location_mismatch')
    ingest = read_json(ingest_path)
    handoff = read_json(handoff_path)
    if (ingest.get('schema_version') != 'gdl_greeting_card_constructor_ingest_report_v0_1'
            or ingest.get('status') != 'ACCEPTED_CONSTRUCTOR_BUNDLE_INGESTED'
            or ingest.get('constructor_input_class') != 'ACCEPTED_CONSTRUCTOR_BUNDLE'
            or ingest.get('ready_for_composition') is not True
            or ingest.get('source_mutation') is not False):
        raise CycleBlocked('constructor_ingest_contract_invalid')
    for flag in ('production_ready', 'production_write_enabled', 'git_mutation',
                 'raw_customer_material_interpretation_performed',
                 'heuristic_role_inference_performed', 'normalized_batch_synthesis_performed'):
        require_exact_bool(ingest, flag, False)
    input_bundle = ingest_path.parents[2] / 'accepted_constructor_bundle.yaml'
    if not input_bundle.is_file():
        raise CycleBlocked('constructor_source_bundle_missing')
    file_digest = sha_file(input_bundle)
    fingerprints = review.get('source_fingerprints_sha256')
    if (not isinstance(fingerprints, dict) or not HEX.fullmatch(file_digest)
            or ingest.get('bundle_file_sha256') != file_digest
            or fingerprints.get('bundle') != file_digest):
        raise CycleBlocked('constructor_builder_bundle_digest_mismatch')
    bundle = yaml.safe_load(input_bundle.read_bytes())
    if not isinstance(bundle, dict):
        raise CycleBlocked('constructor_bundle_not_mapping')
    computed = compute_bundle_sha256(bundle)
    if (bundle.get('provenance_manifest', {}).get('bundle_sha256') != computed
            or ingest.get('bundle_canonical_sha256') != computed
            or ingest.get('bundle_id') != bundle.get('bundle_id')):
        raise CycleBlocked('constructor_bundle_canonical_digest_mismatch')
    actual_ids = [job.get('job_id') for job in jobs]
    constructor_ids = ingest.get('job_ids')
    bundle_jobs = bundle.get('jobs')
    if (not isinstance(constructor_ids, list) or len(set(constructor_ids)) != len(constructor_ids)
            or ingest.get('job_count') != len(constructor_ids)
            or set(constructor_ids) != set(actual_ids)
            or not isinstance(bundle_jobs, list)
            or sorted(x.get('job_id') for x in bundle_jobs if isinstance(x, dict)) != sorted(actual_ids)
            or len(bundle_jobs) != len(actual_ids)):
        raise CycleBlocked('constructor_job_identity_mismatch')
    if (handoff.get('schema_version') != 'gdl_intake_builder_handoff_v0_1'
            or handoff.get('status') != 'PASS_REQUIRES_VISUAL_APPROVAL'
            or handoff.get('job_count') != len(actual_ids)
            or handoff.get('source_zip_unchanged') is not True
            or handoff.get('client_review_published') is not False
            or handoff.get('client_output_subdir') is not None):
        raise CycleBlocked('handoff_review_contract_invalid')
    for flag in ('customer_approved', 'production_approved'):
        require_exact_bool(handoff, flag, False)
    if not package_path.is_file() or sha_file(package_path) != handoff.get('source_zip_sha256'):
        raise CycleBlocked('handoff_source_archive_digest_mismatch')
    with zipfile.ZipFile(package_path, 'r') as package:
        if package.namelist().count('accepted_constructor_bundle.yaml') != 1:
            raise CycleBlocked('handoff_bundle_member_invalid')
        if hashlib.sha256(package.read('accepted_constructor_bundle.yaml')).hexdigest() != file_digest:
            raise CycleBlocked('handoff_bundle_source_mismatch')
    private_run = inside_tmp(Path(str(handoff.get('private_review_dir', ''))), root=root)
    private_archive = inside_tmp(Path(str(handoff.get('private_review_archive', ''))), root=root)
    if (private_run != report_path.parent.parent or private_archive != private_run / 'full_card_review_PRIVATE.zip'
            or not private_archive.is_file()):
        raise CycleBlocked('handoff_review_run_binding_mismatch')
    # The durable review ZIP must represent the same report and exact PDFs.
    with zipfile.ZipFile(private_archive, 'r') as zipped:
        if zipped.namelist().count('review/review_summary.json') != 1:
            raise CycleBlocked('review_archive_summary_missing_or_duplicate')
        if hashlib.sha256(zipped.read('review/review_summary.json')).hexdigest() != sha_file(report_path):
            raise CycleBlocked('review_archive_summary_digest_mismatch')
        for item in review['jobs']:
            name = item['pdf']
            if zipped.namelist().count(name) != 1 or hashlib.sha256(zipped.read(name)).hexdigest() != item['pdf_sha256']:
                raise CycleBlocked('review_archive_pdf_digest_mismatch')
    return {'constructor_ingest_report_sha256': sha_file(ingest_path),
            'handoff_report_sha256': sha_file(handoff_path),
            'handoff_package_sha256': sha_file(package_path),
            'accepted_constructor_bundle_sha256': computed}


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
        if not isinstance(entry, dict):
            raise CycleBlocked('manifest_source_invalid')
        keys = set(entry)
        evidence_keys = {'constructor_ingest_report', 'handoff_report', 'handoff_package'}
        legacy_keys = {'kind', 'report'}
        has_constructor_evidence = keys == (legacy_keys | evidence_keys)
        if keys != legacy_keys and not has_constructor_evidence:
            raise CycleBlocked('manifest_source_invalid')
        kind = entry['kind']
        if has_constructor_evidence and kind != 'STANDARD_REVIEW':
            raise CycleBlocked('constructor_evidence_kind_invalid')
        if has_constructor_evidence and any(not isinstance(entry[key], str) or not entry[key] for key in evidence_keys):
            raise CycleBlocked('constructor_evidence_path_invalid')
        if kind not in VALID_KINDS:
            raise CycleBlocked('manifest_kind_unknown')
        if not isinstance(entry['report'], str):
            raise CycleBlocked('manifest_report_path_invalid')
        report_path = inside_tmp(Path(entry['report']), root=root)
        if str(report_path) in seen_reports:
            raise CycleBlocked('report_duplicate')
        seen_reports.add(str(report_path))
        data = read_json(report_path)
        current_jobs = HANDLERS[kind](report_path, data, root=root)
        current_evidence = dict(kind=kind, report_sha256=sha_file(report_path),
                                report_relative_path=str(report_path.relative_to(root)))
        if has_constructor_evidence:
            verified = verify_constructor_chain(entry, report_path, data, current_jobs, root=root)
            for job in current_jobs:
                job['constructor_accepted_for_internal_review'] = True
                job['accepted_constructor_bundle_sha256'] = verified['accepted_constructor_bundle_sha256']
            current_evidence.update(verified)
        jobs.extend(current_jobs)
        evidence.append(current_evidence)
    ids = [x.get('job_id') for x in jobs]
    if any(not isinstance(v, str) or not ID.fullmatch(v) for v in ids) or len(set(ids)) != len(ids):
        raise CycleBlocked('job_ids_missing_or_duplicate')
    jobs = sorted(jobs, key=lambda x: x['job_id'])
    return {'schema_version': RECEIPT_SCHEMA, 'status': 'INTERNAL_LAYOUT_CYCLE_VERIFIED_NOT_FOR_PRINT',
            'job_count': len(jobs), 'pdf_count': len(jobs), 'page_count': sum(x['page_count'] for x in jobs),
            'production_approvals': 0, 'customer_approvals': 0, 'client_published': False,
            'formal_constructor_acceptance_for_all_jobs': all(
                j.get('constructor_accepted_for_internal_review') is True for j in jobs),
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
        print('CONSTRUCTOR_EVIDENCE_VERIFIED_FOR_ALL_JOBS=' +
              str(record['formal_constructor_acceptance_for_all_jobs']).lower())
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

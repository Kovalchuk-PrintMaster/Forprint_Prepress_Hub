#!/usr/bin/env python3
"""GDL GC-E2E-09 synthetic multi-job PDF proof using project-owned build_bundle.

Reuses an existing *real validated* input bundle's private resources ONLY as
physical test fixtures. Synthetic clones are NOT accepted client orders.
Writes entirely under ignored tmp; never stages/commits, promotes or activates DUAL.
Do not upload the private synthetic bundle, PDFs, or provenance evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pymupdf
import yaml
from PIL import Image

from app.graphic_design_lab.greeting_card_builder_input import validate_builder_ready_bundle_v1
from app.graphic_design_lab.greeting_card_constructor_bundle import compute_bundle_sha256
from app.graphic_design_lab.greeting_card_builder_renderer import PREVIEW_DPI, build_bundle

DEFAULT_CONFIG = ROOT / 'tmp/gdl_gc09b_real_pdf_proof_20261010/private_inputs_local.json'
SIGNATURE_CATALOG = ROOT / 'coordination/graphic_design_lab/directions/greeting_cards/signature_variant_catalog_v0_1.yaml'
REGISTRY = ROOT / 'coordination/graphic_design_lab/directions/greeting_cards/signature_registry_v0_1.yaml'
CURSOR = ROOT / 'coordination/graphic_design_lab/continuity/current_execution_cursor_v0_1.yaml'
REPORT_ROOT = ROOT / 'tmp/gdl_v1_multi_job_pdf_proof'
SENTENCE = 'Бажаємо радості, тепла, натхнення та гарних новин у кожному дні. '
SENDER_LINES = [
    {'id': 'closing_phrase', 'text': 'З найкращими побажаннями'},
    {'id': 'sender_name', 'text': "Ім'я Приклад"},
    {'id': 'sender_role_1', 'text': 'Посада підписанта'},
    {'id': 'sender_role_2', 'text': 'Назва відділу'},
    {'id': 'sender_role_3', 'text': 'Додаткова інформація'},
    {'id': 'sender_role_4', 'text': 'Другий підписант'},
    {'id': 'sender_role_5', 'text': 'Посада другого'},
    {'id': 'sender_role_6', 'text': 'Підрозділ організації'},
]
CASES = (
    ('short_2', 110, 2),
    ('medium_3', 420, 3),
    ('long_6', 850, 6),
)
OVERFLOW = ('overflow_8', 1800, 8)
EXPECTED_HEAD = '49d141c405b102a2c920c4e3b3690be7776d9889'


def sha(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            hasher.update(block)
    return hasher.hexdigest()


def git(*args: str) -> str:
    cp = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, check=False)
    if cp.returncode:
        raise RuntimeError('GIT_PREFLIGHT_FAILED')
    return cp.stdout.decode('utf-8', 'replace').strip()


def synthetic_text(length: int) -> str:
    if not isinstance(length, int) or isinstance(length, bool) or not 20 <= length <= 2000:
        raise ValueError('INVALID_SYNTHETIC_TEXT_LENGTH')
    return (SENTENCE * (length // len(SENTENCE) + 2))[:length].strip()


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('MAPPING_REQUIRED')
    return data


def private_inputs(config: Path) -> dict[str, Path]:
    values = json.loads(config.read_text(encoding='utf-8'))
    if not isinstance(values, dict) or set(values) != {'bundle', 'resource_manifest', 'artifact_manifest'}:
        raise ValueError('PRIVATE_BINDING_KEYS_INVALID')
    paths = {}
    for key in ('bundle', 'resource_manifest', 'artifact_manifest'):
        raw = values.get(key)
        if not isinstance(raw, str) or not raw:
            raise ValueError('PRIVATE_BINDING_EMPTY_' + key)
        item = Path(raw).expanduser()
        if not item.is_absolute():
            item = ROOT / item
        item = item.resolve()
        if not item.is_file():
            raise ValueError('PRIVATE_INPUT_MISSING_' + key)
        paths[key] = item
    return paths


def guard() -> None:
    if git('rev-parse', 'HEAD') != EXPECTED_HEAD:
        raise RuntimeError('SOURCE_HEAD_CHANGED_REVIEW_REQUIRED')
    if git('rev-parse', '@{upstream}') != EXPECTED_HEAD:
        raise RuntimeError('UPSTREAM_CHANGED_REVIEW_REQUIRED')
    if git('diff', '--cached', '--name-only'):
        raise RuntimeError('STAGING_MUST_BE_EMPTY')
    reg = load_yaml(REGISTRY)
    if reg.get('variants', {}).get('DUAL_GRIGO_HERASYMENKO', {}).get('runtime_enabled') is not False:
        raise RuntimeError('DUAL_RUNTIME_MUST_REMAIN_DISABLED')
    cursor = load_yaml(CURSOR)
    tasks = [t for t in cursor.get('active_tasks', [])
             if t.get('task_id') == 'GDL-TASK-GREETING-CARD-E2E-001']
    if len(tasks) != 1 or tasks[0].get('current_step') != 'GC-E2E-09':
        raise RuntimeError('EXECUTION_CURSOR_CHANGED')


def prepare_job(base: dict, case: tuple[str, int, int]) -> dict:
    """Create a non-client synthetic job from a validated reference *shape*."""
    label, length, count = case
    if count < 1 or count > len(SENDER_LINES):
        raise ValueError('SYNTHETIC_SENDER_COUNT_INVALID')
    job = deepcopy(base)
    # Adjust only fields which are actually variable; preserve exact physical
    # asset identity and signature config to isolate universal text composition.
    job['job_id'] = 'gdl-synthetic-' + label + '-v01'
    text = synthetic_text(length)
    structured = job['structured_greeting_data']
    structured['greeting_text'] = text
    structured['greeting_text_source'] = 'GDL_SYNTHETIC_TEST_' + label
    exact = job['exact_person_text_asset_bindings']['greeting_text']
    exact['value'] = text
    exact['source_ref'] = 'GDL_SYNTHETIC_TEST_' + label
    job['accepted_visual_assets'][0]['job_id'] = job['job_id']
    job['builder_v1']['sender_text']['lines'] = deepcopy(SENDER_LINES[:count])
    # Additional metadata only in the separate probe report; no assertion
    # that this synthetic input has been approved by a real customer.
    return job


def prepare_bundle(base: dict, cases: tuple[tuple[str, int, int], ...]) -> dict:
    if len(base.get('jobs', [])) != 1:
        raise ValueError('PROOF_REQUIRES_ONE_BASE_JOB')
    if base['jobs'][0]['builder_v1']['sender_text']['signature_variant_id'] != 'HERASYMENKO':
        raise ValueError('PROOF_REQUIRES_HERASYMENKO_BASE')
    if base['jobs'][0]['builder_v1']['front']['family'] != 'STANDARD':
        raise ValueError('PROOF_REQUIRES_STANDARD_BASE')
    if base['jobs'][0]['builder_v1']['inside_image']['mode'] != 'PORTRAIT':
        raise ValueError('PROOF_REQUIRES_PORTRAIT_BASE')
    bundle = deepcopy(base)
    bundle['bundle_id'] = 'gdl-synthetic-variability-batch-v01'
    bundle['synthetic_fixture_only'] = True
    bundle['jobs'] = [prepare_job(base['jobs'][0], case) for case in cases]
    bundle['provenance_manifest']['bundle_sha256'] = ''
    bundle['provenance_manifest']['bundle_sha256'] = compute_bundle_sha256(bundle)
    return bundle


def normalized(value: str) -> str:
    return ' '.join(value.split())


def verify_outputs(output: Path, bundle: dict) -> list[dict]:
    report_file = output / 'builder_run_report.json'
    if not report_file.is_file():
        raise RuntimeError('BATCH_REPORT_MISSING')
    batch_report = json.loads(report_file.read_text(encoding='utf-8'))
    if batch_report.get('job_count') != len(bundle['jobs']):
        raise RuntimeError('BATCH_COUNT_MISMATCH')
    if batch_report.get('previews_rendered_from_final_pdf') is not True:
        raise RuntimeError('BATCH_PREVIEW_ORIGIN_WRONG')
    if batch_report.get('production_ready') is not False:
        raise RuntimeError('BATCH_PRODUCTION_READY_FORBIDDEN')
    pdfs = list((output / 'completed').glob('*.pdf'))
    reports = list((output / 'report').glob('*.json'))
    if len(pdfs) != len(bundle['jobs']) or len(reports) != len(bundle['jobs']):
        raise RuntimeError('BATCH_OUTPUT_COUNTS_INCORRECT')
    by_id = {j['job_id']: j for j in bundle['jobs']}
    seen = set()
    verified = []
    for path in reports:
        item = json.loads(path.read_text(encoding='utf-8'))
        jobid = item.get('job_id')
        if jobid not in by_id or jobid in seen:
            raise RuntimeError('BATCH_REPORT_JOB_ID_INVALID')
        seen.add(jobid)
        expected = by_id[jobid]
        if item.get('physical_page_count') != 4 or item.get('preview_count') != 4:
            raise RuntimeError('BATCH_PAGE_PREVIEW_COUNT_WRONG')
        if item.get('signature_variant') != 'HERASYMENKO':
            raise RuntimeError('BATCH_SIGNATURE_VARIANT_WRONG')
        if item.get('text_fidelity') != {
            'occasion_text': 'PASS', 'greeting_text': 'PASS', 'sender_text': 'PASS',
            'front_font': 'MonotypeCorsiva', 'greeting_font': 'ZapfChanceryC',
        }:
            raise RuntimeError('BATCH_TEXT_FIDELITY_MISSING')
        fn = item.get('pdf_file')
        if not isinstance(fn, str) or Path(fn).name != fn:
            raise RuntimeError('BATCH_PDF_NAME_INVALID')
        pdf = output / 'completed' / fn
        if not pdf.is_file() or sha(pdf) != item.get('pdf_sha256'):
            raise RuntimeError('BATCH_PDF_INTEGRITY_FAILED')
        thumbs = item.get('preview_files')
        if not isinstance(thumbs, list) or len(thumbs) != 4 or len(set(thumbs)) != 4:
            raise RuntimeError('BATCH_PREVIEW_LIST_INVALID')
        with pymupdf.open(pdf) as document:
            if document.page_count != 4:
                raise RuntimeError('BATCH_PDF_PAGE_COUNT_WRONG')
            text = normalized(document[3].get_text('text'))
            greeting = normalized(expected['structured_greeting_data']['greeting_text'])
            if greeting not in text:
                raise RuntimeError('BATCH_GREETING_FIDELITY_FAILED')
            for line in expected['builder_v1']['sender_text']['lines']:
                if normalized(line['text']) not in text:
                    raise RuntimeError('BATCH_SENDER_FIDELITY_FAILED')
            for i, preview in enumerate(thumbs):
                if not isinstance(preview, str) or Path(preview).name != preview:
                    raise RuntimeError('BATCH_PREVIEW_NAME_INVALID')
                preview_path = output / 'preview' / preview
                if not preview_path.is_file():
                    raise RuntimeError('BATCH_PREVIEW_FILE_MISSING')
                pix = document[i].get_pixmap(
                    matrix=pymupdf.Matrix(PREVIEW_DPI / 72, PREVIEW_DPI / 72), alpha=False
                )
                with Image.open(preview_path) as source:
                    raster = source.convert('RGB')
                    if raster.size != (pix.width, pix.height) or raster.tobytes() != pix.samples:
                        raise RuntimeError('BATCH_PREVIEW_PIXEL_REPLAY_FAILED')
        verified.append({
            'case_id': jobid, 'page_count': 4, 'preview_count': 4,
            'greeting_chars': len(expected['structured_greeting_data']['greeting_text']),
            'sender_line_count': len(expected['builder_v1']['sender_text']['lines']),
            'pdf_sha256': sha(pdf), 'text_fidelity': 'PASS', 'preview_replay': 'PASS',
        })
    if seen != set(by_id):
        raise RuntimeError('BATCH_JOB_SET_INCOMPLETE')
    return sorted(verified, key=lambda x: x['case_id'])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('preflight', 'run'), default='preflight')
    parser.add_argument('--binding-config', type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    guard()
    inputs = private_inputs(args.binding_config)
    input_hashes = {name: sha(path) for name, path in inputs.items()}
    base = load_yaml(inputs['bundle'])
    catalog = load_yaml(SIGNATURE_CATALOG)
    orig_errors = validate_builder_ready_bundle_v1(base, signature_catalog=catalog)
    if orig_errors:
        raise RuntimeError('ORIGINAL_BUNDLE_CONTRACT_FAILED')
    bundle = prepare_bundle(base, CASES)
    errors = validate_builder_ready_bundle_v1(bundle, signature_catalog=catalog)
    if errors:
        raise RuntimeError('SYNTHETIC_BUNDLE_CONTRACT_FAILED')
    print('GDL_V1_MULTI_JOB_PDF_PROOF=START', flush=True)
    print('MODE=' + args.mode.upper(), flush=True)
    print('CASE_COUNT=' + str(len(CASES)), flush=True)
    print('BUNDLE_CONTRACT=PASS', flush=True)
    print('SYNTHETIC_DATA_ONLY=true', flush=True)
    if args.mode == 'preflight':
        print('BUILDER_NOT_RUN=true', flush=True)
        print('GDL_V1_MULTI_JOB_PDF_PROOF=PREFLIGHT_PASS', flush=True)
        return 0
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    working = REPORT_ROOT / 'runs' / stamp
    working.mkdir(parents=True, exist_ok=False)
    bundle_path = working / 'synthetic_test_only_bundle_PRIVATE.yaml'
    bundle_path.write_text(yaml.safe_dump(bundle, allow_unicode=True, sort_keys=False), encoding='utf-8')
    outputs = working / 'builder_outputs_PRIVATE'
    print('BUILDER_EXECUTION=STARTED', flush=True)
    result = build_bundle(
        bundle_path=bundle_path,
        resource_manifest_path=inputs['resource_manifest'],
        artifact_manifest_path=inputs['artifact_manifest'],
        signature_catalog_path=SIGNATURE_CATALOG,
        output_dir=outputs,
    )
    if result['bundle_report'].get('job_count') != len(CASES):
        raise RuntimeError('BUILDER_RETURN_JOB_COUNT_MISMATCH')
    verified = verify_outputs(outputs, bundle)
    # Negative control: 1800 chars and eight sender lines must fail closed.
    bad_bundle = prepare_bundle(base, (OVERFLOW,))
    bad_errors = validate_builder_ready_bundle_v1(bad_bundle, signature_catalog=catalog)
    if bad_errors:
        raise RuntimeError('OVERFLOW_CONTROL_BUNDLE_CONTRACT_FAILED')
    bad_yaml = working / 'overflow_test_only_bundle_PRIVATE.yaml'
    bad_yaml.write_text(yaml.safe_dump(bad_bundle, allow_unicode=True, sort_keys=False), encoding='utf-8')
    bad_output = working / 'overflow_rejection_PRIVATE'
    overflow_rejected = False
    try:
        build_bundle(
            bundle_path=bad_yaml,
            resource_manifest_path=inputs['resource_manifest'],
            artifact_manifest_path=inputs['artifact_manifest'],
            signature_catalog_path=SIGNATURE_CATALOG,
            output_dir=bad_output,
        )
    except ValueError as exc:
        overflow_rejected = str(exc).startswith('greeting_text_does_not_fit_canonical_tiers')
    if not overflow_rejected:
        raise RuntimeError('OVERFLOW_NOT_REJECTED_BY_FULL_BUILDER')
    if (bad_output / 'completed').exists() and list((bad_output / 'completed').glob('*.pdf')):
        raise RuntimeError('OVERFLOW_LEFT_COMPLETED_PDF')
    if {n: sha(p) for n, p in inputs.items()} != input_hashes:
        raise RuntimeError('PRIVATE_INPUT_SOURCE_MUTATED')
    guard()
    report = {
        'schema_version': 'gdl_v1_synthetic_multi_job_pdf_proof_v0_1',
        'machine_proof': 'PASS', 'case_count': len(verified),
        'source_head': EXPECTED_HEAD, 'input_file_sha256': input_hashes,
        'bundle_sha256': compute_bundle_sha256(bundle),
        'synthetic_fixture_not_client_accepted': True,
        'reused_reference_portrait_same_across_jobs': True,
        'reused_reference_herasymenko_signature': True,
        'all_output_pdfs_verified': True,
        'all_preview_pixels_replayed': True,
        'overflow_control_rejected': True,
        'overflow_completed_pdf_count': 0,
        'jobs': verified,
        'complete_v1_acceptance': False,
        'production_ready': False,
        'dual_runtime_activated': False,
        'operator_visual_review_required': True,
        'git_mutated': False,
    }
    status = working / 'sanitized_multi_job_proof.json'
    status.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('GDL_V1_MULTI_JOB_PDF_PROOF=PASS', flush=True)
    print('JOB_COUNT=' + str(len(verified)), flush=True)
    print('PDF_COUNT=' + str(len(verified)), flush=True)
    print('PNG_COUNT=' + str(4 * len(verified)), flush=True)
    print('TEXT_FIDELITY=PASS', flush=True)
    print('PREVIEW_PIXEL_REPLAY=PASS', flush=True)
    print('OVERFLOW_REJECTED_BY_FULL_BUILDER=true', flush=True)
    print('SAME_REFERENCE_PORTRAIT_AND_SIGNATURE=true', flush=True)
    print('REPORT=' + str(status.relative_to(ROOT)), flush=True)
    print('VISUAL_REVIEW_REQUIRED=true', flush=True)
    print('DUAL_RUNTIME_DISABLED=true', flush=True)
    print('CUSTOMER_ACCEPTANCE=false', flush=True)
    print('GIT_STAGING_COMMIT_PUSH=false', flush=True)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        # Never dump untrusted/private pathnames, texts, or builder exceptions.
        print('GDL_V1_MULTI_JOB_PDF_PROOF=BLOCKED', flush=True)
        print('ERROR_CLASS=' + type(exc).__name__, flush=True)
        print('ERROR_DETAILS_PRIVATE=true', flush=True)
        raise SystemExit(2)

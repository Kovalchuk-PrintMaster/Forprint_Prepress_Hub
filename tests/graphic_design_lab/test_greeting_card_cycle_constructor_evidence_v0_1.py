"""Constructor-bound internal cycle closeout; synthetic files only, no publication."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pymupdf
import pytest
import yaml

from app.graphic_design_lab.greeting_card_constructor_bundle import compute_bundle_sha256
from scripts.graphic_design_lab.greeting_cards.cycle_closeout_v0_1 import CycleBlocked, compile_closeout


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding='utf-8')


@pytest.fixture
def constructor_cycle(tmp_path):
    root = tmp_path
    run = root / 'tmp/handoff_runtime/results/runs/fixture-review'
    review_path = run / 'review/review_summary.json'
    pdf_rel = 'builder_outputs_PRIVATE/completed/case_a__r001.pdf'
    pdf_path = run / pdf_rel
    pdf_path.parent.mkdir(parents=True)
    with pymupdf.open() as document:
        for _ in range(4):
            document.new_page(width=297, height=420)
        document.save(pdf_path)
    bundle = {'bundle_id': 'synthetic-review-bundle', 'jobs': [{'job_id': 'case_a'}],
              'provenance_manifest': {'bundle_sha256': ''}}
    bundle['provenance_manifest']['bundle_sha256'] = compute_bundle_sha256(bundle)
    bundle_content = yaml.safe_dump(bundle, sort_keys=True).encode()
    bundle_sha = digest(bundle_content)
    ingest_run = root / 'tmp/handoff_runtime/runs/fixture-execution'
    bundle_path = ingest_run / 'input_PRIVATE/accepted_constructor_bundle.yaml'
    bundle_path.parent.mkdir(parents=True)
    bundle_path.write_bytes(bundle_content)
    ingest_path = ingest_run / 'input_PRIVATE/output/report/job_result.json'
    ingest = {
        'schema_version': 'gdl_greeting_card_constructor_ingest_report_v0_1',
        'status': 'ACCEPTED_CONSTRUCTOR_BUNDLE_INGESTED',
        'constructor_input_class': 'ACCEPTED_CONSTRUCTOR_BUNDLE',
        'ready_for_composition': True, 'source_mutation': False,
        'bundle_file_sha256': bundle_sha,
        'bundle_canonical_sha256': bundle['provenance_manifest']['bundle_sha256'],
        'bundle_id': bundle['bundle_id'], 'job_ids': ['case_a'], 'job_count': 1,
        'production_ready': False, 'production_write_enabled': False,
        'git_mutation': False, 'raw_customer_material_interpretation_performed': False,
        'heuristic_role_inference_performed': False, 'normalized_batch_synthesis_performed': False,
    }
    write_json(ingest_path, ingest)
    review = {
        'schema_version': 'gdl_gc09_full_card_review_v0_1',
        'job_count': 1, 'pdf_count': 1, 'png_preview_count': 4,
        'pdf_preview_pixel_replay': 'PASS', 'synthetic_fixture': False,
        'customer_approved': False, 'production_approved': False,
        'dual_runtime_activated_by_this_runner': False,
        'git_or_source_modified_by_this_runner': False,
        'source_fingerprints_sha256': {'bundle': bundle_sha},
        'jobs': [{'job_id': 'case_a', 'page_count': 4, 'preview_count': 4,
                  'preview_pixel_replay': 'PASS', 'pdf': pdf_rel,
                  'pdf_sha256': digest(pdf_path.read_bytes())}],
    }
    write_json(review_path, review)
    private_archive = run / 'full_card_review_PRIVATE.zip'
    with zipfile.ZipFile(private_archive, 'w') as zf:
        zf.write(review_path, 'review/review_summary.json')
        zf.write(pdf_path, pdf_rel)
    handoff_package = root / 'tmp/intake/output/gdl_intake_handoff.zip'
    handoff_package.parent.mkdir(parents=True)
    with zipfile.ZipFile(handoff_package, 'w') as zf:
        zf.writestr('accepted_constructor_bundle.yaml', bundle_content)
    handoff_path = ingest_run / 'handoff_result.json'
    handoff = {
        'schema_version': 'gdl_intake_builder_handoff_v0_1',
        'status': 'PASS_REQUIRES_VISUAL_APPROVAL',
        'source_zip_sha256': digest(handoff_package.read_bytes()),
        'job_count': 1, 'source_zip_unchanged': True,
        'client_review_published': False, 'client_output_subdir': None,
        'customer_approved': False, 'production_approved': False,
        'private_review_dir': str(run.relative_to(root)),
        'private_review_archive': str(private_archive.relative_to(root)),
    }
    write_json(handoff_path, handoff)
    manifest = root / 'tmp/cycle.yaml'
    manifest_data = {'schema_version': 'gdl_gc_review_cycle_manifest_v0_1',
                     'sources': [{'kind': 'STANDARD_REVIEW',
                                  'report': str(review_path.relative_to(root)),
                                  'constructor_ingest_report': str(ingest_path.relative_to(root)),
                                  'handoff_report': str(handoff_path.relative_to(root)),
                                  'handoff_package': str(handoff_package.relative_to(root))}]}
    manifest.write_text(yaml.safe_dump(manifest_data, sort_keys=False))
    return {'root': root, 'manifest': manifest, 'manifest_data': manifest_data,
            'review_path': review_path, 'review': review,
            'ingest_path': ingest_path, 'ingest': ingest,
            'handoff_path': handoff_path, 'handoff': handoff,
            'package': handoff_package, 'private_archive': private_archive}


def test_accepted_real_chain_receipt_is_review_only(constructor_cycle):
    c = constructor_cycle
    result = compile_closeout(c['manifest'], root=c['root'])
    assert result['job_count'] == 1
    assert result['page_count'] == 4
    assert result['formal_constructor_acceptance_for_all_jobs'] is True
    assert result['production_approvals'] == 0
    assert result['client_published'] is False
    assert result['jobs'][0]['constructor_accepted_for_internal_review'] is True
    assert result['jobs'][0]['production_ready'] is False
    assert result['outstanding_gates'] == ['VISUAL_REVIEW_AND_PRINT_PREFLIGHT']
    assert len(result['source_reports'][0]['handoff_package_sha256']) == 64


def test_legacy_report_stays_unverified(constructor_cycle):
    c = constructor_cycle
    data = c['manifest_data']
    data['sources'] = [{'kind': 'STANDARD_REVIEW', 'report': data['sources'][0]['report']}]
    c['manifest'].write_text(yaml.safe_dump(data))
    result = compile_closeout(c['manifest'], root=c['root'])
    assert result['formal_constructor_acceptance_for_all_jobs'] is False
    assert 'constructor_accepted_for_internal_review' not in result['jobs'][0]


def test_constructor_digest_tamper_blocked(constructor_cycle):
    c = constructor_cycle
    c['ingest']['bundle_file_sha256'] = '0' * 64
    write_json(c['ingest_path'], c['ingest'])
    with pytest.raises(CycleBlocked, match='constructor_builder_bundle_digest_mismatch'):
        compile_closeout(c['manifest'], root=c['root'])


def test_constructor_job_identity_tamper_blocked(constructor_cycle):
    c = constructor_cycle
    c['ingest']['job_ids'] = ['different_customer']
    write_json(c['ingest_path'], c['ingest'])
    with pytest.raises(CycleBlocked, match='constructor_job_identity_mismatch'):
        compile_closeout(c['manifest'], root=c['root'])


def test_client_publication_forbidden_for_private_record(constructor_cycle):
    c = constructor_cycle
    c['handoff']['client_review_published'] = True
    write_json(c['handoff_path'], c['handoff'])
    with pytest.raises(CycleBlocked, match='handoff_review_contract_invalid'):
        compile_closeout(c['manifest'], root=c['root'])


def test_handoff_archive_mutation_blocked(constructor_cycle):
    c = constructor_cycle
    with c['package'].open('ab') as f:
        f.write(b'TAMPER')
    with pytest.raises(CycleBlocked, match='handoff_source_archive_digest_mismatch'):
        compile_closeout(c['manifest'], root=c['root'])


def test_replaced_review_zip_summary_blocked(constructor_cycle):
    c = constructor_cycle
    private = c['private_archive']
    with zipfile.ZipFile(private, 'w') as zf:
        zf.writestr('review/review_summary.json', b'{}')
    with pytest.raises(CycleBlocked, match='review_archive_summary_digest_mismatch'):
        compile_closeout(c['manifest'], root=c['root'])


def test_partial_evidence_manifest_blocked(constructor_cycle):
    c = constructor_cycle
    del c['manifest_data']['sources'][0]['handoff_package']
    c['manifest'].write_text(yaml.safe_dump(c['manifest_data']))
    with pytest.raises(CycleBlocked, match='manifest_source_invalid'):
        compile_closeout(c['manifest'], root=c['root'])


def test_invalid_kind_with_constructor_evidence_blocked(constructor_cycle):
    c = constructor_cycle
    c['manifest_data']['sources'][0]['kind'] = 'BRANDED_LAYOUT_PROOF'
    c['manifest'].write_text(yaml.safe_dump(c['manifest_data']))
    with pytest.raises(CycleBlocked, match='constructor_evidence_kind_invalid'):
        compile_closeout(c['manifest'], root=c['root'])


def test_wrong_handoff_run_identity_blocked(constructor_cycle):
    c = constructor_cycle
    c['manifest_data']['sources'][0]['handoff_report'] = c['manifest_data']['sources'][0]['constructor_ingest_report']
    c['manifest'].write_text(yaml.safe_dump(c['manifest_data']))
    with pytest.raises(CycleBlocked, match='constructor_evidence_location_mismatch'):
        compile_closeout(c['manifest'], root=c['root'])

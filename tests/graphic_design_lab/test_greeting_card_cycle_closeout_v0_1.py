from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pymupdf
import pytest
import yaml

from scripts.graphic_design_lab.greeting_cards.cycle_closeout_v0_1 import (
    CycleBlocked, compile_closeout, inside_tmp,
)


def pdf(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with pymupdf.open() as doc:
        for _ in range(4):
            doc.new_page(width=300, height=400)
        doc.save(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def payload(tmp_path):
    root = tmp_path
    (root / 'tmp').mkdir()
    prefix = root / 'tmp' / 'job_runs'
    a, b, c = (prefix / x / 'review' for x in ('a', 'b', 'c'))
    for p in (a, b, c):
        p.mkdir(parents=True)
    a_pdf = 'builder_outputs_PRIVATE/completed/first.pdf'
    a_sha = pdf(a.parent / a_pdf)
    b_pdf = 'builder_outputs_PRIVATE/completed/second.pdf'
    b_sha = pdf(b.parent / b_pdf)
    deg_pdf = 'builder_outputs_PRIVATE/completed/third.pdf'
    deg_sha = pdf(c.parent / deg_pdf)
    data_std = {
        'schema_version': 'gdl_gc09_full_card_review_v0_1',
        'job_count': 2, 'pdf_count': 2, 'png_preview_count': 8,
        'pdf_preview_pixel_replay': 'PASS', 'synthetic_fixture': False,
        'customer_approved': False, 'production_approved': False,
        'dual_runtime_activated_by_this_runner': False, 'git_or_source_modified_by_this_runner': False,
        'jobs': [
            {'job_id': 'case_a', 'page_count': 4, 'preview_count': 4,
             'preview_pixel_replay': 'PASS', 'pdf': a_pdf, 'pdf_sha256': a_sha},
            {'job_id': 'case_b', 'page_count': 4, 'preview_count': 4,
             'preview_pixel_replay': 'PASS', 'pdf': b_pdf, 'pdf_sha256': b_sha},
        ],
    }
    data_creator = {
        'schema_version': 'gdl_creator_blocked_layout_proof_v0_1',
        'job_id': 'case_c', 'creator_result_state': 'BLOCKED_LOW_SOURCE_RESOLUTION',
        'print_quality_state': 'BLOCKED_INSUFFICIENT_NATIVE_RESOLUTION',
        'pdf_preview_pixel_replay': 'PASS', 'pdf_page_count': 4,
        'accepted_constructor_bundle_created': False,
        'production_ready': False, 'customer_published': False, 'customer_approved': False,
        'git_mutated': False, 'smb_modified': False,
        'creator_asset_accepted_for_constructor': False,
        'final_pdf_path': deg_pdf, 'pdf_sha256': deg_sha,
    }
    # Place second STANDARD report with two PDFs in one run (correct layout).
    # Move second PDF into the same run as first.
    correct = a.parent / b_pdf
    correct.parent.mkdir(parents=True, exist_ok=True)
    correct.write_bytes((b.parent / b_pdf).read_bytes())
    (a / 'review_summary.json').write_text(json.dumps(data_std))
    (c / 'review_summary.json').write_text(json.dumps(data_creator))
    manifest = root / 'tmp' / 'cycle.yaml'
    manifest.write_text(yaml.safe_dump({'schema_version': 'gdl_gc_review_cycle_manifest_v0_1',
                        'sources': [{'kind': 'STANDARD_REVIEW', 'report': str(a / 'review_summary.json')},
                                    {'kind': 'CREATOR_LAYOUT_PROOF', 'report': str(c / 'review_summary.json')}]}, sort_keys=False))
    return root, manifest, data_std, data_creator, a, c


def test_generic_closeout_with_three_jobs(tmp_path):
    root, manifest, *_ = payload(tmp_path)
    result = compile_closeout(manifest, root=root)
    assert result['job_count'] == 3
    assert result['page_count'] == 12
    assert result['production_approvals'] == 0
    assert result['formal_constructor_acceptance_for_all_jobs'] is False
    assert all(x['production_ready'] is False for x in result['jobs'])
    assert result['jobs'][-1]['proof_font_pt'] is None
    assert result['jobs'][-1]['proof_font_evidence'] == 'NOT_IN_SOURCE_REPORT'


def test_digest_tampering_blocks(tmp_path):
    root, manifest, std, creator, a, c = payload(tmp_path)
    p = a / 'review_summary.json'
    std['jobs'][0]['pdf_sha256'] = '0' * 64
    p.write_text(json.dumps(std))
    with pytest.raises(CycleBlocked, match='pdf_missing_or_digest_mismatch'):
        compile_closeout(manifest, root=root)


def test_production_authority_blocked(tmp_path):
    root, manifest, std, creator, a, c = payload(tmp_path)
    std['production_approved'] = True
    (a / 'review_summary.json').write_text(json.dumps(std))
    with pytest.raises(CycleBlocked, match='report_authority_mismatch'):
        compile_closeout(manifest, root=root)


def test_duplicate_job_identity_blocked(tmp_path):
    root, manifest, std, creator, a, c = payload(tmp_path)
    creator['job_id'] = 'case_a'
    (c / 'review_summary.json').write_text(json.dumps(creator))
    with pytest.raises(CycleBlocked, match='job_ids_missing_or_duplicate'):
        compile_closeout(manifest, root=root)


def test_unknown_source_kind_blocks(tmp_path):
    root, manifest, *_ = payload(tmp_path)
    raw = yaml.safe_load(manifest.read_text())
    raw['sources'][0]['kind'] = 'PRODUCTION'
    manifest.write_text(yaml.safe_dump(raw))
    with pytest.raises(CycleBlocked, match='manifest_kind_unknown'):
        compile_closeout(manifest, root=root)


def test_external_path_rejected(tmp_path):
    root, manifest, *_ = payload(tmp_path)
    with pytest.raises(CycleBlocked, match='path_outside_repository_tmp'):
        inside_tmp(tmp_path / 'outside.json', root=tmp_path)


def test_source_review_reports_not_mutated(tmp_path):
    root, manifest, _, _, a, c = payload(tmp_path)
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in (manifest, a/'review_summary.json', c/'review_summary.json')}
    compile_closeout(manifest, root=root)
    assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before}


def test_report_path_outside_tmp_is_blocked(tmp_path):
    root, manifest, *_ = payload(tmp_path)
    raw = yaml.safe_load(manifest.read_text())
    raw['sources'][0]['report'] = str(root / 'outside.json')
    manifest.write_text(yaml.safe_dump(raw))
    with pytest.raises(CycleBlocked, match='path_outside_repository_tmp'):
        compile_closeout(manifest, root=root)


def test_branded_proof_with_canonical_safety(tmp_path):
    root, manifest, _, _, _, _ = payload(tmp_path)
    run = root/'tmp'/'job_runs'/'branded'
    report_dir = run/'review'
    report_dir.mkdir(parents=True)
    pdf_digest = pdf(run/'completed'/'case_d__r001__BRANDED_LAYOUT_PROOF_NOT_FOR_PRINT.pdf')
    branded = {
        'schema_version': 'gdl_gc_bas_branded_layout_proof_v0_1',
        'job_id': 'case_d', 'front_variant': 'RECIPIENT_BRANDING_OVERLAY_CANDIDATE',
        'preview_pixel_replay': 'PASS', 'pages_2_to_4_pixel_identity_vs_base': 'PASS',
        'pdf_page_count': 4, 'pdf_sha256': pdf_digest,
        'accepted_constructor_bundle_created': False, 'production_ready': False,
        'client_published': False, 'client_approved': False,
        'git_mutated': False, 'smb_mutated': False,
        'sender_content_authority': 'PROJECT_CANONICAL_ONLY',
        'canonical_signature_exact_private_source_used': True,
        'temporary_font_pt': 17.0,
    }
    report_path = report_dir/'report.json'
    report_path.write_text(json.dumps(branded))
    content = yaml.safe_load(manifest.read_text())
    content['sources'].append({'kind': 'BRANDED_LAYOUT_PROOF', 'report': str(report_path)})
    manifest.write_text(yaml.safe_dump(content))
    record = compile_closeout(manifest, root=root)
    assert record['job_count'] == 4
    assert record['page_count'] == 16
    assert record['jobs'][-1]['proof_font_pt'] == 17.0
    assert 'BRANDED_FRONT_PERMANENT_RENDERER_NOT_VERIFIED' in record['outstanding_gates']

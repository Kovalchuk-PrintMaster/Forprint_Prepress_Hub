"""GC09D: ordinary Builder must remain closed; DUAL proof is private only."""
from __future__ import annotations
from pathlib import Path
import inspect
import pytest
import yaml
from app.graphic_design_lab import greeting_card_builder_renderer as renderer
from app.graphic_design_lab.greeting_card_canonical_sender_v0_1 import _expected_for_variant
from app.graphic_design_lab.greeting_card_signature_registry import load_registry
from scripts.graphic_design_lab.greeting_cards import dual_full_card_candidate_v0_1 as candidate

ROOT=Path(__file__).resolve().parents[2]
DUAL='DUAL_GRIGO_HERASYMENKO'


def _job(v):
    return {'job_id':'private-fixture','branding_selection':{'presence':'ABSENT'},
            'builder_v1':{'front':{'family':'STANDARD'},'inside_image':{'mode':'PORTRAIT'},
                          'sender_text':{'signature_variant_id':v}}}


def test_default_validator_still_rejects_dual():
    with pytest.raises(ValueError,match='signature_variant_not_implemented'):
        renderer._validate_first_slice_job(_job(DUAL))


def test_candidate_validator_allows_only_known_dual():
    renderer._validate_first_slice_job(_job(DUAL),dual_candidate=True)
    with pytest.raises(ValueError,match='signature_variant_not_implemented'):
        renderer._validate_first_slice_job(_job('UNKNOWN'),dual_candidate=True)


def test_canonical_sender_default_disabled_but_candidate_source_known():
    with pytest.raises(ValueError,match='dual_runtime_disabled'):
        _expected_for_variant(DUAL)
    row=_expected_for_variant(DUAL,dual_candidate=True)
    assert len(row['texts'])==len(row['bboxes_pdf_mm'])==6


def test_dual_private_source_required():
    ids=renderer._required_resource_ids_for_bundle({'jobs':[{'builder_v1':{'sender_text':{'signature_variant_id':DUAL}}}]})
    assert 'source.greeting_card.signature.dual_grigo_herasymenko.v1' in ids


def test_registry_still_source_verified_and_disabled():
    p=ROOT/'coordination/graphic_design_lab/directions/greeting_cards/signature_registry_v0_1.yaml'
    entry=load_registry(p)['variants'][DUAL]
    assert entry['state']=='SOURCE_VERIFIED'
    assert entry['runtime_enabled'] is False
    assert entry['renderer_adapter'] is None


def test_source_profile_first_sender_row_is_exact():
    with pytest.raises(ValueError, match='dual_page4_runtime_disabled'):
        renderer._page4_runtime_profile(DUAL)
    profile=renderer._page4_runtime_profile(DUAL, dual_candidate=True)
    assert profile['dual_sender'][DUAL]['start_y_pdf_mm']==213.965


def test_normal_builder_cli_does_not_expose_candidate_switch():
    cli=(ROOT/'scripts/graphic_design_lab/greeting_cards/builder.py').read_text('utf-8')
    assert 'dual_candidate=True' not in cli
    assert '--dual-candidate' not in cli
    code=inspect.getsource(renderer.build_bundle)
    assert "raise ValueError('dual_builder_runtime_disabled')" in code
    assert 'dual_candidate_output_outside_project_tmp' in code


def test_candidate_output_must_stay_under_project_tmp(tmp_path):
    with pytest.raises(ValueError,match='outside_project_tmp'):
        candidate.project_tmp(tmp_path/'elsewhere')
    assert candidate.project_tmp(ROOT/'tmp'/'safe')==(ROOT/'tmp'/'safe').resolve()


def test_wrong_proof_is_rejected(tmp_path):
    f=tmp_path/'fake_report.json'
    f.write_text('{}',encoding='utf-8')
    with pytest.raises(ValueError,match='page4_proof_status_invalid'):
        candidate.checked_page4_proof(f)


def test_no_synthetic_constructor_approval():
    source=inspect.getsource(candidate.preflight)
    assert 'synthetic_bundle_not_accepted_as_real_proof' in source
    assert 'dual_candidate_requires_real_accepted_dual_job' in source


def test_standard_source_report_never_claims_production():
    source=inspect.getsource(renderer._build_one_job)
    assert '"production_ready":' in source
    assert '"dual_candidate_only":' in source
    assert '_checked_output_with_text' in source


def test_dual_provenance_is_not_accepted_by_default():
    with pytest.raises(ValueError, match='signature_report_variant_unsupported'):
        renderer._verified_signature_report_provenance(
            signature_variant=DUAL, grigo_source_verified=False,
            source_validation={}, rendered_validation={},
        )

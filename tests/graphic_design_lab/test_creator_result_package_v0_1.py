from __future__ import annotations

import copy
from pathlib import Path

import yaml

from app.graphic_design_lab.result_package import (
    build_creator_result_package,
    summarize_creator_result_package,
    validate_creator_result_package,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "contracts/graphic_design_lab/creator_result_package_v0_1.yaml"
FIXTURE = ROOT / "tests/fixtures/graphic_design_lab/creator_result_package_sanitized_v0_1.yaml"


def load(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def valid_package():
    return load(FIXTURE)


def errors(package):
    return validate_creator_result_package(package, load(CONTRACT))


def test_sanitized_fixture_is_valid_and_summary_is_human_readable():
    package = valid_package()
    assert errors(package) == []
    summary = summarize_creator_result_package(package)
    assert package["package_id"] in summary
    assert "Customer forwarding: READY" in summary
    assert "Design approval: NOT_RECORDED" in summary
    assert "Production readiness: NOT_READY" in summary


def test_build_is_deterministic_for_same_input():
    package = valid_package()
    raw = copy.deepcopy(package)
    raw["provenance"]["sha256"] = ""
    a = build_creator_result_package(raw)
    b = build_creator_result_package(raw)
    assert a == b
    assert a["provenance"]["sha256"] == package["provenance"]["sha256"]


def test_technically_valid_does_not_imply_reviewable():
    package = valid_package()
    package["readiness"]["internal_review"] = "NOT_REVIEWABLE"
    package["readiness"]["customer_forwarding"] = "BLOCKED"
    assert errors(package) == []


def test_reviewable_does_not_imply_customer_forwardable():
    package = valid_package()
    package["readiness"]["internal_review"] = "REVIEWABLE"
    package["readiness"]["customer_forwarding"] = "BLOCKED"
    assert errors(package) == []


def test_customer_forwardable_does_not_imply_design_approval_or_production_ready():
    package = valid_package()
    assert package["readiness"]["customer_forwarding"] == "READY"
    assert package["readiness"]["design_approval"] == "NOT_RECORDED"
    assert package["readiness"]["production_readiness"] == "NOT_READY"
    assert errors(package) == []


def test_design_approved_does_not_imply_production_ready():
    package = valid_package()
    package["readiness"]["design_approval"] = "APPROVED"
    package["readiness"]["production_readiness"] = "NOT_READY"
    assert errors(package) == []


def test_operator_acceptance_does_not_imply_customer_acceptance():
    package = valid_package()
    package["outcomes"]["operator_acceptance"] = "ACCEPTED"
    package["outcomes"]["customer_acceptance"] = "NOT_RECORDED"
    assert errors(package) == []


def test_customer_acceptance_does_not_imply_explicit_satisfaction():
    package = valid_package()
    package["outcomes"]["customer_acceptance"] = "ACCEPTED"
    package["outcomes"]["customer_explicit_satisfaction"] = "NOT_OBSERVED"
    assert errors(package) == []


def test_partial_and_style_only_results_cannot_be_customer_forward_ready():
    for state in ("PARTIAL", "STYLE_ONLY", "BLOCKED"):
        package = valid_package()
        package["observed_result"]["result_state"] = state
        package["readiness"]["customer_forwarding"] = "READY"
        assert "customer_forwarding_requires_complete_result" in errors(package)


def test_customer_forwarding_requires_content_fidelity_pass():
    package = valid_package()
    package["content_fidelity"]["status"] = "FAIL"
    assert "customer_forwarding_requires_content_fidelity_pass" in errors(package)


def test_artifact_existence_does_not_imply_customer_review_suitability():
    package = valid_package()
    for artifact in package["artifacts"]:
        artifact["suitability"] = ["INTERNAL_REVIEW"]
    assert "customer_forwarding_requires_customer_review_artifact" in errors(package)


def test_heavy_artifact_and_pii_are_forbidden_in_git_fixture():
    package = valid_package()
    package["privacy"]["pii_present_in_package"] = True
    assert "pii_present_in_package_forbidden" in errors(package)

    package = valid_package()
    package["artifacts"][0]["repository_contains_heavy_artifact"] = True
    assert "heavy_artifact_in_repository_forbidden" in errors(package)


def test_authority_boundaries_remain_disabled():
    package = valid_package()
    package["authority"]["provider_execution_performed"] = True
    assert "provider_execution_must_remain_false" in errors(package)

    package = valid_package()
    package["authority"]["gdl_runtime_initialized"] = True
    assert "gdl_runtime_initialization_must_remain_false" in errors(package)

    package = valid_package()
    package["authority"]["production_write_enabled"] = True
    assert "production_write_must_remain_false" in errors(package)

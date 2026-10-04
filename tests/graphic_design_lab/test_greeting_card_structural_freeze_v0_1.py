from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "scripts"
    / "validation"
    / "check_graphic_design_lab_greeting_card_freeze.py"
)
DIR = (
    ROOT
    / "coordination"
    / "graphic_design_lab"
    / "directions"
    / "greeting_cards"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "greeting_card_freeze_under_test",
        SCRIPT,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load(name: str):
    return yaml.safe_load((DIR / name).read_text(encoding="utf-8"))


def test_canonical_freeze_validator_passes():
    module = load_module()
    assert module.validate(ROOT) == []


def test_skeleton_implements_existing_reusable_skeleton_schema():
    skeleton = load("product_skeleton_v0_1.yaml")
    schema = yaml.safe_load(
        (
            ROOT
            / "coordination"
            / "graphic_design_lab"
            / "client_workflows"
            / "reusable_skeleton_schema_v0_1.yaml"
        ).read_text(encoding="utf-8")
    )
    assert set(schema["required"]).issubset(skeleton)
    assert skeleton["lifecycle"] == "PROMISING"


def test_human_authoring_noise_is_normalized_not_reproduced():
    policy = load("human_authoring_noise_policy_v0_1.yaml")
    assert (
        policy["variant_creation"]["small_coordinate_drift_creates_variant"]
        is False
    )
    assert (
        policy["variant_creation"]["small_font_size_drift_creates_variant"]
        is False
    )
    assert (
        policy["authoring_artifact_policy"][
            "raw_pdf_object_presence_is_semantic_authority"
        ]
        is False
    )
    assert (
        policy["normalization_tolerances"]["purpose"]
        == "CLUSTERING_AND_CANONICALIZATION_ONLY_NOT_FINAL_RENDER_TOLERANCE"
    )


def test_three_front_semantic_families_replace_five_exact_variants():
    skeleton = load("product_skeleton_v0_1.yaml")
    families = skeleton["variant_model"]["front"]["semantic_families"]
    assert {item["id"] for item in families} == {
        "STANDARD",
        "RECIPIENT_BRANDING_OVERLAY",
        "BILINGUAL_OCCASION",
    }
    overlay = next(
        item
        for item in families
        if item["id"] == "RECIPIENT_BRANDING_OVERLAY"
    )
    assert overlay["implementation_subtypes"] == ["TEXT", "RASTER"]


def test_structural_freeze_is_not_customer_design_lock():
    freeze = load("structural_design_freeze_v0_1.yaml")
    skeleton = load("product_skeleton_v0_1.yaml")
    assert freeze["established"] is True
    assert (
        freeze["separate_from_workflow_design_lock"][
            "workflow_design_lock_state"
        ]
        == "NOT_ACTIVATED_BY_THIS_FREEZE"
    )
    assert skeleton["authority"]["workflow_design_lock_activated"] is False
    assert skeleton["authority"]["customer_approval_implied"] is False


def test_execution_remains_blocked_until_exact_fonts_and_later_gates():
    freeze = load("structural_design_freeze_v0_1.yaml")
    readiness = freeze["execution_readiness"]
    assert readiness["exact_fonts_available"] is False
    assert readiness["text_regeneration_ready"] is False
    assert readiness["provider_selected"] is False
    assert readiness["runtime_initialized"] is False
    assert readiness["production_write_enabled"] is False
    assert readiness["production_ready"] is False


def test_client_profile_is_sanitized_and_inherits_reusable_skeleton():
    profile = load("client_execution_profile_v0_1.yaml")
    assert profile["inherits_skeletons"] == [
        "greeting_card_a3_single_fold_v0_1"
    ]
    assert profile["privacy"]["pii_allowed_in_git"] is False
    assert profile["privacy"]["real_workspace_path_allowed_in_git"] is False
    assert profile["privacy"]["heavy_or_raw_customer_assets_allowed_in_git"] is False

#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "coordination/graphic_design_lab/directions/greeting_cards"
CW = ROOT / "coordination/graphic_design_lab/client_workflows"

PATHS = {
    "skeleton": DIR / "product_skeleton_v0_1.yaml",
    "profile": DIR / "client_execution_profile_v0_1.yaml",
    "noise": DIR / "human_authoring_noise_policy_v0_1.yaml",
    "freeze": DIR / "structural_design_freeze_v0_1.yaml",
    "direction": DIR / "direction_v0_1.yaml",
    "direction_index": DIR / "index.yaml",
    "skeleton_schema": CW / "reusable_skeleton_schema_v0_1.yaml",
    "profile_schema": CW / "client_execution_profile_schema_v0_1.yaml",
    "client_workflow_index": CW / "index.yaml",
    "gdl_index": ROOT / "coordination/graphic_design_lab/index.yaml",
    "makefile": ROOT / "Makefile",
}


def load(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []

    for name, path in PATHS.items():
        candidate = root / path.relative_to(ROOT)
        if not candidate.is_file():
            errors.append(f"missing:{name}:{candidate.relative_to(root)}")

    if errors:
        return errors

    skeleton = load(root / PATHS["skeleton"].relative_to(ROOT))
    profile = load(root / PATHS["profile"].relative_to(ROOT))
    noise = load(root / PATHS["noise"].relative_to(ROOT))
    freeze = load(root / PATHS["freeze"].relative_to(ROOT))
    direction = load(root / PATHS["direction"].relative_to(ROOT))
    direction_index = load(root / PATHS["direction_index"].relative_to(ROOT))
    skeleton_schema = load(root / PATHS["skeleton_schema"].relative_to(ROOT))
    profile_schema = load(root / PATHS["profile_schema"].relative_to(ROOT))
    client_workflow_index = load(
        root / PATHS["client_workflow_index"].relative_to(ROOT)
    )
    gdl_index = load(root / PATHS["gdl_index"].relative_to(ROOT))
    makefile = (
        root / PATHS["makefile"].relative_to(ROOT)
    ).read_text(encoding="utf-8")

    for key in skeleton_schema["required"]:
        if key not in skeleton:
            errors.append(f"skeleton:missing_required:{key}")

    for key in profile_schema["required"]:
        if key not in profile:
            errors.append(f"profile:missing_required:{key}")

    if skeleton.get("skeleton_id") != "greeting_card_a3_single_fold_v0_1":
        errors.append("skeleton:id_invalid")
    if skeleton.get("lifecycle") not in skeleton_schema["lifecycle"]:
        errors.append("skeleton:lifecycle_invalid")
    if skeleton.get("lifecycle") != "PROMISING":
        errors.append("skeleton:lifecycle_should_remain_promising_before_first_render")

    geometry = skeleton.get("geometry_model", {})
    if geometry.get("media_size") != [214.0, 301.0]:
        errors.append("skeleton:media_size_invalid")
    if geometry.get("trim_size") != [210.0, 297.0]:
        errors.append("skeleton:trim_size_invalid")
    if geometry.get("bleed_each_side") != 2.0:
        errors.append("skeleton:bleed_invalid")
    if geometry.get("physical_to_logical_page_map") != {
        1: "PAGE_1_FRONT",
        2: "PAGE_4_BACK",
        3: "PAGE_2_INSIDE_IMAGE",
        4: "PAGE_3_INSIDE_GREETING",
    }:
        errors.append("skeleton:page_map_invalid")

    families = {
        item.get("id")
        for item in skeleton.get("variant_model", {})
        .get("front", {})
        .get("semantic_families", [])
    }
    if families != {
        "STANDARD",
        "RECIPIENT_BRANDING_OVERLAY",
        "BILINGUAL_OCCASION",
    }:
        errors.append("skeleton:front_semantic_families_invalid")

    tiers = (
        skeleton.get("variant_model", {})
        .get("greeting_body", {})
        .get("canonical_font_size_tiers_pt")
    )
    if tiers != [22.5, 20.0, 17.0]:
        errors.append("skeleton:typefit_tiers_invalid")

    if skeleton.get("authority", {}).get("structural_design_frozen") is not True:
        errors.append("skeleton:structural_freeze_missing")
    for key in (
        "workflow_design_lock_activated",
        "customer_approval_implied",
        "production_write_authorized",
        "provider_execution_authorized",
        "blueprint_mutation_authorized",
    ):
        if skeleton.get("authority", {}).get(key) is not False:
            errors.append(f"skeleton:authority_boundary_invalid:{key}")

    if profile.get("client_id") != "recurring_greeting_card_client_001":
        errors.append("profile:client_id_invalid")
    if profile.get("inherits_skeletons") != [
        "greeting_card_a3_single_fold_v0_1"
    ]:
        errors.append("profile:skeleton_inheritance_invalid")
    if profile.get("privacy", {}).get("pii_allowed_in_git") is not False:
        errors.append("profile:pii_boundary_invalid")
    if profile.get("privacy", {}).get("real_workspace_path_allowed_in_git") is not False:
        errors.append("profile:workspace_path_boundary_invalid")

    profile_text = (
        root / PATHS["profile"].relative_to(ROOT)
    ).read_text(encoding="utf-8")
    forbidden_patterns = (
        r"\+?380[\s\d()-]{7,}",
        r"/srv/smb/",
        r"@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    )
    for pattern in forbidden_patterns:
        if re.search(pattern, profile_text, re.I):
            errors.append(f"profile:possible_private_data:{pattern}")

    if (
        noise.get("normalization_tolerances", {}).get("purpose")
        != "CLUSTERING_AND_CANONICALIZATION_ONLY_NOT_FINAL_RENDER_TOLERANCE"
    ):
        errors.append("noise:tolerance_purpose_missing")
    if noise.get("variant_creation", {}).get(
        "small_coordinate_drift_creates_variant"
    ) is not False:
        errors.append("noise:small_coordinate_drift_must_not_create_variant")
    if noise.get("variant_creation", {}).get(
        "small_font_size_drift_creates_variant"
    ) is not False:
        errors.append("noise:small_font_drift_must_not_create_variant")
    if noise.get("authoring_artifact_policy", {}).get(
        "raw_pdf_object_presence_is_semantic_authority"
    ) is not False:
        errors.append("noise:raw_pdf_object_must_not_be_semantic_authority")

    if freeze.get("freeze_type") != "PRODUCT_SKELETON_STRUCTURAL_FREEZE":
        errors.append("freeze:type_invalid")
    if freeze.get("established") is not True:
        errors.append("freeze:not_established")
    if freeze.get("separate_from_workflow_design_lock", {}).get(
        "workflow_design_lock_state"
    ) != "NOT_ACTIVATED_BY_THIS_FREEZE":
        errors.append("freeze:workflow_design_lock_boundary_invalid")
    if freeze.get("empirical_basis", {}).get(
        "page4_duplicate_portrait_objects_with_visible_contribution"
    ) != 0:
        errors.append("freeze:hidden_object_evidence_invalid")

    readiness = freeze.get("execution_readiness", {})
    for key in (
        "exact_fonts_available",
        "text_regeneration_ready",
        "provider_selected",
        "runtime_initialized",
        "production_write_enabled",
        "production_ready",
    ):
        if readiness.get(key) is not False:
            errors.append(f"freeze:execution_boundary_invalid:{key}")

    if direction.get("status") != "STRUCTURAL_MODEL_FROZEN_EXECUTION_NOT_READY":
        errors.append("direction:status_not_reconciled")
    if direction.get("canonical_structural_model") != "product_skeleton_v0_1.yaml":
        errors.append("direction:skeleton_ref_missing")
    if direction_index.get("status") != "STRUCTURAL_MODEL_FROZEN_EXECUTION_NOT_READY":
        errors.append("direction_index:status_not_reconciled")

    docs = set(direction_index.get("documents", []))
    for required in (
        "product_skeleton_v0_1.yaml",
        "client_execution_profile_v0_1.yaml",
        "human_authoring_noise_policy_v0_1.yaml",
        "structural_design_freeze_v0_1.yaml",
    ):
        if required not in docs:
            errors.append(f"direction_index:missing_document:{required}")

    instances = client_workflow_index.get("active_instances", [])
    greeting = [
        item for item in instances
        if item.get("direction_id") == "greeting_cards"
    ]
    if len(greeting) != 1:
        errors.append("client_workflow_index:greeting_instance_missing_or_duplicate")

    if "greeting_cards" not in gdl_index.get("active_directions", []):
        errors.append("gdl_index:greeting_cards_not_active")

    if "gdl-greeting-card-freeze-check:" not in makefile:
        errors.append("makefile:freeze_target_missing")

    governance_line = next(
        (
            line
            for line in makefile.splitlines()
            if line.startswith("governance-check:")
        ),
        "",
    )
    if "gdl-greeting-card-freeze-check" not in governance_line:
        errors.append("makefile:governance_missing_freeze_gate")

    return errors


if __name__ == "__main__":
    errors = validate(ROOT)
    if errors:
        print("PREPRESS_HUB_GDL_GREETING_CARD_FREEZE_CHECK=FAIL")
        for error in errors:
            print(f"ERROR={error}")
        raise SystemExit(1)

    print("PREPRESS_HUB_GDL_GREETING_CARD_FREEZE_CHECK=PASS")
    print("SKELETON=greeting_card_a3_single_fold_v0_1")
    print("LIFECYCLE=PROMISING")
    print("STRUCTURAL_DESIGN_FREEZE=ESTABLISHED")
    print("FRONT_SEMANTIC_FAMILY_COUNT=3")
    print("HUMAN_AUTHORING_NOISE_NORMALIZED=true")
    print("WORKFLOW_DESIGN_LOCK_ACTIVATED=false")
    print("TEXT_REGENERATION_READY=false")
    print("PRODUCTION_READY=false")
    print("PROVIDER_SELECTED=false")
    print("GDL_RUNTIME_INITIALIZED=false")
    print("BLUEPRINT_MUTATED=false")

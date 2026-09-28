#!/usr/bin/env python3
from pathlib import Path
import sys
import yaml

ROOT = Path(__file__).resolve().parents[2]
required = [
    "coordination/roadmaps/graphic_design_lab/roadmap_v0_1.yaml",
    "coordination/roadmaps/graphic_design_lab/roadmap_v0_1.md",
    "docs/architecture/graphic_design_lab.md",
    "config/graphic_design_lab.yaml",
    "coordination/roadmaps/graphic_design_lab/capability_catalog_v0_1.yaml",
    "coordination/roadmaps/graphic_design_lab/capability_catalog_v0_1.md",
    "coordination/roadmaps/graphic_design_lab/planning_evidence/index.yaml",
    "coordination/roadmaps/graphic_design_lab/planning_evidence/2026-09-28_guided_intake_creator_handoff_direction.md",
]
errors = [f"missing:{rel}" for rel in required if not (ROOT / rel).is_file()]

if not errors:
    roadmap = yaml.safe_load((ROOT / required[0]).read_text(encoding="utf-8"))
    config = yaml.safe_load((ROOT / "config/graphic_design_lab.yaml").read_text(encoding="utf-8"))
    status = yaml.safe_load((ROOT / "coordination/status/current_status.yaml").read_text(encoding="utf-8"))
    catalog = yaml.safe_load((ROOT / "coordination/roadmaps/graphic_design_lab/capability_catalog_v0_1.yaml").read_text(encoding="utf-8"))
    evidence_index = yaml.safe_load((ROOT / "coordination/roadmaps/graphic_design_lab/planning_evidence/index.yaml").read_text(encoding="utf-8"))

    if roadmap.get("capability_id") != "graphic_design_lab":
        errors.append("wrong_capability_id")
    if roadmap.get("authority", {}).get("roadmap_is_execution_authority") is not False:
        errors.append("roadmap_must_not_grant_execution")
    if roadmap.get("current_state", {}).get("runtime") != "PLANNED_NOT_INITIALIZED":
        errors.append("roadmap_runtime_state_must_remain_uninitialized")
    if config.get("status") != "PLANNING_ONLY_RUNTIME_NOT_INITIALIZED":
        errors.append("config_must_be_planning_only")

    for role, value in config.get("storage", {}).items():
        p = Path(str(value))
        if p.is_absolute() or ".." in p.parts:
            errors.append(f"unsafe_storage_path:{role}")

    for provider, spec in config.get("providers", {}).items():
        if spec.get("selected") != "UNRESOLVED":
            errors.append(f"provider_selected_too_early:{provider}")

    if status.get("graphic_design_lab") != "PLANNED_NOT_INITIALIZED":
        errors.append("module_status_must_remain_uninitialized")
    if status.get("graphic_design_lab_runtime_initialized") is not False:
        errors.append("runtime_initialized_too_early")
    if (ROOT / "graphic_design_lab").exists():
        errors.append("root_graphic_design_lab_directory_forbidden")

    if catalog.get("document_type") != "GDL_CAPABILITY_CATALOG":
        errors.append("wrong_capability_catalog_type")

    catalog_authority = catalog.get("authority", {})
    for key in (
        "grants_execution_authority",
        "grants_provider_selection",
        "grants_runtime_initialization",
        "grants_production_write",
    ):
        if catalog_authority.get(key) is not False:
            errors.append(f"capability_catalog_authority_must_be_false:{key}")

    entries = catalog.get("entries", [])
    entry_ids = [entry.get("id") for entry in entries]
    if not entry_ids or len(entry_ids) != len(set(entry_ids)):
        errors.append("capability_catalog_ids_missing_or_duplicate")

    near_ids = {item.get("id") for item in roadmap.get("near_term_practical", [])}
    farther_ids = {item.get("id") for item in roadmap.get("farther_practical", [])}
    all_roadmap_ids = near_ids | farther_ids | {
        item.get("id")
        for item in roadmap.get("strategic_reevaluate_before_promotion", [])
        if isinstance(item, dict)
    }

    for item_id in ("GDL-F06", "GDL-F07"):
        if item_id not in near_ids:
            errors.append(f"near_term_promotion_missing:{item_id}")
        if item_id in farther_ids:
            errors.append(f"promoted_item_still_duplicated_in_farther:{item_id}")

    for entry in entries:
        for ref in entry.get("related_roadmap", []):
            if ref not in all_roadmap_ids:
                errors.append(
                    f"catalog_unknown_roadmap_ref:{entry.get('id')}:{ref}"
                )

    if evidence_index.get("authority") != "LOCAL_PLANNING_EVIDENCE_NOT_HUMAN_INTENT_AUTHORITY":
        errors.append("planning_evidence_authority_invalid")

    if status.get("current_focus") != "gdl_guided_design_intake_and_creator_handoff_planning":
        errors.append("gdl_current_focus_not_reconciled")

    if status.get("preview_renderer_candidate_state") != "EXPERIMENTALLY_VERIFIED_NOT_SELECTED":
        errors.append("preview_candidate_state_not_reconciled")

    svg_renderer = config.get("providers", {}).get("svg_renderer", {})
    if "librsvg_rsvg_convert" not in svg_renderer.get("candidates", []):
        errors.append("verified_preview_candidate_missing_from_config")

if errors:
    print("PREPRESS_HUB_GDL_PLANNING_CHECK=FAIL")
    for error in errors:
        print(f"ERROR={error}")
    sys.exit(1)

print("PREPRESS_HUB_GDL_PLANNING_CHECK=PASS")
print("CAPABILITY=graphic_design_lab")
print("RUNTIME=PLANNED_NOT_INITIALIZED")
print("CONFIG_MODE=PLANNING_ONLY")
print("PROVIDER_SELECTION=UNRESOLVED")
print("ROOT_GRAPHIC_DESIGN_LAB_PRESENT=false")
print("CAPABILITY_CATALOG=PASS")
print("LOCAL_PLANNING_EVIDENCE=PASS")
print("INTAKE_HANDOFF_HORIZON=NEAR_TERM_PLANNED_NOT_ACTIVATED")
print("PREVIEW_CANDIDATE=EXPERIMENTALLY_VERIFIED_NOT_SELECTED")

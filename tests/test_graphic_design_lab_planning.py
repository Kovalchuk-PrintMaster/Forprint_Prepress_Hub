from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]

def load_yaml(rel):
    return yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))

def test_planning_surfaces_exist():
    for rel in (
        "coordination/roadmaps/graphic_design_lab/roadmap_v0_1.yaml",
        "coordination/roadmaps/graphic_design_lab/roadmap_v0_1.md",
        "docs/architecture/graphic_design_lab.md",
        "config/graphic_design_lab.yaml",
        "scripts/validation/check_graphic_design_lab_planning.py",
        "coordination/roadmaps/graphic_design_lab/capability_catalog_v0_1.yaml",
        "coordination/roadmaps/graphic_design_lab/capability_catalog_v0_1.md",
        "coordination/roadmaps/graphic_design_lab/planning_evidence/index.yaml",
        "coordination/roadmaps/graphic_design_lab/planning_evidence/2026-09-28_guided_intake_creator_handoff_direction.md",
    ):
        assert (ROOT / rel).is_file(), rel

def test_roadmap_is_planning_not_execution():
    roadmap = load_yaml("coordination/roadmaps/graphic_design_lab/roadmap_v0_1.yaml")
    assert roadmap["authority"]["roadmap_is_execution_authority"] is False
    assert roadmap["current_state"]["runtime"] == "PLANNED_NOT_INITIALIZED"

def test_config_uses_relative_roles_and_no_provider_is_selected():
    config = load_yaml("config/graphic_design_lab.yaml")
    for value in config["storage"].values():
        p = Path(value)
        assert not p.is_absolute()
        assert ".." not in p.parts
    for spec in config["providers"].values():
        assert spec["selected"] == "UNRESOLVED"

def test_abram_is_planning_pilot_only():
    config = load_yaml("config/graphic_design_lab.yaml")
    assert config["pilot"]["id"] == "abram_diary_phase1"
    assert config["pilot"]["runtime_enabled"] is False
    assert config["pilot"]["full_rollout_before_phase1_approval"] is False

def test_root_runtime_boundary_remains_uninitialized():
    status = load_yaml("coordination/status/current_status.yaml")
    assert status["graphic_design_lab"] == "PLANNED_NOT_INITIALIZED"
    assert status["graphic_design_lab_runtime_initialized"] is False
    assert not (ROOT / "graphic_design_lab").exists()


def test_capability_catalog_is_reference_not_execution_authority():
    catalog = load_yaml(
        "coordination/roadmaps/graphic_design_lab/capability_catalog_v0_1.yaml"
    )
    assert catalog["document_type"] == "GDL_CAPABILITY_CATALOG"
    assert catalog["status"] == "PLANNING_REFERENCE"
    assert all(value is False for value in catalog["authority"].values())

    ids = [entry["id"] for entry in catalog["entries"]]
    assert len(ids) == len(set(ids))
    assert "guided_design_intake" in ids
    assert "creator_handoff_package" in ids
    assert "semantic_raster_to_vector_reconstruction" in ids

    preview = next(
        entry for entry in catalog["entries"]
        if entry["id"] == "svg_to_png_review_preview"
    )
    assert preview["state"] == "EXPERIMENTALLY_VERIFIED"
    assert preview["canonical_provider_selected"] is False
    assert preview["print_output"] is False


def test_intake_and_design_package_are_promoted_without_duplicate_ids():
    roadmap = load_yaml(
        "coordination/roadmaps/graphic_design_lab/roadmap_v0_1.yaml"
    )
    near_ids = [item["id"] for item in roadmap["near_term_practical"]]
    farther_ids = [item["id"] for item in roadmap["farther_practical"]]

    assert "GDL-F07" in near_ids
    assert "GDL-F06" in near_ids
    assert "GDL-F07" not in farther_ids
    assert "GDL-F06" not in farther_ids
    assert len(near_ids + farther_ids) == len(set(near_ids + farther_ids))


def test_local_planning_evidence_does_not_claim_human_intent_authority():
    index = load_yaml(
        "coordination/roadmaps/graphic_design_lab/planning_evidence/index.yaml"
    )
    assert (
        index["authority"]
        == "LOCAL_PLANNING_EVIDENCE_NOT_HUMAN_INTENT_AUTHORITY"
    )
    assert index["entries"][0]["id"] == "GDL-PE-20260928-INTAKE-HANDOFF"
    assert index["entries"][0]["blueprint_human_intent_sync_pending"] is True


def test_status_records_preview_experiment_without_selecting_provider():
    status = load_yaml("coordination/status/current_status.yaml")
    config = load_yaml("config/graphic_design_lab.yaml")

    assert (
        status["current_focus"]
        == "gdl_creator_result_package_foundation_accepted"
    )
    assert (
        status["source_prompt_id"]
        == "prepress_gdl_creator_result_package_foundation_v0_1"
    )
    assert status["prompt_intake"]["status"] == "completed_in_module"
    assert "active_prompt_id" not in status["prompt_intake"]
    assert status["prompt_intake"]["blueprint_access"] == "READ_ONLY_STRICT"
    assert (
        status["preview_renderer_candidate_state"]
        == "EXPERIMENTALLY_VERIFIED_NOT_SELECTED"
    )
    assert status["preview_renderer_candidate"] == "librsvg_rsvg_convert"
    assert "librsvg_rsvg_convert" in config["providers"]["svg_renderer"]["candidates"]
    assert config["providers"]["svg_renderer"]["selected"] == "UNRESOLVED"
    assert status["graphic_design_lab_runtime_initialized"] is False
    assert status["production_write_enabled"] is False


def test_verified_intake_handoff_partial_state():
    roadmap = load_yaml(
        "coordination/roadmaps/graphic_design_lab/roadmap_v0_1.yaml"
    )
    catalog = load_yaml(
        "coordination/roadmaps/graphic_design_lab/capability_catalog_v0_1.yaml"
    )

    near = {item["id"]: item for item in roadmap["near_term_practical"]}

    for item_id in ("GDL-N07", "GDL-F07", "GDL-F06"):
        assert near[item_id]["state"] == "PARTIAL_IMPLEMENTED_VERIFIED"

    pilot = roadmap["intake_handoff_pilot_sequence"]
    assert pilot["status"] == "PARTIAL_IMPLEMENTED_VERIFIED"
    assert pilot["first"]["state"] == "FOUNDATION_IMPLEMENTED_VERIFIED"
    assert (
        pilot["second"]["state"]
        == "DEFERRED_NOT_AUTHORIZED_IN_THIS_CONTOUR"
    )

    entries = {entry["id"]: entry for entry in catalog["entries"]}

    for capability_id in (
        "product_playbook",
        "guided_design_intake",
        "creator_handoff_package",
    ):
        assert entries[capability_id]["state"] == "PARTIAL_IMPLEMENTED_VERIFIED"

    assert entries["creator_result_package"]["state"] == "IMPLEMENTED_VERIFIED"


def test_human_readable_views_match_verified_intake_state():
    status = load_yaml("coordination/status/current_status.yaml")

    assert (
        status["next_expected_focus"]
        == "separately_authorized_next_gdl_contour"
    )

    latest = status["latest_gdl_intake_handoff_foundation"]
    assert latest["status"] == "PARTIAL_IMPLEMENTED_VERIFIED"
    assert latest["next_contour_activated"] is False
    assert latest["provider_selected"] is False
    assert latest["provider_executed"] is False
    assert latest["runtime_initialized"] is False
    assert latest["production_write_enabled"] is False
    assert latest["blueprint_mutated"] is False

    markers = {
        "coordination/roadmaps/graphic_design_lab/roadmap_v0_1.md":
            "## Verified Guided Intake / Creator Handoff foundation",
        "coordination/roadmaps/graphic_design_lab/capability_catalog_v0_1.md":
            "## Verified intake/handoff capability slice",
        "coordination/status/current_status.md":
            "## Verified GDL intake/handoff foundation",
    }

    for rel, marker in markers.items():
        assert marker in (ROOT / rel).read_text(encoding="utf-8")

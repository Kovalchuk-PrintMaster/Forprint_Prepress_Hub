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

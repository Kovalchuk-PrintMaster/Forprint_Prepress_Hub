from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_required_operator_surfaces_exist():
    for path in (
        ".gitignore",
        "README.md",
        "AGENTS.md",
        "Makefile",
        "pyproject.toml",
        "coordination/module/manifest.yaml",
        "coordination/status/current_status.yaml",
    ):
        assert (ROOT / path).is_file(), path


def test_bootstrap_state_is_safe():
    status = yaml.safe_load(
        (ROOT / "coordination/status/current_status.yaml").read_text(encoding="utf-8")
    )
    assert status["canonical_runtime_ready"] is False
    assert status["production_write_enabled"] is False
    assert status["graphic_design_lab"] == "PLANNED_NOT_INITIALIZED"


def test_graphic_design_lab_is_not_initialized():
    assert not (ROOT / "graphic_design_lab").exists()


def test_operator_workspace_is_ignored():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "/tmp/" in ignore
    assert "/tmp.py" in ignore
    assert "/preview" in ignore

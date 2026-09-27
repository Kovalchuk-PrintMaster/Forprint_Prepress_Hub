from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_clean_root_manifest_policy():
    assert (ROOT / "coordination/module/manifest.yaml").is_file()
    assert not (ROOT / "forprint_module_manifest.yaml").exists()

def test_continuity_bootstrap_surfaces_exist():
    required = [
        "coordination/bootstrap/START_HERE.md",
        "coordination/bootstrap/module_bootstrap_manifest.yaml",
        "coordination/blueprint_source.yaml",
        "coordination/status/current_status.md",
        "coordination/prompts/index.yaml",
        "coordination/reports/index.yaml",
        "scripts/coordination/module_assistant_context.py",
    ]
    for rel in required:
        assert (ROOT / rel).is_file(), rel

def test_helper_uses_canonical_manifest_and_zero_authority():
    text = (ROOT / "scripts/coordination/module_assistant_context.py").read_text()
    assert '"coordination/module/manifest.yaml"' in text
    assert '"forprint_module_manifest.yaml"' not in text
    assert '"execution": False' in text
    assert '"acceptance": False' in text
    assert '"release": False' in text
    assert '"blueprint_write": False' in text

def test_makefile_exposes_continuity_operator_map():
    text = (ROOT / "Makefile").read_text()
    for target in (
        "assistant-handoff-check:",
        "assistant-pack:",
        "assistant-context-pack:",
    ):
        assert target in text
    assert "MODULE_ONBOARD" in text
    assert "MODULE_CONTEXT" in text

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

def test_generated_assistant_packages_embed_strict_blueprint_read_only_policy(
    tmp_path, monkeypatch
):
    import importlib.util
    import json
    import sys

    script_path = ROOT / "scripts/coordination/module_assistant_context.py"
    spec = importlib.util.spec_from_file_location(
        "prepress_module_assistant_context_tested",
        script_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    assert (
        module.SYSTEM_BLUEPRINT_POLICY_MARKER
        == "SYSTEM_BLUEPRINT_ACCESS_FROM_PREPRESS=READ_ONLY_STRICT"
    )

    module_root = tmp_path / "module"
    blueprint_root = tmp_path / "blueprint"
    module_root.mkdir()
    blueprint_root.mkdir()

    agents = module_root / "AGENTS.md"
    agents.write_text(
        "System Blueprint is read-only from Prepress.\n",
        encoding="utf-8",
    )

    fake_check = {
        "status": "PASS",
        "module": {
            "head": "a" * 40,
            "branch": "main",
        },
        "blueprint": {
            "head": "b" * 40,
            "branch": "audit/test",
        },
        "errors": [],
        "warnings": [],
    }

    monkeypatch.setattr(module, "verify", lambda **kwargs: fake_check)
    monkeypatch.setattr(
        module,
        "local_candidates",
        lambda module_root, package_type, topics: [agents],
    )
    monkeypatch.setattr(module, "blueprint_ref_catalog", lambda blueprint_root: [])

    for package_type in ("MODULE_ONBOARD", "MODULE_CONTEXT"):
        result = module.build_pack(
            module_root=module_root,
            blueprint_root=blueprint_root,
            module_id="forprint_prepress_hub",
            registration_state="registered",
            package_type=package_type,
            scope="bootstrap",
            topics=["graphic_design_lab"],
            max_file_bytes=256 * 1024,
            max_total_bytes=4 * 1024 * 1024,
        )

        package_dir = module_root / result["package_dir"]
        manifest = json.loads(
            (package_dir / "manifest.json").read_text(encoding="utf-8")
        )
        readme = (package_dir / "README.md").read_text(encoding="utf-8")

        assert (
            manifest["policy_markers"]["system_blueprint_access_from_prepress"]
            == "READ_ONLY_STRICT"
        )
        assert (
            "SYSTEM_BLUEPRINT_ACCESS_FROM_PREPRESS=READ_ONLY_STRICT"
            in readme
        )
        normalized_readme = " ".join(readme.split())
        assert "must not create, edit, stage, commit, push, apply, release" in normalized_readme
        assert "Blueprint-side processing and confirmation" in normalized_readme

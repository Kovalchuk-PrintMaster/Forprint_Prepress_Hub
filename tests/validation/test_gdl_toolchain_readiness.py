from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/validation/check_gdl_toolchain_readiness.py"
CONTRACT = (
    ROOT
    / "coordination"
    / "graphic_design_lab"
    / "execution"
    / "gdl_toolchain_contract_v0_1.yaml"
)
CONFIG = ROOT / "config/graphic_design_lab.yaml"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "gdl_toolchain_readiness_under_test",
        SCRIPT,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_portable_contract_validation_passes():
    module = load_module()
    assert module.structural_errors(ROOT) == []


def test_pdf_first_component_strategy_and_authority_boundaries():
    contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    assert contract["document_strategy"]["mode"] == "PDF_FIRST_COMPONENT_BASED"
    assert contract["document_strategy"]["working_document_container"] == "pdf"
    assert contract["document_strategy"]["illustrator_private_data"] == {
        "allowed_as_compatibility_layer": True,
        "machine_source_of_truth": False,
    }
    assert contract["authority"] == {
        "selects_provider": False,
        "initializes_runtime": False,
        "enables_production_write": False,
        "authorizes_creator_execution": False,
        "mutates_blueprint": False,
    }


def test_config_preserves_svg_atomic_assets_but_pdf_working_container():
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    defaults = config["document_defaults"]
    assert defaults["working_document_container"] == "pdf"
    assert defaults["atomic_vector_interchange"] == "svg"
    assert defaults["editable_interchange"] == "svg"
    assert defaults["review_output"] == "pdf"
    assert defaults["production_output"] == "pdf"
    assert all(
        spec["selected"] == "UNRESOLVED"
        for spec in config["providers"].values()
    )


def test_pyproject_exposes_reproducible_gdl_dependency_group():
    data = tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    deps = data["project"]["optional-dependencies"]["gdl"]
    joined = "\n".join(deps).lower()
    for name in (
        "pymupdf",
        "pillow",
        "pikepdf",
        "pypdf",
        "reportlab",
        "fonttools",
        "lxml",
        "python-docx",
        "cairosvg",
    ):
        assert name in joined


def test_font_policy_forbids_silent_substitution():
    contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    policy = contract["font_policy"]
    assert policy["automatic_substitution_allowed"] is False
    assert policy["exact_font_required_for_text_regeneration"] is True
    assert policy["missing_exact_fonts_are"]["host_readiness_failure"] is False
    assert (
        policy["missing_exact_fonts_are"][
            "text_regeneration_blocker_for_affected_objects"
        ]
        is True
    )


def test_makefile_exposes_host_and_portable_operator_gates():
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "gdl-toolchain-contract-check:" in text
    assert "gdl-toolchain-check:" in text
    governance = next(
        line
        for line in text.splitlines()
        if line.startswith("governance-check:")
    )
    assert "gdl-toolchain-contract-check" in governance

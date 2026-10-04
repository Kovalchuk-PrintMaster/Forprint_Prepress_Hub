#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "coordination/graphic_design_lab/execution/gdl_toolchain_contract_v0_1.yaml"
CONFIG = ROOT / "config/graphic_design_lab.yaml"
PYPROJECT = ROOT / "pyproject.toml"
MAKEFILE = ROOT / "Makefile"


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def normalize_distribution(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def dependency_name(spec: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9_.-]+)", spec)
    return normalize_distribution(match.group(1)) if match else ""


def structural_errors(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    contract_path = root / CONTRACT.relative_to(ROOT)
    config_path = root / CONFIG.relative_to(ROOT)
    pyproject_path = root / PYPROJECT.relative_to(ROOT)
    makefile_path = root / MAKEFILE.relative_to(ROOT)

    for name, path in (
        ("contract", contract_path),
        ("config", config_path),
        ("pyproject", pyproject_path),
        ("makefile", makefile_path),
    ):
        if not path.is_file():
            errors.append(f"missing:{name}:{path.relative_to(root)}")

    if errors:
        return errors

    contract = load_yaml(contract_path)
    config = load_yaml(config_path)
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    makefile = makefile_path.read_text(encoding="utf-8")

    if contract.get("schema_version") != "forprint_gdl_toolchain_contract_v0_1":
        errors.append("contract:schema_version_invalid")
    if contract.get("contract_id") != "gdl_toolchain_contract_v0_1":
        errors.append("contract:id_invalid")
    if contract.get("capability") != "graphic_design_lab":
        errors.append("contract:capability_invalid")

    authority = contract.get("authority", {})
    for key in (
        "selects_provider",
        "initializes_runtime",
        "enables_production_write",
        "authorizes_creator_execution",
        "mutates_blueprint",
    ):
        if authority.get(key) is not False:
            errors.append(f"authority_must_be_false:{key}")

    strategy = contract.get("document_strategy", {})
    if strategy.get("mode") != "PDF_FIRST_COMPONENT_BASED":
        errors.append("document_strategy:mode_invalid")
    if strategy.get("working_document_container") != "pdf":
        errors.append("document_strategy:working_container_must_be_pdf")
    if strategy.get("review_output") != "pdf":
        errors.append("document_strategy:review_output_must_be_pdf")
    if strategy.get("production_output") != "pdf":
        errors.append("document_strategy:production_output_must_be_pdf")
    if strategy.get("illustrator_private_data", {}).get("machine_source_of_truth") is not False:
        errors.append("document_strategy:illustrator_private_data_not_authoritative")

    font_policy = contract.get("font_policy", {})
    if font_policy.get("automatic_substitution_allowed") is not False:
        errors.append("font_policy:auto_substitution_must_be_false")
    if font_policy.get("exact_font_required_for_text_regeneration") is not True:
        errors.append("font_policy:exact_font_regeneration_gate_missing")

    privacy = contract.get("privacy", {})
    for key in (
        "client_paths_in_contract",
        "pii_in_contract",
        "heavy_customer_artifacts_in_repository",
    ):
        if privacy.get(key) is not False:
            errors.append(f"privacy_boundary_invalid:{key}")

    cfg_toolchain = config.get("toolchain", {})
    expected_contract = (
        "coordination/graphic_design_lab/execution/"
        "gdl_toolchain_contract_v0_1.yaml"
    )
    if cfg_toolchain.get("contract") != expected_contract:
        errors.append("config:toolchain_contract_pointer_invalid")
    for key in (
        "provider_selection_from_availability",
        "runtime_initialization_from_availability",
        "production_write_from_availability",
    ):
        if cfg_toolchain.get(key) is not False:
            errors.append(f"config:toolchain_authority_boundary_invalid:{key}")

    defaults = config.get("document_defaults", {})
    if defaults.get("working_document_container") != "pdf":
        errors.append("config:working_document_container_must_be_pdf")
    if defaults.get("atomic_vector_interchange") != "svg":
        errors.append("config:atomic_vector_interchange_must_be_svg")
    if defaults.get("review_output") != "pdf":
        errors.append("config:review_output_must_be_pdf")
    if defaults.get("production_output") != "pdf":
        errors.append("config:production_output_must_be_pdf")

    for provider, spec in config.get("providers", {}).items():
        if spec.get("selected") != "UNRESOLVED":
            errors.append(f"config:provider_selected:{provider}")

    group = (
        pyproject.get("project", {})
        .get("optional-dependencies", {})
        .get("gdl", [])
    )
    declared = {dependency_name(item) for item in group}
    required = {
        normalize_distribution(item["distribution"])
        for item in contract.get("python_environment", {}).get("required", [])
    }
    missing = sorted(required - declared)
    if missing:
        errors.append("pyproject:gdl_dependencies_missing:" + ",".join(missing))

    for target in (
        "gdl-toolchain-contract-check:",
        "gdl-toolchain-check:",
    ):
        if target not in makefile:
            errors.append(f"makefile:target_missing:{target[:-1]}")

    governance_line = next(
        (
            line
            for line in makefile.splitlines()
            if line.startswith("governance-check:")
        ),
        "",
    )
    if "gdl-toolchain-contract-check" not in governance_line:
        errors.append("makefile:governance_missing_portable_toolchain_gate")

    return errors


def _font_exactish(query: str) -> tuple[bool, str]:
    cp = subprocess.run(
        ["fc-match", "-f", "%{family}|%{style}|%{file}\\n", query],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    raw = cp.stdout.strip()
    family = raw.split("|", 1)[0].strip() if raw else ""
    q = query.casefold().replace(" ", "")
    f = family.casefold().replace(" ", "")
    return bool(f) and (q in f or f in q), raw


def host_readiness(root: Path = ROOT) -> tuple[list[str], list[str]]:
    contract = load_yaml(
        root
        / "coordination/graphic_design_lab/execution/"
        "gdl_toolchain_contract_v0_1.yaml"
    )
    errors: list[str] = []
    warnings: list[str] = []

    for item in contract.get("system_tools", []):
        command = item["command"]
        if shutil.which(command) is None:
            errors.append(f"system_command_missing:{item['id']}:{command}")

    for item in contract.get("python_environment", {}).get("required", []):
        try:
            importlib.import_module(item["import_name"])
        except Exception as exc:
            errors.append(
                f"python_import_failed:{item['distribution']}:"
                f"{type(exc).__name__}:{exc}"
            )

    if shutil.which("fc-match") is None:
        errors.append("system_command_missing:fontconfig_fc_match:fc-match")
    else:
        for font in contract.get("font_policy", {}).get("observed_template_fonts", []):
            exactish, raw = _font_exactish(font)
            if not exactish:
                warnings.append(f"exact_template_font_missing:{font}:{raw}")

    return errors, warnings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("contract", "host"), default="host")
    args = parser.parse_args()

    errors = structural_errors(ROOT)
    warnings: list[str] = []

    if not errors and args.mode == "host":
        host_errors, warnings = host_readiness(ROOT)
        errors.extend(host_errors)

    if errors:
        print("PREPRESS_HUB_GDL_TOOLCHAIN_CHECK=FAIL")
        for error in errors:
            print(f"ERROR={error}")
        raise SystemExit(1)

    if args.mode == "contract":
        print("PREPRESS_HUB_GDL_TOOLCHAIN_CONTRACT_CHECK=PASS")
        print("PORTABLE_CONTRACT_CHECK=true")
    else:
        print("PREPRESS_HUB_GDL_TOOLCHAIN_HOST_CHECK=PASS")
        print("SYSTEM_AND_PYTHON_TOOLCHAIN=READY")
        print(f"MISSING_EXACT_TEMPLATE_FONT_COUNT={len(warnings)}")
        for warning in warnings:
            print(f"WARNING={warning}")
        print("FONT_SUBSTITUTION_PERFORMED=false")
        print("TEXT_REGENERATION_WITH_MISSING_EXACT_FONT_ALLOWED=false")

    print("DOCUMENT_STRATEGY=PDF_FIRST_COMPONENT_BASED")
    print("WORKING_DOCUMENT_CONTAINER=pdf")
    print("ATOMIC_VECTOR_INTERCHANGE=svg")
    print("PROVIDER_SELECTED=false")
    print("GDL_RUNTIME_INITIALIZED=false")
    print("PRODUCTION_WRITE_ENABLED=false")
    print("BLUEPRINT_MUTATED=false")


if __name__ == "__main__":
    main()

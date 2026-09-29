#!/usr/bin/env python3
from pathlib import Path
import sys

import yaml

from app.graphic_design_lab.intake import (
    build_creator_handoff,
    normalize_guided_intake,
    validate_creator_handoff,
    validate_guided_intake,
    validate_product_playbook,
)

ROOT = Path(__file__).resolve().parents[2]

paths = {
    "playbook_contract": ROOT / "contracts/graphic_design_lab/product_playbook_v0_1.yaml",
    "guided_contract": ROOT / "contracts/graphic_design_lab/guided_intake_v0_1.yaml",
    "handoff_contract": ROOT / "contracts/graphic_design_lab/creator_handoff_v0_1.yaml",
    "asset_contract": ROOT / "contracts/graphic_design_lab/asset_reference_v0_1.yaml",
    "playbook": ROOT / "config/graphic_design_lab/product_playbooks/recurring_greeting_card_v0_1.yaml",
    "fixture": ROOT / "tests/fixtures/graphic_design_lab/recurring_greeting_card_intake_v0_1.yaml",
    "config": ROOT / "config/graphic_design_lab.yaml",
    "status": ROOT / "coordination/status/current_status.yaml",
}

errors = [
    f"missing:{name}:{path.relative_to(ROOT)}"
    for name, path in paths.items()
    if not path.is_file()
]

if not errors:
    loaded = {
        name: yaml.safe_load(path.read_text(encoding="utf-8"))
        for name, path in paths.items()
    }

    expected_contracts = {
        "playbook_contract": ("product_playbook_v0_1", "product_playbook"),
        "guided_contract": ("guided_intake_v0_1", "guided_intake"),
        "handoff_contract": ("creator_handoff_v0_1", "creator_handoff"),
    }
    for name, expected in expected_contracts.items():
        contract = loaded[name]
        if (contract.get("contract_id"), contract.get("contract_type")) != expected:
            errors.append(f"{name}:identity_mismatch")

    playbook = loaded["playbook"]
    fixture = loaded["fixture"]
    raw = fixture["raw_input"]
    errors.extend(validate_product_playbook(playbook))

    try:
        intake = normalize_guided_intake(playbook, raw)
    except ValueError as exc:
        errors.append(f"guided_intake_build:{exc}")
        intake = {}

    if intake:
        errors.extend(
            validate_guided_intake(
                intake,
                playbook=playbook,
                assets=raw["assets"],
                references=raw["references"],
            )
        )

    try:
        handoff = build_creator_handoff(
            playbook,
            intake,
            assets=raw["assets"],
            references=raw["references"],
        )
    except (KeyError, ValueError) as exc:
        errors.append(f"creator_handoff_build:{exc}")
        handoff = {}

    if handoff:
        errors.extend(
            validate_creator_handoff(
                handoff,
                playbook=playbook,
                assets=raw["assets"],
                references=raw["references"],
            )
        )

    if intake:
        states = {item["mapping_state"] for item in intake["asset_mappings"]}
        if states != {"CONFIRMED", "PROPOSED", "UNRESOLVED"}:
            errors.append("fixture:mapping_state_coverage_incomplete")

    if handoff:
        second = build_creator_handoff(
            playbook,
            normalize_guided_intake(playbook, raw),
            assets=raw["assets"],
            references=raw["references"],
        )
        if handoff != second:
            errors.append("creator_handoff:not_deterministic")
        if handoff.get("creator_execution_authorized") is not False:
            errors.append("creator_execution_must_remain_disabled")
        if handoff.get("provider_execution_required") is not False:
            errors.append("provider_execution_must_not_be_required")

    config = loaded["config"]
    if (
        config.get("storage", {}).get("product_playbooks_root")
        != "config/graphic_design_lab/product_playbooks"
    ):
        errors.append("config:product_playbooks_root_missing_or_invalid")

    for provider, spec in config.get("providers", {}).items():
        if spec.get("selected") != "UNRESOLVED":
            errors.append(f"provider_selected:{provider}")

    status = loaded["status"]
    if status.get("graphic_design_lab_runtime_initialized") is not False:
        errors.append("gdl_runtime_must_remain_uninitialized")
    if status.get("production_write_enabled") is not False:
        errors.append("production_write_must_remain_disabled")

if errors:
    print("PREPRESS_HUB_GDL_INTAKE_HANDOFF_CHECK=FAIL")
    for error in errors:
        print(f"ERROR={error}")
    sys.exit(1)

print("PREPRESS_HUB_GDL_INTAKE_HANDOFF_CHECK=PASS")
print("PRODUCT_PLAYBOOK=recurring_greeting_card_v0_1")
print("GUIDED_INTAKE=forprint_guided_intake_v0_1")
print("CREATOR_HANDOFF=forprint_creator_handoff_v0_1")
print("MAPPING_STATES=CONFIRMED,PROPOSED,UNRESOLVED")
print("AMBIGUITY_REQUIRES_HUMAN_CONFIRMATION=true")
print("ASSET_REFERENCE_IDENTITY_REUSED=true")
print("NUMERIC_CONFIDENCE_SCORING=false")
print("DETERMINISTIC_HANDOFF=true")
print("CREATOR_EXECUTION_AUTHORIZED=false")
print("PROVIDER_EXECUTION_REQUIRED=false")
print("GDL_RUNTIME_INITIALIZED=false")
print("PRODUCTION_WRITE_ENABLED=false")

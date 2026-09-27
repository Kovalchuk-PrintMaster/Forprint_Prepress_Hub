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
]
errors = [f"missing:{rel}" for rel in required if not (ROOT / rel).is_file()]

if not errors:
    roadmap = yaml.safe_load((ROOT / required[0]).read_text(encoding="utf-8"))
    config = yaml.safe_load((ROOT / "config/graphic_design_lab.yaml").read_text(encoding="utf-8"))
    status = yaml.safe_load((ROOT / "coordination/status/current_status.yaml").read_text(encoding="utf-8"))

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

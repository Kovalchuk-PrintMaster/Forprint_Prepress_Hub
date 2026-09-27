#!/usr/bin/env python3
from pathlib import Path
import sys
import yaml

root = Path(__file__).resolve().parents[2]

required = [
    ".gitignore",
    "README.md",
    "AGENTS.md",
    "Makefile",
    "pyproject.toml",
    "coordination/module/manifest.yaml",
    "coordination/status/current_status.yaml",
    "coordination/status/next_questions_for_blueprint.md",
    "docs/architecture/module_boundary.md",
]

missing = [path for path in required if not (root / path).is_file()]
if missing:
    print("PREPRESS_HUB_BOOTSTRAP_CHECK=FAIL")
    for path in missing:
        print(f"MISSING={path}")
    sys.exit(1)

status = yaml.safe_load(
    (root / "coordination/status/current_status.yaml").read_text(encoding="utf-8")
)

errors = []
if status.get("module_id") != "forprint_prepress_hub":
    errors.append("wrong_module_id")
if status.get("production_write_enabled") is not False:
    errors.append("production_write_must_be_false")
if status.get("canonical_runtime_ready") is not False:
    errors.append("canonical_runtime_ready_must_be_false")
if status.get("graphic_design_lab") != "PLANNED_NOT_INITIALIZED":
    errors.append("graphic_design_lab_must_remain_uninitialized")
if (root / "graphic_design_lab").exists():
    errors.append("graphic_design_lab_directory_exists_too_early")

if errors:
    print("PREPRESS_HUB_BOOTSTRAP_CHECK=FAIL")
    for error in errors:
        print(f"ERROR={error}")
    sys.exit(1)

print("PREPRESS_HUB_BOOTSTRAP_CHECK=PASS")
print("MODULE=forprint_prepress_hub")
print("PRODUCTION_WRITE_ENABLED=false")
print("CANONICAL_RUNTIME_READY=false")
print("GRAPHIC_DESIGN_LAB=PLANNED_NOT_INITIALIZED")

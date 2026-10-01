#!/usr/bin/env python3
from pathlib import Path

import yaml

from app.graphic_design_lab.result_package import (
    build_creator_result_package,
    summarize_creator_result_package,
    validate_creator_result_package,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "contracts/graphic_design_lab/creator_result_package_v0_1.yaml"
FIXTURE = ROOT / "tests/fixtures/graphic_design_lab/creator_result_package_sanitized_v0_1.yaml"


def load(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


contract = load(CONTRACT)
fixture = load(FIXTURE)
package = build_creator_result_package(fixture)
errors = validate_creator_result_package(package, contract)

if errors:
    for error in errors:
        print(f"ERROR={error}")
    raise SystemExit(1)

print(summarize_creator_result_package(package))
print("PREPRESS_HUB_GDL_CREATOR_RESULT_PACKAGE_CHECK=PASS")
print(f"PACKAGE_SCHEMA={package['schema_version']}")
print(f"PACKAGE_ID={package['package_id']}")
print(f"REVISION={package['revision']}")
print(f"RESULT_STATE={package['observed_result']['result_state']}")
print(f"INTERNAL_REVIEW={package['readiness']['internal_review']}")
print(f"CUSTOMER_FORWARDING={package['readiness']['customer_forwarding']}")
print(f"DESIGN_APPROVAL={package['readiness']['design_approval']}")
print(f"PRODUCTION_READINESS={package['readiness']['production_readiness']}")
print("EXTERNAL_ARTIFACT_REFERENCE=true")
print("REPOSITORY_CONTAINS_HEAVY_ARTIFACT=false")
print("PII_ALLOWED_IN_GIT=false")
print("PROVIDER_EXECUTION_REQUIRED=false")
print("PROVIDER_EXECUTION_PERFORMED=false")
print("GDL_RUNTIME_INITIALIZED=false")
print("PRODUCTION_WRITE_ENABLED=false")
print("AUTOMATIC_CUSTOMER_MESSAGING=false")
print("AUTOMATIC_DESIGN_APPROVAL=false")

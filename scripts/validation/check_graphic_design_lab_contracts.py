#!/usr/bin/env python3
from pathlib import Path
import sys
import yaml

from app.graphic_design_lab.validation import validate_design_spec, validate_product_profile

ROOT = Path(__file__).resolve().parents[2]

paths = {
    "design_contract": ROOT / "contracts/graphic_design_lab/design_spec_v0_1.yaml",
    "asset_contract": ROOT / "contracts/graphic_design_lab/asset_reference_v0_1.yaml",
    "revision_contract": ROOT / "contracts/graphic_design_lab/revision_patch_v0_1.yaml",
    "profile_contract": ROOT / "contracts/graphic_design_lab/product_profile_v0_1.yaml",
    "diary_profile": ROOT / "config/graphic_design_lab/product_profiles/dated_diary_a5_v0_1.yaml",
    "fixture": ROOT / "tests/fixtures/graphic_design_lab/dated_diary_a5_phase1_v0_1.yaml",
}

errors = []
for name, path in paths.items():
    if not path.is_file():
        errors.append(f"missing:{name}:{path.relative_to(ROOT)}")

if not errors:
    loaded = {name: yaml.safe_load(path.read_text(encoding="utf-8")) for name, path in paths.items()}
    errors.extend(validate_product_profile(loaded["diary_profile"]))
    errors.extend(
        validate_design_spec(
            loaded["fixture"],
            loaded["design_contract"],
            loaded["diary_profile"],
        )
    )

    if loaded["fixture"]["review"]["full_rollout_allowed"] is not False:
        errors.append("fixture.review.full_rollout_allowed:must_be_false")
    if loaded["fixture"]["assets"] != []:
        errors.append("fixture.assets:phase1_must_not_require_photos")
    if loaded["diary_profile"]["constraints"]["full_rollout_requires_phase1_approval"] is not True:
        errors.append("diary_profile:phase1_gate_missing")

if errors:
    print("PREPRESS_HUB_GDL_CONTRACTS_CHECK=FAIL")
    for error in errors:
        print(f"ERROR={error}")
    sys.exit(1)

print("PREPRESS_HUB_GDL_CONTRACTS_CHECK=PASS")
print("DESIGN_SPEC=forprint_design_spec_v0_1")
print("PRODUCT_PROFILE=dated_diary_a5_v0_1")
print("FIXTURE=dated_diary_a5_phase1_v0_1")
print("STABLE_OBJECT_IDS=VALIDATED")
print("FULL_ROLLOUT_ALLOWED=false")
print("RENDERER_IMPLEMENTED=false")
print("PROVIDER_SELECTED=false")

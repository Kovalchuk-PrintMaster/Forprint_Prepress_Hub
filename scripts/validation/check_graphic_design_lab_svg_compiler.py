#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import yaml

from app.graphic_design_lab.artifacts import build_artifact_manifest
from app.graphic_design_lab.compiler import compile_document
from app.graphic_design_lab.structural_validation import validate_compiled_svg
from app.graphic_design_lab.validation import validate_design_spec

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config/graphic_design_lab.yaml"
CONTRACT = ROOT / "contracts/graphic_design_lab/design_spec_v0_1.yaml"
PROFILE = ROOT / "config/graphic_design_lab/product_profiles/dated_diary_a5_v0_1.yaml"
FIXTURE = ROOT / "tests/fixtures/graphic_design_lab/dated_diary_a5_phase1_v0_1.yaml"

config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
spec = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))

errors = validate_design_spec(spec, contract, profile)
artifacts = compile_document(spec) if not errors else []

spread_by_id = {spread["id"]: spread for spread in spec.get("spreads", [])}
structural = {}
for artifact in artifacts:
    item_errors = validate_compiled_svg(
        artifact.svg_text,
        spec,
        spread_by_id[artifact.spread_id],
    )
    structural[artifact.spread_id] = item_errors
    errors.extend(f"{artifact.spread_id}:{error}" for error in item_errors)

temp_root = ROOT / config["storage"]["temp_root"]
output_dir = temp_root / "h2_svg_compiler_validation"
output_dir.mkdir(parents=True, exist_ok=True)

expected_svg_names = {item.filename for item in artifacts}
for existing in output_dir.glob("*.svg"):
    if existing.name not in expected_svg_names:
        existing.unlink()

for artifact in artifacts:
    (output_dir / artifact.filename).write_text(artifact.svg_text, encoding="utf-8")

manifest = build_artifact_manifest(
    document_id=spec["document_id"],
    revision_id=spec["revision_id"],
    artifacts=artifacts,
    output_role="temp_h2_validation",
)
(output_dir / "artifact_manifest.json").write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

report = {
    "schema_version": "forprint_gdl_svg_compiler_validation_report_v0_1",
    "document_id": spec["document_id"],
    "revision_id": spec["revision_id"],
    "spread_count": len(spec.get("spreads", [])),
    "svg_file_count": len(artifacts),
    "structural_errors": structural,
    "preview_available": False,
    "review_pdf_available": False,
    "production_ready": False,
    "provider_selected": False,
    "errors": errors,
}
(output_dir / "validation_report.json").write_text(
    json.dumps(report, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

if errors:
    print("PREPRESS_HUB_GDL_SVG_COMPILER_CHECK=FAIL")
    for error in errors:
        print(f"ERROR={error}")
    raise SystemExit(1)

object_count = sum(len(spread.get("objects", [])) for spread in spec["spreads"])
print("PREPRESS_HUB_GDL_SVG_COMPILER_CHECK=PASS")
print(f"DOCUMENT_ID={spec['document_id']}")
print(f"REVISION_ID={spec['revision_id']}")
print(f"SPREAD_COUNT={len(spec['spreads'])}")
print(f"SVG_FILE_COUNT={len(artifacts)}")
print(f"STABLE_OBJECT_ID_COUNT={object_count}")
print("STABLE_OBJECT_IDS_PRESERVED=true")
print("STRUCTURAL_VALIDATION=PASS")
print("PREVIEW_AVAILABLE=false")
print("REVIEW_PDF_AVAILABLE=false")
print("PRODUCTION_READY=false")
print("PROVIDER_SELECTED=false")
print(f"OUTPUT_DIR={output_dir}")
print(f"MANIFEST={output_dir / 'artifact_manifest.json'}")
print(f"REPORT={output_dir / 'validation_report.json'}")

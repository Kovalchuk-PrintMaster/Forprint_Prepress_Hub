#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.graphic_design_lab.greeting_card_constructor_bundle import (  # noqa: E402
    compute_bundle_sha256,
    validate_accepted_constructor_bundle,
)

MACHINE_DIR = "_forprint_automation"
OUTPUT_DIR = "output"
SIGNATURE_CATALOG = (
    REPO
    / "coordination"
    / "graphic_design_lab"
    / "directions"
    / "greeting_cards"
    / "signature_variant_catalog_v0_1.yaml"
)
REPORT_SCHEMA = "gdl_greeting_card_constructor_ingest_report_v0_1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return value or "bundle"


def load_yaml_mapping(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"{label}_load_failed:{path}:{exc}") from exc
    if not isinstance(value, Mapping):
        raise RuntimeError(f"{label}_must_be_mapping:{path}")
    return dict(value)


def _validated_bundle(
    bundle_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    bundle = load_yaml_mapping(
        bundle_path,
        label="accepted_constructor_bundle",
    )
    catalog = load_yaml_mapping(
        SIGNATURE_CATALOG,
        label="signature_catalog",
    )

    errors = validate_accepted_constructor_bundle(
        bundle,
        signature_catalog=catalog,
    )
    if errors:
        raise RuntimeError(
            "accepted_constructor_bundle_invalid:" + ";".join(errors)
        )

    return bundle, catalog


def run_bundle(
    bundle_path: Path,
) -> dict[str, Any]:
    bundle_path = bundle_path.expanduser().resolve()

    if not bundle_path.is_file():
        raise RuntimeError(
            f"accepted_constructor_bundle_missing:{bundle_path}"
        )
    if not SIGNATURE_CATALOG.is_file():
        raise RuntimeError(
            f"signature_catalog_missing:{SIGNATURE_CATALOG}"
        )

    bundle_file_before = sha256(bundle_path)
    catalog_before = sha256(SIGNATURE_CATALOG)

    bundle, catalog = _validated_bundle(bundle_path)

    canonical_digest = compute_bundle_sha256(bundle)
    recorded_digest = (
        bundle.get("provenance_manifest", {}).get("bundle_sha256")
    )
    if canonical_digest != recorded_digest:
        raise RuntimeError(
            "accepted_constructor_bundle_digest_mismatch"
        )

    bundle_id = str(bundle["bundle_id"])
    run_id = f"{slug(bundle_id)}-{canonical_digest[:12]}"

    workspace_root = bundle_path.parent
    machine = (
        workspace_root
        / MACHINE_DIR
        / "jobs"
        / run_id
    )
    report_dir = workspace_root / OUTPUT_DIR / "report"

    jobs = bundle["jobs"]
    job_ids = [str(item["job_id"]) for item in jobs]

    manifest = {
        "schema_version":
            "gdl_greeting_card_constructor_input_manifest_v0_1",
        "run_id": run_id,
        "constructor_input_class":
            "ACCEPTED_CONSTRUCTOR_BUNDLE",
        "bundle_id": bundle_id,
        "bundle_schema_version": bundle.get("schema_version"),
        "bundle_canonical_sha256": canonical_digest,
        "bundle_file_sha256": bundle_file_before,
        "signature_catalog_id": catalog.get("catalog_id"),
        "signature_catalog_sha256": catalog_before,
        "job_ids": job_ids,
        "job_count": len(job_ids),
        "raw_customer_material_interpretation_performed": False,
        "heuristic_role_inference_performed": False,
        "normalized_batch_synthesis_performed": False,
    }

    report = {
        "schema_version": REPORT_SCHEMA,
        "run_id": run_id,
        "status": "ACCEPTED_CONSTRUCTOR_BUNDLE_INGESTED",
        "constructor_input_class":
            "ACCEPTED_CONSTRUCTOR_BUNDLE",
        "bundle_id": bundle_id,
        "bundle_canonical_sha256": canonical_digest,
        "bundle_file_sha256": bundle_file_before,
        "job_ids": job_ids,
        "job_count": len(job_ids),
        "constructor_workspace_created": True,
        "source_mutation": False,
        "raw_customer_material_interpretation_performed": False,
        "heuristic_role_inference_performed": False,
        "normalized_batch_synthesis_performed": False,
        "ready_for_composition": True,
        "next_state": "READY_FOR_DETERMINISTIC_COMPOSITION",
        "production_ready": False,
        "production_write_enabled": False,
        "git_mutation": False,
    }

    atomic_json(
        machine / "constructor_input_manifest.json",
        manifest,
    )
    atomic_json(
        machine / "run_report.json",
        report,
    )
    atomic_json(
        report_dir / "job_result.json",
        report,
    )

    bundle_file_after = sha256(bundle_path)
    catalog_after = sha256(SIGNATURE_CATALOG)
    if bundle_file_before != bundle_file_after:
        raise RuntimeError(
            "accepted_constructor_bundle_source_mutation_detected"
        )
    if catalog_before != catalog_after:
        raise RuntimeError(
            "signature_catalog_source_mutation_detected"
        )

    print("GDL_GREETING_CARD_CONSTRUCTOR_INGEST=PASS")
    print(f"RUN_ID={run_id}")
    print(f"BUNDLE_ID={bundle_id}")
    print(f"BUNDLE_SHA256={canonical_digest}")
    print(f"JOB_COUNT={len(job_ids)}")
    print("NEXT_STATE=READY_FOR_DETERMINISTIC_COMPOSITION")
    print("SOURCE_MUTATION=false")
    print("RAW_CUSTOMER_MATERIAL_INTERPRETATION=false")
    print("HEURISTIC_ROLE_INFERENCE=false")
    print("PRODUCTION_READY=false")
    print(f"JOB_REPORT={report_dir / 'job_result.json'}")

    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bundle",
        required=True,
        help="Exact path to ACCEPTED_CONSTRUCTOR_BUNDLE YAML/JSON.",
    )
    args = parser.parse_args()

    run_bundle(
        Path(args.bundle),
    )


if __name__ == "__main__":
    main()

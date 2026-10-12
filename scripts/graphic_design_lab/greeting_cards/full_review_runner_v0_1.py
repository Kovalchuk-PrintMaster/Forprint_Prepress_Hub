#!/usr/bin/env python3
"""ForPrint GDL: build a complete four-page greeting-card *review candidate*.

Consumes a reviewed Builder-ready Accepted Constructor Bundle and existing
private manifests. Invokes the project-owned Renderer exactly once per batch;
then verifies real PDFs against all their PNG previews and prepares contact
sheets and an operator archive under the ignored tmp/ tree.

This is a review boundary, NOT production acceptance or customer messaging.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pymupdf
import yaml
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_INPUTS = ROOT / "tmp/gdl_gc09b_real_pdf_proof_20261010/private_inputs_local.json"
DEFAULT_OUTPUT = ROOT / "tmp/gdl_gc09_full_card_review"
CATALOG = ROOT / "coordination/graphic_design_lab/directions/greeting_cards/signature_variant_catalog_v0_1.yaml"
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
PAGE_LABELS = (
    "01 FRONT · greeting / logo",
    "02 BACK · locked",
    "03 INSIDE PHOTO · accepted asset",
    "04 INSIDE GREETING · sender / signature",
)
SCHEMA = "gdl_gc09_full_card_review_v0_1"


class ReviewBlocked(ValueError):
    """Machine-safe error with no customer names, source or resource paths."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def mapping_yaml(path: Path, label: str) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReviewBlocked(f"{label}_yaml_invalid") from exc
    if not isinstance(value, dict):
        raise ReviewBlocked(f"{label}_mapping_required")
    return value


def inputs_from_config(path: Path) -> dict[str, Path]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReviewBlocked("private_input_config_invalid") from exc
    keys = {"bundle", "resource_manifest", "artifact_manifest"}
    if not isinstance(payload, dict) or set(payload) != keys:
        raise ReviewBlocked("private_input_config_keys_invalid")
    result: dict[str, Path] = {}
    for key in sorted(keys):
        raw = payload[key]
        if not isinstance(raw, str) or not raw.strip():
            raise ReviewBlocked(f"private_{key}_missing")
        p = Path(raw).expanduser()
        if not p.is_absolute():
            p = ROOT / p
        p = p.resolve()
        if not p.is_file():
            raise ReviewBlocked(f"private_{key}_not_found")
        result[key] = p
    return result


def preflight(inputs: Mapping[str, Path]) -> dict[str, Any]:
    """Validate the accepted bundle; never infer or rewrite order content."""
    from app.graphic_design_lab.greeting_card_builder_input import (
        validate_builder_ready_bundle_v1,
    )
    bundle = mapping_yaml(inputs["bundle"], "bundle")
    catalog = mapping_yaml(CATALOG, "signature_catalog")
    errors = validate_builder_ready_bundle_v1(bundle, signature_catalog=catalog)
    if errors:
        raise ReviewBlocked("builder_ready_bundle_contract_invalid")
    jobs = bundle.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        raise ReviewBlocked("builder_jobs_missing")
    seen: set[str] = set()
    variants: list[str] = []
    for job in jobs:
        if not isinstance(job, dict):
            raise ReviewBlocked("builder_job_invalid")
        payload = job.get("builder_v1") or {}
        job_id = job.get("job_id")
        revision = payload.get("revision")
        if not isinstance(job_id, str) or not SAFE_NAME.fullmatch(job_id):
            raise ReviewBlocked("job_id_unsafe_for_output")
        if not isinstance(revision, str) or not re.fullmatch(r"r\d{3}", revision):
            raise ReviewBlocked("job_revision_invalid")
        stem = f"{job_id}__{revision}"
        if stem in seen:
            raise ReviewBlocked("duplicate_output_stem")
        seen.add(stem)
        variant = (payload.get("sender_text") or {}).get("signature_variant_id")
        if not isinstance(variant, str) or not variant:
            raise ReviewBlocked("signature_variant_unspecified")
        variants.append(variant)
    fingerprints = {key: sha256(path) for key, path in inputs.items()}
    fingerprints["signature_catalog"] = sha256(CATALOG)
    synthetic = bool(bundle.get("synthetic_fixture_only", False)) or any(
        str(job.get("job_id", "")).startswith("gdl-synthetic-") for job in jobs
    )
    return {
        "jobs": jobs,
        "stems": tuple(sorted(seen)),
        "variants": tuple(variants),
        "fingerprints": fingerprints,
        "synthetic": synthetic,
    }


def check_source_unchanged(inputs: Mapping[str, Path], expected: Mapping[str, str]) -> None:
    current = {key: sha256(path) for key, path in inputs.items()}
    current["signature_catalog"] = sha256(CATALOG)
    if current != dict(expected):
        raise ReviewBlocked("input_files_changed_during_review_run")


def verify_one(pdf: Path, previews: list[Path], *, dpi: int = 120) -> dict[str, Any]:
    """Re-render every PDF page and require pixel-identical stored previews."""
    if not pdf.is_file() or len(previews) != 4 or any(not p.is_file() for p in previews):
        raise ReviewBlocked("pdf_or_preview_file_missing")
    dimensions = []
    with pymupdf.open(pdf) as document:
        if document.page_count != 4:
            raise ReviewBlocked("full_card_must_have_four_pages")
        for index, (page, png) in enumerate(zip(document, previews, strict=True), start=1):
            pix = page.get_pixmap(matrix=pymupdf.Matrix(dpi / 72, dpi / 72), alpha=False)
            with Image.open(png) as image:
                rgb = image.convert("RGB")
                if rgb.size != (pix.width, pix.height) or rgb.tobytes() != pix.samples:
                    raise ReviewBlocked(f"pdf_png_pixel_replay_mismatch_page_{index}")
                dimensions.append([int(rgb.width), int(rgb.height)])
    return {"pdf_sha256": sha256(pdf), "page_count": 4,
            "preview_count": 4, "preview_pixel_replay": "PASS",
            "preview_sizes_px": dimensions}


def _font(size: int) -> ImageFont.ImageFont:
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def contact_sheet(previews: list[Path], output: Path) -> None:
    """Only composes previews; no design recreation or AI image generation."""
    if len(previews) != 4:
        raise ReviewBlocked("review_contact_requires_four_pages")
    thumb_width, header, margin = 560, 39, 22
    with Image.open(previews[0]) as sample:
        aspect = sample.height / sample.width
    thumb_height = int(round(thumb_width * aspect))
    cell_w, cell_h = thumb_width + margin * 2, thumb_height + header + margin * 2
    result = Image.new("RGB", (cell_w * 2, cell_h * 2), "white")
    drawer = ImageDraw.Draw(result)
    font = _font(17)
    for index, path in enumerate(previews):
        with Image.open(path) as item:
            thumb = item.convert("RGB").resize((thumb_width, thumb_height), Image.Resampling.LANCZOS)
        x = (index % 2) * cell_w + margin
        y = (index // 2) * cell_h + margin
        drawer.text((x, y), PAGE_LABELS[index], fill="black", font=font)
        result.paste(thumb, (x, y + header))
        drawer.rectangle([x - 1, y + header - 1, x + thumb_width,
                          y + header + thumb_height], outline=(175, 175, 175), width=1)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.save(output, "PNG")


def _review_root(path: Path) -> Path:
    root = path.expanduser().resolve()
    permitted = (ROOT / "tmp").resolve()
    if root == permitted or permitted not in root.parents:
        raise ReviewBlocked("review_output_must_be_inside_repository_tmp")
    return root


def _rel_from_run(path: Path, run: Path) -> str:
    try:
        return path.resolve().relative_to(run.resolve()).as_posix()
    except ValueError as exc:
        raise ReviewBlocked("artifact_outside_review_run") from exc


def package_review(run: Path, files: list[Path]) -> Path:
    archive = run / "full_card_review_PRIVATE.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=5, allowZip64=True) as zf:
        for path in sorted(files):
            zf.write(path, arcname=_rel_from_run(path, run))
    return archive


def run_review(inputs: dict[str, Path], baseline: dict[str, Any], output_root: Path) -> dict[str, Any]:
    from app.graphic_design_lab.greeting_card_builder_renderer import (
        PREVIEW_DPI, build_bundle,
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    identity = sha256(inputs["bundle"])[:10]
    run = output_root / "runs" / f"{stamp}-{identity}"
    run.mkdir(parents=True, exist_ok=False)
    private_output = run / "builder_outputs_PRIVATE"
    print("GDL_FULL_CARD_REVIEW=BUILD_START", flush=True)
    result = build_bundle(bundle_path=inputs["bundle"],
                          resource_manifest_path=inputs["resource_manifest"],
                          artifact_manifest_path=inputs["artifact_manifest"],
                          signature_catalog_path=CATALOG, output_dir=private_output)
    check_source_unchanged(inputs, baseline["fingerprints"])
    rendered = result.get("jobs")
    if not isinstance(rendered, list) or len(rendered) != len(baseline["jobs"]):
        raise ReviewBlocked("rendered_job_count_invalid")
    files: list[Path] = []
    checked: list[dict[str, Any]] = []
    expected_stems = set(baseline["stems"])
    seen: set[str] = set()
    for job in rendered:
        stem = f"{job['job_id']}__{job['revision']}"
        if stem not in expected_stems or stem in seen:
            raise ReviewBlocked("rendered_job_identity_mismatch")
        seen.add(stem)
        pdf = private_output / "completed" / (stem + ".pdf")
        pngs = [private_output / "preview" / f"{stem}__{i:02}.png" for i in range(1, 5)]
        machine_report = private_output / "report" / (stem + ".json")
        if not machine_report.is_file():
            raise ReviewBlocked("builder_job_report_missing")
        measured = verify_one(pdf, pngs, dpi=PREVIEW_DPI)
        sheet = run / "review" / f"{stem}__all_four_pages.png"
        contact_sheet(pngs, sheet)
        files.extend([pdf, *pngs, sheet, machine_report])
        checked.append({"job_id": job["job_id"], "revision": job["revision"],
                        **measured, "contact_sheet": _rel_from_run(sheet, run),
                        "pdf": _rel_from_run(pdf, run)})
    if seen != expected_stems:
        raise ReviewBlocked("rendered_job_set_incomplete")
    bundle_report = private_output / "builder_run_report.json"
    if not bundle_report.is_file():
        raise ReviewBlocked("builder_bundle_report_missing")
    report: dict[str, Any] = {
        "schema_version": SCHEMA,
        "review_state": "READY_FOR_INTERNAL_VISUAL_REVIEW",
        "job_count": len(checked), "pdf_count": len(checked),
        "png_preview_count": 4 * len(checked),
        "pdf_preview_pixel_replay": "PASS",
        "source_fingerprints_sha256": baseline["fingerprints"],
        "synthetic_fixture": baseline["synthetic"],
        "not_real_customer_acceptance_if_synthetic": True,
        "customer_approved": False,
        "production_approved": False,
        "dual_runtime_activated_by_this_runner": False,
        "git_or_source_modified_by_this_runner": False,
        "page_order": list(PAGE_LABELS),
        "jobs": checked,
    }
    report_path = run / "review" / "review_summary.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    files.extend([report_path, bundle_report])
    archive = package_review(run, files)
    check_source_unchanged(inputs, baseline["fingerprints"])
    print("GDL_FULL_CARD_REVIEW=PASS_REQUIRES_VISUAL_APPROVAL", flush=True)
    print(f"JOB_COUNT={len(checked)} PDF_COUNT={len(checked)} PNG_COUNT={4 * len(checked)}")
    print(f"SYNTHETIC_FIXTURE={str(baseline['synthetic']).lower()}")
    print("ALL_FOUR_PAGE_PIXEL_REPLAYS=PASS")
    print("CONTACT_SHEETS=" + ";".join(_rel_from_run(run / 'review' / (f"{j['job_id']}__{j['revision']}__all_four_pages.png"), ROOT) for j in checked))
    print("REPORT=" + _rel_from_run(report_path, ROOT))
    print("REVIEW_ARCHIVE=" + _rel_from_run(archive, ROOT))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("preflight", "run"), required=True)
    parser.add_argument("--inputs-config", type=Path, default=DEFAULT_INPUTS)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        inputs = inputs_from_config(args.inputs_config)
        baseline = preflight(inputs)
        _review_root(args.output_root)
        print("GDL_FULL_CARD_REVIEW_PREFLIGHT=PASS")
        print(f"JOB_COUNT={len(baseline['jobs'])}")
        print("SIGNATURE_VARIANTS=" + ",".join(baseline["variants"]))
        print(f"SYNTHETIC_FIXTURE={str(baseline['synthetic']).lower()}")
        print("FRONT_AND_PORTRAIT_FROM_ACCEPTED_BUNDLE=true")
        if args.mode == "run":
            run_review(inputs, baseline, _review_root(args.output_root))
        return 0
    except (ReviewBlocked, Exception) as exc:
        # No private paths, names, or input content are printed to the console.
        if isinstance(exc, ReviewBlocked):
            code = str(exc)
        else:
            code = type(exc).__name__
        print("GDL_FULL_CARD_REVIEW=BLOCKED")
        print("ERROR_CODE=" + code)
        print("PRODUCTION_ACCEPTANCE=false")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

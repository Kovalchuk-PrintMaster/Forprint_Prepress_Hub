#!/usr/bin/env python3
"""ForPrint GDL: safe final Intake ZIP -> existing ingest -> existing full PDF review.

Builder remains authoritative for PDF and previews. Human/operator approval and
Creator review evidence must already exist in the Accepted Constructor Bundle.
No synthetic customer approval, no silent resource fallback, no ZIP extraction
into SMB source, no tracked source writes, no automatic production release.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

import yaml

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.graphic_design_lab.greeting_card_builder_input import validate_builder_ready_bundle_v1
from app.graphic_design_lab.greeting_card_constructor_bundle import compute_bundle_sha256
from scripts.graphic_design_lab.greeting_cards import full_review_runner_v0_1 as review

SCHEMA = "gdl_intake_builder_handoff_v0_1"
ARTIFACT_SCHEMA = "gdl_greeting_card_builder_artifact_manifest_v0_1"
HANDOFF_FILENAME = "gdl_intake_handoff.zip"
REQUIRED = frozenset({"handoff_manifest.json", "accepted_constructor_bundle.yaml", "artifact_manifest.yaml"})
RUNTIME = REPO / "tmp/gdl_intake_handoff_runtime_v0_1"
CONFIG = RUNTIME / "local_config.json"
CLIENT_SHARE_ROOT = Path("/srv/smb/In_Progress/data")
CATALOG = REPO / "coordination/graphic_design_lab/directions/greeting_cards/signature_variant_catalog_v0_1.yaml"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_MEMBERS = 512
MAX_FILE_BYTES = 96 * 1024 * 1024
MAX_ARCHIVE_BYTES = 250 * 1024 * 1024
MAX_TOTAL_BYTES = 850 * 1024 * 1024


class HandoffBlocked(ValueError):
    pass


def digest_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_mapping_bytes(b: bytes, *, kind: str) -> dict[str, Any]:
    try:
        data = json.loads(b.decode("utf-8")) if kind == "json" else yaml.safe_load(b.decode("utf-8"))
    except Exception as exc:
        raise HandoffBlocked(f"{kind}_invalid") from exc
    if not isinstance(data, dict):
        raise HandoffBlocked(f"{kind}_must_be_mapping")
    return data


def zip_path(raw: str) -> str:
    if not isinstance(raw, str) or not raw or "\\" in raw or "\x00" in raw:
        raise HandoffBlocked("unsafe_archive_member_path")
    p = PurePosixPath(raw)
    if p.is_absolute() or any(s in {"", ".", ".."} for s in raw.split("/")):
        raise HandoffBlocked("unsafe_archive_member_path")
    if ":" in p.parts[0]:
        raise HandoffBlocked("unsafe_archive_member_path")
    return str(p)


def validate_inventory(zf: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    info: dict[str, zipfile.ZipInfo] = {}
    names_casefold: set[str] = set()
    total = 0
    items = zf.infolist()
    if len(items) > MAX_MEMBERS:
        raise HandoffBlocked("zip_too_many_members")
    for item in items:
        name = zip_path(item.filename)
        if item.is_dir():
            # Common ZIP tools add ordinary directory entries; allow only safe ones.
            zip_path(item.filename.rstrip("/"))
            continue
        mode = (item.external_attr >> 16) & 0o170000
        if mode not in (0, 0o100000):
            raise HandoffBlocked("zip_non_regular_file_forbidden")
        if name in info or name.casefold() in names_casefold:
            raise HandoffBlocked("duplicate_archive_member")
        names_casefold.add(name.casefold())
        if not (name in REQUIRED or name.startswith("assets/") or name.startswith("intake_evidence/")):
            raise HandoffBlocked("unexpected_archive_member")
        if item.file_size > MAX_FILE_BYTES:
            raise HandoffBlocked("archive_member_too_large")
        total += item.file_size
        if total > MAX_TOTAL_BYTES:
            raise HandoffBlocked("archive_uncompressed_limit_exceeded")
        info[name] = item
    if not REQUIRED.issubset(info):
        raise HandoffBlocked("handoff_required_file_missing")
    return info


def load_runtime_config(config_path: Path = CONFIG) -> Path:
    if not config_path.is_file():
        raise HandoffBlocked("server_resource_config_missing_run_init_config")
    data = read_mapping_bytes(config_path.read_bytes(), kind="json")
    if set(data) != {"resource_manifest"}:
        raise HandoffBlocked("server_resource_config_invalid")
    val = data["resource_manifest"]
    if not isinstance(val, str) or not Path(val).is_absolute():
        raise HandoffBlocked("server_resource_path_must_be_absolute")
    p = Path(val).resolve()
    if not p.is_file():
        raise HandoffBlocked("server_resource_manifest_missing")
    return p


def _bundle_portraits(bundle: dict[str, Any]) -> dict[str, tuple[str, str]]:
    result = {}
    for job in bundle["jobs"]:
        part = job["builder_v1"]["inside_image"]
        if part["mode"] != "PORTRAIT":
            raise HandoffBlocked("image_mode_not_supported_in_handoff_v0_1")
        ref = str(part["accepted_artifact_ref"])
        expected = (str(part["asset_id"]), str(part["asset_sha256"]))
        if ref in result and result[ref] != expected:
            raise HandoffBlocked("artifact_ref_conflicting_bindings")
        result[ref] = expected
    return result


def inspect_zip(package_path: Path, config_path: Path = CONFIG) -> dict[str, Any]:
    path = package_path.resolve()
    if path.name != HANDOFF_FILENAME or not path.is_file():
        raise HandoffBlocked("handoff_filename_or_file_invalid")
    if path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise HandoffBlocked("zip_compressed_limit_exceeded")
    # Require a configured server-only resource library, never a ZIP-supplied font path.
    resource_manifest_path = load_runtime_config(config_path)
    with zipfile.ZipFile(path, "r") as zf:
        index = validate_inventory(zf)
        handoff = read_mapping_bytes(zf.read("handoff_manifest.json"), kind="json")
        bundle_raw = zf.read("accepted_constructor_bundle.yaml")
        artifact_raw = zf.read("artifact_manifest.yaml")
        bundle = read_mapping_bytes(bundle_raw, kind="yaml")
        artifacts = read_mapping_bytes(artifact_raw, kind="yaml")
        if set(handoff) != {"schema_version", "mode", "accepted_bundle_file_sha256", "artifact_manifest_file_sha256"}:
            raise HandoffBlocked("handoff_manifest_contract_invalid")
        if handoff["schema_version"] != SCHEMA or handoff["mode"] != "REVIEW_ONLY":
            raise HandoffBlocked("handoff_schema_or_mode_invalid")
        if handoff["accepted_bundle_file_sha256"] != digest_bytes(bundle_raw):
            raise HandoffBlocked("accepted_bundle_file_digest_invalid")
        if handoff["artifact_manifest_file_sha256"] != digest_bytes(artifact_raw):
            raise HandoffBlocked("artifact_manifest_digest_invalid")
        catalog = read_mapping_bytes(CATALOG.read_bytes(), kind="yaml")
        errors = validate_builder_ready_bundle_v1(bundle, signature_catalog=catalog)
        if errors:
            # Don't print private job names or greeting text from validation errors.
            raise HandoffBlocked("accepted_constructor_bundle_validation_failed")
        if bundle.get("provenance_manifest", {}).get("bundle_sha256") != compute_bundle_sha256(bundle):
            raise HandoffBlocked("accepted_bundle_canonical_digest_invalid")
        if artifacts.get("schema_version") != ARTIFACT_SCHEMA or not isinstance(artifacts.get("artifacts"), dict):
            raise HandoffBlocked("artifact_manifest_schema_invalid")
        bindings = _bundle_portraits(bundle)
        entries = artifacts["artifacts"]
        if set(entries) != set(bindings):
            raise HandoffBlocked("artifact_binding_set_mismatch")
        used: set[str] = set()
        for ref, (source_id, sha) in bindings.items():
            entry = entries[ref]
            if not isinstance(entry, dict) or set(entry) != {"source_asset_id", "path", "sha256"}:
                raise HandoffBlocked("artifact_entry_contract_invalid")
            name = zip_path(entry["path"])
            if not name.startswith("assets/") or name not in index:
                raise HandoffBlocked("artifact_path_not_in_archive")
            if entry["source_asset_id"] != source_id or entry["sha256"] != sha or not SHA_RE.fullmatch(sha):
                raise HandoffBlocked("artifact_identity_mismatch")
            if digest_bytes(zf.read(name)) != sha:
                raise HandoffBlocked("artifact_asset_sha256_mismatch")
            used.add(name)
        for name in index:
            if name.startswith("assets/") and name not in used:
                raise HandoffBlocked("unreferenced_asset_in_final_handoff")
        # We have proven the signed-identity envelope; review preflight also checks
        # the exact resource and job contracts when rendering.
        jobs = bundle.get("jobs", [])
    return {"package": path, "archive_sha256": digest_file(path),
            "resource_manifest": resource_manifest_path, "bundle": bundle,
            "jobs": len(jobs), "assets": len(bindings),
            "synthetic": bool(bundle.get("synthetic_fixture_only", False))}



def publish_client_review(package: Path, run: Path, *, share_root: Path = CLIENT_SHARE_ROOT) -> str:
    """Publish review outputs into the original client SMB folder on success.

    Never replace source ZIP, existing review, or accepted customer output.
    """
    root = share_root.resolve()
    client_dir = package.resolve().parent
    if client_dir != root and root not in client_dir.parents:
        raise HandoffBlocked("handoff_package_not_within_allowed_smb_share")
    target_root = client_dir / "output"
    if target_root.is_symlink():
        raise HandoffBlocked("client_output_symlink_forbidden")
    target_root.mkdir(exist_ok=True)
    if target_root.resolve() != target_root.absolute():
        raise HandoffBlocked("client_output_directory_not_canonical")
    name = "GDL_REVIEW_" + run.name
    final = target_root / name
    if final.exists() or final.is_symlink():
        raise HandoffBlocked("client_review_output_collision")
    temporary = target_root / ("." + name + ".assembling")
    temporary.mkdir(exist_ok=False)
    try:
        essential = [run / "full_card_review_PRIVATE.zip", run / "review/review_summary.json"]
        sheets = sorted((run / "review").glob("*__all_four_pages.png"))
        if not all(x.is_file() for x in essential) or not sheets:
            raise HandoffBlocked("review_publish_artifacts_missing")
        for src in [*essential, *sheets]:
            shutil.copy2(src, temporary / src.name)
        os.rename(temporary, final)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return name


def materialize_and_run(inspection: Mapping[str, Any], config_path: Path = CONFIG) -> dict[str, Any]:
    # Isolated run, never extract on the SMB client side or in tracked tree.
    package = inspection["package"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_root = RUNTIME / "runs" / f"{stamp}-{inspection['archive_sha256'][:10]}"
    source = run_root / "input_PRIVATE"
    source.mkdir(parents=True, exist_ok=False)
    try:
        with zipfile.ZipFile(package, "r") as zf:
            index = validate_inventory(zf)
            for name in index:
                dst = source / name
                dst.parent.mkdir(parents=True, exist_ok=True)
                # exclusive file creation and 96MB per member cap via validated inventory
                with dst.open("xb") as f:
                    with zf.open(index[name]) as stream:
                        while True:
                            buf = stream.read(1024 * 1024)
                            if not buf:
                                break
                            f.write(buf)
        # ZIP may have been changed between preflight and extraction.
        if digest_file(package) != inspection["archive_sha256"]:
            raise HandoffBlocked("zip_changed_after_preflight")
        artifact_file = source / "artifact_manifest.yaml"
        artifacts = read_mapping_bytes(artifact_file.read_bytes(), kind="yaml")
        for entry in artifacts["artifacts"].values():
            asset_path = (source / entry["path"]).resolve()
            if source.resolve() not in asset_path.parents or not asset_path.is_file():
                raise HandoffBlocked("asset_path_escaped_runtime")
            if digest_file(asset_path) != entry["sha256"]:
                raise HandoffBlocked("asset_changed_after_extraction")
            entry["path"] = str(asset_path)
        runtime_artifacts = run_root / "runtime_artifact_manifest_PRIVATE.yaml"
        runtime_artifacts.write_text(yaml.safe_dump(artifacts, allow_unicode=True, sort_keys=False), encoding="utf-8")
        bundle_path = source / "accepted_constructor_bundle.yaml"
        # Reuse original constructor ingest / strict provenance without mutating bundle.
        from scripts.graphic_design_lab.greeting_cards.job_runner import run_bundle
        run_bundle(bundle_path)
        inputs = {"bundle": bundle_path,
                  "resource_manifest": inspection["resource_manifest"],
                  "artifact_manifest": runtime_artifacts}
        baseline = review.preflight(inputs)
        result_dir = RUNTIME / "results" / "runs"
        known_runs = {p.name for p in result_dir.iterdir()} if result_dir.is_dir() else set()
        summary = review.run_review(inputs, baseline, RUNTIME / "results")
        new_runs = [p for p in result_dir.iterdir() if p.is_dir() and p.name not in known_runs]
        if len(new_runs) != 1:
            raise HandoffBlocked("review_run_identity_ambiguous")
        review_dir = new_runs[0]
        if digest_file(package) != inspection["archive_sha256"]:
            raise HandoffBlocked("zip_changed_after_build")
        client_output = publish_client_review(package, review_dir)
        report = {"schema_version": SCHEMA, "status": "PASS_REQUIRES_VISUAL_APPROVAL",
                  "source_zip_sha256": inspection["archive_sha256"], "job_count": summary["job_count"],
                  "customer_approved": False, "production_approved": False,
                  "source_zip_unchanged": digest_file(package) == inspection["archive_sha256"],
                  "client_output_subdir": "output/" + client_output}
        (run_root / "handoff_result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return report
    except Exception:
        (run_root / "BLOCKED.txt").write_text("GDL_INTAKE_HANDOFF=BLOCKED\n", encoding="utf-8")
        raise


def init_config(existing_inputs: Path, config_path: Path = CONFIG) -> None:
    try:
        data = json.loads(existing_inputs.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HandoffBlocked("existing_private_input_config_invalid") from exc
    raw = data.get("resource_manifest") if isinstance(data, dict) else None
    if not isinstance(raw, str) or not raw:
        raise HandoffBlocked("existing_private_resource_manifest_missing")
    manifest = Path(raw).expanduser()
    if not manifest.is_absolute():
        manifest = (REPO / manifest).resolve()
    if not manifest.is_file():
        raise HandoffBlocked("existing_private_resource_manifest_unavailable")
    if config_path.exists():
        raise HandoffBlocked("runtime_config_already_exists")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps({"resource_manifest": str(manifest)}, indent=2) + "\n", encoding="utf-8")
    os.chmod(config_path, 0o600)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=("init-config", "preflight", "run"), required=True)
    p.add_argument("--package", type=Path)
    p.add_argument("--config", type=Path, default=CONFIG)
    p.add_argument("--from-inputs-config", type=Path)
    args = p.parse_args()
    try:
        if args.mode == "init-config":
            if not args.from_inputs_config:
                raise HandoffBlocked("from_inputs_config_required")
            init_config(args.from_inputs_config, args.config)
            print("GDL_INTAKE_HANDOFF_RUNTIME_CONFIG=PASS")
            return 0
        if args.package is None:
            raise HandoffBlocked("package_required")
        summary = inspect_zip(args.package, args.config)
        print("GDL_INTAKE_HANDOFF_PREFLIGHT=PASS")
        print(f"JOB_COUNT={summary['jobs']} ASSET_COUNT={summary['assets']}")
        print("SOURCE_ZIP_MUTATED=false")
        if args.mode == "run":
            report = materialize_and_run(summary, args.config)
            print("GDL_INTAKE_HANDOFF=PASS_REQUIRES_VISUAL_APPROVAL")
            print("PRODUCTION_APPROVAL=false")
            print(f"JOB_COUNT={report['job_count']}")
            print("CLIENT_REVIEW_PUBLISHED=true")
            print("CLIENT_OUTPUT_SUBDIR=" + report["client_output_subdir"])
        return 0
    except Exception as exc:
        print("GDL_INTAKE_HANDOFF=BLOCKED")
        print("ERROR_CODE=" + (str(exc) if isinstance(exc, HandoffBlocked) else type(exc).__name__))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

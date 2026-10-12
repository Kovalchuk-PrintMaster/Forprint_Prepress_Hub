"""V1 Intake handoff security and routing, independent of private client resources."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
import types
import zipfile
from pathlib import Path

import pytest
import yaml

SOURCE = Path(__file__).resolve().parents[2] / "scripts/graphic_design_lab/greeting_cards/intake_handoff_runner_v0_1.py"


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@pytest.fixture
def module(monkeypatch, tmp_path):
    # Stub only imported modules; exercise the real ZIP reader, routing and safety.
    sig = types.ModuleType("app.graphic_design_lab.greeting_card_builder_input")
    sig.validate_builder_ready_bundle_v1 = lambda *a, **kw: []
    base = types.ModuleType("app.graphic_design_lab.greeting_card_constructor_bundle")
    base.compute_bundle_sha256 = lambda *a, **kw: "test-bundle-digest"
    review = types.ModuleType("scripts.graphic_design_lab.greeting_cards.full_review_runner_v0_1")
    for key, value in [
        ("app.graphic_design_lab.greeting_card_builder_input", sig),
        ("app.graphic_design_lab.greeting_card_constructor_bundle", base),
        ("scripts.graphic_design_lab.greeting_cards.full_review_runner_v0_1", review),
    ]:
        monkeypatch.setitem(sys.modules, key, value)
    spec = importlib.util.spec_from_file_location("_gdl_handoff_probe", SOURCE)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.CATALOG = tmp_path / "catalog.yaml"
    m.CATALOG.write_text("catalog_id: test\n", encoding="utf-8")
    m.RUNTIME = tmp_path / "runtime"
    return m


def inputs(tmp_path, module):
    image = b"\x89PNG\r\nTEST BYTES"  # identity test, not visual validation
    image_sha = sha(image)
    bundle = {"jobs": [{"builder_v1": {"inside_image": {
        "mode": "PORTRAIT", "accepted_artifact_ref": "accepted-photo-1",
        "asset_id": "photo-original-1", "asset_sha256": image_sha}}}],
        "provenance_manifest": {"bundle_sha256": "test-bundle-digest"}}
    bundle_bytes = yaml.safe_dump(bundle).encode()
    manifest = {"schema_version": module.ARTIFACT_SCHEMA, "artifacts": {
        "accepted-photo-1": {"source_asset_id": "photo-original-1", "path": "assets/photo.png", "sha256": image_sha}}}
    manifest_bytes = yaml.safe_dump(manifest).encode()
    header = {"schema_version": module.SCHEMA, "mode": "REVIEW_ONLY",
              "accepted_bundle_file_sha256": sha(bundle_bytes),
              "artifact_manifest_file_sha256": sha(manifest_bytes)}
    members = {"handoff_manifest.json": json.dumps(header).encode(),
               "accepted_constructor_bundle.yaml": bundle_bytes,
               "artifact_manifest.yaml": manifest_bytes,
               "assets/photo.png": image}
    resources = tmp_path / "private_resource_manifest.yaml"
    resources.write_text("schema_version: private\n", encoding="utf8")
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"resource_manifest": str(resources)}), encoding="utf8")
    return members, config


def archive(tmp_path, members):
    p = tmp_path / "gdl_intake_handoff.zip"
    with zipfile.ZipFile(p, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return p


def test_valid_zip_inspects_with_local_resource_config(module, tmp_path):
    members, config = inputs(tmp_path, module)
    report = module.inspect_zip(archive(tmp_path, members), config)
    assert report["jobs"] == 1 and report["assets"] == 1


@pytest.mark.parametrize("bad", ["../escape", "/etc/passwd", "assets/../x", "C:/x", "assets\\evil.png"])
def test_zip_slip_and_backslash_rejected(module, bad):
    with pytest.raises(module.HandoffBlocked):
        module.zip_path(bad)


def test_duplicate_archive_members_rejected(module, tmp_path):
    with zipfile.ZipFile(io.BytesIO(), "w") as zf:
        zf.writestr("assets/p.png", b"a")
        zf.writestr("assets/p.png", b"b")
        with pytest.raises(module.HandoffBlocked, match="duplicate_archive_member"):
            module.validate_inventory(zf)


def test_unreferenced_asset_rejected(module, tmp_path):
    members, config = inputs(tmp_path, module)
    members["assets/unknown.png"] = b"not referenced"
    with pytest.raises(module.HandoffBlocked, match="unreferenced_asset"):
        module.inspect_zip(archive(tmp_path, members), config)


def test_manifest_sha_tamper_rejected(module, tmp_path):
    members, config = inputs(tmp_path, module)
    members["artifact_manifest.yaml"] += b"#changed\n"
    with pytest.raises(module.HandoffBlocked, match="artifact_manifest_digest_invalid"):
        module.inspect_zip(archive(tmp_path, members), config)


def test_asset_sha_tamper_rejected(module, tmp_path):
    members, config = inputs(tmp_path, module)
    members["assets/photo.png"] = b"mismatched-image"
    with pytest.raises(module.HandoffBlocked, match="artifact_asset_sha256_mismatch"):
        module.inspect_zip(archive(tmp_path, members), config)


def test_private_config_not_stored_in_zip(module, tmp_path):
    members, config = inputs(tmp_path, module)
    config.unlink()
    with pytest.raises(module.HandoffBlocked, match="server_resource_config_missing"):
        module.inspect_zip(archive(tmp_path, members), config)


def test_unknown_untrusted_member_rejected(module, tmp_path):
    members, config = inputs(tmp_path, module)
    members["resource_manifest.yaml"] = b"cannot choose server fonts"
    with pytest.raises(module.HandoffBlocked, match="unexpected_archive_member"):
        module.inspect_zip(archive(tmp_path, members), config)


def test_only_exact_filename_accepted(module, tmp_path):
    members, config = inputs(tmp_path, module)
    p = archive(tmp_path, members)
    other = tmp_path / "arbitrary.zip"
    p.rename(other)
    with pytest.raises(module.HandoffBlocked, match="handoff_filename_or_file_invalid"):
        module.inspect_zip(other, config)


def test_bridge_preserves_existing_yaml_path():
    source = (Path(__file__).resolve().parents[2] / "scripts/graphic_design_lab/greeting_cards/smb_launcher_bridge.py").read_text()
    assert 'CONSTRUCTOR_MAKE_TARGET = "gdl-greeting-card-constructor-ingest"' in source
    assert 'INTAKE_MAKE_TARGET = "gdl-greeting-card-intake-handoff-run"' in source
    assert 'gdl_intake_handoff.zip' in source


def test_existing_renderer_is_not_modified():
    assert SOURCE.is_file()
    root = Path(__file__).resolve().parents[2]
    script = (root / "scripts/graphic_design_lab/greeting_cards/intake_handoff_runner_v0_1.py").read_text()
    assert "review.run_review(" in script
    assert "from scripts.graphic_design_lab.greeting_cards.job_runner import run_bundle" in script


def test_review_is_published_to_client_output_without_replacing_source(module, tmp_path):
    share = tmp_path / "smb"
    client = share / "client-workflow"
    client.mkdir(parents=True)
    package = client / "gdl_intake_handoff.zip"
    package.write_bytes(b"source")
    review_run = tmp_path / "runs" / "run-abc"
    (review_run / "review").mkdir(parents=True)
    (review_run / "full_card_review_PRIVATE.zip").write_bytes(b"pdf and png evidence")
    (review_run / "review/review_summary.json").write_text("{}")
    (review_run / "review/demo__r001__all_four_pages.png").write_bytes(b"preview")
    name = module.publish_client_review(package, review_run, share_root=share)
    assert name == "GDL_REVIEW_run-abc"
    result = client / "output" / name
    assert (result / "full_card_review_PRIVATE.zip").read_bytes() == b"pdf and png evidence"
    assert (result / "demo__r001__all_four_pages.png").is_file()
    assert package.read_bytes() == b"source"
    with pytest.raises(module.HandoffBlocked, match="client_review_output_collision"):
        module.publish_client_review(package, review_run, share_root=share)


def test_review_outside_allowed_share_is_rejected(module, tmp_path):
    path = tmp_path / "outside" / "gdl_intake_handoff.zip"
    path.parent.mkdir()
    path.write_bytes(b"data")
    with pytest.raises(module.HandoffBlocked, match="handoff_package_not_within_allowed_smb_share"):
        module.publish_client_review(path, tmp_path / "review", share_root=tmp_path / "smb")

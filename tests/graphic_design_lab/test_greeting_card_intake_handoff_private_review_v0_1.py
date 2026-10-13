"""Regression for opt-in local-only four-page greeting card review execution.

No real customer artifacts, SMB writes, approval, or PDF release in tests.
"""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

import pytest
import yaml

from scripts.graphic_design_lab.greeting_cards import intake_handoff_runner_v0_1 as handoff
from scripts.graphic_design_lab.greeting_cards import job_runner


def digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


@pytest.fixture
def private_case(tmp_path, monkeypatch):
    runtime = tmp_path / "tmp" / "runtime"
    monkeypatch.setattr(handoff, "REPO", tmp_path)
    monkeypatch.setattr(handoff, "RUNTIME", runtime)
    photo = b"synthetic-photo-not-an-image"
    logo = b"synthetic-logo-not-an-image"
    package = tmp_path / "gdl_intake_handoff.zip"
    artifacts = {
        "schema_version": handoff.ARTIFACT_SCHEMA,
        "artifacts": {
            "portrait-ref": {"source_asset_id": "portrait-1", "path": "assets/portrait.bin", "sha256": digest(photo)},
            "logo-ref": {"source_asset_id": "logo-1", "path": "assets/logo.bin", "sha256": digest(logo)},
        },
    }
    with zipfile.ZipFile(package, "w") as zf:
        zf.writestr("handoff_manifest.json", "{}")
        zf.writestr("accepted_constructor_bundle.yaml", "jobs: []\n")
        zf.writestr("artifact_manifest.yaml", yaml.safe_dump(artifacts))
        zf.writestr("assets/portrait.bin", photo)
        zf.writestr("assets/logo.bin", logo)

    resource = tmp_path / "private_resources.yaml"
    resource.write_text("resource: source-bound-fixture\n", encoding="utf-8")
    inspection = {"package": package, "archive_sha256": handoff.digest_file(package),
                  "resource_manifest": resource, "jobs": 1, "assets": 2}

    seen = {"builder_preflight": 0, "render": 0, "ingest": 0, "published": 0}

    def ingest(bundle_path):
        seen["ingest"] += 1
        assert bundle_path.is_file()
        assert str(bundle_path).startswith(str(runtime))

    def strict_preflight(inputs):
        seen["builder_preflight"] += 1
        assert inputs["bundle"].is_file()
        assert inputs["resource_manifest"] == resource
        resolved = yaml.safe_load(inputs["artifact_manifest"].read_text())
        assert len(resolved["artifacts"]) == 2
        for item in resolved["artifacts"].values():
            path = Path(item["path"])
            assert path.is_file() and str(path).startswith(str(runtime))
            assert handoff.digest_file(path) == item["sha256"]
        return {"verified": True}

    def render(inputs, baseline, output_root):
        seen["render"] += 1
        assert baseline == {"verified": True}
        run = output_root / "runs" / "synthetic-review-run"
        (run / "review").mkdir(parents=True)
        (run / "full_card_review_PRIVATE.zip").write_bytes(b"synthetic-review-archive")
        (run / "review" / "review_summary.json").write_text("{}", encoding="utf-8")
        return {"job_count": 1}

    def publish(*args, **kwargs):
        seen["published"] += 1
        return "GDL_REVIEW_fixture"

    monkeypatch.setattr(job_runner, "run_bundle", ingest)
    monkeypatch.setattr(handoff.review, "preflight", strict_preflight)
    monkeypatch.setattr(handoff.review, "run_review", render)
    monkeypatch.setattr(handoff, "publish_client_review", publish)
    return inspection, runtime, seen


def test_run_private_preserves_review_and_never_publishes(private_case):
    inspection, runtime, seen = private_case
    report = handoff.materialize_and_run(inspection, publish_client=False)
    assert seen == {"builder_preflight": 1, "render": 1, "ingest": 1, "published": 0}
    assert report["job_count"] == 1
    assert report["client_review_published"] is False
    assert report["client_output_subdir"] is None
    assert report["customer_approved"] is False
    assert report["production_approved"] is False
    assert report["source_zip_unchanged"] is True
    assert report["private_review_dir"].startswith("tmp/")
    assert (runtime / "results" / "runs" / "synthetic-review-run" /
            "full_card_review_PRIVATE.zip").is_file()
    saved = list((runtime / "runs").glob("*/handoff_result.json"))
    assert len(saved) == 1
    assert json.loads(saved[0].read_text())["client_review_published"] is False
    assert handoff.digest_file(inspection["package"]) == inspection["archive_sha256"]


def test_legacy_run_keeps_explicit_publication_behavior(private_case):
    inspection, _, seen = private_case
    report = handoff.materialize_and_run(inspection)
    assert seen["published"] == 1
    assert report["client_review_published"] is True
    assert report["client_output_subdir"] == "output/GDL_REVIEW_fixture"


def test_private_mode_requires_actual_review_archive(private_case, monkeypatch):
    inspection, _, seen = private_case

    def no_artifacts(inputs, baseline, output_root):
        folder = output_root / "runs" / "synthetic-missing-run"
        folder.mkdir(parents=True)
        return {"job_count": 1}

    monkeypatch.setattr(handoff.review, "run_review", no_artifacts)
    with pytest.raises(handoff.HandoffBlocked, match="private_review_artifacts_missing"):
        handoff.materialize_and_run(inspection, publish_client=False)
    assert seen["published"] == 0


def test_cli_run_private_routes_without_publishing(monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(handoff, "inspect_zip", lambda *a: {"jobs": 1, "assets": 2})

    def fake_run(summary, config, *, publish_client=True):
        seen.append(publish_client)
        return {"job_count": 1, "private_review_dir": "tmp/local-run",
                "private_review_archive": "tmp/local-run/review.zip",
                "client_output_subdir": "output/legacy"}

    monkeypatch.setattr(handoff, "materialize_and_run", fake_run)
    monkeypatch.setattr(sys, "argv", ["gdl", "--mode", "run-private", "--package", "fixture.zip"])
    assert handoff.main() == 0
    assert seen == [False]
    out = capsys.readouterr().out
    assert "CLIENT_REVIEW_PUBLISHED=false" in out
    assert "PRIVATE_REVIEW_ARCHIVE=tmp/local-run/review.zip" in out
    assert "CLIENT_OUTPUT_SUBDIR" not in out
    assert "PRODUCTION_APPROVAL=false" in out


def test_cli_standard_run_remains_publishing(monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(handoff, "inspect_zip", lambda *a: {"jobs": 1, "assets": 2})

    def fake_run(summary, config, *, publish_client=True):
        seen.append(publish_client)
        return {"job_count": 1, "client_output_subdir": "output/legacy"}

    monkeypatch.setattr(handoff, "materialize_and_run", fake_run)
    monkeypatch.setattr(sys, "argv", ["gdl", "--mode", "run", "--package", "fixture.zip"])
    assert handoff.main() == 0
    assert seen == [True]
    assert "CLIENT_REVIEW_PUBLISHED=true" in capsys.readouterr().out

"""Synthetic two-job Full Review integration gate; no client files or approvals.

The mocked Builder generates distinct real 4-page PDFs and raster previews;
the actual project Full Review Runner must collect, verify, and package them.
This verifies batch orchestration, NOT real-builder render fidelity.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pymupdf
import pytest
import yaml
from PIL import Image

from app.graphic_design_lab import greeting_card_builder_renderer as renderer
from scripts.graphic_design_lab.greeting_cards import full_review_runner_v0_1 as review


JOBS = [
    {"job_id": "gdl-synthetic-batch-a", "revision": "r001", "signature": "GRIGO"},
    {"job_id": "gdl-synthetic-batch-b", "revision": "r002", "signature": "HERASYMENKO"},
]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def batch_inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # All inputs and output locations belong to pytest's disposable tmp_path.
    paths = {
        "bundle": tmp_path / "accepted_synthetic_batch.yaml",
        "resource_manifest": tmp_path / "synthetic_resources.yaml",
        "artifact_manifest": tmp_path / "synthetic_artifacts.yaml",
    }
    payload = {
        "synthetic_fixture_only": True,
        "jobs": [
            {"job_id": j["job_id"], "builder_v1": {
                "revision": j["revision"],
                "sender_text": {"signature_variant_id": j["signature"]},
            }}
            for j in JOBS
        ],
    }
    paths["bundle"].write_text(yaml.safe_dump(payload), encoding="utf-8")
    paths["resource_manifest"].write_text("synthetic: true\n", encoding="utf-8")
    paths["artifact_manifest"].write_text("synthetic: true\n", encoding="utf-8")
    catalog = tmp_path / "synthetic_signature_catalog.yaml"
    catalog.write_text("synthetic: true\n", encoding="utf-8")
    monkeypatch.setattr(review, "CATALOG", catalog)
    monkeypatch.setattr(review, "ROOT", tmp_path)
    fingerprints = {k: _sha(p) for k, p in paths.items()}
    fingerprints["signature_catalog"] = _sha(catalog)
    baseline = {
        "jobs": payload["jobs"],
        "stems": tuple(sorted(f'{j["job_id"]}__{j["revision"]}' for j in JOBS)),
        "variants": tuple(j["signature"] for j in JOBS),
        "fingerprints": fingerprints,
        "synthetic": True,
    }
    return paths, baseline, tmp_path / "tmp" / "batch_reviews"


def _fake_builder(monkeypatch: pytest.MonkeyPatch, *,
                  missing_report: bool = False,
                  corrupt_preview: bool = False,
                  wrong_job_set: bool = False):
    def build_bundle(*, bundle_path: Path, resource_manifest_path: Path,
                     artifact_manifest_path: Path, signature_catalog_path: Path,
                     output_dir: Path):
        # The mock only replaces the Renderer. The real Full Review collection,
        # PDF<->PNG pixel checks, job identity checks, and ZIP writer run normally.
        assert bundle_path.is_file()
        assert resource_manifest_path.is_file()
        assert artifact_manifest_path.is_file()
        assert signature_catalog_path.is_file()
        rendered = []
        for idx, job in enumerate(JOBS):
            stem = f'{job["job_id"]}__{job["revision"]}'
            completed = output_dir / "completed"
            preview_dir = output_dir / "preview"
            report_dir = output_dir / "report"
            for directory in (completed, preview_dir, report_dir):
                directory.mkdir(parents=True, exist_ok=True)
            pdf = completed / (stem + ".pdf")
            with pymupdf.open() as doc:
                for page_index in range(4):
                    page = doc.new_page(width=300, height=400)
                    page.insert_text((25, 50), f'{job["job_id"]} PAGE {page_index + 1}')
                doc.save(pdf)
            with pymupdf.open(pdf) as doc:
                for page_index, page in enumerate(doc, start=1):
                    destination = preview_dir / f'{stem}__{page_index:02}.png'
                    page.get_pixmap(matrix=pymupdf.Matrix(
                        renderer.PREVIEW_DPI / 72, renderer.PREVIEW_DPI / 72
                    ), alpha=False).save(destination)
            if corrupt_preview and idx == 1:
                # Fail only the second job; first remains a valid candidate.
                target = preview_dir / f"{stem}__01.png"
                with Image.open(target) as original:
                    Image.new("RGB", original.size, "white").save(target)
            if not (missing_report and idx == 1):
                (report_dir / (stem + ".json")).write_text(json.dumps({
                    "job_id": job["job_id"], "revision": job["revision"],
                    "signature_variant": job["signature"],
                    "production_ready": False,
                }), encoding="utf-8")
            rendered.append({"job_id": job["job_id"],
                             "revision": job["revision"]})
        (output_dir / "builder_run_report.json").write_text(json.dumps({
            "job_count": len(JOBS),
            "production_ready": False,
        }), encoding="utf-8")
        return {"jobs": rendered[:1] if wrong_job_set else rendered}

    monkeypatch.setattr(renderer, "build_bundle", build_bundle)


def test_synthetic_two_job_review_exact_identity_and_archive(batch_inputs, monkeypatch):
    inputs, baseline, output = batch_inputs
    assert review._review_root(output) == output.resolve()
    _fake_builder(monkeypatch)
    summary = review.run_review(inputs, baseline, output)
    assert summary["job_count"] == summary["pdf_count"] == 2
    assert summary["png_preview_count"] == 8
    assert summary["pdf_preview_pixel_replay"] == "PASS"
    assert summary["synthetic_fixture"] is True
    assert summary["customer_approved"] is False
    assert summary["production_approved"] is False
    assert summary["dual_runtime_activated_by_this_runner"] is False
    assert summary["git_or_source_modified_by_this_runner"] is False
    assert {j["job_id"] for j in summary["jobs"]} == {j["job_id"] for j in JOBS}
    assert all(j["page_count"] == j["preview_count"] == 4 for j in summary["jobs"])
    assert all(j["preview_pixel_replay"] == "PASS" for j in summary["jobs"])
    assert len({j["pdf_sha256"] for j in summary["jobs"]}) == 2
    run_dirs = list((output / "runs").iterdir())
    assert len(run_dirs) == 1
    run = run_dirs[0]
    zip_path = run / "full_card_review_PRIVATE.zip"
    assert zip_path.is_file()
    expected = {"review/review_summary.json", "builder_outputs_PRIVATE/builder_run_report.json"}
    for job in JOBS:
        stem = f'{job["job_id"]}__{job["revision"]}'
        expected.add(f"builder_outputs_PRIVATE/completed/{stem}.pdf")
        expected.add(f"builder_outputs_PRIVATE/report/{stem}.json")
        expected.add(f"review/{stem}__all_four_pages.png")
        expected.update(f"builder_outputs_PRIVATE/preview/{stem}__{i:02}.png" for i in range(1, 5))
        with pymupdf.open(run / "builder_outputs_PRIVATE" / "completed" / f"{stem}.pdf") as doc:
            assert doc.page_count == 4
            assert all(job["job_id"] in page.get_text() for page in doc)
            assert all(other["job_id"] not in page.get_text()
                       for other in JOBS if other != job for page in doc)
    with zipfile.ZipFile(zip_path) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == expected
    assert not (run / "output").exists()


@pytest.mark.parametrize(("failure", "expected_error"), [
    ("missing_report", "builder_job_report_missing"),
    ("corrupt_preview", "pdf_png_pixel_replay_mismatch_page_1"),
    ("wrong_job_set", "rendered_job_count_invalid"),
])
def test_synthetic_batch_fails_closed(batch_inputs, monkeypatch, failure, expected_error):
    inputs, baseline, output = batch_inputs
    _fake_builder(monkeypatch, **{failure: True})
    with pytest.raises(review.ReviewBlocked, match=expected_error):
        review.run_review(inputs, baseline, output)
    assert not list((output / "runs").glob("*/full_card_review_PRIVATE.zip"))


def test_batch_source_immutability_gate(batch_inputs):
    inputs, baseline, _ = batch_inputs
    review.check_source_unchanged(inputs, baseline["fingerprints"])
    inputs["bundle"].write_text("tampered: true\n", encoding="utf-8")
    with pytest.raises(review.ReviewBlocked, match="input_files_changed_during_review_run"):
        review.check_source_unchanged(inputs, baseline["fingerprints"])


def test_duplicate_stem_rejected_before_builder(batch_inputs, monkeypatch):
    inputs, _, _ = batch_inputs
    data = yaml.safe_load(inputs["bundle"].read_text(encoding="utf-8"))
    data["jobs"][1]["job_id"] = data["jobs"][0]["job_id"]
    data["jobs"][1]["builder_v1"]["revision"] = data["jobs"][0]["builder_v1"]["revision"]
    inputs["bundle"].write_text(yaml.safe_dump(data), encoding="utf-8")
    from app.graphic_design_lab import greeting_card_builder_input as builder_input
    monkeypatch.setattr(builder_input, "validate_builder_ready_bundle_v1",
                        lambda bundle, *, signature_catalog: [])
    with pytest.raises(review.ReviewBlocked, match="duplicate_output_stem"):
        review.preflight(inputs)

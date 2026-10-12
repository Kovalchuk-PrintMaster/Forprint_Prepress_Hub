"""GC09 full four-page review runner: pure checks, no private input needed."""
import json
from pathlib import Path

import pymupdf
import pytest
from PIL import Image

from scripts.graphic_design_lab.greeting_cards.full_review_runner_v0_1 import (
    ReviewBlocked, _review_root, contact_sheet, inputs_from_config,
    package_review, verify_one,
)


def test_exact_four_pages_and_pixels_from_final_pdf(tmp_path):
    pdf = tmp_path / "review.pdf"
    doc = pymupdf.open()
    for i in range(4):
        page = doc.new_page(width=210, height=297)
        page.insert_text((40, 80), f"PAGE_{i+1}")
    doc.save(pdf)
    doc.close()
    preview = []
    with pymupdf.open(pdf) as d:
        for i, p in enumerate(d):
            path = tmp_path / f"page_{i + 1}.png"
            p.get_pixmap(matrix=pymupdf.Matrix(120 / 72, 120 / 72), alpha=False).save(str(path))
            preview.append(path)
    info = verify_one(pdf, preview)
    assert info["preview_pixel_replay"] == "PASS"
    assert info["page_count"] == info["preview_count"] == 4
    sheet = tmp_path / "review" / "sheet.png"
    contact_sheet(preview, sheet)
    with Image.open(sheet) as result:
        assert result.width > 1000
    with Image.open(preview[0]) as bad:
        bad.convert("RGB").save(preview[1])
    with pytest.raises(ReviewBlocked, match="pixel_replay_mismatch"):
        verify_one(pdf, preview)


def test_incomplete_pdf_rejected(tmp_path):
    pdf = tmp_path / "only_three.pdf"
    d = pymupdf.open()
    for _ in range(3):
        d.new_page()
    d.save(pdf)
    d.close()
    previews = [tmp_path / f"{i}.png" for i in range(4)]
    for p in previews:
        Image.new("RGB", (5, 5), "white").save(p)
    with pytest.raises(ReviewBlocked, match="four_pages"):
        verify_one(pdf, previews)


def test_inputs_configuration_fail_closed(tmp_path):
    conf = tmp_path / "config.json"
    conf.write_text(json.dumps({"bundle": "/private/nope"}), encoding="utf-8")
    with pytest.raises(ReviewBlocked, match="config_keys_invalid"):
        inputs_from_config(conf)


def test_review_archive_paths_must_be_inside_run(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    local = run / "internal.txt"
    local.write_text("internal", encoding="utf-8")
    archive = package_review(run, [local])
    assert archive.exists()
    outside = tmp_path / "outside.txt"
    outside.write_text("nope", encoding="utf-8")
    with pytest.raises(ReviewBlocked, match="outside_review_run"):
        package_review(run, [outside])


def test_tmp_only_guard(tmp_path):
    # ROOT is an actual repository path, never accidentally write outside tmp.
    with pytest.raises(ReviewBlocked, match="inside_repository_tmp"):
        _review_root(tmp_path / "wrong_place")

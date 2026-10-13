"""GC09 DUAL Page4 candidate fail-closed unit tests (no private customer data)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.graphic_design_lab import greeting_card_dual_page4_candidate_v0_1 as page4


def _line(text: str, y_mm: float) -> dict:
    pt_y = y_mm / page4.MM_PER_PT
    return {
        "bbox": (20, pt_y, 200, pt_y + 10),
        "spans": [{"text": text, "origin": (20, pt_y + 5), "size": 12, "color": 0}],
    }


def test_canonical_rows_separate_greeting_and_sender_without_rewriting():
    page = MagicMock()
    page.get_text.return_value = {
        "blocks": [
            {"type": 0, "bbox": (0, 60, 200, 80), "lines": [_line("Real source greeting", 30)]},
            {"type": 1, "bbox": (0, 100, 200, 120)},
            {"type": 0, "bbox": (0, 215 / page4.MM_PER_PT, 200, 900), "lines": [_line("Signer", 215)]},
        ]
    }
    greeting, sender = page4.canonical_rows(page)
    assert [s["text"] for s in greeting] == ["Real source greeting"]
    assert [s["text"] for s in sender] == ["Signer"]
    assert greeting[0]["spans"][0]["origin"] == (20, 30 / page4.MM_PER_PT + 5)


def _test_sender():
    rows = []
    for index in range(6):
        rows.append({
            "text": "sender_" + str(index),
            "bbox_mm": [31, 220 + index * 7, 95, 225 + index * 7],
            "spans": [{"text": "sender_" + str(index), "origin": (31, 600), "size": 12}],
        })
    registry = {
        "texts": [item["text"] for item in rows],
        "bboxes_pdf_mm": [item["bbox_mm"] for item in rows],
        "text_sha256": hashlib.sha256("\n".join(item["text"] for item in rows).encode()).hexdigest(),
    }
    return rows, registry


def test_exact_six_sender_rows_success_and_no_source_mutation():
    sender, registry = _test_sender()
    greeting = [{"spans": [{"text": "hello", "origin": (40, 60), "size": 20}], "text": "hello"}]
    result = page4.validate_canonical_text_rows(greeting, sender, registry)
    assert result["sender_line_count"] == 6
    assert result["greeting_line_count"] == 1
    assert result["sender_text_sha256"] == registry["text_sha256"]


@pytest.mark.parametrize("mode", ["missing", "wrong_text", "wrong_bbox", "wrong_hash", "missing_origin", "missing_greeting"])
def test_sender_rows_and_greeting_fail_closed(mode):
    sender, registry = _test_sender()
    greeting = [{"spans": [{"text": "hi", "origin": (40, 60), "size": 20}], "text": "hi"}]
    if mode == "missing":
        sender.pop()
    elif mode == "wrong_text":
        sender[0] = {**sender[0], "text": "Tampered"}
    elif mode == "wrong_bbox":
        sender[0] = {**sender[0], "bbox_mm": [0, 0, 1, 1]}
    elif mode == "wrong_hash":
        registry["text_sha256"] = "0" * 64
    elif mode == "missing_origin":
        sender[0] = {**sender[0], "spans": [{"text": "x", "size": 12}]}
    elif mode == "missing_greeting":
        greeting.clear()
    with pytest.raises(ValueError):
        page4.validate_canonical_text_rows(greeting, sender, registry)


def _prior_proof(tmp_path: Path):
    source_hash, component_hash = "a" * 64, "b" * 64
    pdf = tmp_path / page4.ISOLATED_PDF
    pdf.write_bytes(b"PDF_BYTES_TEST_ONLY")
    png = tmp_path / "DUAL_COMPONENT_ONLY_NOT_FULL_CARD.png"
    png.write_bytes(b"PNG_BYTES_TEST_ONLY")
    report = {
        "status": "ISOLATED_DUAL_COMPONENT_CANDIDATE_NOT_BUILDER_OUTPUT",
        "source_pdf_sha256": source_hash,
        "source_signature_component_sha256": component_hash,
        "component_count": 2,
        "source_grigo_vectors": 7,
        "output": {"output_vector_count": 7, "output_soft_mask": "PASS", "output_native_vector_sha256": "c" * 64,
                   "output_rgba_pixel_sha256": "d" * 64},
        "canonical_sender_source": {"status": "PASS"},
        "source_signature_sender_overlap": {"status": "TRANSPARENT_REGION"},
        "proof_pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        "proof_png_sha256": hashlib.sha256(png.read_bytes()).hexdigest(),
        "dual_runtime_enabled": False,
        "production_ready": False,
        "customer_approved": False,
        "client_published": False,
        "has_full_card_layout": False,
        "sender_text_rendered_in_proof": False,
    }
    report_path = tmp_path / page4.PROOF_REPORT
    report_path.write_text(json.dumps(report), encoding="utf-8")
    return report_path, report, source_hash, component_hash


def test_prior_proof_requires_artifact_sha_and_authority_flags(tmp_path):
    report_path, report, src, component = _prior_proof(tmp_path)
    assert page4.checked_prior_proof(report_path, src, component) == report
    with pytest.raises(ValueError, match="source_identity"):
        page4.checked_prior_proof(report_path, src, "f" * 64)
    (tmp_path / page4.ISOLATED_PDF).write_bytes(b"MUTATED")
    with pytest.raises(ValueError, match="pdf_identity"):
        page4.checked_prior_proof(report_path, src, component)


def test_prior_proof_does_not_accept_client_release(tmp_path):
    report_path, report, src, component = _prior_proof(tmp_path)
    report["client_published"] = True
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="authority"):
        page4.checked_prior_proof(report_path, src, component)


def test_prior_proof_does_not_accept_missing_digest(tmp_path):
    report_path, report, src, component = _prior_proof(tmp_path)
    report["output"]["output_native_vector_sha256"] = "bad"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="vector_digest"):
        page4.checked_prior_proof(report_path, src, component)


def test_page4_candidate_not_builder_activation():
    path = page4.ROOT if hasattr(page4, "ROOT") else Path(__file__).resolve().parents[2]
    import yaml
    registry = yaml.safe_load((path / "coordination/graphic_design_lab/directions/greeting_cards/signature_registry_v0_1.yaml").read_text())
    assert registry["variants"]["DUAL_GRIGO_HERASYMENKO"]["runtime_enabled"] is False
    assert registry["variants"]["DUAL_GRIGO_HERASYMENKO"]["renderer_adapter"] is None
    assert page4.PROOF_PDF.endswith("NOT_FULL_CARD.pdf")

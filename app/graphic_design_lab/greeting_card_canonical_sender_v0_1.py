"""Exact source-PDF-owned sender text, independent of Intake text fields.

The immutable resource SHA256 is first verified by the existing private-resource
resolver. This module additionally verifies the exact extracted line contents
and three-decimal PDF-mm geometry before drawing with the same font at the
source's original span origins. The signature artwork itself is untouched.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pymupdf

MM_PER_PT = 25.4 / 72.0
SENDER_THRESHOLD_MM = 198.0  # extraction only, not a placement policy
REGISTRY_PATH = (Path(__file__).resolve().parents[2] / "coordination" / "graphic_design_lab"
                 / "directions" / "greeting_cards" / "canonical_sender_blocks_v0_1.yaml")


def _expected_for_variant(variant_id: str) -> dict[str, Any]:
    import yaml
    doc = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or doc.get("schema_version") != "gdl_greeting_card_canonical_sender_blocks_v0_1":
        raise ValueError("canonical_sender_registry_invalid")
    if variant_id == "DUAL_GRIGO_HERASYMENKO":
        raise ValueError("canonical_sender_dual_runtime_disabled")
    variants = doc.get("variants")
    if not isinstance(variants, dict) or variant_id not in variants:
        raise ValueError("unknown_canonical_sender_variant:" + str(variant_id))
    row = variants[variant_id]
    if not isinstance(row, dict) or len(row.get("texts", [])) != len(row.get("bboxes_pdf_mm", [])):
        raise ValueError("canonical_sender_registry_variant_invalid")
    return row


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def source_sender_rows(variant_id: str, source_path: Path) -> list[dict[str, Any]]:
    """Fail closed unless source text and its geometry match the frozen audit."""
    expected = _expected_for_variant(variant_id)
    if _sha256_file(source_path) != expected["source_sha256"]:
        raise ValueError("canonical_sender_source_sha256_mismatch:" + variant_id)
    rows: list[dict[str, Any]] = []
    with pymupdf.open(source_path) as doc:
        if len(doc) != 4:
            raise ValueError("canonical_sender_source_page_count_mismatch")
        page = doc[3]
        if not (abs(page.rect.width * MM_PER_PT - 214) < .7
                and abs(page.rect.height * MM_PER_PT - 301) < .7):
            raise ValueError("canonical_sender_source_page_size_mismatch")
        for block in page.get_text("dict", sort=True).get("blocks", []):
            if block.get("type") != 0 or block["bbox"][1] * MM_PER_PT < SENDER_THRESHOLD_MM:
                continue
            for line in block.get("lines", []):
                spans = [s for s in line.get("spans", []) if str(s.get("text", "")).strip()]
                text = "".join(str(s.get("text", "")) for s in spans).strip()
                if not text:
                    continue
                rows.append({
                    "id": f"canonical_sender_{len(rows) + 1:02d}",
                    "text": text,
                    "bbox_pdf_mm": [round(float(n) * MM_PER_PT, 3) for n in line["bbox"]],
                    "spans": [dict(s) for s in spans],
                })
    actual_texts = [row["text"] for row in rows]
    if actual_texts != expected["texts"]:
        raise ValueError("canonical_sender_source_text_mismatch:" + variant_id)
    if [row["bbox_pdf_mm"] for row in rows] != expected["bboxes_pdf_mm"]:
        raise ValueError("canonical_sender_source_geometry_mismatch:" + variant_id)
    if hashlib.sha256("\n".join(actual_texts).encode("utf-8")).hexdigest() != expected["text_sha256"]:
        raise ValueError("canonical_sender_text_digest_mismatch:" + variant_id)
    if any(not row["spans"] for row in rows):
        raise ValueError("canonical_sender_spans_missing:" + variant_id)
    return rows


def render_source_sender_text(page: pymupdf.Page, rows: list[dict[str, Any]], *, font_path: Path) -> None:
    """Text-only native spans at original PDF baselines; no hidden template paths."""
    for row in rows:
        for s in row["spans"]:
            color = int(s["color"])
            rgb = (((color >> 16) & 255) / 255.0,
                   ((color >> 8) & 255) / 255.0,
                   (color & 255) / 255.0)
            origin = s["origin"]
            if len(origin) != 2 or float(s["size"]) <= 0:
                raise ValueError("canonical_sender_span_geometry_invalid")
            page.insert_text(
                pymupdf.Point(float(origin[0]), float(origin[1])),
                str(s["text"]),
                fontname="ZapfChanceryC",
                fontfile=str(font_path),
                fontsize=float(s["size"]),
                color=rgb,
                overlay=True,
            )

#!/usr/bin/env python3
"""GDL sender-zone plan: read-only contract and optional exact-font test.

No client text is logged; source locked renderer remains authoritative.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from app.graphic_design_lab.greeting_card_sender_zone_planner_v0_1 import (
    SenderZoneBlocked, candidate_v03_slots, source_locked_slots,
)

ZONES = ROOT / "coordination/graphic_design_lab/directions/greeting_cards/geometry_zones_v0_1.yaml"
OUT = ROOT / "tmp/gdl_sender_container_plan_v0_1/sanitized_plan.json"


def collect() -> dict:
    data = yaml.safe_load(ZONES.read_text(encoding="utf-8"))
    profiles = data["pages"]["physical_4"]["signature_profiles_candidate_v0_3"]
    scenarios = []
    for variant in ("GRIGO", "HERASYMENKO", "DUAL_GRIGO_HERASYMENKO"):
        for n in (2, 3, 6):
            ids = [f"sender_role_{i}" for i in range(n)]
            legacy = source_locked_slots(ids, start_y_pdf_mm=214.0)
            try:
                proposed = candidate_v03_slots(ids, variant=variant, profile=profiles[variant])
                status, code = "GEOMETRY_FITS", None
            except SenderZoneBlocked as exc:
                proposed = ()
                status, code = "BLOCKED", str(exc)
            scenarios.append({
                "variant": variant,
                "sender_line_count": n,
                "source_locked_slot_count": len(legacy),
                "candidate_slot_count": len(proposed),
                "candidate_geometry": status,
                "error_code": code,
                "font_fit_verified": False,
                "visible_ink_collision_verified": False,
                "runtime_profile_activated": False,
            })
    if len(scenarios) != 9:
        raise ValueError("sender_plan_scenario_count_invalid")
    return {
        "schema_version": "gdl_sender_container_plan_v0_1",
        "status": "PASS_REQUIRES_FONT_AND_VISUAL_PROOF",
        "scenarios": scenarios,
        "source_locked_runtime_preserved": True,
        "candidate_runtime_activated": False,
        "dual_runtime_enabled": False,
        "customer_acceptance": False,
    }


def bbox_excess_mm(glyph_bboxes_pt: list, zone_pdf_mm: list | tuple, *, pt_per_mm: float) -> dict:
    """Conservative PDF glyph-metric envelope versus one complete design zone.

    Glyph BBoxes are not visible ink contours. Values are millimetres outside
    each zone side. This helper is pure and never stores the source text.
    """
    if len(zone_pdf_mm) != 4 or pt_per_mm <= 0:
        raise ValueError("sender_zone_invalid_geometry")
    if not glyph_bboxes_pt:
        return {"has_glyphs": False, "inside": False,
                "outside_mm": {k: None for k in ("left", "top", "right", "bottom")}}
    x0 = min(float(q[0]) / pt_per_mm for q in glyph_bboxes_pt)
    y0 = min(float(q[1]) / pt_per_mm for q in glyph_bboxes_pt)
    x1 = max(float(q[2]) / pt_per_mm for q in glyph_bboxes_pt)
    y1 = max(float(q[3]) / pt_per_mm for q in glyph_bboxes_pt)
    left, top, right, bottom = (float(v) for v in zone_pdf_mm)
    outside = {
        "left": round(max(0.0, left - x0), 4),
        "top": round(max(0.0, top - y0), 4),
        "right": round(max(0.0, x1 - right), 4),
        "bottom": round(max(0.0, y1 - bottom), 4),
    }
    return {"has_glyphs": True,
            "inside": all(v <= 0.0004 for v in outside.values()),
            "outside_mm": outside}


def candidate_container_bbox_pdf_mm(profile: dict) -> tuple[float, float, float, float]:
    """Convert operator centre/size in trim coordinates into PDF+2mm bleed."""
    x, y = (float(q) for q in profile["sender_text_center_trim_mm"])
    w, h = (float(q) for q in profile["sender_text_size_mm"])
    if w <= 0 or h <= 0:
        raise ValueError("sender_container_invalid_size")
    return (x - w / 2 + 2.0, y - h / 2 + 2.0,
            x + w / 2 + 2.0, y + h / 2 + 2.0)


def font_proof(result: dict) -> None:
    """Use exact Builder font, never persist names/text/private locations."""
    import pymupdf
    from app.graphic_design_lab import greeting_card_builder_renderer as renderer
    from scripts.validation.gdl_greeting_card_variability_probe_v0_1 import (
        DEFAULT_CONFIG, SENDER_LINES, resolve_exact_greeting_font,
    )

    font_path = resolve_exact_greeting_font(DEFAULT_CONFIG)
    profiles = yaml.safe_load(ZONES.read_text(encoding="utf-8"))["pages"]["physical_4"]["signature_profiles_candidate_v0_3"]
    source_signature_pdf_mm = profiles["HERASYMENKO"]["source_signature_bbox_trim_mm"]
    source_signature_pdf_mm = [v + 2.0 for v in source_signature_pdf_mm]
    full_candidate_pdf_mm = candidate_container_bbox_pdf_mm(profiles["HERASYMENKO"])
    to_run = {2, 3}
    proofs = []
    for count in sorted(to_run):
        lines = SENDER_LINES[:count]
        slots = candidate_v03_slots([line["id"] for line in lines], variant="HERASYMENKO", profile=profiles["HERASYMENKO"])
        outcomes = []
        all_glyph_bboxes_pt = []
        for raw, slot in zip(lines, slots):
            doc = pymupdf.open()
            try:
                page = doc.new_page(width=214 * renderer.PT_PER_MM, height=301 * renderer.PT_PER_MM)
                rect = renderer._rect_mm(slot.bbox_pdf_mm)
                try:
                    renderer._insert_textbox_exact(
                        page, rect, raw["text"], font_path=font_path, fontname="ZapfChanceryC",
                        fontsize=renderer._sender_font_size(raw["id"]), align=pymupdf.TEXT_ALIGN_LEFT,
                        lineheight=1.0,
                    )
                    text_fits = True
                except ValueError:
                    text_fits = False
                chars = []
                for block in page.get_text("rawdict").get("blocks", []):
                    if block.get("type") != 0:
                        continue
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            chars.extend(char["bbox"] for char in span.get("chars", []) if "bbox" in char)
                # Per-slot is a typography metric, NOT the full container gate.
                slot_envelope = bbox_excess_mm(
                    chars, slot.bbox_pdf_mm, pt_per_mm=renderer.PT_PER_MM,
                )
                container_envelope = bbox_excess_mm(
                    chars, full_candidate_pdf_mm, pt_per_mm=renderer.PT_PER_MM,
                )
                all_glyph_bboxes_pt.extend(chars)
                # Glyph rectangles, not ink contours. Require conservative non-overlap.
                source_rect = renderer._rect_mm(source_signature_pdf_mm)
                overlaps = any(renderer.pymupdf.Rect(g).intersects(source_rect) for g in chars)
                bbox = renderer.pymupdf.Rect()
                for g in chars:
                    bbox |= renderer.pymupdf.Rect(g)
                glyphs_inside = bool(chars) and (
                    bbox.x0 >= rect.x0 - 0.001 and bbox.y0 >= rect.y0 - 0.001
                    and bbox.x1 <= rect.x1 + 0.001 and bbox.y1 <= rect.y1 + 0.001
                )
                outcomes.append({
                    "line_id": raw["id"], "font_textbox_fit": text_fits,
                    "glyph_bboxes_inside_slot": glyphs_inside,
                    "glyph_bbox_overlaps_source_signature_bbox": overlaps,
                    "glyph_count": len(chars),
                    "glyph_metric_excess_slot_mm": slot_envelope["outside_mm"],
                    "glyph_metric_excess_full_container_mm": container_envelope["outside_mm"],
                    "glyph_bboxes_inside_full_container": container_envelope["inside"],
                })
            finally:
                doc.close()
        aggregate_container_envelope = bbox_excess_mm(
            all_glyph_bboxes_pt, full_candidate_pdf_mm,
            pt_per_mm=renderer.PT_PER_MM,
        )
        proofs.append({
            "variant": "HERASYMENKO", "line_count": count,
            "all_glyph_bboxes_inside_full_container": aggregate_container_envelope["inside"],
            "whole_block_glyph_metric_excess_container_mm": aggregate_container_envelope["outside_mm"],
            "accepted_font_loaded": True,
            "all_lines_fit_exact_font": all(q["font_textbox_fit"] for q in outcomes),
            "all_glyphs_inside_rect": all(q["glyph_bboxes_inside_slot"] for q in outcomes),
            "no_rectangular_signature_overlap": all(not q["glyph_bbox_overlaps_source_signature_bbox"] for q in outcomes),
            "lines": outcomes,
            "real_ink_collision_proved": False,
        })
    result["font_probe"] = proofs
    result["font_probe_completed"] = True
    result["font_probe_geometry_basis"] = (
        "PDF_EXTRACTED_GLYPH_METRIC_BBOX_NOT_VISIBLE_INK;"
        "PER_LINE_SLOT_VS_COMPLETE_CANDIDATE_CONTAINER"
    )
    result["candidate_whole_container_status"] = (
        "WHOLE_CONTAINER_GLYPH_BBOX_PASS_VISUAL_REVIEW_REQUIRED"
        if all(p["all_lines_fit_exact_font"]
               and p["all_glyph_bboxes_inside_full_container"]
               and p["no_rectangular_signature_overlap"] for p in proofs)
        else "WHOLE_CONTAINER_GLYPH_BBOX_REVIEW_REQUIRED"
    )
    # Preserve the old slot-level status as legacy evidence; do not silently
    # promote candidate to accepted runtime, or overwrite an existing report key.
    result["candidate_font_fit_status"] = (
        "CANDIDATE_FONT_GEOMETRY_PASS_VISUAL_REVIEW_REQUIRED"
        if all(p["all_lines_fit_exact_font"] and p["all_glyphs_inside_rect"]
               and p["no_rectangular_signature_overlap"] for p in proofs)
        else "CANDIDATE_FONT_GEOMETRY_REVIEW_REQUIRED"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["contract", "font"], required=True)
    args = ap.parse_args()
    try:
        result = collect()
        if args.mode == "font":
            font_proof(result)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        for row in result["scenarios"]:
            print("PROFILE="+row["variant"]+
                  " LINES="+str(row["sender_line_count"])+
                  " CANDIDATE="+row["candidate_geometry"]+
                  (" REASON="+row["error_code"] if row["error_code"] else ""))
        if args.mode == "font":
            print("FONT_STATUS=" + result["candidate_font_fit_status"])
            print("WHOLE_CONTAINER_STATUS=" + result["candidate_whole_container_status"])
            for proof in result["font_probe"]:
                print("LINES=" + str(proof["line_count"]) +
                      " ALL_GLYPHS_IN_FULL_CONTAINER=" +
                      str(proof["all_glyph_bboxes_inside_full_container"]) +
                      " CONTAINER_EXCESS_MM=" +
                      json.dumps(proof["whole_block_glyph_metric_excess_container_mm"],
                                 sort_keys=True, separators=(",", ":")))
        print("REPORT=tmp/gdl_sender_container_plan_v0_1/sanitized_plan.json")
        print("GDL_SENDER_CONTAINER_PLAN=PASS_REQUIRES_FONT_AND_VISUAL_PROOF")
        return 0
    except Exception as exc:
        print("GDL_SENDER_CONTAINER_PLAN=BLOCKED")
        print("ERROR_CLASS="+type(exc).__name__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

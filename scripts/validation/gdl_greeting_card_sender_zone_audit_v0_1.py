#!/usr/bin/env python3
"""GDL sender zones: non-mutating candidate-vs-source and PDF text bounds audit.

No runtime activation, source reflow, secret dumping or acceptance/promotion.
Print sanitized structural evidence; detailed geometry to ignored tmp/ only.
"""
from __future__ import annotations

import argparse
import ast
import json
import math
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
ZONE_FILE = ROOT / "coordination/graphic_design_lab/directions/greeting_cards/geometry_zones_v0_1.yaml"
EMBEDDED = ROOT / "app/graphic_design_lab/greeting_card_embedded_components.py"
RENDERER = ROOT / "app/graphic_design_lab/greeting_card_builder_renderer.py"
OUT = ROOT / "tmp/gdl_sender_zone_audit_v0_1/sanitized_report.json"
MM_PER_PT = 25.4 / 72
BLEED_MM = 2.0
VARIANTS = ("GRIGO", "HERASYMENKO", "DUAL_GRIGO_HERASYMENKO")


def bbox_from_center(center: list[float], size: list[float]) -> list[float]:
    if len(center) != 2 or len(size) != 2 or any(not math.isfinite(float(v)) for v in center + size):
        raise ValueError("invalid_geometry_values")
    if not all(float(v) > 0 for v in size):
        raise ValueError("nonpositive_container_size")
    x, y = map(float, center)
    w, h = map(float, size)
    return [x-w/2, y-h/2, x+w/2, y+h/2]


def outside_mm(actual: list[float], target: list[float]) -> dict[str, float]:
    return {
        "left": round(max(0, target[0]-actual[0]), 3),
        "top": round(max(0, target[1]-actual[1]), 3),
        "right": round(max(0, actual[2]-target[2]), 3),
        "bottom": round(max(0, actual[3]-target[3]), 3),
    }


def overlap_area(a: list[float], b: list[float]) -> float:
    return round(max(0, min(a[2],b[2])-max(a[0],b[0])) *
                 max(0, min(a[3],b[3])-max(a[1],b[1])), 3)


def read_tuple_constants(path: Path, names: set[str]) -> dict[str, Any]:
    # Syntax-tree literal extraction, no execution of renderer or private assets.
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result = {}
    for item in tree.body:
        if isinstance(item, (ast.Assign, ast.AnnAssign)):
            targets = item.targets if isinstance(item, ast.Assign) else [item.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id in names:
                    result[target.id] = ast.literal_eval(item.value)
    missing = names - set(result)
    if missing:
        raise ValueError("required_source_constants_missing:" + ",".join(sorted(missing)))
    return result


def reference_ink_bboxes() -> dict[str, list[float]]:
    names = {"GRIGO_SIGNATURE_BBOX_MM", "HERASYMENKO_SIGNATURE_BBOX_MM",
             "DUAL_GRIGO_BBOX_MM", "DUAL_HERASYMENKO_BBOX_MM"}
    source = read_tuple_constants(EMBEDDED, names)
    def trim_box(box: tuple[float, ...]) -> list[float]:
        return [round(float(v)-BLEED_MM, 3) for v in box]
    grigo = trim_box(source["GRIGO_SIGNATURE_BBOX_MM"])
    hera = trim_box(source["HERASYMENKO_SIGNATURE_BBOX_MM"])
    two = [trim_box(source[x]) for x in ("DUAL_GRIGO_BBOX_MM", "DUAL_HERASYMENKO_BBOX_MM")]
    dual = [min(b[0] for b in two), min(b[1] for b in two),
            max(b[2] for b in two), max(b[3] for b in two)]
    return dict(zip(VARIANTS,(grigo,hera,dual)))


def audit_contract() -> dict[str, Any]:
    document = yaml.safe_load(ZONE_FILE.read_text(encoding="utf-8"))
    page = document["pages"]["physical_4"]
    greeting = page["zones"]["inside_text.greeting"]
    if greeting["bbox_trim_mm"] != [25.0,30.0,185.0,210.0]:
        raise ValueError("greeting_zone_geometry_mismatch")
    if greeting["bottom_visual_line_reservation"]["count"] != 2:
        raise ValueError("greeting_reservation_mismatch")
    profiles = page["signature_profiles_candidate_v0_3"]
    refs = reference_ink_bboxes()
    runtime = read_tuple_constants(RENDERER, {"SENDER_TEXT_LEFT_MM", "SENDER_TEXT_RIGHT_MM",
                                              "SENDER_LINE_ADVANCE_MM", "SENDER_START_Y_VARIANTS_MM"})
    if set(VARIANTS) != set(profiles):
        raise ValueError("signature_profile_set_mismatch")
    out = []
    for variant in VARIANTS:
        p = profiles[variant]
        sender = bbox_from_center(p["sender_text_center_trim_mm"], p["sender_text_size_mm"])
        sign = bbox_from_center(p["signature_center_trim_mm"], p["signature_size_mm"])
        source = refs[variant]
        if variant == "DUAL_GRIGO_HERASYMENKO" and p.get("runtime_enabled") is not False:
            raise ValueError("dual_runtime_must_remain_disabled")
        issues = outside_mm(source,sign)
        mismatch = any(v > 0.05 for v in issues.values())
        out.append({
            "variant":variant,
            "candidate_sender_bbox_trim_mm":sender,
            "candidate_signature_bbox_trim_mm":sign,
            "source_signature_ink_bbox_trim_mm":source,
            "source_ink_outside_candidate_mm":issues,
            "source_signature_fits_candidate":not mismatch,
            "candidate_signature_overlaps_full_greeting_mm2":overlap_area(sign,greeting["bbox_trim_mm"]),
            "source_ink_overlaps_full_greeting_mm2":overlap_area(source,greeting["bbox_trim_mm"]),
            "signature_fit_status":"REVIEW_REQUIRED" if mismatch else "SOURCE_BBOX_INSIDE",
        })
    return {
        "schema_version":"gdl_sender_zone_candidate_audit_v0_1",
        "mode":"CONTRACT",
        "greeting_zone_trim_mm":greeting["bbox_trim_mm"],
        "bottom_reserved_visual_lines":2,
        "renderer_sender_current_bbox_x_pdf_mm":[runtime["SENDER_TEXT_LEFT_MM"],runtime["SENDER_TEXT_RIGHT_MM"]],
        "renderer_sender_current_start_y_pdf_mm":list(runtime["SENDER_START_Y_VARIANTS_MM"]),
        "renderer_sender_line_advance_mm":runtime["SENDER_LINE_ADVANCE_MM"],
        "profiles":out,
        "profile_activation_authorized":False,
        "dual_runtime_enabled":False,
        "customer_acceptance":False,
        "geometric_overlap_does_not_prove_ink_collision":True,
        "project_source_mutated":False,
    }


def audit_pdf(pdf: Path, variant: str, contract: dict[str,Any]) -> dict[str, Any]:
    import pymupdf
    if variant not in VARIANTS:
        raise ValueError("invalid_variant")
    p = next(r for r in contract["profiles"] if r["variant"] == variant)
    with pymupdf.open(pdf) as doc:
        if doc.page_count != 4:
            raise ValueError("pdf_page_count_not_four")
        page = doc[3]
        if abs(page.rect.width*MM_PER_PT-214)>0.15 or abs(page.rect.height*MM_PER_PT-301)>0.15:
            raise ValueError("pdf_page_size_mismatch")
        # Use glyph positions (not the source string). Never record or print text.
        sender_glyphs = []
        for block in page.get_text("rawdict").get("blocks",[]):
            if block.get("type") != 0:
                continue
            for line in block.get("lines",[]):
                for span in line.get("spans",[]):
                    origin = span.get("origin")
                    if not origin or float(origin[1])*MM_PER_PT < 210.0:
                        continue
                    for c in span.get("chars",[]):
                        box = c.get("bbox")
                        if not box:
                            continue
                        box = [float(z)*MM_PER_PT-BLEED_MM for z in box]
                        sender_glyphs.append(box)
    nominal = p["candidate_sender_bbox_trim_mm"]
    ink = p["source_signature_ink_bbox_trim_mm"]
    if sender_glyphs:
        ext = [round(min(b[0] for b in sender_glyphs),3),
               round(min(b[1] for b in sender_glyphs),3),
               round(max(b[2] for b in sender_glyphs),3),
               round(max(b[3] for b in sender_glyphs),3)]
        outside_count = sum(any(v>0.3 for v in outside_mm(b,nominal).values()) for b in sender_glyphs)
        bbox_overlap_count = sum(overlap_area(b,ink)>0 for b in sender_glyphs)
    else:
        ext=None; outside_count=0; bbox_overlap_count=0
    return {
        "variant":variant,
        "sender_glyph_count":len(sender_glyphs),
        "observed_sender_glyph_bbox_trim_mm":ext,
        "sender_glyphs_outside_candidate_container_count":outside_count,
        "glyph_bbox_overlaps_source_ink_bbox_count":bbox_overlap_count,
        "source_signature_ink_bbox_trim_mm":ink,
        "glyph_vs_real_signature_strokes_proved":False,
        "sender_classification_basis":"GLYPH_SPAN_ORIGIN_Y_GE_210_PDF_MM;REQUIRES_VISUAL_REVIEW",
        "pdf_accepted_for_production":False,
    }


def main() -> int:
    pa = argparse.ArgumentParser()
    pa.add_argument("--mode",required=True,choices=["contract","pdf"])
    pa.add_argument("--pdf",type=Path)
    pa.add_argument("--variant",choices=VARIANTS)
    args=pa.parse_args()
    try:
        result=audit_contract()
        if args.mode=="pdf":
            if args.pdf is None or args.variant is None or not args.pdf.is_file():
                raise ValueError("pdf_mode_requires_existing_pdf_and_variant")
            result["mode"]="PDF"
            result["pdf_evidence"]=audit_pdf(args.pdf,args.variant,result)
        OUT.parent.mkdir(parents=True,exist_ok=True)
        OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        for item in result["profiles"]:
            print("PROFILE="+item["variant"]+
                  " SOURCE_FITS_CANDIDATE="+str(item["source_signature_fits_candidate"]).lower()+
                  " MAX_SOURCE_BBOX_EXCESS_MM="+str(max(item["source_ink_outside_candidate_mm"].values())))
        if args.mode=="pdf":
            item=result["pdf_evidence"]
            print("PDF_VARIANT="+item["variant"])
            print("PDF_SENDER_GLYPH_COUNT="+str(item["sender_glyph_count"]))
            print("PDF_SENDER_OUTSIDE_CANDIDATE="+str(item["sender_glyphs_outside_candidate_container_count"]))
            print("PDF_GLYPH_BBOX_SIGNATURE_BBOX_OVERLAP="+str(item["glyph_bbox_overlaps_source_ink_bbox_count"]))
        print("REPORT=tmp/gdl_sender_zone_audit_v0_1/sanitized_report.json")
        print("GDL_SENDER_ZONE_AUDIT=PASS_WITH_REVIEW_REQUIRED")
        print("RUNTIME_OR_GIT_CHANGED=false")
        return 0
    except Exception as exc:
        print("GDL_SENDER_ZONE_AUDIT=BLOCKED")
        print("ERROR_CLASS="+type(exc).__name__)
        print("ERROR_CODE="+str(exc).split(":")[0][:90])
        return 2

if __name__=="__main__":
    raise SystemExit(main())

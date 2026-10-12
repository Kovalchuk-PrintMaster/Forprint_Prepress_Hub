#!/usr/bin/env python3
"""Project-owned, evidence-only variable input probe for GDL Builder V1.

Run with --mode contract (no private inputs), or --mode layout (exact private
font via an already-bound ignored proof config). Never edits the Builder, bundle
or manifests; outputs sanitized JSON under tmp/ only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

import pymupdf
import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MATRIX_PATH = ROOT / "coordination/graphic_design_lab/directions/greeting_cards/gdl_greeting_card_variability_matrix_v0_1.yaml"
DEFAULT_CONFIG = ROOT / "tmp/gdl_gc09b_real_pdf_proof_20261010/private_inputs_local.json"
REPORT_PATH = ROOT / "tmp/gdl_v1_variability_baseline/variability_report_v0_1.json"
SENTENCE = "Бажаємо радості, тепла, натхнення та гарних новин у кожному дні. "
SENDER_LINES = [
    {"id": "closing_phrase", "text": "З найкращими побажаннями"},
    {"id": "sender_name", "text": "Ім'я Приклад"},
    {"id": "sender_role_1", "text": "Посада підписанта"},
    {"id": "sender_role_2", "text": "Назва відділу"},
    {"id": "sender_role_3", "text": "Додаткова інформація"},
    {"id": "sender_role_4", "text": "Другий підписант"},
    {"id": "sender_role_5", "text": "Посада другого"},
    {"id": "sender_role_6", "text": "Підрозділ організації"},
]


def synthetic_text(length: int) -> str:
    if not isinstance(length, int) or length < 20 or length > 10000:
        raise ValueError("synthetic_text_length_out_of_range")
    return (SENTENCE * ((length // len(SENTENCE)) + 2))[:length].strip()


def matrix() -> dict:
    data = yaml.safe_load(MATRIX_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != "gdl_greeting_card_variability_matrix_v0_1":
        raise ValueError("variability_matrix_schema_invalid")
    return data


def check_binding() -> None:
    cursor = yaml.safe_load((ROOT / "coordination/graphic_design_lab/continuity/current_execution_cursor_v0_1.yaml").read_text(encoding="utf-8"))
    tasks = [r for r in cursor.get("active_tasks", []) if r.get("task_id") == "GDL-TASK-GREETING-CARD-E2E-001"]
    if len(tasks) != 1 or tasks[0].get("current_step") != "GC-E2E-09":
        raise ValueError("gdl_variability_cursor_binding_changed")
    registry_path = ROOT / "coordination/graphic_design_lab/directions/greeting_cards/signature_registry_v0_1.yaml"
    if registry_path.is_file():
        reg = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
        if reg.get("variants", {}).get("DUAL_GRIGO_HERASYMENKO", {}).get("runtime_enabled") is not False:
            raise ValueError("gdl_variability_dual_runtime_must_remain_disabled")


def variant_gate_rows(rows: list[dict]) -> list[dict]:
    from app.graphic_design_lab.greeting_card_builder_renderer import _validate_first_slice_job
    results = []
    for case in rows:
        base = {
            "job_id": "synthetic-variability",
            "branding_selection": {"presence": case["branding"]},
            "builder_v1": {
                "front": {"family": case["front"]},
                "inside_image": {"mode": case["image"]},
                "sender_text": {"signature_variant_id": case["signature"]},
            },
        }
        try:
            _validate_first_slice_job(deepcopy(base))
            observed = "ALLOWED"
            reason = ""
        except ValueError as exc:
            observed = "BLOCKED"
            reason = str(exc).split(":", 1)[0]
        results.append({
            "case_id": case["id"], "expected": case["expected"],
            "observed": observed, "matches_expected": observed == case["expected"],
            "reason_code": reason,
        })
    return results


def resolve_exact_greeting_font(config_path: Path) -> Path:
    from app.graphic_design_lab.greeting_card_private_resources import (
        RESOURCE_GREETING_FONT, validate_and_resolve_private_resources,
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    raw = config.get("resource_manifest")
    if not isinstance(raw, str) or not raw:
        raise ValueError("private_resource_manifest_binding_required")
    location = Path(raw).expanduser()
    if not location.is_absolute():
        location = (ROOT / location).resolve()
    source = yaml.safe_load(location.read_text(encoding="utf-8"))
    resolved = validate_and_resolve_private_resources(source, required_ids=[RESOURCE_GREETING_FONT])
    return Path(resolved[RESOURCE_GREETING_FONT]["path"])


def layout_case(case: dict, font_path: Path) -> dict:
    from app.graphic_design_lab import greeting_card_builder_renderer as b
    length = int(case["greeting_length"])
    count = int(case["sender_lines"])
    if count < 1 or count > len(SENDER_LINES):
        raise ValueError("sender_line_count_invalid")
    text = synthetic_text(length)
    lines = deepcopy(SENDER_LINES[:count])
    doc = pymupdf.open()
    page = doc.new_page(width=214 * b.PT_PER_MM, height=301 * b.PT_PER_MM)
    result = {"case_id": case["id"], "greeting_chars": len(text), "sender_line_count": count}
    try:
        size, sender_y, rect = b._fit_greeting(
            page, text, font_path=font_path, sender_line_count=count
        )
        b._insert_textbox_exact(page, rect, text, font_path=font_path,
                                fontname="ZapfChanceryC", fontsize=size,
                                align=pymupdf.TEXT_ALIGN_CENTER, lineheight=1.0)
        b._render_sender_lines(page, lines, font_path=font_path, start_y_mm=sender_y)
        sender_end = round(float(sender_y + count * b.SENDER_LINE_ADVANCE_MM), 3)
        signature_zone = b._rect_mm(b.HERASYMENKO_SIGNATURE_BBOX_MM)
        signature_intersections = len(b._text_intersections_with_rect(page, signature_zone))
        result.update({
            "observed": "RENDERED_TEXT_ONLY", "font_pt": size,
            "sender_start_mm": sender_y, "sender_end_mm": sender_end,
            "sender_within_conservative_safe_zone": sender_end <= b.SENDER_CONSERVATIVE_SAFE_BOTTOM_MM,
            "herasymenko_signature_zone_text_hits": signature_intersections,
            "layout_safe_for_herasymenko": sender_end <= b.SENDER_CONSERVATIVE_SAFE_BOTTOM_MM and signature_intersections == 0,
        })
    except Exception as exc:
        # Only fixed error class and code, never log text or private paths.
        safe_codes = (
            "greeting_text_does_not_fit_canonical_tiers",
            "text_does_not_fit",
            "herasymenko_signature",
        )
        code = str(exc).split(":", 1)[0].split("=", 1)[0]
        if not any(code.startswith(marker) for marker in safe_codes):
            code = "UNEXPECTED_LAYOUT_EXCEPTION_REDACTED"
        result.update({"observed": "BLOCKED", "error_type": type(exc).__name__,
                       "error_code": code})
    finally:
        doc.close()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("contract", "layout"), default="contract")
    parser.add_argument("--binding-config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    check_binding()
    m = matrix()
    gates = variant_gate_rows(m["variant_gate_cases"])
    if not all(row["matches_expected"] for row in gates):
        raise ValueError("variant_gate_contract_regression")
    layout = []
    if args.mode == "layout":
        font = resolve_exact_greeting_font(args.binding_config)
        layout = [layout_case(c, font) for c in m["synthetic_greeting_cases"]]
    layout_expectations_verified = None
    if args.mode == "layout":
        outcomes = {item["case_id"]: item for item in layout}
        safe_cases = (
            "short_two_line_sender", "medium_three_line_sender",
            "long_three_line_sender", "long_six_line_sender",
        )
        layout_expectations_verified = (
            all(
                outcomes.get(key, {}).get("observed") == "RENDERED_TEXT_ONLY"
                and outcomes[key].get("layout_safe_for_herasymenko") is True
                for key in safe_cases
            )
            and outcomes.get("overflow_probe", {}).get("observed") == "BLOCKED"
            and outcomes["overflow_probe"].get("error_code")
            == "greeting_text_does_not_fit_canonical_tiers"
        )
        if not layout_expectations_verified:
            raise ValueError("sender_layout_guard_regression")
    report = {
        "schema_version": "gdl_v1_variability_probe_report_v0_1",
        "sender_layout_guard_expectations_verified": layout_expectations_verified,
        "mode": args.mode,
        "matrix_sha256": hashlib.sha256(MATRIX_PATH.read_bytes()).hexdigest(),
        "variant_gate_results": gates,
        "synthetic_text_layout_results": layout,
        "baseline_measured": True,
        "complete_v1_acceptance": False,
        "full_pdf_batch_proven": False,
        "old_customer_text_rebinding_performed": False,
        "production_ready": False,
        "dual_runtime_activated": False,
        "tracked_sources_mutated": False,
        "next_gate": "REVIEW_VARIABILITY_GAPS_AND_SELECT_ONE_BOUNDED_IMPLEMENTATION_SLICE",
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("GDL_V1_VARIABILITY_PROBE=PASS")
    print("MODE=" + args.mode.upper())
    print("VARIANT_CASES=" + str(len(gates)))
    print("VARIANT_GATES_MATCH_EXPECTATION=true")
    print("TEXT_LAYOUT_CASES=" + str(len(layout)))
    for row in layout:
        print("CASE=" + row["case_id"] + " STATUS=" + row["observed"]
              + (" SAFE_FOR_HER=" + str(row["layout_safe_for_herasymenko"]).lower()
                 if "layout_safe_for_herasymenko" in row else ""))
    print("REAL_CUSTOMER_PDF_ACCEPTANCE=false")
    print("UNIVERSAL_BUILDER_V1_COMPLETE=false")
    print("REPORT=" + str(REPORT_PATH.relative_to(ROOT)))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("GDL_V1_VARIABILITY_PROBE=BLOCKED")
        print("ERROR_CLASS=" + type(exc).__name__)
        print("ERROR_CODE=CHECK_LOCAL_EXCEPTION_WITHOUT_SHARING_PRIVATE_PATHS")
        raise SystemExit(2)

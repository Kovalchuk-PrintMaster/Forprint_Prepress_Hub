from __future__ import annotations

from pathlib import Path

import yaml

from scripts.validation import gdl_greeting_card_variability_probe_v0_1 as p


def test_variability_matrix_covers_dynamic_inputs_and_fail_closed_variants():
    data = yaml.safe_load(p.MATRIX_PATH.read_text(encoding="utf-8"))
    assert data["bound_step"] == "GC-E2E-09"
    cases = data["synthetic_greeting_cases"]
    assert len(cases) >= 5
    assert len({case["id"] for case in cases}) == len(cases)
    assert len({case["greeting_length"] for case in cases}) >= 4
    assert max(case["sender_lines"] for case in cases) >= 6
    names = {case["id"] for case in data["variant_gate_cases"]}
    assert {"standard_grigo", "standard_herasymenko", "dual_not_enabled",
            "recipient_branding_overlay", "default_asset_flowers", "bilingual_front"} <= names
    assert data["authority"]["dual_runtime_activation"] is False
    assert data["authority"]["cursor_advance"] is False


def test_synthetic_inputs_deterministic_and_not_real_customer_text():
    assert p.synthetic_text(110) == p.synthetic_text(110)
    assert p.synthetic_text(110) != p.synthetic_text(420)
    assert "Шановна" not in p.synthetic_text(420)
    assert "Герасименко" not in p.synthetic_text(420)
    assert len(p.SENDER_LINES) >= 8
    assert all("id" in line and "text" in line for line in p.SENDER_LINES)


def test_variant_gate_matches_current_bounded_builder_capability():
    m = p.matrix()
    results = p.variant_gate_rows(m["variant_gate_cases"])
    assert len(results) >= 6
    assert all(r["matches_expected"] for r in results)
    assert {r["observed"] for r in results} == {"ALLOWED", "BLOCKED"}


def test_private_bindings_only_read_at_layout_mode():
    import inspect
    src = inspect.getsource(p.main)
    assert 'if args.mode == "layout"' in src
    assert "complete_v1_acceptance" in src
    assert "full_pdf_batch_proven" in src
    assert "resolve_exact_greeting_font" in src

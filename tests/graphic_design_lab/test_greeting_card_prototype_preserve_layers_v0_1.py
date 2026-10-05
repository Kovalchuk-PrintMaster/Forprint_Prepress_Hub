from __future__ import annotations

import importlib.util
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
RUNNER = (
    ROOT
    / "scripts"
    / "graphic_design_lab"
    / "greeting_cards"
    / "prototype.py"
)


def load_runner():
    spec = importlib.util.spec_from_file_location(
        "greeting_card_prototype_under_test",
        RUNNER,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_perceptual_diff_reports_multiple_thresholds():
    module = load_runner()

    a = Image.new("RGB", (10, 10), (100, 100, 100))
    b = Image.new("RGB", (10, 10), (105, 105, 105))
    metrics = module.image_diff_metrics(a, b, 10.0, 10.0)

    assert metrics["changed_pixel_ratio"] == 1.0
    assert metrics["changed_pixel_ratio_gt10"] == 0.0
    assert metrics["changed_pixel_ratio_gt20"] == 0.0
    assert metrics["mean_abs_rgb_delta"] == 5.0


def test_reference_layers_are_preserved_for_non_regenerated_pages():
    text = RUNNER.read_text(encoding="utf-8")

    assert "PRESERVED_REFERENCE_PAGE_PLUS_CANONICAL_SENDER_LOGO" in text
    assert "LOCKED_REUSE_ONLY_PAGE_TRANSPLANT" in text
    assert "PRESERVED_REFERENCE_PAGE_MINUS_HIDDEN_AUTHORING_OBJECT" in text
    assert "DETERMINISTIC_BASE_PLUS_PRESERVED_PORTRAIT_MASK_LAYER" in text

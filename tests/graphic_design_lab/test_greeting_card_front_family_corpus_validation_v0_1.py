from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
RUNNER = (
    ROOT
    / "scripts"
    / "graphic_design_lab"
    / "greeting_cards"
    / "prototype.py"
)
SKELETON = (
    ROOT
    / "coordination"
    / "graphic_design_lab"
    / "directions"
    / "greeting_cards"
    / "product_skeleton_v0_1.yaml"
)


def load_runner():
    spec = importlib.util.spec_from_file_location(
        "greeting_card_front_family_under_test",
        RUNNER,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_skeleton():
    return yaml.safe_load(
        SKELETON.read_text(encoding="utf-8")
    )


def test_each_canonical_sender_logo_bbox_classifies_to_its_family():
    module = load_runner()
    skeleton = load_skeleton()

    for family in skeleton["variant_model"]["front"][
        "semantic_families"
    ]:
        result = module.classify_front_family_from_bbox(
            family["sender_logo_bbox_mm"],
            skeleton,
        )
        assert result["resolved"] is True
        assert result["family"] == family["id"]


def test_far_geometry_is_unresolved():
    module = load_runner()
    skeleton = load_skeleton()

    result = module.classify_front_family_from_bbox(
        [0.0, 0.0, 20.0, 20.0],
        skeleton,
    )

    assert result["resolved"] is False
    assert result["family"] == "UNRESOLVED"


def test_classifier_policy_is_not_filename_based():
    skeleton = load_skeleton()
    classifier = skeleton["variant_model"]["front"][
        "classifier"
    ]

    assert classifier["primary_signal"] == (
        "sender_logo_bbox_nearest_canonical_family"
    )
    assert (
        classifier["filename_based_classification_allowed"]
        is False
    )


def test_makefile_has_corpus_validation_entrypoint():
    makefile = (ROOT / "Makefile").read_text(
        encoding="utf-8"
    )

    assert "gdl-greeting-card-corpus-validate:" in makefile
    assert "--mode corpus-validate" in makefile

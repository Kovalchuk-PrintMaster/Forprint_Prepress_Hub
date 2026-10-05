from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO
    / "scripts"
    / "graphic_design_lab"
    / "greeting_cards"
    / "prototype.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "gdl_greeting_card_prototype",
        MODULE_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def synthetic_skeleton() -> dict:
    return {
        "variant_model": {
            "front": {
                "semantic_families": [
                    {
                        "id": "STANDARD",
                        "sender_logo_bbox_mm": [64.5, 59.5, 149.5, 144.5],
                    },
                    {
                        "id": "RECIPIENT_BRANDING_OVERLAY",
                        "sender_logo_bbox_mm": [68.86, 38.86, 145.14, 114.899],
                    },
                    {
                        "id": "BILINGUAL_OCCASION",
                        "sender_logo_bbox_mm": [60.0, 40.0, 150.0, 130.0],
                    },
                ]
            }
        }
    }


@pytest.mark.parametrize(
    ("family_id", "expected_bbox"),
    [
        ("STANDARD", [64.5, 59.5, 149.5, 144.5]),
        (
            "RECIPIENT_BRANDING_OVERLAY",
            [68.86, 38.86, 145.14, 114.899],
        ),
        ("BILINGUAL_OCCASION", [60.0, 40.0, 150.0, 130.0]),
    ],
)
def test_compositor_geometry_dispatches_by_resolved_front_family(
    family_id: str,
    expected_bbox: list[float],
) -> None:
    module = load_module()
    resolved_family, bbox = (
        module.resolved_front_family_sender_logo_geometry(
            {"resolved": True, "family": family_id},
            synthetic_skeleton(),
        )
    )

    assert resolved_family == family_id
    assert bbox == expected_bbox


def test_unresolved_family_is_rejected_before_compositor_dispatch() -> None:
    module = load_module()

    with pytest.raises(
        ValueError,
        match="front family must be resolved",
    ):
        module.resolved_front_family_sender_logo_geometry(
            {"resolved": False, "family": "UNRESOLVED"},
            synthetic_skeleton(),
        )


def test_main_compositor_is_not_hardwired_to_standard_geometry() -> None:
    source = MODULE_PATH.read_text()

    assert 'standard_logo_rect = rect_from_mm(' not in source
    assert "dest_rect=front_family_logo_rect" in source
    assert '"front_family": front_family_id' in source

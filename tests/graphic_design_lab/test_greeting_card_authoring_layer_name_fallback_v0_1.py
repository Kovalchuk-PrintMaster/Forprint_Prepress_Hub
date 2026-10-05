from __future__ import annotations

import importlib.util
from pathlib import Path


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


class FakeDoc:
    def xref_object(self, xref: int) -> str:
        assert xref == 16
        return (
            "<<\n"
            "  /Type /OCG\n"
            "  /Intent 13 0 R\n"
            "  /Name (danger zone)\n"
            "  /Usage 14 0 R\n"
            ">>"
        )


def test_ocg_name_falls_back_to_xref_object_when_get_ocgs_is_empty():
    module = load_runner()
    assert (
        module.ocg_name_from_xref(
            FakeDoc(),
            16,
            {},
        )
        == "danger zone"
    )


def test_authoring_layer_hint_matches_danger_zone():
    module = load_runner()
    assert module.AUTHORING_LAYER_HINTS.search("danger zone")

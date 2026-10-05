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
    def __init__(self):
        self.objects = {
            1: "<< /Type /XObject /Subtype /Image /SMask 3 0 R >>",
            2: "<< /Type /XObject /Subtype /Image /SMask 4 0 R >>",
            3: "<< /Type /XObject /Subtype /Image /ColorSpace 7 0 R >>",
            4: "<< /Type /XObject /Subtype /Image /ColorSpace /DeviceGray >>",
            7: "[ /ICCBased 8 0 R ]",
            8: "<< /N 1 /Alternate /DeviceGray >>",
        }
        self.color_spaces = {
            3: ("xref", "7 0 R"),
            4: ("name", "/DeviceGray"),
        }
        self.set_calls = []

    def xref_length(self):
        return 9

    def xref_object(self, xref):
        return self.objects.get(xref, "")

    def xref_get_key(self, xref, key):
        assert key == "ColorSpace"
        return self.color_spaces.get(xref, ("null", "null"))

    def xref_set_key(self, xref, key, value):
        self.set_calls.append((xref, key, value))
        self.color_spaces[xref] = ("name", value)


def test_image_soft_mask_colorspace_is_normalized_to_devicegray():
    module = load_runner()
    doc = FakeDoc()

    changed = module.normalize_image_soft_mask_colorspaces(doc)

    assert changed == [3]
    assert doc.set_calls == [
        (3, "ColorSpace", "/DeviceGray"),
    ]


def test_runner_has_cross_renderer_gate():
    text = RUNNER.read_text(encoding="utf-8")

    assert 'import tempfile' in text
    assert '"pdftoppm"' in text
    assert "PDFTOPPM_CHECK=" in text
    assert "SMASK_DEVICEGRAY_NORMALIZED_COUNT=" in text
    assert "prototype_pdf_cross_renderer_check_failed" in text

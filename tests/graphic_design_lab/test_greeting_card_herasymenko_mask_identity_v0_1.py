from __future__ import annotations

import io

import pytest
from PIL import Image

import app.graphic_design_lab.greeting_card_builder_renderer as renderer


def _png(size: tuple[int, int], mode: str) -> bytes:
    image = Image.new(mode, size, 100 if mode == "L" else (20, 40, 60, 255))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


class _FakeDocument:
    def __init__(self, mask_size: tuple[int, int]):
        self.base = _png((8, 11), "RGBA")
        self.mask = _png(mask_size, "L")

    def extract_image(self, xref: int) -> dict[str, bytes]:
        return {"image": self.base if xref == 10 else self.mask}

    def xref_get_key(self, xref: int, key: str) -> tuple[str, str]:
        assert (xref, key) == (20, "ColorSpace")
        return ("name", "/DeviceGray")


class _FakePage:
    def __init__(self, mask_size: tuple[int, int]):
        self.parent = _FakeDocument(mask_size)


def test_pdf_image_identity_rejects_soft_mask_dimension_mismatch(monkeypatch):
    monkeypatch.setattr(renderer, "_image_soft_mask_xref", lambda page, xref: 20)
    page = _FakePage((4, 11))
    with pytest.raises(ValueError, match="pdf_image_soft_mask_pixel_size_mismatch"):
        renderer._pdf_image_rgba_pixel_identity(page, 10)


def test_pdf_image_identity_keeps_equal_size_mask_exact(monkeypatch):
    monkeypatch.setattr(renderer, "_image_soft_mask_xref", lambda page, xref: 20)
    page = _FakePage((8, 11))
    result = renderer._pdf_image_rgba_pixel_identity(page, 10)
    assert result["pixel_size"] == [8, 11]
    assert result["soft_mask_xref"] == 20
    assert result["soft_mask_colorspace"] == "/DeviceGray"
    assert len(result["rgba_pixel_sha256"]) == 64

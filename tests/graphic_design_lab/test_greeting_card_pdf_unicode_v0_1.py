"""Page-4 Unicode semantics must change without changing visual PDF artwork."""
from pathlib import Path
import pytest
from app.graphic_design_lab.greeting_card_pdf_unicode_v0_1 import (
    _correct_zapf_cmap, repair_page4_canonical_unicode,
)


SOURCE_CMAP = (
    b"/CIDInit /ProcSet findresource begin\n"
    b"1 begincodespacerange\n<0000> <ffff>\nendcodespacerange\n"
    b"11 beginbfrange\n"
    b"<0002> <000d> <0021>\n"
    b"<0088> <008b> <00ab>\n"
    b"endbfrange\n"
    b"1 beginbfchar\n"
    b"<0001> <00a0>\n"
    b"endbfchar\n"
)


def test_change_is_only_intended_tounicode_mapping():
    corrected = _correct_zapf_cmap(SOURCE_CMAP)
    assert b"13 beginbfrange" in corrected
    assert b"<0088> <0089> <00ab>" in corrected
    assert b"<008a> <008a> <002d>" in corrected
    assert b"<008b> <008b> <00ae>" in corrected
    assert b"<0001> <0020>" in corrected
    assert corrected.count(b"<0002> <000d> <0021>") == 1
    assert b"<0088> <008b> <00ab>" not in corrected
    assert b"<0001> <00a0>" not in corrected


@pytest.mark.parametrize("bad", [
    SOURCE_CMAP.replace(b"<0001> <00a0>", b"<0001> <0020>"),
    SOURCE_CMAP.replace(b"<0088> <008b> <00ab>", b"<0088> <008b> <00ac>"),
    SOURCE_CMAP.replace(b"11 beginbfrange", b"11 beginbfrange\n11 beginbfrange"),
])
def test_unexpected_font_mappings_fail_closed(bad):
    with pytest.raises(ValueError, match="canonical_font_cmap_"):
        _correct_zapf_cmap(bad)


class FakePage:
    def __init__(self, fonts):
        self.fonts = fonts

    def get_fonts(self, full=True):
        assert full
        return self.fonts


class FakeDocument:
    def __init__(self, fonts):
        self.fonts = fonts
        self.updated = None

    def __len__(self):
        return 4

    def __getitem__(self, index):
        assert index == 3
        return FakePage(self.fonts)

    def xref_get_key(self, xref, name):
        assert xref == 5 and name == "ToUnicode"
        return ("xref", "6 0 R")

    def xref_stream(self, xref):
        assert xref == 6
        return SOURCE_CMAP

    def update_stream(self, xref, content):
        self.updated = (xref, content)


def test_only_canonical_page4_font_map_is_updated():
    doc = FakeDocument([(5, "otf", "Type0", "ZapfChanceryC Regular", "ZapfChanceryC", "Identity-H", 0)])
    evidence = repair_page4_canonical_unicode(doc)
    assert evidence["status"] == "PASS"
    assert evidence["layout_modified"] is False
    assert evidence["font_program_modified"] is False
    assert evidence["signature_artwork_modified"] is False
    assert doc.updated[0] == 6
    assert b"<008a> <008a> <002d>" in doc.updated[1]


def test_unknown_font_fails_without_stream_write():
    doc = FakeDocument([(5, "otf", "Type0", "Other Regular", "WrongFont", "Identity-H", 0)])
    with pytest.raises(ValueError, match="canonical_font_page4_identity_h_count"):
        repair_page4_canonical_unicode(doc)
    assert doc.updated is None


def test_renderer_calls_cmap_fix_before_pdf_save():
    source = (Path(__file__).resolve().parents[2] / "app/graphic_design_lab/greeting_card_builder_renderer.py").read_text(encoding="utf-8")
    # Exact bounded order within the composition tail.
    begin = source.index("canonical_unicode_evidence = repair_page4_canonical_unicode(out)")
    end = source.index("        out.save(\n", begin)
    assert 0 < end - begin < 250
    assert '"canonical_sender_pdf_unicode": canonical_unicode_evidence' in source

"""Correct only the frozen ZapfChanceryC PDF /ToUnicode mapping.

The hash-verified font has an unusual internal cmap: font character code 0x008A
extracts as SOFT HYPHEN although the source text contains an ASCII hyphen;
code 0x0001 extracts as NBSP although source text uses spaces. The glyphs and
PDF drawing instructions MUST remain unchanged. This is a PDF text-semantics
repair only, performed before saving the finished four-page review document.
"""
from __future__ import annotations

import re
from typing import Any

import pymupdf

_FONT = "ZapfChanceryC"
_ENCODING = "Identity-H"
_OLD_RANGE = b"<0088> <008b> <00ab>"
_NEW_RANGE = (
    b"<0088> <0089> <00ab>\n"
    b"<008a> <008a> <002d>\n"
    b"<008b> <008b> <00ae>"
)
_OLD_SPACE = b"<0001> <00a0>"
_NEW_SPACE = b"<0001> <0020>"


def _correct_zapf_cmap(raw: bytes) -> bytes:
    """Fail closed unless the expected, exactly-one font CMap is present."""
    if not isinstance(raw, bytes):
        raise ValueError("canonical_font_cmap_not_bytes")
    if raw.count(_OLD_RANGE) != 1 or raw.count(_OLD_SPACE) != 1:
        raise ValueError("canonical_font_cmap_unexpected_glyph_mappings")
    if raw.count(b"<008a> <008a> <002d>") != 0:
        raise ValueError("canonical_font_cmap_already_patched")
    matches = list(re.finditer(rb"(?m)^(\d+) beginbfrange\s*$", raw))
    if len(matches) != 1:
        raise ValueError("canonical_font_cmap_bfrange_header_ambiguous")
    old_count = int(matches[0].group(1))
    if old_count < 1 or old_count > 1000:
        raise ValueError("canonical_font_cmap_bfrange_count_invalid")
    first = raw[:matches[0].start()]
    last = raw[matches[0].end():]
    new_header = str(old_count + 2).encode("ascii") + b" beginbfrange"
    corrected = first + new_header + last
    corrected = corrected.replace(_OLD_RANGE, _NEW_RANGE)
    corrected = corrected.replace(_OLD_SPACE, _NEW_SPACE)
    if corrected == raw or _OLD_RANGE in corrected or _OLD_SPACE in corrected:
        raise ValueError("canonical_font_cmap_correction_failed")
    return corrected


def repair_page4_canonical_unicode(document: pymupdf.Document) -> dict[str, Any]:
    """Edit only /ToUnicode of the canonical font used on physical page 4.

    No font bytes, content streams, coordinates, signatures, or graphics change.
    Raises on any resource mismatch rather than touching an unknown PDF.
    """
    if len(document) != 4:
        raise ValueError("canonical_font_document_must_have_four_pages")
    page = document[3]
    fonts = {
        int(row[0])
        for row in page.get_fonts(full=True)
        if len(row) >= 6 and row[4] == _FONT and row[5] == _ENCODING
    }
    if len(fonts) != 1:
        raise ValueError("canonical_font_page4_identity_h_count:" + str(len(fonts)))
    font_xref = next(iter(fonts))
    kind, value = document.xref_get_key(font_xref, "ToUnicode")
    if kind != "xref" or not re.fullmatch(r"\d+ 0 R", value):
        raise ValueError("canonical_font_tounicode_reference_missing")
    cmap_xref = int(value.split()[0])
    before = document.xref_stream(cmap_xref)
    corrected = _correct_zapf_cmap(before)
    document.update_stream(cmap_xref, corrected)
    return {
        "status": "PASS",
        "font": _FONT,
        "page": 4,
        "semantic_changes": ["FONT_CID_0001_NBSP_TO_SPACE", "FONT_CID_008A_SHY_TO_HYPHEN"],
        "page_content_stream_modified": False,
        "font_program_modified": False,
        "signature_artwork_modified": False,
        "layout_modified": False,
    }

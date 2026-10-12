"""Deterministic sender slots for GDL greeting-card Builder.

SOURCE_LOCKED exactly preserves existing renderer rectangles.  CANDIDATE_V03
is a non-activated geometry proof only; an operator-approved source/ink proof
is required before enabling candidate coordinates in customer PDF output.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping, Sequence


BLEED_MM = 2.0
ADVANCE_MM = 8.0
LEGACY_LEFT_PDF_MM = 31.0
LEGACY_RIGHT_PDF_MM = 101.0
TRIM_PAGE_MM = (210.0, 297.0)
VARIANTS = ("GRIGO", "HERASYMENKO", "DUAL_GRIGO_HERASYMENKO")


class SenderZoneBlocked(ValueError):
    """Fail-closed sender planning; machine-readable code, no input text."""


@dataclass(frozen=True)
class SenderSlot:
    line_id: str
    bbox_pdf_mm: tuple[float, float, float, float]


def _ids(line_ids: Sequence[str], *, unique: bool = True) -> tuple[str, ...]:
    if isinstance(line_ids, (str, bytes)) or not line_ids:
        raise SenderZoneBlocked("sender_line_ids_missing")
    if any(not isinstance(k, str) or not k.strip() for k in line_ids):
        raise SenderZoneBlocked("sender_line_id_invalid")
    if unique and len(set(line_ids)) != len(line_ids):
        raise SenderZoneBlocked("sender_line_id_duplicate")
    return tuple(line_ids)


def source_locked_slots(
    line_ids: Sequence[str], *, start_y_pdf_mm: float
) -> tuple[SenderSlot, ...]:
    """Exactly reproduce old _render_sender_lines() slot coordinates."""
    ids = _ids(line_ids, unique=False)  # legacy accepted repeated IDs; do not change it
    start = float(start_y_pdf_mm)
    if not isfinite(start):
        raise SenderZoneBlocked("sender_source_y_invalid")
    return tuple(
        SenderSlot(
            line_id=line_id,
            bbox_pdf_mm=(
                LEGACY_LEFT_PDF_MM,
                start + i * ADVANCE_MM,
                LEGACY_RIGHT_PDF_MM,
                start + (i + 1) * ADVANCE_MM,
            ),
        )
        for i, line_id in enumerate(ids)
    )


def candidate_v03_slots(
    line_ids: Sequence[str], *, variant: str, profile: Mapping
) -> tuple[SenderSlot, ...]:
    """Plan operator proposed sender text rectangle; NOT a runtime activation.

    A candidate must be font-fitted and visually reviewed before use; this
    function deliberately does not claim to prove ink or font fit.
    """
    ids = _ids(line_ids)
    if variant not in VARIANTS:
        raise SenderZoneBlocked("sender_variant_not_registered")
    if variant == "DUAL_GRIGO_HERASYMENKO":
        if profile.get("runtime_enabled") is not False:
            raise SenderZoneBlocked("dual_runtime_gate_missing")
    center = profile.get("sender_text_center_trim_mm")
    size = profile.get("sender_text_size_mm")
    if (
        not isinstance(center, (list, tuple)) or len(center) != 2
        or not isinstance(size, (list, tuple)) or len(size) != 2
    ):
        raise SenderZoneBlocked("sender_profile_geometry_missing")
    try:
        x, y = (float(q) for q in center)
        w, h = (float(q) for q in size)
    except (ValueError, TypeError) as exc:
        raise SenderZoneBlocked("sender_profile_geometry_invalid") from exc
    if not all(isfinite(q) for q in (x, y, w, h)) or w <= 0 or h <= 0:
        raise SenderZoneBlocked("sender_profile_geometry_invalid")
    left, top, right, bottom = (x-w/2, y-h/2, x+w/2, y+h/2)
    if left < 0 or top < 0 or right > TRIM_PAGE_MM[0] or bottom > TRIM_PAGE_MM[1]:
        raise SenderZoneBlocked("sender_profile_outside_trim")
    # Operator's candidate container stays fixed. Shift only the typesetting
    # slots *within* the HERASYMENKO candidate by the registry's small inset.
    # Legacy source_locked geometry is intentionally unaffected.
    try:
        top_inset = float(profile.get("sender_text_inner_top_inset_mm", 0.0))
    except (ValueError, TypeError) as exc:
        raise SenderZoneBlocked("sender_inner_top_inset_invalid") from exc
    if not isfinite(top_inset) or top_inset < 0:
        raise SenderZoneBlocked("sender_inner_top_inset_invalid")
    if top_inset and variant != "HERASYMENKO":
        raise SenderZoneBlocked("sender_inner_top_inset_variant_not_verified")
    if len(ids) * ADVANCE_MM + top_inset > h + 1e-8:
        raise SenderZoneBlocked("sender_lines_exceed_candidate_height")
    return tuple(
        SenderSlot(
            line_id=line_id,
            bbox_pdf_mm=(
                left + BLEED_MM,
                top + BLEED_MM + top_inset + i * ADVANCE_MM,
                right + BLEED_MM,
                top + BLEED_MM + top_inset + (i + 1) * ADVANCE_MM,
            ),
        )
        for i, line_id in enumerate(ids)
    )

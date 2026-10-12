"""One governed type/leading profile for single greeting-card signers.

The profile is shared by GRIGO and HERASYMENKO; DUAL is intentionally not
supported here. All coordinates are PDF millimetres (with bleed).
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Mapping, Sequence

import yaml

REGISTRY = Path(__file__).resolve().parents[2] / (
    'coordination/graphic_design_lab/directions/greeting_cards/'
    'sender_typography_profiles_v0_1.yaml'
)
PT_PER_MM = 72.0 / 25.4
SINGLES = ('GRIGO', 'HERASYMENKO')


class SenderTypographyBlocked(ValueError):
    """Fail-closed typographic planning; no customer text in exception strings."""


@dataclass(frozen=True)
class SenderTypeSlot:
    object_id: str
    semantic_role: str
    font_size_pt: float
    bbox_pdf_mm: tuple[float, float, float, float]
    baseline_pdf_mm: float


def _role(line_id: str) -> str:
    if line_id == 'closing_phrase':
        return 'closing_phrase'
    if line_id == 'sender_name' or 'name' in line_id.lower():
        return 'sender_name'
    return 'sender_role'


def shared_single_profile(registry: Mapping | None = None) -> dict:
    data = registry if registry is not None else yaml.safe_load(REGISTRY.read_text(encoding='utf-8'))
    if not isinstance(data, Mapping) or data.get('schema_version') != 'gdl_gc09_sender_typography_profiles_v0_1':
        raise SenderTypographyBlocked('sender_type_registry_invalid')
    profiles = data.get('profiles')
    if not isinstance(profiles, Mapping):
        raise SenderTypographyBlocked('sender_type_profiles_missing')
    dual = profiles.get('DUAL_INDIVIDUAL_V0_1')
    if not isinstance(dual, Mapping) or dual.get('runtime_enabled') is not False:
        raise SenderTypographyBlocked('dual_sender_typography_gate_invalid')
    shared = profiles.get('SINGLE_SHARED_V0_1')
    if not isinstance(shared, Mapping) or shared.get('applies_to') != list(SINGLES):
        raise SenderTypographyBlocked('single_shared_variant_binding_invalid')
    fonts, leading = shared.get('font_size_mm'), shared.get('baseline_advance_mm')
    if not isinstance(fonts, Mapping) or not isinstance(leading, Mapping):
        raise SenderTypographyBlocked('sender_type_metrics_missing')
    required_fonts = ('closing_phrase', 'sender_name', 'sender_role')
    required_leading = ('closing_to_name', 'name_to_role', 'role_to_role', 'other')
    for key in required_fonts:
        value = fonts.get(key)
        if not isinstance(value, (int, float)) or not isfinite(value) or not 2 <= value <= 8:
            raise SenderTypographyBlocked('sender_type_font_mm_invalid')
    for key in required_leading:
        value = leading.get(key)
        if not isinstance(value, (int, float)) or not isfinite(value) or not 3 <= value <= 12:
            raise SenderTypographyBlocked('sender_type_leading_mm_invalid')
    if shared.get('alignment') != 'LEFT' or shared.get('tracking') != 0:
        raise SenderTypographyBlocked('sender_type_alignment_invalid')
    width = shared.get('textbox_x_pdf_mm')
    height = shared.get('textbox_height_mm')
    if width != [31.0, 101.0] or height != 8.0:
        raise SenderTypographyBlocked('sender_type_legacy_box_guard_changed')
    if leading['closing_to_name'] <= leading['role_to_role'] or leading['name_to_role'] <= leading['role_to_role']:
        raise SenderTypographyBlocked('sender_type_group_gap_not_larger')
    return dict(shared)


def plan_single_sender_lines(
    line_ids: Sequence[str], *, start_y_pdf_mm: float,
    variant: str, registry: Mapping | None = None, font_ascender: float = 1.0,
) -> tuple[SenderTypeSlot, ...]:
    if variant not in (*SINGLES, 'SINGLE_SHARED'):
        raise SenderTypographyBlocked('sender_single_variant_only')
    if isinstance(line_ids, (str, bytes)) or not line_ids:
        raise SenderTypographyBlocked('sender_line_ids_missing')
    if any(not isinstance(x, str) or not x.strip() for x in line_ids):
        raise SenderTypographyBlocked('sender_line_id_invalid')
    if len(set(line_ids)) != len(line_ids):
        raise SenderTypographyBlocked('sender_line_id_duplicate')
    try:
        start_y = float(start_y_pdf_mm)
        ascender = float(font_ascender)
    except (ValueError, TypeError) as exc:
        raise SenderTypographyBlocked('sender_font_metric_invalid') from exc
    if not isfinite(start_y) or not isfinite(ascender) or not (0.25 < ascender < 3.0):
        raise SenderTypographyBlocked('sender_font_metric_invalid')
    config = shared_single_profile(registry)
    fonts = config['font_size_mm']
    lead = config['baseline_advance_mm']
    x0, x1 = config['textbox_x_pdf_mm']
    h = config['textbox_height_mm']
    y = start_y
    previous_role = None
    previous_baseline = None
    planned: list[SenderTypeSlot] = []
    for line_id in line_ids:
        role = _role(line_id)
        font_mm = float(fonts[role])
        if previous_role is not None:
            if previous_role == 'closing_phrase' and role == 'sender_name':
                gap = lead['closing_to_name']
            elif previous_role == 'sender_name' and role == 'sender_role':
                gap = lead['name_to_role']
            elif previous_role == 'sender_role' and role == 'sender_role':
                gap = lead['role_to_role']
            else:
                gap = lead['other']
            # For different point sizes, a constant textbox-top delta is NOT
            # a constant baseline delta. Normalize with actual font ascender.
            y = float(previous_baseline) + float(gap) - font_mm * ascender
        baseline = y + font_mm * ascender
        if y < 0 or y + h > 301.0:
            raise SenderTypographyBlocked('sender_typography_outside_pdf')
        planned.append(SenderTypeSlot(
            object_id='inside_text.sender_block.' + line_id,
            semantic_role=role,
            font_size_pt=round(font_mm * PT_PER_MM, 6),
            bbox_pdf_mm=(float(x0), round(y, 6), float(x1), round(y + h, 6)),
            baseline_pdf_mm=round(baseline, 6),
        ))
        previous_role = role
        previous_baseline = baseline
    return tuple(planned)

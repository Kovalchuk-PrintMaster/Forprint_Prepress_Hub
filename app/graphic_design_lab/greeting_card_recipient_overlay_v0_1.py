"""Source-bound raster recipient branding for the canonical greeting-card front.

Internal review renderer capability only. No constructor acceptance or print authority.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pymupdf
import yaml
from PIL import Image

FRONT_FAMILY = 'RECIPIENT_BRANDING_OVERLAY'
SENDER_BBOX_PDF_MM = (69.0, 39.0, 145.0, 115.0)
RECIPIENT_ZONE_PDF_MM = (26.0, 134.0, 188.0, 191.0)
OCCASION_BBOX_PDF_MM = (32.0, 203.5, 182.0, 248.0)
MAX_LOGO_BYTES = 16 * 1024 * 1024
MAX_IMAGE_EDGE = 16000
SHA256 = re.compile(r'^[0-9a-f]{64}$')
ROOT = Path(__file__).resolve().parents[2]
SKELETON = ROOT / 'coordination/graphic_design_lab/directions/greeting_cards/product_skeleton_v0_1.yaml'


def _map(obj: Any) -> dict[str, Any]:
    return dict(obj) if isinstance(obj, Mapping) else {}


def _rect_mm(values: tuple[float, ...]) -> pymupdf.Rect:
    return pymupdf.Rect(*(v * 72.0 / 25.4 for v in values))


def validate_overlay_job(job: Mapping[str, Any]) -> None:
    """Reject mismatched Intake identity; never source logo from sender fields."""
    obj = _map(job)
    front = _map(_map(obj.get('builder_v1')).get('front'))
    family = front.get('family')
    selected = _map(obj.get('branding_selection'))
    presence = selected.get('presence')
    if family == 'STANDARD':
        if presence != 'ABSENT' or front.get('recipient_branding') is not None:
            raise ValueError('standard_front_forbids_recipient_branding')
        return
    if family != FRONT_FAMILY:
        raise ValueError('recipient_overlay_family_unsupported')
    if presence != 'PRESENT':
        raise ValueError('recipient_overlay_requires_present_branding')
    binding = _map(front.get('recipient_branding'))
    if set(binding) != {'asset_id', 'asset_sha256', 'accepted_artifact_ref'}:
        raise ValueError('recipient_overlay_binding_fields_invalid')
    source_id = selected.get('source_asset_id')
    exact = _map(_map(obj.get('exact_person_text_asset_bindings')).get('recipient_branding'))
    if (not isinstance(source_id, str) or not source_id
            or selected.get('target_object_id') not in ('front.recipient_branding', None)
            or exact.get('source_asset_id') != source_id
            or binding['asset_id'] != source_id):
        raise ValueError('recipient_overlay_source_identity_mismatch')
    if (not isinstance(binding['asset_sha256'], str)
            or not SHA256.fullmatch(binding['asset_sha256'])
            or not isinstance(binding['accepted_artifact_ref'], str)
            or not binding['accepted_artifact_ref']):
        raise ValueError('recipient_overlay_artifact_binding_invalid')


def verify_canonical_geometry() -> None:
    if not SKELETON.is_file():
        raise ValueError('recipient_overlay_skeleton_missing')
    doc = yaml.safe_load(SKELETON.read_text(encoding='utf-8'))
    families = doc['variant_model']['front']['semantic_families']
    matches = [x for x in families if x.get('id') == FRONT_FAMILY]
    if len(matches) != 1:
        raise ValueError('recipient_overlay_skeleton_variant_not_unique')
    row = matches[0]
    for key, expected in (
        ('sender_logo_bbox_mm', SENDER_BBOX_PDF_MM),
        ('recipient_branding_zone_mm', RECIPIENT_ZONE_PDF_MM),
        ('occasion_bbox_mm', OCCASION_BBOX_PDF_MM),
    ):
        if tuple(row.get(key) or ()) != expected:
            raise ValueError('recipient_overlay_skeleton_geometry_changed:' + key)


def verify_logo_file(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size > MAX_LOGO_BYTES:
        raise ValueError('recipient_overlay_logo_missing_or_oversize')
    try:
        with Image.open(path) as image:
            if image.format != 'PNG':
                raise ValueError('recipient_overlay_only_png_supported')
            width, height = image.size
            if not (32 <= width <= MAX_IMAGE_EDGE and 32 <= height <= MAX_IMAGE_EDGE):
                raise ValueError('recipient_overlay_logo_dimensions_invalid')
            image.verify()
    except (OSError, SyntaxError) as exc:
        raise ValueError('recipient_overlay_logo_invalid_image') from exc
    return {'pixel_size': [width, height], 'format': 'PNG'}


def fitted_bbox_mm(pixel_size: tuple[int, int]) -> tuple[float, float, float, float]:
    width, height = pixel_size
    if width < 1 or height < 1:
        raise ValueError('recipient_overlay_pixel_size_invalid')
    x0, y0, x1, y1 = RECIPIENT_ZONE_PDF_MM
    scale = min((x1-x0)/width, (y1-y0)/height)
    w, h = width * scale, height * scale
    midx, midy = (x0+x1)/2.0, (y0+y1)/2.0
    bbox = (midx-w/2.0, midy-h/2.0, midx+w/2.0, midy+h/2.0)
    if not (x0-1e-7 <= bbox[0] <= bbox[2] <= x1+1e-7
            and y0-1e-7 <= bbox[1] <= bbox[3] <= y1+1e-7):
        raise ValueError('recipient_overlay_logo_fit_outside_canonical_zone')
    return bbox


def insert_recipient_logo(page: pymupdf.Page, path: Path, logo_info: Mapping[str, Any]) -> dict[str, Any]:
    verify_canonical_geometry()
    dimensions = logo_info['pixel_size']
    bbox = fitted_bbox_mm((int(dimensions[0]), int(dimensions[1])))
    page.insert_image(_rect_mm(bbox), stream=path.read_bytes(), overlay=True, keep_proportion=False)
    return {'presence': 'PRESENT', 'bbox_pdf_mm': [round(v, 5) for v in bbox],
            'source_image_size_px': list(dimensions)}


def verify_rendered_recipient_logo(page: pymupdf.Page, bbox_mm: list[float], dimensions: list[int]) -> None:
    target = tuple(_rect_mm(tuple(bbox_mm)))
    matches = []
    for entry in page.get_image_info(xrefs=True):
        if list((entry.get('width'), entry.get('height'))) != list(dimensions):
            continue
        actual = tuple(entry['bbox'])
        if len(actual) == 4 and max(abs(a-b) for a,b in zip(actual,target)) <= 0.4:
            matches.append(entry)
    if len(matches) != 1:
        raise ValueError('recipient_overlay_rendered_logo_missing_or_ambiguous')

"""Structural validation for deterministic Graphic Design Lab SVG output."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, Mapping

SVG_NS = "http://www.w3.org/2000/svg"


def validate_compiled_svg(
    svg_text: str,
    spec: Mapping[str, Any],
    spread: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []

    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        return [f"svg_xml_parse_error:{exc}"]

    if root.tag != f"{{{SVG_NS}}}svg":
        errors.append("svg_root_invalid")

    page = spec["document"]["page"]
    expected_width = float(page["width_mm"]) * 2.0
    expected_height = float(page["height_mm"])

    if root.get("width") != f"{expected_width:g}mm":
        errors.append("svg_width_mismatch")
    if root.get("height") != f"{expected_height:g}mm":
        errors.append("svg_height_mismatch")
    if root.get("viewBox") != f"0 0 {expected_width:g} {expected_height:g}":
        errors.append("svg_viewbox_mismatch")
    if root.get("data-document-id") != str(spec["document_id"]):
        errors.append("svg_document_id_mismatch")
    if root.get("data-revision-id") != str(spec["revision_id"]):
        errors.append("svg_revision_id_mismatch")
    if root.get("data-spread-id") != str(spread["id"]):
        errors.append("svg_spread_id_mismatch")

    ids: list[str] = []
    for element in root.iter():
        value = element.get("id")
        if value:
            ids.append(value)

    if len(ids) != len(set(ids)):
        errors.append("svg_duplicate_ids")

    expected_object_ids = {str(obj["id"]) for obj in spread.get("objects") or []}
    missing_ids = sorted(expected_object_ids - set(ids))
    errors.extend(f"svg_missing_object_id:{value}" for value in missing_ids)

    if str(spread["id"]) not in ids:
        errors.append("svg_missing_spread_id")

    image_tag = f"{{{SVG_NS}}}image"
    if any(element.tag == image_tag for element in root.iter()):
        errors.append("svg_embedded_raster_not_allowed_in_phase1")

    text_values = [
        (element.text or "")
        for element in root.iter()
        if element.tag == f"{{{SVG_NS}}}text"
    ]
    for obj in spread.get("objects") or []:
        if obj.get("type") == "text" and obj.get("content"):
            if str(obj["content"]) not in text_values:
                errors.append(f"svg_missing_text_content:{obj['id']}")

    return errors

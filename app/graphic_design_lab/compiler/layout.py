"""Deterministic geometry for the first Graphic Design Lab SVG compiler.

This module deliberately handles only the currently supported Phase 1 spread
classes. Geometry is expressed in millimetres and is independent of any GUI or
graphics provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    width: float
    height: float


WEEKDAY_ORDER = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _split_vertical(box: Box, count: int, gap: float = 2.0) -> list[Box]:
    if count <= 0:
        return []
    total_gap = gap * (count - 1)
    height = (box.height - total_gap) / count
    return [
        Box(box.x, box.y + i * (height + gap), box.width, height)
        for i in range(count)
    ]


def layout_spread(
    spread: Mapping[str, Any],
    page_width_mm: float,
    page_height_mm: float,
) -> dict[str, Box]:
    """Return deterministic boxes for all top-level objects in one spread."""
    kind = spread.get("kind")
    objects = list(spread.get("objects") or [])
    spread_width = page_width_mm * 2.0

    if kind == "monthly":
        return _layout_monthly(objects, page_width_mm, page_height_mm)

    if kind == "weekly":
        return _layout_weekly(objects, page_width_mm, page_height_mm)

    # Generic deterministic fallback: vertical stack over the full spread.
    area = Box(10.0, 12.0, spread_width - 20.0, page_height_mm - 24.0)
    boxes = _split_vertical(area, max(len(objects), 1), gap=2.0)
    return {
        str(obj["id"]): boxes[index]
        for index, obj in enumerate(objects)
    }


def _layout_monthly(
    objects: list[Mapping[str, Any]],
    page_width_mm: float,
    page_height_mm: float,
) -> dict[str, Box]:
    left_x = 10.0
    right_x = page_width_mm + 10.0
    usable_width = page_width_mm - 20.0
    result: dict[str, Box] = {}

    title_y = 12.0
    title_h = 9.0
    body_y = 32.0
    body_h = page_height_mm - body_y - 12.0

    for obj in objects:
        role = str(obj.get("role") or "")
        object_id = str(obj["id"])

        if role == "month_name_uk":
            result[object_id] = Box(left_x, title_y, usable_width, title_h)
        elif role == "month_name_en":
            result[object_id] = Box(left_x, title_y + 9.0, usable_width, 7.0)
        elif role == "month_calendar":
            result[object_id] = Box(left_x, body_y, usable_width, body_h)
        elif role == "notes":
            result[object_id] = Box(right_x, body_y, usable_width, body_h)
        else:
            result[object_id] = Box(right_x, 12.0, usable_width, page_height_mm - 24.0)

    return result


def _layout_weekly(
    objects: list[Mapping[str, Any]],
    page_width_mm: float,
    page_height_mm: float,
) -> dict[str, Box]:
    left_area = Box(10.0, 14.0, page_width_mm - 20.0, page_height_mm - 28.0)
    right_area = Box(page_width_mm + 10.0, 14.0, page_width_mm - 20.0, page_height_mm - 28.0)

    left_roles = ["monday", "tuesday", "wednesday"]
    right_roles = ["thursday", "friday", "saturday", "sunday"]
    left_boxes = dict(zip(left_roles, _split_vertical(left_area, 3, gap=2.0)))
    right_boxes = dict(zip(right_roles, _split_vertical(right_area, 4, gap=2.0)))

    result: dict[str, Box] = {}
    fallback_left = left_area
    for obj in objects:
        role = str(obj.get("role") or "")
        object_id = str(obj["id"])
        if role in left_boxes:
            result[object_id] = left_boxes[role]
        elif role in right_boxes:
            result[object_id] = right_boxes[role]
        elif role == "de_emphasized_prior_days":
            result[object_id] = fallback_left
        else:
            result[object_id] = Box(
                page_width_mm + 10.0,
                page_height_mm - 24.0,
                page_width_mm - 20.0,
                10.0,
            )

    return result

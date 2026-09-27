"""Deterministic editable-SVG compiler for Graphic Design Lab v0.1.

The first compiler intentionally targets structured SVG only. It does not render
PNG/PDF, select a provider, or perform production prepress.
"""

from __future__ import annotations

import calendar
import hashlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Mapping

from .layout import Box, layout_spread

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


@dataclass(frozen=True)
class CompiledSvg:
    spread_id: str
    filename: str
    svg_text: str
    sha256: str


def _svg(tag: str) -> str:
    return f"{{{SVG_NS}}}{tag}"


def _fmt(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _cmyk_to_hex(values: list[float] | tuple[float, float, float, float]) -> str:
    c, m, y, k = [max(0.0, min(100.0, float(v))) / 100.0 for v in values]
    r = round(255 * (1 - c) * (1 - k))
    g = round(255 * (1 - m) * (1 - k))
    b = round(255 * (1 - y) * (1 - k))
    return f"#{r:02x}{g:02x}{b:02x}"


def _month_accent(spec: Mapping[str, Any], month: int) -> tuple[str, str | None]:
    month_name = calendar.month_name[month].lower()
    entry = (
        spec.get("design_system", {})
        .get("month_colors", {})
        .get(month_name, {})
    )
    cmyk = entry.get("print_cmyk")
    if isinstance(cmyk, list) and len(cmyk) == 4:
        return _cmyk_to_hex(cmyk), ",".join(str(v) for v in cmyk)
    return "#555555", None


def _period_dates(spread: Mapping[str, Any]) -> list[date]:
    period = spread.get("period") or {}
    if spread.get("kind") == "weekly":
        start = date.fromisoformat(str(period["start_date"]))
        end = date.fromisoformat(str(period["end_date"]))
        days = (end - start).days
        return [start + timedelta(days=i) for i in range(days + 1)]
    return []


def _role_date_map(spread: Mapping[str, Any]) -> dict[str, date]:
    return {d.strftime("%A").lower(): d for d in _period_dates(spread)}


def _add_rect(parent: ET.Element, box: Box, *, stroke: str = "#b0b0b0",
              fill: str = "none", stroke_width: float = 0.35,
              radius: float = 0.0, opacity: float | None = None) -> ET.Element:
    attrs = {
        "x": _fmt(box.x),
        "y": _fmt(box.y),
        "width": _fmt(box.width),
        "height": _fmt(box.height),
        "fill": fill,
        "stroke": stroke,
        "stroke-width": _fmt(stroke_width),
    }
    if radius:
        attrs["rx"] = _fmt(radius)
    if opacity is not None:
        attrs["opacity"] = _fmt(opacity)
    return ET.SubElement(parent, _svg("rect"), attrs)


def _add_text(
    parent: ET.Element,
    x: float,
    y: float,
    text: str,
    *,
    size: float = 4.0,
    weight: str = "400",
    fill: str = "#222222",
    anchor: str | None = None,
) -> ET.Element:
    attrs = {
        "x": _fmt(x),
        "y": _fmt(y),
        "font-family": "Arial, sans-serif",
        "font-size": _fmt(size),
        "font-weight": weight,
        "fill": fill,
    }
    if anchor:
        attrs["text-anchor"] = anchor

    el = ET.SubElement(parent, _svg("text"), attrs)
    el.text = text
    return el


def _render_calendar_grid(
    group: ET.Element,
    box: Box,
    year: int,
    month: int,
    accent: str,
) -> None:
    # The bilingual month heading is already a separate semantic object.
    # Keep the calendar itself quiet: weekday row + the exact number of weeks.
    weekday_h = 8.0
    grid_y = box.y + weekday_h
    grid_h = box.height - weekday_h

    col_w = box.width / 7.0
    weekdays = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    for idx, label in enumerate(weekdays):
        _add_text(
            group,
            box.x + (idx + 0.5) * col_w,
            box.y + 5.0,
            label,
            size=2.4,
            weight="500",
            fill="#666666",
            anchor="middle",
        )

    weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(year, month)
    rows = len(weeks)
    row_h = grid_h / rows

    for col in range(8):
        x = box.x + col * col_w
        ET.SubElement(
            group,
            _svg("line"),
            {
                "x1": _fmt(x),
                "y1": _fmt(grid_y),
                "x2": _fmt(x),
                "y2": _fmt(grid_y + grid_h),
                "stroke": "#d8d8d8",
                "stroke-width": "0.18",
            },
        )

    for row in range(rows + 1):
        y = grid_y + row * row_h
        ET.SubElement(
            group,
            _svg("line"),
            {
                "x1": _fmt(box.x),
                "y1": _fmt(y),
                "x2": _fmt(box.x + box.width),
                "y2": _fmt(y),
                "stroke": "#d8d8d8",
                "stroke-width": "0.18",
            },
        )

    for row, week in enumerate(weeks):
        for col, day in enumerate(week):
            if day:
                _add_text(
                    group,
                    box.x + col * col_w + 1.4,
                    grid_y + row * row_h + 4.0,
                    str(day),
                    size=2.6,
                    fill="#444444",
                )


def _render_notes(group: ET.Element, box: Box, accent: str) -> None:
    _add_text(group, box.x, box.y + 5.0, "NOTES", size=3.0, weight="500", fill=accent)

    y = box.y + 16.0
    while y <= box.y + box.height:
        ET.SubElement(
            group,
            _svg("line"),
            {
                "x1": _fmt(box.x),
                "y1": _fmt(y),
                "x2": _fmt(box.x + box.width),
                "y2": _fmt(y),
                "stroke": "#dddddd",
                "stroke-width": "0.18",
            },
        )
        y += 8.5


def _render_day_block(
    group: ET.Element,
    box: Box,
    role: str,
    day: date | None,
    accent: str,
    print_cmyk: str | None,
) -> None:
    _add_rect(group, box, stroke="#b8b8b8", radius=1.2)
    ET.SubElement(
        group,
        _svg("line"),
        {
            "x1": _fmt(box.x),
            "y1": _fmt(box.y),
            "x2": _fmt(box.x + box.width),
            "y2": _fmt(box.y),
            "stroke": accent,
            "stroke-width": "1.0",
            **({"data-print-cmyk": print_cmyk} if print_cmyk else {}),
        },
    )
    label = role.capitalize()
    if day is not None:
        label = f"{label}  {day.day:02d}.{day.month:02d}"
    _add_text(group, box.x + 2.5, box.y + 6.0, label, size=3.6, weight="600")


def _render_object(
    parent: ET.Element,
    obj: Mapping[str, Any],
    box: Box,
    spread: Mapping[str, Any],
    spec: Mapping[str, Any],
) -> None:
    role = str(obj.get("role") or "")
    object_type = str(obj.get("type"))
    group = ET.SubElement(
        parent,
        _svg("g"),
        {
            "id": str(obj["id"]),
            "data-object-type": object_type,
            "data-role": role,
            **({"data-layer": str(obj["layer"])} if obj.get("layer") else {}),
        },
    )
    if obj.get("style_ref"):
        group.set("data-style-ref", str(obj["style_ref"]))

    period = spread.get("period") or {}
    raw_month = period.get("month")
    if raw_month is not None:
        month = int(raw_month)
    else:
        start_value = period.get("start_date", "2000-01-01")
        if isinstance(start_value, date):
            month = start_value.month
        else:
            month = date.fromisoformat(str(start_value)).month
    accent, print_cmyk = _month_accent(spec, month)

    if object_type == "text":
        content = str(obj.get("content") or "")
        size = 4.6 if role == "month_name_uk" else 2.8
        weight = "500" if role == "month_name_uk" else "400"
        fill = accent if role.startswith("month_name") else "#222222"
        _add_text(group, box.x, box.y + min(box.height - 1.0, size + 1.0),
                  content, size=size, weight=weight, fill=fill)
        if print_cmyk and role.startswith("month_name"):
            group.set("data-print-cmyk", print_cmyk)
        return

    if object_type == "calendar_grid":
        if print_cmyk:
            group.set("data-print-cmyk", print_cmyk)
        _render_calendar_grid(
            group,
            box,
            int(period["year"]),
            int(period["month"]),
            accent,
        )
        return

    if object_type == "notes_block":
        if print_cmyk:
            group.set("data-print-cmyk", print_cmyk)
        _render_notes(group, box, accent)
        return

    if object_type == "day_block":
        role_dates = _role_date_map(spread)
        day = role_dates.get(role)
        if day is not None:
            accent, print_cmyk = _month_accent(spec, day.month)
        if print_cmyk:
            group.set("data-print-cmyk", print_cmyk)
        _render_day_block(group, box, role, day, accent, print_cmyk)
        return

    if object_type == "group" and role == "de_emphasized_prior_days":
        _add_rect(group, box, stroke="#d0d0d0", fill="#fafafa", opacity=0.65)
        _add_text(group, box.x + 3.0, box.y + 7.0, "Prior days — not in diary range",
                  size=3.0, fill="#8a8a8a")
        return

    if object_type == "rectangle":
        _add_rect(group, box)
        return

    if object_type == "line":
        ET.SubElement(
            group,
            _svg("line"),
            {
                "x1": _fmt(box.x),
                "y1": _fmt(box.y),
                "x2": _fmt(box.x + box.width),
                "y2": _fmt(box.y),
                "stroke": "#444444",
                "stroke-width": "0.35",
            },
        )
        return

    # Unsupported-for-rendering contract types remain visible placeholders rather
    # than disappearing silently.
    _add_rect(group, box, stroke="#999999")
    _add_text(group, box.x + 2.0, box.y + 5.0, object_type, size=3.0, fill="#666666")


def compile_spread(spec: Mapping[str, Any], spread: Mapping[str, Any]) -> CompiledSvg:
    page = spec["document"]["page"]
    page_width = float(page["width_mm"])
    page_height = float(page["height_mm"])
    spread_width = page_width * 2.0
    boxes = layout_spread(spread, page_width, page_height)

    root = ET.Element(
        _svg("svg"),
        {
            "width": f"{_fmt(spread_width)}mm",
            "height": f"{_fmt(page_height)}mm",
            "viewBox": f"0 0 {_fmt(spread_width)} {_fmt(page_height)}",
            "data-document-id": str(spec["document_id"]),
            "data-revision-id": str(spec["revision_id"]),
            "data-spread-id": str(spread["id"]),
        },
    )

    _add_rect(root, Box(0.0, 0.0, spread_width, page_height), stroke="none", fill="#ffffff")
    spread_group = ET.SubElement(
        root,
        _svg("g"),
        {"id": str(spread["id"]), "data-spread-kind": str(spread["kind"])},
    )

    for obj in spread.get("objects") or []:
        object_id = str(obj["id"])
        _render_object(spread_group, obj, boxes[object_id], spread, spec)

    ET.indent(root, space="  ")
    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    text = xml_bytes.decode("utf-8") + "\n"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    filename = str(spread["id"]).replace("/", "_") + ".svg"
    return CompiledSvg(str(spread["id"]), filename, text, digest)


def compile_document(spec: Mapping[str, Any]) -> list[CompiledSvg]:
    return [compile_spread(spec, spread) for spread in spec.get("spreads") or []]

from __future__ import annotations

import re
from typing import Any

import pymupdf


AUTHORING_LAYER_HINTS = re.compile(
    r"(danger\s*zone|danger\s*board|guide|guides|non[-_\s]*print|technical\s*guide)",
    re.I,
)


def ocg_name_from_xref(
    doc: pymupdf.Document,
    xref: int,
    ocgs: dict[int, dict[str, Any]] | None = None,
) -> str:
    info = (ocgs or {}).get(int(xref), {})
    name = str(info.get("name") or "")
    if name:
        return name

    try:
        raw = doc.xref_object(int(xref))
    except Exception:
        return ""

    match = re.search(
        r"/Name\s*\((.*?)\)",
        raw,
        re.S,
    )
    if not match:
        return ""

    return match.group(1).strip()


def marked_content_remove(
    data: bytes,
    property_name: str,
) -> tuple[bytes, int]:
    prop = re.escape(
        property_name.encode("latin1")
    )
    start_pattern = re.compile(
        rb"/OC\s*/" + prop + rb"\s+BDC"
    )
    token_pattern = re.compile(
        rb"\b(?:BDC|BMC|EMC)\b"
    )

    removed = 0
    cursor = 0
    chunks: list[bytes] = []

    while True:
        match = start_pattern.search(
            data,
            cursor,
        )
        if match is None:
            chunks.append(
                data[cursor:]
            )
            break

        chunks.append(
            data[cursor:match.start()]
        )
        depth = 1
        end_pos = None

        for token in token_pattern.finditer(
            data,
            match.end(),
        ):
            op = token.group(0)
            if op in (
                b"BDC",
                b"BMC",
            ):
                depth += 1
            else:
                depth -= 1
                if depth == 0:
                    end_pos = token.end()
                    break

        if end_pos is None:
            chunks.append(
                data[match.start():]
            )
            cursor = len(data)
            break

        removed += 1
        cursor = end_pos

    return b"".join(chunks), removed


def strip_authoring_layers(
    doc: pymupdf.Document,
) -> list[dict[str, Any]]:
    ocgs = doc.get_ocgs() or {}
    props_to_strip: dict[
        str,
        dict[str, Any],
    ] = {}

    for page in doc:
        try:
            oc_items = page.get_oc_items()
        except Exception:
            oc_items = []

        for (
            prop_name,
            xref,
            oc_type,
        ) in oc_items:
            layer_name = (
                ocg_name_from_xref(
                    doc,
                    int(xref),
                    ocgs,
                )
            )
            if AUTHORING_LAYER_HINTS.search(
                layer_name
            ):
                props_to_strip[
                    str(prop_name)
                ] = {
                    "property_name":
                        str(prop_name),
                    "xref":
                        int(xref),
                    "type":
                        str(oc_type),
                    "layer_name":
                        layer_name,
                }

    removals = []
    if not props_to_strip:
        return removals

    for xref in range(
        1,
        doc.xref_length(),
    ):
        try:
            stream = doc.xref_stream(
                xref
            )
        except Exception:
            continue

        if not stream:
            continue

        updated = stream
        stream_removed = []

        for (
            prop_name,
            meta,
        ) in props_to_strip.items():
            if (
                b"/OC" not in updated
                or prop_name.encode(
                    "latin1"
                )
                not in updated
            ):
                continue

            updated2, count = (
                marked_content_remove(
                    updated,
                    prop_name,
                )
            )
            if count:
                updated = updated2
                stream_removed.append(
                    {
                        **meta,
                        "stream_xref":
                            xref,
                        "block_count":
                            count,
                    }
                )

        if stream_removed:
            doc.update_stream(
                xref,
                updated,
            )
            removals.extend(
                stream_removed
            )

    return removals


def normalize_image_soft_mask_colorspaces(
    doc: pymupdf.Document,
) -> list[int]:
    """Normalize image soft-mask color spaces for strict PDF renderers."""
    smask_xrefs: set[int] = set()

    for xref in range(
        1,
        doc.xref_length(),
    ):
        try:
            obj = doc.xref_object(
                xref
            )
        except Exception:
            continue

        if "/SMask" not in obj:
            continue

        for match in re.finditer(
            r"/SMask\s+(\d+)\s+0\s+R",
            obj,
        ):
            smask_xrefs.add(
                int(
                    match.group(1)
                )
            )

    normalized: list[int] = []

    for smask_xref in sorted(
        smask_xrefs
    ):
        try:
            obj = doc.xref_object(
                smask_xref
            )
        except Exception:
            continue

        if "/Subtype /Image" not in obj:
            continue

        kind, value = (
            doc.xref_get_key(
                smask_xref,
                "ColorSpace",
            )
        )

        if (
            kind == "name"
            and value == "/DeviceGray"
        ):
            continue

        doc.xref_set_key(
            smask_xref,
            "ColorSpace",
            "/DeviceGray",
        )
        normalized.append(
            smask_xref
        )

    return normalized

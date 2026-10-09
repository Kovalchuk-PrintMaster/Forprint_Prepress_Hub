
from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pymupdf
import yaml
from PIL import Image

from app.graphic_design_lab.greeting_card_builder_input import (
    validate_builder_ready_bundle_v1,
)
from app.graphic_design_lab.greeting_card_embedded_components import (
    GRIGO_SIGNATURE_BBOX_MM,
    GRIGO_SIGNATURE_DRAWING_COUNT,
    SENDER_LOGO_IMAGE_DIGEST_HEX,
    _inspect_grigo_signature,
)
from app.graphic_design_lab.greeting_card_pdf_primitives import (
    normalize_image_soft_mask_colorspaces,
    strip_authoring_layers,
)
from app.graphic_design_lab.greeting_card_private_resources import (
    RESOURCE_FRONT_FONT,
    RESOURCE_GREETING_FONT,
    RESOURCE_REFERENCE_PDF,
    validate_and_resolve_private_resources,
)


ARTIFACT_MANIFEST_SCHEMA = (
    "gdl_greeting_card_builder_artifact_manifest_v0_1"
)
RENDER_REPORT_SCHEMA = (
    "gdl_greeting_card_builder_render_report_v0_1"
)

SUPPORTED_FRONT_FAMILIES = ("STANDARD",)
SUPPORTED_IMAGE_MODES = ("PORTRAIT",)
SUPPORTED_SIGNATURE_VARIANTS = ("GRIGO",)

PT_PER_MM = 72.0 / 25.4
MM_PER_PT = 25.4 / 72.0

COMMON_IMAGE_DIGESTS = {
    "background.paper": "7e00983a508f9c59fb6148e9d33a52ca",
    "frame.ornate": "b136196cfb1dcc996333e75707257946",
    "watermark.emblem": "216f5696fab35f44f4b18c8efe82cefa",
    "front.sender_logo": SENDER_LOGO_IMAGE_DIGEST_HEX,
}

FRONT_STANDARD_SENDER_LOGO_BBOX_MM = (
    64.5,
    59.5,
    149.5,
    144.5,
)
FRONT_STANDARD_OCCASION_BBOX_MM = (
    32.0,
    203.5,
    182.0,
    248.0,
)
FRONT_STANDARD_OCCASION_FONT_SIZE_PT = 52.0

STANDARD_BIRTHDAY_DISPLAY_TEXT = (
    "Привітання з нагоди Дня Народження!"
)
STANDARD_BIRTHDAY_LINES = (
    "Привітання з нагоди",
    "Дня Народження!",
)

GREETING_FONT_SIZE_TIERS_PT = (
    22.5,
    20.0,
    17.0,
)
SENDER_START_Y_VARIANTS_MM = (
    214.0,
    224.0,
    236.0,
)
GREETING_BODY_LEFT_MM = 26.0
GREETING_BODY_TOP_MM = 34.0
GREETING_BODY_RIGHT_MM = 190.0
MIN_SENDER_GAP_LINE_HEIGHTS = 2.0

SENDER_TEXT_LEFT_MM = 31.0
SENDER_TEXT_RIGHT_MM = 101.0
SENDER_LINE_ADVANCE_MM = 8.0
SENDER_BASE_FONT_SIZE_PT = 12.171
SENDER_NAME_FONT_SIZE_PT = 15.591

PREVIEW_DPI = 120

_TEXT_BLOCK_RE = re.compile(
    rb"(?s)(?<![A-Za-z0-9])BT(?![A-Za-z0-9]).*?"
    rb"(?<![A-Za-z0-9])ET(?![A-Za-z0-9])"
)


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(
            lambda: stream.read(1024 * 1024),
            b"",
        ):
            digest.update(block)
    return digest.hexdigest()


def _load_yaml_mapping(
    path: Path,
    *,
    label: str,
) -> dict[str, Any]:
    value = yaml.safe_load(
        path.read_text(encoding="utf-8")
    )
    if not isinstance(value, Mapping):
        raise ValueError(
            f"{label}:must_be_mapping"
        )
    return dict(value)


def _rect_mm(
    values: tuple[float, float, float, float]
    | list[float],
) -> pymupdf.Rect:
    return pymupdf.Rect(
        *(
            float(value) * PT_PER_MM
            for value in values
        )
    )


def _digest_hex(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).hex()
    return str(value)


def _page_image_info(
    page: pymupdf.Page,
) -> list[dict[str, Any]]:
    result = []
    for raw in page.get_image_info(
        hashes=True,
        xrefs=True,
    ):
        item = dict(raw)
        item["digest_hex"] = _digest_hex(
            item.get("digest")
        )
        item["bbox_rect"] = pymupdf.Rect(
            item["bbox"]
        )
        result.append(item)
    return result


def _find_image(
    page: pymupdf.Page,
    digest: str,
    *,
    required: bool = True,
) -> dict[str, Any] | None:
    matches = [
        item
        for item in _page_image_info(page)
        if item["digest_hex"] == digest
    ]

    if len(matches) > 1:
        raise ValueError(
            "image_digest_not_unique:"
            + digest
        )

    if not matches:
        if required:
            raise ValueError(
                "image_digest_missing:"
                + digest
            )
        return None

    return matches[0]


def _raw_image_payload(
    document: pymupdf.Document,
    page: pymupdf.Page,
    xref: int,
) -> tuple[bytes, bytes | None]:
    extracted = document.extract_image(
        xref
    )
    stream = extracted["image"]

    smask = 0
    for item in page.get_images(
        full=True
    ):
        if int(item[0]) == int(xref):
            smask = int(item[1] or 0)
            break

    mask = None
    if smask > 0:
        try:
            mask = document.extract_image(
                smask
            )["image"]
        except Exception:
            mask = None

    return stream, mask


def _insert_digest_image(
    source_doc: pymupdf.Document,
    source_page: pymupdf.Page,
    target_page: pymupdf.Page,
    digest: str,
    *,
    destination: pymupdf.Rect,
) -> None:
    info = _find_image(
        source_page,
        digest,
    )
    assert info is not None

    stream, mask = _raw_image_payload(
        source_doc,
        source_page,
        int(info["xref"]),
    )

    kwargs: dict[str, Any] = {
        "stream": stream,
        "keep_proportion": False,
        "overlay": True,
    }
    if mask:
        kwargs["mask"] = mask

    target_page.insert_image(
        destination,
        **kwargs,
    )


def strip_page_text_blocks(
    document: pymupdf.Document,
    *,
    page_index: int = 0,
) -> int:
    page = document[
        page_index
    ]
    content_xrefs = [
        int(xref)
        for xref in page.get_contents()
    ]

    if not content_xrefs:
        return 0

    removed = 0

    for xref in content_xrefs:
        stream = document.xref_stream(
            xref
        )

        if not stream:
            continue

        updated, count = (
            _TEXT_BLOCK_RE.subn(
                b"",
                stream,
            )
        )

        if count:
            document.update_stream(
                xref,
                updated,
            )
            removed += count

    return removed


def assert_reference_text_removed(
    document: pymupdf.Document,
    *,
    page_index: int = 0,
    label: str,
) -> None:
    page = document[
        page_index
    ]
    residual = _normalized_whitespace(
        page.get_text(
            "text"
        )
    )

    if residual:
        raise ValueError(
            f"{label}:residual_reference_text_after_strip"
        )


def _delete_digest_image(
    page: pymupdf.Page,
    digest: str,
    *,
    required: bool,
) -> bool:
    info = _find_image(
        page,
        digest,
        required=required,
    )
    if info is None:
        return False

    xref = int(
        info.get("xref") or 0
    )
    if xref <= 0:
        raise ValueError(
            "image_xref_missing:"
            + digest
        )

    page.delete_image(xref)
    return True


def _clone_reference_page(
    reference: pymupdf.Document,
    page_index: int,
) -> tuple[
    pymupdf.Document,
    list[dict[str, Any]],
]:
    result = pymupdf.open()
    result.insert_pdf(
        reference,
        from_page=page_index,
        to_page=page_index,
    )
    removals = strip_authoring_layers(
        result
    )
    if not removals:
        result.close()
        raise ValueError(
            "canonical_authoring_layer_not_removed:"
            + str(page_index + 1)
        )
    return result, removals



def _copy_page_boxes(
    source: pymupdf.Page,
    target: pymupdf.Page,
) -> None:
    for getter_name, setter_name in (
        ("cropbox", "set_cropbox"),
        ("bleedbox", "set_bleedbox"),
        ("trimbox", "set_trimbox"),
        ("artbox", "set_artbox"),
    ):
        setter = getattr(
            target,
            setter_name,
            None,
        )
        if setter is None:
            continue
        try:
            setter(
                getattr(
                    source,
                    getter_name,
                )
            )
        except Exception:
            pass


def _new_matching_page(
    document: pymupdf.Document,
    source_page: pymupdf.Page,
) -> pymupdf.Page:
    page = document.new_page(
        width=float(
            source_page.mediabox.width
        ),
        height=float(
            source_page.mediabox.height
        ),
    )
    _copy_page_boxes(
        source_page,
        page,
    )
    return page


def _insert_reference_digest_at_source_geometry(
    source_doc: pymupdf.Document,
    source_page: pymupdf.Page,
    target_page: pymupdf.Page,
    digest: str,
) -> None:
    info = _find_image(
        source_page,
        digest,
    )
    assert info is not None
    _insert_digest_image(
        source_doc,
        source_page,
        target_page,
        digest,
        destination=pymupdf.Rect(
            info["bbox_rect"]
        ),
    )


def _rects_intersect(
    left: pymupdf.Rect,
    right: pymupdf.Rect,
) -> bool:
    return not (
        left.x1 <= right.x0
        or right.x1 <= left.x0
        or left.y1 <= right.y0
        or right.y1 <= left.y0
    )


def _prepare_grigo_signature_overlay(
    reference: pymupdf.Document,
    portrait_digests: set[str],
) -> tuple[
    pymupdf.Document,
    list[dict[str, Any]],
]:
    overlay, removals = (
        _clone_reference_page(
            reference,
            3,
        )
    )
    page = overlay[0]

    for digest in (
        COMMON_IMAGE_DIGESTS[
            "background.paper"
        ],
        COMMON_IMAGE_DIGESTS[
            "frame.ornate"
        ],
        COMMON_IMAGE_DIGESTS[
            "watermark.emblem"
        ],
        *sorted(
            portrait_digests
        ),
    ):
        _delete_digest_image(
            page,
            digest,
            required=False,
        )

    clip = _rect_mm(
        list(
            GRIGO_SIGNATURE_BBOX_MM
        )
    )

    text_hits = []
    raw = page.get_text(
        "dict"
    )
    for block in _list(
        raw.get("blocks")
    ):
        block_map = _mapping(
            block
        )
        for line in _list(
            block_map.get("lines")
        ):
            line_map = _mapping(
                line
            )
            for span in _list(
                line_map.get("spans")
            ):
                item = _mapping(
                    span
                )
                bbox = item.get(
                    "bbox"
                )
                if not bbox:
                    continue
                if _rects_intersect(
                    pymupdf.Rect(
                        bbox
                    ),
                    clip,
                ):
                    text = str(
                        item.get(
                            "text"
                        )
                        or ""
                    ).strip()
                    if text:
                        text_hits.append(
                            text
                        )

    if text_hits:
        overlay.close()
        raise ValueError(
            "grigo_signature_clip_contains_reference_text"
        )

    drawing_hits = [
        drawing
        for drawing in page.get_drawings()
        if _rects_intersect(
            pymupdf.Rect(
                drawing["rect"]
            ),
            clip,
        )
    ]
    if (
        len(
            drawing_hits
        )
        != GRIGO_SIGNATURE_DRAWING_COUNT
    ):
        overlay.close()
        raise ValueError(
            "grigo_signature_clip_drawing_count_mismatch:"
            + str(
                len(
                    drawing_hits
                )
            )
        )

    return overlay, removals


def _overlay_grigo_signature(
    target_page: pymupdf.Page,
    overlay: pymupdf.Document,
) -> None:
    clip = _rect_mm(
        list(
            GRIGO_SIGNATURE_BBOX_MM
        )
    )
    target_page.show_pdf_page(
        clip,
        overlay,
        0,
        clip=clip,
        keep_proportion=False,
        overlay=True,
    )


def _normalized_whitespace(
    value: str,
) -> str:
    return " ".join(
        str(value).split()
    )


def _front_occasion_span_layout(
    page: pymupdf.Page,
) -> list[dict[str, Any]]:
    expected = list(
        STANDARD_BIRTHDAY_LINES
    )
    found = []

    raw = page.get_text(
        "dict"
    )

    for block in _list(
        raw.get("blocks")
    ):
        block_map = _mapping(
            block
        )
        for line in _list(
            block_map.get("lines")
        ):
            line_map = _mapping(
                line
            )
            for span in _list(
                line_map.get("spans")
            ):
                item = _mapping(
                    span
                )
                text = str(
                    item.get("text") or ""
                ).strip()
                font = str(
                    item.get("font") or ""
                )

                if text not in expected:
                    continue
                if (
                    "MonotypeCorsiva"
                    not in font
                ):
                    continue

                origin = item.get(
                    "origin"
                )
                bbox = item.get(
                    "bbox"
                )
                size = item.get(
                    "size"
                )

                if (
                    not isinstance(
                        origin,
                        (list, tuple),
                    )
                    or len(origin) != 2
                    or not isinstance(
                        bbox,
                        (list, tuple),
                    )
                    or len(bbox) != 4
                    or not isinstance(
                        size,
                        (int, float),
                    )
                ):
                    raise ValueError(
                        "canonical_front_occasion_geometry_invalid"
                    )

                found.append(
                    {
                        "text": text,
                        "origin": [
                            float(
                                origin[0]
                            ),
                            float(
                                origin[1]
                            ),
                        ],
                        "bbox": [
                            float(value)
                            for value in bbox
                        ],
                        "size": float(
                            size
                        ),
                        "font": font,
                    }
                )

    found.sort(
        key=lambda item: (
            item["origin"][1],
            item["origin"][0],
        )
    )

    texts = [
        item["text"]
        for item in found
    ]

    if texts != expected:
        raise ValueError(
            "canonical_front_occasion_layout_mismatch:"
            + "|".join(
                texts
            )
        )

    for item in found:
        if not (
            50.0
            <= float(
                item["size"]
            )
            <= 54.0
        ):
            raise ValueError(
                "canonical_front_occasion_font_size_out_of_bounds"
            )

    return found


def _render_standard_birthday_occasion(
    page: pymupdf.Page,
    display_text: str,
    *,
    font_path: Path,
    canonical_layout: list[
        dict[str, Any]
    ],
) -> dict[str, Any]:
    if (
        _normalized_whitespace(
            display_text
        )
        != STANDARD_BIRTHDAY_DISPLAY_TEXT
    ):
        raise ValueError(
            "builder_v0_1_standard_occasion_not_implemented:"
            + _normalized_whitespace(
                display_text
            )
        )

    if len(
        canonical_layout
    ) != 2:
        raise ValueError(
            "canonical_front_occasion_line_count_mismatch"
        )

    for expected_text, raw in zip(
        STANDARD_BIRTHDAY_LINES,
        canonical_layout,
    ):
        item = _mapping(
            raw
        )

        if (
            item.get("text")
            != expected_text
        ):
            raise ValueError(
                "canonical_front_occasion_line_identity_mismatch"
            )

        origin = item[
            "origin"
        ]
        size = float(
            item["size"]
        )

        page.insert_text(
            pymupdf.Point(
                float(
                    origin[0]
                ),
                float(
                    origin[1]
                ),
            ),
            expected_text,
            fontname="MonotypeCorsiva",
            fontfile=str(
                font_path
            ),
            fontsize=size,
            color=(0, 0, 0),
            overlay=True,
        )

    return {
        "display_text":
            STANDARD_BIRTHDAY_DISPLAY_TEXT,
        "line_count":
            2,
        "line_texts":
            list(
                STANDARD_BIRTHDAY_LINES
            ),
        "geometry_source":
            "EXACT_CANONICAL_REFERENCE_TEXT_ORIGINS",
        "font_size_source":
            "EXACT_CANONICAL_REFERENCE_SPANS",
        "font":
            "MonotypeCorsiva",
    }


def _insert_textbox_exact(
    page: pymupdf.Page,
    rect: pymupdf.Rect,
    text: str,
    *,
    font_path: Path,
    fontname: str,
    fontsize: float,
    align: int,
    lineheight: float = 1.0,
) -> float:
    result = page.insert_textbox(
        rect,
        text,
        fontname=fontname,
        fontfile=str(font_path),
        fontsize=fontsize,
        lineheight=lineheight,
        align=align,
        color=(0, 0, 0),
        overlay=True,
    )

    if result < 0:
        raise ValueError(
            "text_does_not_fit:"
            f"font={fontname}:size={fontsize}:"
            f"deficit={result}"
        )

    return float(result)


def _fit_greeting(
    page: pymupdf.Page,
    text: str,
    *,
    font_path: Path,
) -> tuple[float, float, pymupdf.Rect]:
    for font_size in (
        GREETING_FONT_SIZE_TIERS_PT
    ):
        line_height_mm = (
            font_size * MM_PER_PT
        )

        for sender_y_mm in (
            SENDER_START_Y_VARIANTS_MM
        ):
            body_bottom_mm = (
                sender_y_mm
                - (
                    MIN_SENDER_GAP_LINE_HEIGHTS
                    * line_height_mm
                )
            )

            if (
                body_bottom_mm
                <= GREETING_BODY_TOP_MM
            ):
                continue

            rect = _rect_mm(
                [
                    GREETING_BODY_LEFT_MM,
                    GREETING_BODY_TOP_MM,
                    GREETING_BODY_RIGHT_MM,
                    body_bottom_mm,
                ]
            )

            scratch = pymupdf.open()
            scratch_page = scratch.new_page(
                width=float(page.rect.width),
                height=float(page.rect.height),
            )

            result = scratch_page.insert_textbox(
                rect,
                text,
                fontname="ZapfChanceryC",
                fontfile=str(font_path),
                fontsize=font_size,
                lineheight=1.0,
                align=pymupdf.TEXT_ALIGN_CENTER,
                color=(0, 0, 0),
            )
            scratch.close()

            if result >= 0:
                return (
                    float(font_size),
                    float(sender_y_mm),
                    rect,
                )

    raise ValueError(
        "greeting_text_does_not_fit_canonical_tiers"
    )


def _sender_font_size(
    line_id: str,
) -> float:
    if "name" in line_id.lower():
        return SENDER_NAME_FONT_SIZE_PT
    return SENDER_BASE_FONT_SIZE_PT


def _render_sender_lines(
    page: pymupdf.Page,
    lines: list[dict[str, Any]],
    *,
    font_path: Path,
    start_y_mm: float,
) -> None:
    current_y = float(start_y_mm)

    for raw in lines:
        line = _mapping(raw)
        line_id = str(line["id"])
        text = str(line["text"])
        font_size = _sender_font_size(
            line_id
        )

        rect = _rect_mm(
            [
                SENDER_TEXT_LEFT_MM,
                current_y,
                SENDER_TEXT_RIGHT_MM,
                current_y
                + SENDER_LINE_ADVANCE_MM,
            ]
        )

        _insert_textbox_exact(
            page,
            rect,
            text,
            font_path=font_path,
            fontname="ZapfChanceryC",
            fontsize=font_size,
            align=pymupdf.TEXT_ALIGN_LEFT,
            lineheight=1.0,
        )

        current_y += (
            SENDER_LINE_ADVANCE_MM
        )


def normalize_portrait_bytes(
    source_path: Path,
    *,
    width: int,
    height: int,
) -> bytes:
    if width <= 0 or height <= 0:
        raise ValueError(
            "portrait_target_size_invalid"
        )

    with Image.open(
        source_path
    ) as source:
        image = source.convert("RGBA")

    source_ratio = (
        image.width / image.height
    )
    target_ratio = (
        width / height
    )

    if source_ratio > target_ratio:
        crop_width = round(
            image.height * target_ratio
        )
        left = (
            image.width - crop_width
        ) // 2
        box = (
            left,
            0,
            left + crop_width,
            image.height,
        )
    else:
        crop_height = round(
            image.width / target_ratio
        )
        top = (
            image.height - crop_height
        ) // 2
        box = (
            0,
            top,
            image.width,
            top + crop_height,
        )

    image = image.crop(
        box
    ).resize(
        (width, height),
        Image.Resampling.LANCZOS,
    )

    output = io.BytesIO()
    image.save(
        output,
        format="PNG",
        optimize=False,
    )
    return output.getvalue()


def _alpha_profile_image(
    image: Image.Image,
) -> dict[str, Any]:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    histogram = alpha.histogram()
    transparent = int(histogram[0])
    opaque = int(histogram[255])
    total = int(rgba.width * rgba.height)
    partial = int(total - transparent - opaque)
    return {
        "pixel_size": [int(rgba.width), int(rgba.height)],
        "transparent_pixels": transparent,
        "partial_alpha_pixels": partial,
        "opaque_pixels": opaque,
        "has_transparency": bool(transparent > 0 or partial > 0),
    }


def _alpha_profile_path(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        return _alpha_profile_image(image)


def _alpha_profile_bytes(payload: bytes) -> dict[str, Any]:
    with Image.open(io.BytesIO(payload)) as image:
        return _alpha_profile_image(image)


def _image_soft_mask_xref(page: pymupdf.Page, image_xref: int) -> int:
    for item in page.get_images(full=True):
        if int(item[0]) == int(image_xref):
            return int(item[1] or 0)
    return 0


def _reference_page3_portrait_info(
    reference_page: pymupdf.Page,
) -> dict[str, Any]:
    common = set(COMMON_IMAGE_DIGESTS.values())
    variable = [
        item
        for item in _page_image_info(reference_page)
        if item["digest_hex"] not in common
    ]
    unique = {item["digest_hex"]: item for item in variable}
    if len(unique) != 1:
        raise ValueError(
            "reference_page3_expected_one_variable_portrait:"
            + ",".join(sorted(str(key) for key in unique))
        )
    item = next(iter(unique.values()))
    width = int(item.get("width") or 0)
    height = int(item.get("height") or 0)
    if width <= 0 or height <= 0:
        raise ValueError("reference_portrait_pixel_size_invalid")
    return {**item, "width": width, "height": height}


def _page_content_stream_sha256(
    document: pymupdf.Document,
    page: pymupdf.Page,
) -> str:
    digest = hashlib.sha256()

    for xref in page.get_contents():
        digest.update(
            document.xref_stream(
                int(xref)
            )
        )

    return digest.hexdigest()


def _clone_page3_portrait_mask_overlay(
    reference: pymupdf.Document,
    *,
    portrait_path: Path,
) -> tuple[pymupdf.Document, dict[str, Any]]:
    reference_page = reference[2]
    item = _reference_page3_portrait_info(
        reference_page
    )

    source_alpha = _alpha_profile_path(
        portrait_path
    )

    normalized = normalize_portrait_bytes(
        portrait_path,
        width=int(
            item["width"]
        ),
        height=int(
            item["height"]
        ),
    )

    normalized_alpha = _alpha_profile_bytes(
        normalized
    )

    if (
        source_alpha["has_transparency"]
        and not normalized_alpha[
            "has_transparency"
        ]
    ):
        raise ValueError(
            "accepted_portrait_transparency_lost_during_normalization"
        )

    overlay = pymupdf.open()
    overlay.insert_pdf(
        reference,
        from_page=2,
        to_page=2,
    )

    authoring_removed = strip_authoring_layers(
        overlay
    )

    page = overlay[0]
    images = _page_image_info(
        page
    )

    portrait_matches = [
        entry
        for entry in images
        if entry["digest_hex"]
        == item["digest_hex"]
    ]

    if len(portrait_matches) != 1:
        overlay.close()
        raise ValueError(
            "canonical_portrait_overlay_expected_one_reference_portrait:"
            + str(len(portrait_matches))
        )

    portrait_xref = int(
        portrait_matches[0].get("xref")
        or 0
    )

    if portrait_xref <= 0:
        overlay.close()
        raise ValueError(
            "canonical_portrait_overlay_xref_missing"
        )

    background_xrefs = sorted(
        {
            int(
                entry.get("xref")
                or 0
            )
            for entry in images
            if entry["digest_hex"]
            == COMMON_IMAGE_DIGESTS[
                "background.paper"
            ]
            and int(
                entry.get("xref")
                or 0
            )
            > 0
        }
    )

    frame_xrefs = sorted(
        {
            int(
                entry.get("xref")
                or 0
            )
            for entry in images
            if entry["digest_hex"]
            == COMMON_IMAGE_DIGESTS[
                "frame.ornate"
            ]
            and int(
                entry.get("xref")
                or 0
            )
            > 0
        }
    )

    if not background_xrefs:
        overlay.close()
        raise ValueError(
            "canonical_portrait_overlay_background_missing"
        )

    if not frame_xrefs:
        overlay.close()
        raise ValueError(
            "canonical_portrait_overlay_frame_missing"
        )

    portrait_rects_before = [
        [
            float(rect.x0),
            float(rect.y0),
            float(rect.x1),
            float(rect.y1),
        ]
        for rect in page.get_image_rects(
            portrait_xref
        )
    ]

    if not portrait_rects_before:
        overlay.close()
        raise ValueError(
            "canonical_portrait_reference_placement_missing"
        )

    page.replace_image(
        portrait_xref,
        stream=normalized,
    )

    portrait_rects_after = [
        [
            float(rect.x0),
            float(rect.y0),
            float(rect.x1),
            float(rect.y1),
        ]
        for rect in page.get_image_rects(
            portrait_xref
        )
    ]

    if portrait_rects_after != portrait_rects_before:
        overlay.close()
        raise ValueError(
            "canonical_portrait_reference_placement_changed"
        )

    for xref in (
        background_xrefs
        + frame_xrefs
    ):
        page.delete_image(
            xref
        )

    normalize_image_soft_mask_colorspaces(
        overlay
    )

    soft_mask_xref = _image_soft_mask_xref(
        page,
        portrait_xref,
    )

    if (
        normalized_alpha[
            "has_transparency"
        ]
        and soft_mask_xref <= 0
    ):
        overlay.close()
        raise ValueError(
            "accepted_portrait_soft_mask_missing_in_canonical_overlay"
        )

    return overlay, {
        "reference_portrait_digest":
            item["digest_hex"],
        "reference_pixel_size": [
            int(item["width"]),
            int(item["height"]),
        ],
        "reference_bbox_pt": [
            float(value)
            for value in item[
                "bbox_rect"
            ]
        ],
        "source_alpha":
            source_alpha,
        "normalized_alpha":
            normalized_alpha,
        "portrait_xref":
            portrait_xref,
        "portrait_soft_mask_xref":
            soft_mask_xref,
        "authoring_layers_removed":
            authoring_removed,
        "background_xrefs_neutralized":
            background_xrefs,
        "frame_xrefs_neutralized":
            frame_xrefs,
        "reference_portrait_placement_before":
            portrait_rects_before,
        "reference_portrait_placement_after":
            portrait_rects_after,
        "reference_portrait_placement_preserved":
            True,
        "canonical_portrait_mask_layer_reused":
            True,
    }


def _compose_page3_with_accepted_portrait(
    output: pymupdf.Document,
    reference: pymupdf.Document,
    *,
    portrait_path: Path,
) -> dict[str, Any]:
    reference_page = reference[2]

    overlay, overlay_meta = (
        _clone_page3_portrait_mask_overlay(
            reference,
            portrait_path=portrait_path,
        )
    )

    page = _new_matching_page(
        output,
        reference_page,
    )

    _insert_reference_digest_at_source_geometry(
        reference,
        reference_page,
        page,
        COMMON_IMAGE_DIGESTS[
            "background.paper"
        ],
    )

    page.show_pdf_page(
        page.rect,
        overlay,
        0,
        overlay=True,
    )

    overlay.close()

    _insert_reference_digest_at_source_geometry(
        reference,
        reference_page,
        page,
        COMMON_IMAGE_DIGESTS[
            "frame.ornate"
        ],
    )

    return {
        "reference_portrait_digest":
            overlay_meta[
                "reference_portrait_digest"
            ],
        "reference_pixel_size":
            overlay_meta[
                "reference_pixel_size"
            ],
        "reference_bbox_pt":
            overlay_meta[
                "reference_bbox_pt"
            ],
        "geometry_reused":
            True,
        "source_alpha":
            overlay_meta[
                "source_alpha"
            ],
        "normalized_alpha":
            overlay_meta[
                "normalized_alpha"
            ],
        "inserted_image_xref":
            overlay_meta[
                "portrait_xref"
            ],
        "inserted_soft_mask_xref":
            overlay_meta[
                "portrait_soft_mask_xref"
            ],
        "accepted_rgba_soft_mask_preserved":
            bool(
                (
                    not overlay_meta[
                        "normalized_alpha"
                    ][
                        "has_transparency"
                    ]
                )
                or overlay_meta[
                    "portrait_soft_mask_xref"
                ]
                > 0
            ),
        "canonical_portrait_mask_layer_reused":
            True,
        "reference_portrait_placement_preserved":
            overlay_meta[
                "reference_portrait_placement_preserved"
            ],
        "portrait_overlay_filter": {
            "authoring_layers_removed":
                overlay_meta[
                    "authoring_layers_removed"
                ],
            "background_xrefs_neutralized":
                overlay_meta[
                    "background_xrefs_neutralized"
                ],
            "frame_xrefs_neutralized":
                overlay_meta[
                    "frame_xrefs_neutralized"
                ],
            "reference_portrait_placement_before":
                overlay_meta[
                    "reference_portrait_placement_before"
                ],
            "reference_portrait_placement_after":
                overlay_meta[
                    "reference_portrait_placement_after"
                ],
        },
        "composition":
            "DETERMINISTIC_BASE_PLUS_PRESERVED_CANONICAL_PORTRAIT_MASK_LAYER",
    }


def _bbox_close(
    actual: pymupdf.Rect,
    expected: list[float],
    *,
    tolerance_pt: float = 0.75,
) -> bool:
    if len(expected) != 4:
        raise ValueError("portrait_expected_bbox_invalid")

    actual_values = [
        float(actual.x0),
        float(actual.y0),
        float(actual.x1),
        float(actual.y1),
    ]

    return all(
        abs(current - float(target)) <= tolerance_pt
        for current, target in zip(actual_values, expected)
    )


def _page_portrait_soft_mask_evidence(
    pdf_path: Path,
    *,
    page_index: int,
    transparency_required: bool,
    expected_pixel_size: list[int],
    expected_bbox_pt: list[float],
) -> dict[str, Any]:
    if len(expected_pixel_size) != 2:
        raise ValueError("portrait_expected_pixel_size_invalid")

    expected_width = int(expected_pixel_size[0])
    expected_height = int(expected_pixel_size[1])

    if expected_width <= 0 or expected_height <= 0:
        raise ValueError("portrait_expected_pixel_size_invalid")

    with pymupdf.open(pdf_path) as document:
        if page_index < 0 or page_index >= document.page_count:
            raise ValueError("portrait_evidence_page_index_invalid")

        page = document[page_index]
        infos = _page_image_info(page)
        candidates = []

        for item in infos:
            width = int(item.get("width") or 0)
            height = int(item.get("height") or 0)
            bbox = item.get("bbox_rect")

            if width != expected_width or height != expected_height:
                continue

            if not isinstance(bbox, pymupdf.Rect):
                continue

            if not _bbox_close(
                bbox,
                expected_bbox_pt,
            ):
                continue

            candidates.append(item)

        if len(candidates) != 1:
            raise ValueError(
                "output_page3_portrait_candidate_count:"
                + str(len(candidates))
            )

        item = candidates[0]
        image_xref = int(item.get("xref") or 0)

        if image_xref <= 0:
            raise ValueError("output_page3_portrait_xref_missing")

        soft_mask_xref = _image_soft_mask_xref(
            page,
            image_xref,
        )

        if transparency_required and soft_mask_xref <= 0:
            raise ValueError(
                "output_page3_portrait_soft_mask_missing"
            )

        soft_mask_colorspace = None

        if soft_mask_xref > 0:
            _, soft_mask_colorspace = document.xref_get_key(
                soft_mask_xref,
                "ColorSpace",
            )

            if soft_mask_colorspace != "/DeviceGray":
                raise ValueError(
                    "output_page3_soft_mask_not_devicegray:"
                    + str(soft_mask_colorspace)
                )

        return {
            "page_image_count": len(infos),
            "portrait_candidate_count": len(candidates),
            "portrait_identity":
                "REFERENCE_PIXEL_SIZE_AND_BBOX",
            "expected_pixel_size": [
                expected_width,
                expected_height,
            ],
            "expected_bbox_pt": [
                float(value)
                for value in expected_bbox_pt
            ],
            "image_xref": image_xref,
            "soft_mask_xref": soft_mask_xref,
            "soft_mask_colorspace": soft_mask_colorspace,
            "transparency_required": transparency_required,
            "soft_mask_valid": bool(
                (not transparency_required)
                or (
                    soft_mask_xref > 0
                    and soft_mask_colorspace == "/DeviceGray"
                )
            ),
        }


def _artifact_manifest_entry(
    manifest: Mapping[str, Any],
    *,
    artifact_ref: str,
    source_asset_id: str,
    expected_sha256: str,
) -> Path:
    data = _mapping(manifest)

    if (
        data.get("schema_version")
        != ARTIFACT_MANIFEST_SCHEMA
    ):
        raise ValueError(
            "artifact_manifest.schema_version:unsupported"
        )

    artifacts = _mapping(
        data.get("artifacts")
    )
    entry = _mapping(
        artifacts.get(artifact_ref)
    )

    if not entry:
        raise ValueError(
            "artifact_manifest.binding_missing:"
            + artifact_ref
        )

    if (
        entry.get("source_asset_id")
        != source_asset_id
    ):
        raise ValueError(
            "artifact_manifest.source_asset_id_mismatch:"
            + artifact_ref
        )

    raw_path = entry.get("path")
    if (
        not isinstance(
            raw_path,
            str,
        )
        or not raw_path
    ):
        raise ValueError(
            "artifact_manifest.path_required:"
            + artifact_ref
        )

    path = Path(
        raw_path
    ).expanduser()

    if not path.is_absolute():
        raise ValueError(
            "artifact_manifest.path_must_be_absolute:"
            + artifact_ref
        )

    path = path.resolve()

    if not path.is_file():
        raise ValueError(
            "artifact_manifest.file_missing:"
            + artifact_ref
        )

    actual = _sha256_file(
        path
    )
    if actual != expected_sha256:
        raise ValueError(
            "artifact_manifest.sha256_mismatch:"
            + artifact_ref
        )

    recorded = entry.get(
        "sha256"
    )
    if recorded != expected_sha256:
        raise ValueError(
            "artifact_manifest.recorded_sha256_mismatch:"
            + artifact_ref
        )

    return path


def _resource_path(
    resources: Mapping[
        str,
        Mapping[str, Any],
    ],
    resource_id: str,
) -> Path:
    item = _mapping(
        resources.get(
            resource_id
        )
    )
    value = item.get("path")

    if isinstance(
        value,
        Path,
    ):
        path = value
    elif isinstance(
        value,
        str,
    ):
        path = Path(value)
    else:
        raise ValueError(
            "private_resource_runtime_path_missing:"
            + resource_id
        )

    path = path.resolve()
    if not path.is_file():
        raise ValueError(
            "private_resource_runtime_file_missing:"
            + resource_id
        )

    return path


def _validate_first_slice_job(
    job: Mapping[str, Any],
) -> None:
    data = _mapping(job)
    payload = _mapping(
        data.get("builder_v1")
    )
    front = _mapping(
        payload.get("front")
    )
    inside_image = _mapping(
        payload.get("inside_image")
    )
    sender = _mapping(
        payload.get("sender_text")
    )
    branding = _mapping(
        data.get("branding_selection")
    )

    if (
        front.get("family")
        not in SUPPORTED_FRONT_FAMILIES
    ):
        raise ValueError(
            "builder_v0_1_front_family_not_implemented:"
            + str(
                front.get("family")
            )
        )

    if (
        inside_image.get("mode")
        not in SUPPORTED_IMAGE_MODES
    ):
        raise ValueError(
            "builder_v0_1_inside_image_mode_not_implemented:"
            + str(
                inside_image.get("mode")
            )
        )

    if (
        sender.get(
            "signature_variant_id"
        )
        not in SUPPORTED_SIGNATURE_VARIANTS
    ):
        raise ValueError(
            "builder_v0_1_signature_variant_not_implemented:"
            + str(
                sender.get(
                    "signature_variant_id"
                )
            )
        )

    if (
        branding.get("presence")
        != "ABSENT"
    ):
        raise ValueError(
            "builder_v0_1_recipient_branding_not_implemented"
        )


def _text_fidelity_check(
    pdf_path: Path,
    *,
    occasion_text: str,
    greeting_text: str,
    sender_lines: list[
        dict[str, Any]
    ],
) -> dict[str, Any]:
    with pymupdf.open(
        pdf_path
    ) as document:
        page1_text = (
            _normalized_whitespace(
                document[0].get_text(
                    "text"
                )
            )
        )
        page4_text = (
            _normalized_whitespace(
                document[3].get_text(
                    "text"
                )
            )
        )

        expected_occasion = (
            _normalized_whitespace(
                occasion_text
            )
        )
        expected_greeting = (
            _normalized_whitespace(
                greeting_text
            )
        )

        if (
            expected_occasion
            not in page1_text
        ):
            raise ValueError(
                "output_occasion_text_fidelity_failed"
            )

        if (
            expected_greeting
            not in page4_text
        ):
            raise ValueError(
                "output_greeting_text_fidelity_failed"
            )

        expected_page4_parts = [
            expected_greeting
        ]

        for raw in sender_lines:
            line = _mapping(
                raw
            )
            expected = (
                _normalized_whitespace(
                    str(
                        line["text"]
                    )
                )
            )
            if expected not in page4_text:
                raise ValueError(
                    "output_sender_text_fidelity_failed:"
                    + str(
                        line["id"]
                    )
                )
            expected_page4_parts.append(
                expected
            )

        expected_page4_text = (
            _normalized_whitespace(
                " ".join(
                    expected_page4_parts
                )
            )
        )
        if page4_text != expected_page4_text:
            raise ValueError(
                "output_page4_unexpected_extractable_text"
            )

        page1_fonts = {
            str(
                item[4]
            )
            for item in document[0].get_fonts(
                full=True
            )
        }
        page4_fonts = {
            str(
                item[4]
            )
            for item in document[3].get_fonts(
                full=True
            )
        }

        if (
            "MonotypeCorsiva"
            not in page1_fonts
        ):
            raise ValueError(
                "output_front_font_not_exact"
            )

        if (
            "ZapfChanceryC"
            not in page4_fonts
        ):
            raise ValueError(
                "output_greeting_font_not_exact"
            )

    return {
        "occasion_text": "PASS",
        "greeting_text": "PASS",
        "sender_text": "PASS",
        "front_font": "MonotypeCorsiva",
        "greeting_font": "ZapfChanceryC",
    }


def _external_checks(
    pdf_path: Path,
) -> dict[str, Any]:
    checks: dict[
        str,
        Any,
    ] = {}

    for name, command in (
        (
            "qpdf",
            [
                "qpdf",
                "--check",
                str(pdf_path),
            ],
        ),
        (
            "pdfinfo",
            [
                "pdfinfo",
                "-box",
                str(pdf_path),
            ],
        ),
    ):
        executable = shutil.which(
            command[0]
        )
        if executable is None:
            raise ValueError(
                "required_pdf_checker_missing:"
                + command[0]
            )

        cp = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        checks[name] = {
            "exit_code":
                cp.returncode,
            "output":
                cp.stdout.strip(),
        }

        if cp.returncode != 0:
            raise ValueError(
                "external_pdf_check_failed:"
                + name
            )

    return checks


def render_previews_from_final_pdf(
    pdf_path: Path,
    preview_dir: Path,
    *,
    stem: str,
    dpi: int = PREVIEW_DPI,
) -> list[Path]:
    preview_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    paths = []

    with pymupdf.open(
        pdf_path
    ) as document:
        if document.page_count != 4:
            raise ValueError(
                "final_pdf_page_count_mismatch:"
                + str(
                    document.page_count
                )
            )

        matrix = pymupdf.Matrix(
            dpi / 72.0,
            dpi / 72.0,
        )

        for index, page in enumerate(
            document,
            start=1,
        ):
            pix = page.get_pixmap(
                matrix=matrix,
                alpha=False,
            )
            path = (
                preview_dir
                / (
                    f"{stem}__"
                    f"{index:02d}.png"
                )
            )
            pix.save(
                str(path)
            )
            paths.append(
                path
            )

    return paths


def _build_one_job(
    job: Mapping[str, Any],
    *,
    resources: Mapping[
        str,
        Mapping[str, Any],
    ],
    artifact_manifest:
        Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    data = _mapping(
        job
    )
    _validate_first_slice_job(
        data
    )

    payload = _mapping(
        data["builder_v1"]
    )
    front = _mapping(
        payload["front"]
    )
    occasion = _mapping(
        front["occasion"]
    )
    image = _mapping(
        payload["inside_image"]
    )
    sender = _mapping(
        payload["sender_text"]
    )

    exact = _mapping(
        data.get(
            "exact_person_text_asset_bindings"
        )
    )
    portrait_binding = _mapping(
        exact.get(
            "portrait"
        )
    )

    accepted_artifact_ref = str(
        image["accepted_artifact_ref"]
    )
    source_asset_id = str(
        portrait_binding[
            "source_asset_id"
        ]
    )

    portrait_path = (
        _artifact_manifest_entry(
            artifact_manifest,
            artifact_ref=accepted_artifact_ref,
            source_asset_id=source_asset_id,
            expected_sha256=str(
                image[
                    "asset_sha256"
                ]
            ),
        )
    )

    reference_path = (
        _resource_path(
            resources,
            RESOURCE_REFERENCE_PDF,
        )
    )
    front_font_path = (
        _resource_path(
            resources,
            RESOURCE_FRONT_FONT,
        )
    )
    greeting_font_path = (
        _resource_path(
            resources,
            RESOURCE_GREETING_FONT,
        )
    )

    job_id = str(
        data["job_id"]
    )
    revision = str(
        payload["revision"]
    )
    stem = (
        f"{job_id}__{revision}"
    )

    completed = (
        output_dir / "completed"
    )
    preview_dir = (
        output_dir / "preview"
    )
    report_dir = (
        output_dir / "report"
    )

    completed.mkdir(
        parents=True,
        exist_ok=True,
    )
    preview_dir.mkdir(
        parents=True,
        exist_ok=True,
    )
    report_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    pdf_path = (
        completed
        / f"{stem}.pdf"
    )

    with pymupdf.open(
        reference_path
    ) as reference:
        if reference.page_count != 4:
            raise ValueError(
                "reference_pdf_page_count_mismatch"
            )

        out = pymupdf.open()

        # Physical page 1 / logical PAGE_1_FRONT.
        canonical_front_occasion_layout = (
            _front_occasion_span_layout(
                reference[0]
            )
        )

        (
            page1_doc,
            page1_authoring_removed,
        ) = _clone_reference_page(
            reference,
            0,
        )
        strip_count_p1 = (
            strip_page_text_blocks(
                page1_doc,
                page_index=0,
            )
        )
        assert_reference_text_removed(
            page1_doc,
            page_index=0,
            label="page1",
        )
        page1 = page1_doc[0]

        _delete_digest_image(
            page1,
            COMMON_IMAGE_DIGESTS[
                "front.sender_logo"
            ],
            required=True,
        )

        _insert_digest_image(
            reference,
            reference[0],
            page1,
            COMMON_IMAGE_DIGESTS[
                "front.sender_logo"
            ],
            destination=_rect_mm(
                FRONT_STANDARD_SENDER_LOGO_BBOX_MM
            ),
        )

        front_occasion_meta = (
            _render_standard_birthday_occasion(
                page1,
                str(
                    occasion[
                        "display_text"
                    ]
                ),
                font_path=front_font_path,
                canonical_layout=(
                    canonical_front_occasion_layout
                ),
            )
        )

        out.insert_pdf(
            page1_doc
        )
        page1_doc.close()

        # Physical page 2 / logical PAGE_4_BACK:
        # locked transplant after proven authoring-layer filtering.
        (
            page2_doc,
            page2_authoring_removed,
        ) = _clone_reference_page(
            reference,
            1,
        )
        out.insert_pdf(
            page2_doc
        )
        page2_doc.close()

        # Physical page 3 / logical PAGE_2_INSIDE_IMAGE:
        # deterministic base + exact accepted raster geometry +
        # preserved Creator RGBA alpha as PDF soft mask + canonical frame.
        page3_authoring_removed = []
        portrait_meta = _compose_page3_with_accepted_portrait(
            out,
            reference,
            portrait_path=portrait_path,
        )

        # Physical page 4 / logical PAGE_3_INSIDE_GREETING:
        # deterministic base + exact regenerated text +
        # isolated canonical GRIGO vector clip.
        reference_p3_variable = [
            item
            for item in _page_image_info(
                reference[2]
            )
            if (
                item["digest_hex"]
                not in set(
                    COMMON_IMAGE_DIGESTS.values()
                )
            )
        ]
        reference_portrait_digests = {
            str(
                item["digest_hex"]
            )
            for item in reference_p3_variable
        }

        page4 = _new_matching_page(
            out,
            reference[3],
        )
        for digest in (
            COMMON_IMAGE_DIGESTS[
                "background.paper"
            ],
            COMMON_IMAGE_DIGESTS[
                "frame.ornate"
            ],
            COMMON_IMAGE_DIGESTS[
                "watermark.emblem"
            ],
        ):
            _insert_reference_digest_at_source_geometry(
                reference,
                reference[3],
                page4,
                digest,
            )

        (
            signature_overlay,
            page4_authoring_removed,
        ) = _prepare_grigo_signature_overlay(
            reference,
            reference_portrait_digests,
        )

        greeting_text = str(
            _mapping(
                data[
                    "structured_greeting_data"
                ]
            )[
                "greeting_text"
            ]
        )

        (
            greeting_font_size,
            sender_start_y_mm,
            greeting_rect,
        ) = _fit_greeting(
            page4,
            greeting_text,
            font_path=greeting_font_path,
        )

        _insert_textbox_exact(
            page4,
            greeting_rect,
            greeting_text,
            font_path=greeting_font_path,
            fontname="ZapfChanceryC",
            fontsize=greeting_font_size,
            align=pymupdf.TEXT_ALIGN_CENTER,
            lineheight=1.0,
        )

        sender_lines = [
            _mapping(
                item
            )
            for item in _list(
                sender.get(
                    "lines"
                )
            )
        ]

        _render_sender_lines(
            page4,
            sender_lines,
            font_path=greeting_font_path,
            start_y_mm=sender_start_y_mm,
        )

        _overlay_grigo_signature(
            page4,
            signature_overlay,
        )
        signature_overlay.close()

        strip_count_p4 = 0

        out.set_metadata(
            {
                "title":
                    "ForPrint deterministic greeting card",
                "author":
                    "ForPrint Graphic Design Lab",
                "subject":
                    "GC-E2E-09 Builder v0.1",
                "keywords":
                    "ForPrint,GDL,greeting-card",
            }
        )

        normalized_smask_xrefs = (
            normalize_image_soft_mask_colorspaces(
                out
            )
        )

        out.save(
            pdf_path,
            garbage=4,
            deflate=True,
            clean=True,
        )
        out.close()

    previews = (
        render_previews_from_final_pdf(
            pdf_path,
            preview_dir,
            stem=stem,
        )
    )

    with pymupdf.open(
        pdf_path
    ) as rendered_document:
        output_signature = (
            _inspect_grigo_signature(
                rendered_document[3]
            )
        )

    page3_soft_mask_evidence = (
        _page_portrait_soft_mask_evidence(
            pdf_path,
            page_index=2,
            transparency_required=bool(
                _mapping(
                    portrait_meta.get("normalized_alpha")
                ).get("has_transparency")
            ),
            expected_pixel_size=list(
                portrait_meta["reference_pixel_size"]
            ),
            expected_bbox_pt=list(
                portrait_meta["reference_bbox_pt"]
            ),
        )
    )

    fidelity = (
        _text_fidelity_check(
            pdf_path,
            occasion_text=str(
                occasion[
                    "display_text"
                ]
            ),
            greeting_text=greeting_text,
            sender_lines=sender_lines,
        )
    )

    external_checks = (
        _external_checks(
            pdf_path
        )
    )

    report = {
        "schema_version":
            RENDER_REPORT_SCHEMA,
        "job_id":
            job_id,
        "revision":
            revision,
        "renderer_slice":
            "STANDARD_PORTRAIT_GRIGO_V0_1",
        "physical_page_count":
            4,
        "page_mapping": {
            "1": "PAGE_1_FRONT",
            "2": "PAGE_4_BACK",
            "3": "PAGE_2_INSIDE_IMAGE",
            "4": "PAGE_3_INSIDE_GREETING",
        },
        "front_family":
            "STANDARD",
        "front_occasion":
            front_occasion_meta,
        "inside_image_mode":
            "PORTRAIT",
        "signature_variant":
            "GRIGO",
        "occasion_text_regenerated":
            True,
        "greeting_text_regenerated":
            True,
        "sender_text_regenerated":
            True,
        "signature_vector_preserved_from_reference":
            True,
        "signature_vector_validation": {
            "drawing_count":
                output_signature[
                    "drawing_count"
                ],
            "bbox_mm":
                output_signature[
                    "bbox_mm"
                ],
            "normalized_sha256":
                output_signature[
                    "normalized_sha256"
                ],
        },
        "locked_back_page_transplanted":
            True,
        "authoring_layer_blocks_removed": {
            "page_1":
                sum(
                    int(
                        item.get(
                            "block_count",
                            0,
                        )
                    )
                    for item
                    in page1_authoring_removed
                ),
            "page_2":
                sum(
                    int(
                        item.get(
                            "block_count",
                            0,
                        )
                    )
                    for item
                    in page2_authoring_removed
                ),
            "page_3":
                sum(
                    int(
                        item.get(
                            "block_count",
                            0,
                        )
                    )
                    for item
                    in page3_authoring_removed
                ),
            "page_4_signature_source":
                sum(
                    int(
                        item.get(
                            "block_count",
                            0,
                        )
                    )
                    for item
                    in page4_authoring_removed
                ),
        },
        "danger_zone_authoring_layer_in_final_composition":
            False,
        "page4_composition":
            "DETERMINISTIC_BASE_PLUS_EXACT_TEXT_AND_GRIGO_VECTOR_CLIP",
        "soft_mask_devicegray_normalized_count":
            len(
                normalized_smask_xrefs
            ),
        "previews_rendered_from_final_pdf":
            True,
        "preview_count":
            len(previews),
        "preview_files": [
            path.name
            for path in previews
        ],
        "pdf_file":
            pdf_path.name,
        "pdf_sha256":
            _sha256_file(
                pdf_path
            ),
        "front_removed_text_blocks":
            strip_count_p1,
        "inside_greeting_removed_text_blocks":
            strip_count_p4,
        "portrait":
            portrait_meta,
        "page3_composition":
            "DETERMINISTIC_BASE_PLUS_ACCEPTED_RGBA_SOFTMASK_PLUS_FRAME",
        "page3_post_render_soft_mask":
            page3_soft_mask_evidence,
        "greeting_font_size_pt":
            greeting_font_size,
        "sender_start_y_mm":
            sender_start_y_mm,
        "text_fidelity":
            fidelity,
        "external_checks":
            external_checks,
        "illustrator_runtime_dependency":
            False,
        "raw_customer_interpretation":
            False,
        "heuristic_inference":
            False,
        "font_substitution":
            False,
        "production_ready":
            False,
    }

    report_path = (
        report_dir
        / f"{stem}.json"
    )
    report_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "job_id":
            job_id,
        "revision":
            revision,
        "pdf_path":
            pdf_path,
        "preview_paths":
            previews,
        "report_path":
            report_path,
        "report":
            report,
    }


def build_bundle(
    *,
    bundle_path: Path,
    resource_manifest_path: Path,
    artifact_manifest_path: Path,
    signature_catalog_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    bundle_path = (
        bundle_path.expanduser().resolve()
    )
    resource_manifest_path = (
        resource_manifest_path
        .expanduser()
        .resolve()
    )
    artifact_manifest_path = (
        artifact_manifest_path
        .expanduser()
        .resolve()
    )
    signature_catalog_path = (
        signature_catalog_path
        .expanduser()
        .resolve()
    )
    output_dir = (
        output_dir.expanduser().resolve()
    )

    source_paths = [
        bundle_path,
        resource_manifest_path,
        artifact_manifest_path,
        signature_catalog_path,
    ]

    for path in source_paths:
        if not path.is_file():
            raise ValueError(
                "builder_input_file_missing:"
                + str(
                    path.name
                )
            )

    before = {
        str(path):
            _sha256_file(
                path
            )
        for path in source_paths
    }

    bundle = _load_yaml_mapping(
        bundle_path,
        label="bundle",
    )
    catalog = _load_yaml_mapping(
        signature_catalog_path,
        label="signature_catalog",
    )
    resource_manifest = (
        _load_yaml_mapping(
            resource_manifest_path,
            label="resource_manifest",
        )
    )
    artifact_manifest = (
        _load_yaml_mapping(
            artifact_manifest_path,
            label="artifact_manifest",
        )
    )

    errors = (
        validate_builder_ready_bundle_v1(
            bundle,
            signature_catalog=catalog,
        )
    )

    if errors:
        raise ValueError(
            "builder_ready_bundle_invalid:"
            + ";".join(
                errors
            )
        )

    resources = (
        validate_and_resolve_private_resources(
            resource_manifest,
            required_ids=[
                RESOURCE_FRONT_FONT,
                RESOURCE_GREETING_FONT,
                RESOURCE_REFERENCE_PDF,
            ],
        )
    )

    jobs = _list(
        bundle.get(
            "jobs"
        )
    )
    if not jobs:
        raise ValueError(
            "builder_ready_bundle_has_no_jobs"
        )

    results = []

    for job in jobs:
        results.append(
            _build_one_job(
                _mapping(
                    job
                ),
                resources=resources,
                artifact_manifest=artifact_manifest,
                output_dir=output_dir,
            )
        )

    after = {
        str(path):
            _sha256_file(
                path
            )
        for path in source_paths
    }

    if before != after:
        raise ValueError(
            "builder_source_mutation_detected"
        )

    bundle_report = {
        "schema_version":
            RENDER_REPORT_SCHEMA,
        "bundle_id":
            bundle.get(
                "bundle_id"
            ),
        "job_count":
            len(results),
        "job_ids": [
            item[
                "job_id"
            ]
            for item in results
        ],
        "source_mutation":
            False,
        "raw_customer_interpretation":
            False,
        "heuristic_inference":
            False,
        "illustrator_runtime_dependency":
            False,
        "previews_rendered_from_final_pdf":
            True,
        "production_ready":
            False,
    }

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )
    bundle_report_path = (
        output_dir
        / "builder_run_report.json"
    )
    bundle_report_path.write_text(
        json.dumps(
            bundle_report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "bundle_report":
            bundle_report,
        "bundle_report_path":
            bundle_report_path,
        "jobs":
            results,
    }

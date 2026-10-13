
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
from PIL import Image, ImageChops

from app.graphic_design_lab.greeting_card_builder_input import (
    validate_builder_ready_bundle_v1,
)
from app.graphic_design_lab.greeting_card_recipient_overlay_v0_1 import (
    SENDER_BBOX_PDF_MM as RECIPIENT_OVERLAY_SENDER_BBOX_MM,
    validate_overlay_job, verify_logo_file, insert_recipient_logo,
    verify_rendered_recipient_logo,
)
from app.graphic_design_lab.greeting_card_canonical_sender_v0_1 import (
    source_sender_rows,
    render_source_sender_text,
)
from app.graphic_design_lab.greeting_card_pdf_unicode_v0_1 import (
    repair_page4_canonical_unicode,
)
from app.graphic_design_lab.greeting_card_embedded_components import (
    GRIGO_SIGNATURE_BBOX_MM,
    GRIGO_SIGNATURE_DRAWING_COUNT,
    HERASYMENKO_SIGNATURE_BBOX_MM,
    HERASYMENKO_SIGNATURE_IMAGE_DIGEST_HEX,
    HERASYMENKO_SIGNATURE_PIXEL_SIZE,
    SENDER_LOGO_IMAGE_DIGEST_HEX,
    _inspect_grigo_signature,
    _select_grigo_signature_drawings,
    _signature_cluster_sha256,
    _cluster_union,
    _inspect_herasymenko_signature,
)
from app.graphic_design_lab.greeting_card_pdf_primitives import (
    normalize_image_soft_mask_colorspaces,
    strip_authoring_layers,
)
from app.graphic_design_lab.greeting_card_private_resources import (
    RESOURCE_FRONT_FONT,
    RESOURCE_GREETING_FONT,
    RESOURCE_REFERENCE_PDF,
    RESOURCE_SIGNATURE_HERASYMENKO,
    validate_and_resolve_private_resources,
)


ARTIFACT_MANIFEST_SCHEMA = (
    "gdl_greeting_card_builder_artifact_manifest_v0_1"
)
RENDER_REPORT_SCHEMA = (
    "gdl_greeting_card_builder_render_report_v0_1"
)

SUPPORTED_FRONT_FAMILIES = ("STANDARD", "RECIPIENT_BRANDING_OVERLAY")
SUPPORTED_IMAGE_MODES = ("PORTRAIT",)
SUPPORTED_SIGNATURE_VARIANTS = ("GRIGO", "HERASYMENKO")

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
FRONT_OCCASION_COLOR_RGB = (96.0 / 255.0, 57.0 / 255.0, 19.0 / 255.0)

STANDARD_BIRTHDAY_DISPLAY_TEXT = (
    "Привітання з нагоди Дня Народження!"
)
STANDARD_BIRTHDAY_LINES = (
    "Привітання з нагоди",
    "Дня Народження!",
)

# Illustrator Character panel, 2026-10-10: ZapfChanceryC Regular,
# size 7 mm, baseline-to-baseline leading 8 mm. The other tiers are
# bounded shrink-to-fit fallbacks, not alternative design defaults.
GREETING_REFERENCE_FONT_SIZE_MM = 7.0
GREETING_REFERENCE_LINE_ADVANCE_MM = 8.0
GREETING_LINE_ADVANCE_RATIO = (
    GREETING_REFERENCE_LINE_ADVANCE_MM / GREETING_REFERENCE_FONT_SIZE_MM
)
GREETING_FONT_SIZE_TIERS_PT = (
    GREETING_REFERENCE_FONT_SIZE_MM * PT_PER_MM,
    18.5,
    17.0,
)
SENDER_START_Y_VARIANTS_MM = (
    214.0,
    224.0,
    236.0,
)
# Physical PDF includes 2 mm bleed around the 210 x 297 mm trim.
# Operator-confirmed Illustrator greeting box: X-center=105, Y-center=120,
# W=160, H=180 mm in trim coordinates; max PDF box = (27,32,187,212).
GREETING_BODY_LEFT_MM = 27.0
GREETING_BODY_TOP_MM = 32.0
GREETING_BODY_RIGHT_MM = 187.0
GREETING_BODY_MAX_BOTTOM_MM = 212.0
MIN_SENDER_GAP_LINE_HEIGHTS = 2.0
# Operator-confirmed: two visually empty lines at bottom of the fixed
# 160 x 180 mm greeting zone. This is not customer text or PDF trim.
GREETING_BOTTOM_RESERVED_LINE_SLOTS = 2

SENDER_TEXT_LEFT_MM = 31.0
SENDER_TEXT_RIGHT_MM = 101.0
SENDER_LINE_ADVANCE_MM = 8.0
# Conservative V1 variability test bound (NOT a print specification).
SENDER_CONSERVATIVE_SAFE_BOTTOM_MM = 285.0
SENDER_BASE_FONT_SIZE_PT = 12.171
SENDER_NAME_FONT_SIZE_PT = 15.591

# GC-E2E Page4 proof: the second, Illustrator-editable PDF revision.
# Profiles use physical PDF mm including the original 2 mm bleed.
PAGE4_PROFILE_PATH = (
    Path(__file__).resolve().parents[2]
    / 'coordination/graphic_design_lab/directions/greeting_cards/'
    'page4_canonical_repair_profile_v0_1.yaml'
)
GRIGO_REPLAY_VECTOR_SHA256 = (
    '7944c3c1984b9bcab38fc406445f4180f279e5d55c8c1329fe9f8b8cd5a3f47c'
)


def _page4_runtime_profile(signature_variant: str) -> dict[str, Any]:
    """Numeric reference profile, never Illustrator screenshot heuristics."""
    raw = yaml.safe_load(PAGE4_PROFILE_PATH.read_text(encoding='utf-8'))
    if not isinstance(raw, dict) or raw.get('schema_version') != 'gdl_gc_page4_canonical_repair_v0_1':
        raise ValueError('page4_profile_invalid')
    if raw.get('watermark_opacity') != 0.5:
        raise ValueError('page4_watermark_opacity_unexpected')
    if raw.get('greeting_bbox_pdf_mm') != [27.0, 32.0, 187.0, 212.0]:
        raise ValueError('page4_greeting_geometry_contract_mismatch')
    sender = raw.get('single_sender')
    if not isinstance(sender, dict):
        raise ValueError('page4_sender_profile_missing')
    row = sender.get(signature_variant)
    if not isinstance(row, dict) or row.get('text_x_pdf_mm') != [31.0, 101.0]:
        raise ValueError('page4_sender_bbox_invalid')
    expected_y = {'GRIGO': 222.0, 'HERASYMENKO': 224.5}
    if signature_variant not in expected_y or row.get('start_y_pdf_mm') != expected_y[signature_variant]:
        raise ValueError('page4_sender_start_unapproved')
    return dict(raw)


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


def _insert_page4_watermark_half_opacity(
    reference: pymupdf.Document,
    source: pymupdf.Page,
    target: pymupdf.Page,
) -> None:
    """Reuse canonical watermark pixels and bbox; halve only alpha."""
    info = _find_image(source, COMMON_IMAGE_DIGESTS['watermark.emblem'])
    assert info is not None
    stream, mask = _raw_image_payload(reference, source, int(info['xref']))
    with Image.open(io.BytesIO(stream)) as image:
        rgba = image.convert('RGBA')
    alpha = rgba.getchannel('A')
    if mask is not None:
        with Image.open(io.BytesIO(mask)) as m:
            smask = m.convert('L')
            if smask.size != rgba.size:
                raise ValueError('watermark_smask_pixel_size_mismatch')
            alpha = ImageChops.multiply(alpha, smask)
    # Integer alpha attenuation; no change to RGB pixels or geometry.
    alpha = alpha.point(lambda x: int(round(x * 0.5)))
    rgba.putalpha(alpha)
    out = io.BytesIO()
    rgba.save(out, format='PNG')
    target.insert_image(
        pymupdf.Rect(info['bbox_rect']),
        stream=out.getvalue(),
        keep_proportion=False,
        overlay=True,
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
    """Copy ONLY the seven source-verified blue ink paths into the page.

    show_pdf_page(clip=...) embedded all source-page form resources, including
    113 invisible reference sender strokes. Illustrator exposed those objects.
    Replaying source paths as native page vector drawings removes the hidden
    form without rasterizing or shifting the signature.
    """
    clip = _rect_mm(list(GRIGO_SIGNATURE_BBOX_MM))
    selected = [
        d for d in overlay[0].get_drawings()
        if _rects_intersect(pymupdf.Rect(d['rect']), clip)
    ]
    if len(selected) != GRIGO_SIGNATURE_DRAWING_COUNT:
        raise ValueError('grigo_vector_replay_source_count_mismatch')
    if any(d.get('type') != 'f' or d.get('fill') is None for d in selected):
        raise ValueError('grigo_vector_replay_non_signature_path')

    for drawing in selected:
        shape = target_page.new_shape()
        for item in drawing['items']:
            if item[0] == 'l':
                shape.draw_line(item[1], item[2])
            elif item[0] == 'c':
                shape.draw_bezier(item[1], item[2], item[3], item[4])
            else:
                raise ValueError('grigo_vector_path_operation_unsupported')
        shape.finish(
            width=float(drawing.get('width') or 1),
            color=drawing.get('color'),
            fill=drawing['fill'],
            closePath=True,
            even_odd=bool(drawing.get('even_odd')),
            fill_opacity=float(drawing.get('fill_opacity') or 1.0),
        )
        shape.commit(overlay=True)


def _inspect_grigo_vector_only_page(page: pymupdf.Page) -> dict[str, Any]:
    """Strict post-render gate for exact source-derived vector replay.

    Original reference signature authenticity is independently verified by
    _inspect_grigo_signature(reference[3]); this verifies native-path replay.
    """
    selected = _select_grigo_signature_drawings(page)
    if len(selected) != GRIGO_SIGNATURE_DRAWING_COUNT:
        raise ValueError('grigo_replayed_drawing_count_mismatch')
    union = _cluster_union(selected)
    bbox = [round(x * MM_PER_PT, 3) for x in union]
    if any(abs(x - y) > 0.03 for x, y in zip(bbox, GRIGO_SIGNATURE_BBOX_MM)):
        raise ValueError('grigo_replayed_vector_bbox_mismatch')
    actual = _signature_cluster_sha256(selected, union=union)
    if actual != GRIGO_REPLAY_VECTOR_SHA256:
        raise ValueError('grigo_replayed_vector_hash_mismatch:' + actual)
    if len(page.get_drawings()) != GRIGO_SIGNATURE_DRAWING_COUNT:
        raise ValueError('page4_unexpected_hidden_or_duplicate_vector_paths')
    return {
        'component_id': 'component.signature.grigo.embedded_vector.v1',
        'kind': 'native_vector_only_replay',
        'signature_variant_id': 'GRIGO',
        'physical_page': 4,
        'bbox_mm': bbox,
        'drawing_count': len(selected),
        'normalized_sha256': actual,
        'source_hash_validated_before_replay': True,
        'unrelated_template_drawings_present': False,
        'status': 'PASS',
    }


def _text_intersections_with_rect(
    page: pymupdf.Page,
    rect: pymupdf.Rect,
) -> list[dict[str, Any]]:
    hits = []

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
                    item.get("text")
                    or ""
                ).strip()
                bbox = item.get(
                    "bbox"
                )

                if (
                    not text
                    or not bbox
                ):
                    continue

                span_rect = pymupdf.Rect(
                    bbox
                )

                if _rects_intersect(
                    span_rect,
                    rect,
                ):
                    hits.append(
                        {
                            "bbox": [
                                float(
                                    span_rect.x0
                                ),
                                float(
                                    span_rect.y0
                                ),
                                float(
                                    span_rect.x1
                                ),
                                float(
                                    span_rect.y1
                                ),
                            ],
                            "text_sha256":
                                hashlib.sha256(
                                    text.encode(
                                        "utf-8"
                                    )
                                ).hexdigest(),
                        }
                    )

    return hits


def _assert_text_clear_of_rect(
    page: pymupdf.Page,
    rect: pymupdf.Rect,
    *,
    label: str,
) -> None:
    hits = _text_intersections_with_rect(
        page,
        rect,
    )

    if hits:
        raise ValueError(
            label
            + ":text_intersects_signature:"
            + str(
                len(
                    hits
                )
            )
        )


def _pdf_image_rgba_pixel_identity(
    page: pymupdf.Page,
    image_xref: int,
) -> dict[str, Any]:
    if image_xref <= 0:
        raise ValueError(
            "pdf_image_identity_xref_invalid"
        )

    extracted = page.parent.extract_image(
        image_xref
    )

    payload = extracted[
        "image"
    ]

    with Image.open(
        io.BytesIO(
            payload
        )
    ) as source:
        rgba = source.convert(
            "RGBA"
        )

    soft_mask_xref = (
        _image_soft_mask_xref(
            page,
            image_xref,
        )
    )

    soft_mask_colorspace = None

    if soft_mask_xref > 0:
        mask_payload = (
            page.parent.extract_image(
                soft_mask_xref
            )[
                "image"
            ]
        )

        with Image.open(
            io.BytesIO(
                mask_payload
            )
        ) as mask_source:
            mask = (
                mask_source.convert(
                    "L"
                )
            )

        if (
            mask.size
            != rgba.size
        ):
            raise ValueError(
                "pdf_image_soft_mask_pixel_size_mismatch:"
                + f"mask={mask.size},image={rgba.size}"
            )

        rgba.putalpha(
            mask
        )

        (
            _,
            soft_mask_colorspace,
        ) = page.parent.xref_get_key(
            soft_mask_xref,
            "ColorSpace",
        )

    digest = hashlib.sha256()

    digest.update(
        int(
            rgba.width
        ).to_bytes(
            4,
            "big",
        )
    )

    digest.update(
        int(
            rgba.height
        ).to_bytes(
            4,
            "big",
        )
    )

    digest.update(
        rgba.tobytes()
    )

    return {
        "rgba_pixel_sha256":
            digest.hexdigest(),
        "pixel_size": [
            int(
                rgba.width
            ),
            int(
                rgba.height
            ),
        ],
        "soft_mask_xref":
            soft_mask_xref,
        "soft_mask_colorspace":
            soft_mask_colorspace,
        "extracted_sha256":
            hashlib.sha256(
                payload
            ).hexdigest(),
    }


def _insert_herasymenko_signature(
    target_page: pymupdf.Page,
    signature_source: pymupdf.Document,
) -> dict[str, Any]:
    if (
        signature_source.page_count
        != 4
    ):
        raise ValueError(
            "herasymenko_signature_source_page_count_mismatch"
        )

    source_page = (
        signature_source[
            3
        ]
    )

    # This remains the strict canonical private-source validation.
    source_component = (
        _inspect_herasymenko_signature(
            source_page
        )
    )

    destination = _rect_mm(
        list(
            HERASYMENKO_SIGNATURE_BBOX_MM
        )
    )

    _assert_text_clear_of_rect(
        target_page,
        destination,
        label="herasymenko_signature",
    )

    source_info = _find_image(
        source_page,
        HERASYMENKO_SIGNATURE_IMAGE_DIGEST_HEX,
    )

    if source_info is None:
        raise ValueError(
            "herasymenko_signature_source_image_missing"
        )

    source_xref = int(
        source_info.get(
            "xref"
        )
        or 0
    )

    if source_xref <= 0:
        raise ValueError(
            "herasymenko_signature_source_xref_missing"
        )

    source_pixel_identity = (
        _pdf_image_rgba_pixel_identity(
            source_page,
            source_xref,
        )
    )

    _insert_digest_image(
        signature_source,
        source_page,
        target_page,
        HERASYMENKO_SIGNATURE_IMAGE_DIGEST_HEX,
        destination=destination,
    )

    return {
        **source_component,
        "rgba_pixel_sha256":
            source_pixel_identity[
                "rgba_pixel_sha256"
            ],
        "rgba_pixel_size":
            source_pixel_identity[
                "pixel_size"
            ],
        "source_soft_mask_present":
            source_pixel_identity[
                "soft_mask_xref"
            ]
            > 0,
    }


def _inspect_rendered_herasymenko_signature(
    page: pymupdf.Page,
    *,
    expected_rgba_pixel_sha256: str,
) -> dict[str, Any]:
    if (
        not isinstance(
            expected_rgba_pixel_sha256,
            str,
        )
        or len(
            expected_rgba_pixel_sha256
        )
        != 64
    ):
        raise ValueError(
            "rendered_herasymenko_expected_rgba_sha_invalid"
        )

    candidates = []

    for info in page.get_image_info(
        hashes=True,
        xrefs=True,
    ):
        width = int(
            info.get(
                "width"
            )
            or 0
        )

        height = int(
            info.get(
                "height"
            )
            or 0
        )

        if (
            width,
            height,
        ) != (
            HERASYMENKO_SIGNATURE_PIXEL_SIZE
        ):
            continue

        bbox = pymupdf.Rect(
            info[
                "bbox"
            ]
        )

        bbox_mm = [
            round(
                float(
                    bbox.x0
                )
                * MM_PER_PT,
                3,
            ),
            round(
                float(
                    bbox.y0
                )
                * MM_PER_PT,
                3,
            ),
            round(
                float(
                    bbox.x1
                )
                * MM_PER_PT,
                3,
            ),
            round(
                float(
                    bbox.y1
                )
                * MM_PER_PT,
                3,
            ),
        ]

        if not all(
            abs(
                float(
                    bbox_mm[
                        index
                    ]
                )
                - float(
                    HERASYMENKO_SIGNATURE_BBOX_MM[
                        index
                    ]
                )
            )
            <= 0.05
            for index in range(
                4
            )
        ):
            continue

        candidates.append(
            {
                "info":
                    info,
                "bbox_mm":
                    bbox_mm,
            }
        )

    if len(
        candidates
    ) != 1:
        raise ValueError(
            "rendered_herasymenko_signature_candidate_count_mismatch:"
            + str(
                len(
                    candidates
                )
            )
        )

    candidate = (
        candidates[
            0
        ]
    )

    info = candidate[
        "info"
    ]

    xref = int(
        info.get(
            "xref"
        )
        or 0
    )

    if xref <= 0:
        raise ValueError(
            "rendered_herasymenko_signature_xref_missing"
        )

    identity = (
        _pdf_image_rgba_pixel_identity(
            page,
            xref,
        )
    )

    if (
        identity[
            "rgba_pixel_sha256"
        ]
        != expected_rgba_pixel_sha256
    ):
        raise ValueError(
            "rendered_herasymenko_signature_rgba_pixel_hash_mismatch:"
            + str(
                identity[
                    "rgba_pixel_sha256"
                ]
            )
        )

    soft_mask_xref = int(
        identity[
            "soft_mask_xref"
        ]
        or 0
    )

    if soft_mask_xref <= 0:
        raise ValueError(
            "rendered_herasymenko_signature_soft_mask_missing"
        )

    soft_mask_colorspace = (
        identity[
            "soft_mask_colorspace"
        ]
    )

    if (
        soft_mask_colorspace
        != "/DeviceGray"
    ):
        raise ValueError(
            "rendered_herasymenko_signature_soft_mask_not_devicegray:"
            + str(
                soft_mask_colorspace
            )
        )

    return {
        "component_id":
            "component.signature.herasymenko.embedded_image.v1",
        "kind":
            "embedded_image",
        "signature_variant_id":
            "HERASYMENKO",
        "physical_page":
            4,
        "identity_mode":
            "PIXEL_SIZE_BBOX_RGBA_PIXEL_SHA256_SOFT_MASK",
        "source_pymupdf_digest_required":
            False,
        "source_extracted_sha256_required_post_render":
            False,
        "output_pymupdf_digest_hex":
            _digest_hex(
                info.get(
                    "digest"
                )
            ),
        "output_extracted_sha256":
            identity[
                "extracted_sha256"
            ],
        "rgba_pixel_sha256":
            identity[
                "rgba_pixel_sha256"
            ],
        "pixel_size":
            identity[
                "pixel_size"
            ],
        "bbox_mm":
            candidate[
                "bbox_mm"
            ],
        "soft_mask_xref":
            soft_mask_xref,
        "soft_mask_colorspace":
            soft_mask_colorspace,
        "status":
            "PASS",
    }


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
            color=FRONT_OCCASION_COLOR_RGB,
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


def _sender_block_within_conservative_safe_zone(
    start_y_mm: float,
    sender_line_count: int,
) -> bool:
    """Conservative test envelope for the full sender text slot sequence.

    The actual glyph fit of each slot is checked by _insert_textbox_exact.
    This is not a replacement for a future verified print-safe-area spec.
    """
    if (
        isinstance(sender_line_count, bool)
        or not isinstance(sender_line_count, int)
        or sender_line_count <= 0
    ):
        raise ValueError("sender_line_count_invalid")
    return (
        float(start_y_mm)
        + sender_line_count * SENDER_LINE_ADVANCE_MM
        <= SENDER_CONSERVATIVE_SAFE_BOTTOM_MM
    )


def _greeting_pdf_lineheight(font_path: Path) -> float:
    """Use accepted font ascender to get actual Illustrator baseline spacing."""
    ascender = float(pymupdf.Font(fontfile=str(font_path)).ascender)
    if not (0.25 < ascender < 3.0):
        raise ValueError("greeting_font_ascender_invalid")
    return GREETING_LINE_ADVANCE_RATIO / ascender


def _fit_greeting(
    page: pymupdf.Page,
    text: str,
    *,
    font_path: Path,
    sender_line_count: int,
    fixed_sender_y_mm: float | None = None,
) -> tuple[float, float, pymupdf.Rect]:
    _sender_block_within_conservative_safe_zone(214.0, sender_line_count)
    lineheight_factor = _greeting_pdf_lineheight(font_path)
    for font_size in (
        GREETING_FONT_SIZE_TIERS_PT
    ):
        # Reserve empty rows by actual leading, not glyph point size.
        line_height_mm = (
            font_size * MM_PER_PT * GREETING_LINE_ADVANCE_RATIO
        )

        for sender_y_mm in (
            SENDER_START_Y_VARIANTS_MM if fixed_sender_y_mm is None
            else (float(fixed_sender_y_mm),)
        ):
            if not _sender_block_within_conservative_safe_zone(
                sender_y_mm, sender_line_count
            ):
                continue
            # The greeting box is a FIXED maximum region, not a floating
            # canvas. Keep the earlier sender gap as a stricter local cap.
            body_bottom_mm = min(
                # Reserve two complete visual line slots INSIDE the fixed
                # operator-confirmed greeting rectangle (not trailing '\n').
                GREETING_BODY_MAX_BOTTOM_MM - (
                    GREETING_BOTTOM_RESERVED_LINE_SLOTS * line_height_mm
                ),
                sender_y_mm - (
                    MIN_SENDER_GAP_LINE_HEIGHTS * line_height_mm
                ),
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
                lineheight=lineheight_factor,
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


def _canonical_single_sender_lines(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reorder existing accepted semantic slots, never invent missing lines."""
    mapped = [_mapping(line) for line in lines]
    ids = [str(row.get('id', '')) for row in mapped]
    if len(set(ids)) != len(ids) or not ids:
        raise ValueError('sender_ids_missing_or_duplicate')
    closing = [x for x in mapped if x['id'] == 'closing_phrase']
    names = [x for x in mapped if x['id'] == 'sender_name']
    other = [x for x in mapped if x['id'] not in ('closing_phrase', 'sender_name')]
    if len(closing) != 1 or len(names) != 1 or not other:
        raise ValueError('sender_required_roles_not_confirmed')
    if any(not str(x.get('text', '')).strip() for x in mapped):
        raise ValueError('sender_text_line_empty')
    return closing + names + other


def _page4_greeting_compact_paragraphs(text: str) -> str:
    """Preserve ALL words and paragraph breaks, remove only blank rows."""
    cleaned = text.replace('\r\n', '\n').replace('\r', '\n')
    return re.sub(r'\n(?:[ \t]*\n)+', '\n', cleaned).strip()


def _render_sender_lines(
    page: pymupdf.Page,
    lines: list[dict[str, Any]],
    *,
    font_path: Path,
    start_y_mm: float,
) -> None:
    # GC09: the *same* operator-review typography for GRIGO and HERASYMENKO.
    # Reuse the prior first-row origin, never change signature artwork geometry.
    # DUAL is not accepted by the upstream Builder runtime gate.
    from app.graphic_design_lab.greeting_card_sender_zone_planner_v0_1 import (
        source_locked_slots,
    )
    from app.graphic_design_lab.greeting_card_sender_typography_v0_1 import (
        plan_single_sender_lines,
    )

    slot_ids = [str(_mapping(item)["id"]) for item in lines]
    legacy = source_locked_slots(slot_ids, start_y_pdf_mm=float(start_y_mm))
    slots = plan_single_sender_lines(
        slot_ids,
        start_y_pdf_mm=legacy[0].bbox_pdf_mm[1],
        variant="SINGLE_SHARED",
        font_ascender=float(pymupdf.Font(fontfile=str(font_path)).ascender),
    )
    for raw, slot in zip(lines, slots):
        line = _mapping(raw)
        _insert_textbox_exact(
            page,
            _rect_mm(slot.bbox_pdf_mm),
            str(line["text"]),
            font_path=font_path,
            fontname="ZapfChanceryC",
            fontsize=slot.font_size_pt,
            align=pymupdf.TEXT_ALIGN_LEFT,
            lineheight=1.0,
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


def _required_resource_ids_for_bundle(
    bundle: Mapping[str, Any],
) -> list[str]:
    required = [
        RESOURCE_FRONT_FONT,
        RESOURCE_GREETING_FONT,
        RESOURCE_REFERENCE_PDF,
    ]

    jobs = _list(
        _mapping(
            bundle
        ).get(
            "jobs"
        )
    )

    variants = {
        str(
            _mapping(
                _mapping(
                    _mapping(
                        job
                    ).get(
                        "builder_v1"
                    )
                ).get(
                    "sender_text"
                )
            ).get(
                "signature_variant_id"
            )
        )
        for job in jobs
    }

    if "HERASYMENKO" in variants:
        required.append(
            RESOURCE_SIGNATURE_HERASYMENKO
        )

    return required


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

    validate_overlay_job(data)


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


def _verified_signature_report_provenance(
    *,
    signature_variant: str,
    grigo_source_verified: bool,
    source_validation: dict[str, Any] | None,
    rendered_validation: dict[str, Any],
) -> bool:
    """Return authenticated only after both source and output checks agree.

    This controls a *report field*, not customer acceptance or print authority.
    PDF-byte encoding is intentionally not an identity requirement for the
    HERASYMENKO image: RGBA pixel SHA256 and soft-mask identity are authoritative.
    """
    if signature_variant not in SUPPORTED_SIGNATURE_VARIANTS:
        raise ValueError("signature_report_variant_unsupported")
    if (
        not isinstance(rendered_validation, dict)
        or rendered_validation.get("status") != "PASS"
        or rendered_validation.get("signature_variant_id") != signature_variant
    ):
        raise ValueError("signature_report_authentication_incomplete")
    if signature_variant == "GRIGO":
        if (
            grigo_source_verified is not True
            or rendered_validation.get("source_hash_validated_before_replay") is not True
        ):
            raise ValueError("signature_report_authentication_incomplete")
        return True

    if not isinstance(source_validation, dict):
        raise ValueError("signature_report_authentication_incomplete")
    sha = source_validation.get("rgba_pixel_sha256")
    if (
        source_validation.get("status") != "PASS"
        or source_validation.get("signature_variant_id") != signature_variant
        or source_validation.get("source_soft_mask_present") is not True
        or not isinstance(sha, str)
        or re.fullmatch(r"[a-f0-9]{64}", sha) is None
        or rendered_validation.get("rgba_pixel_sha256") != sha
        or rendered_validation.get("identity_mode")
        != "PIXEL_SIZE_BBOX_RGBA_PIXEL_SHA256_SOFT_MASK"
        or rendered_validation.get("soft_mask_colorspace") != "/DeviceGray"
        or not isinstance(rendered_validation.get("soft_mask_xref"), int)
        or isinstance(rendered_validation.get("soft_mask_xref"), bool)
        or rendered_validation["soft_mask_xref"] <= 0
    ):
        raise ValueError("signature_report_authentication_incomplete")
    return True


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
    # The only signatory selection under Intake control is the catalog ID.
    # Incoming sender_text.lines, names, titles, signatures and coordinates
    # are not render authority, even when present in legacy accepted bundles.
    signature_variant = str(
        _mapping(data["signature_selection"])["variant_id"]
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

    branded_logo_path = None
    branded_logo_info = None
    if front.get("family") == "RECIPIENT_BRANDING_OVERLAY":
        selected_logo = _mapping(front.get("recipient_branding"))
        branded_logo_path = _artifact_manifest_entry(
            artifact_manifest,
            artifact_ref=str(selected_logo["accepted_artifact_ref"]),
            source_asset_id=str(selected_logo["asset_id"]),
            expected_sha256=str(selected_logo["asset_sha256"]),
        )
        branded_logo_info = verify_logo_file(branded_logo_path)

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

    signature_source_path = None
    if (
        signature_variant
        == "HERASYMENKO"
    ):
        signature_source_path = (
            _resource_path(
                resources,
                RESOURCE_SIGNATURE_HERASYMENKO,
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
                RECIPIENT_OVERLAY_SENDER_BBOX_MM
                if branded_logo_path is not None
                else FRONT_STANDARD_SENDER_LOGO_BBOX_MM
            ),
        )

        recipient_logo_meta = None
        if branded_logo_path is not None:
            assert branded_logo_info is not None
            recipient_logo_meta = insert_recipient_logo(
                page1, branded_logo_path, branded_logo_info,
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
            COMMON_IMAGE_DIGESTS['background.paper'],
            COMMON_IMAGE_DIGESTS['frame.ornate'],
        ):
            _insert_reference_digest_at_source_geometry(
                reference, reference[3], page4, digest,
            )
        _insert_page4_watermark_half_opacity(reference, reference[3], page4)

        signature_overlay = None
        page4_authoring_removed = []

        page4_profile = _page4_runtime_profile(signature_variant)
        source_signature_verified = False
        if signature_variant == 'GRIGO':
            _inspect_grigo_signature(reference[3])
            source_signature_verified = True
            (
                signature_overlay,
                page4_authoring_removed,
            ) = _prepare_grigo_signature_overlay(
                reference,
                reference_portrait_digests,
            )

        greeting_text_original = str(
            _mapping(data['structured_greeting_data'])['greeting_text']
        )
        greeting_text = _page4_greeting_compact_paragraphs(greeting_text_original)
        canonical_sender_source = (
            reference_path if signature_variant == "GRIGO"
            else signature_source_path
        )
        if canonical_sender_source is None:
            raise ValueError("canonical_sender_source_missing")
        sender_lines = source_sender_rows(
            signature_variant, canonical_sender_source,
        )

        (
            greeting_font_size,
            sender_start_y_mm,
            greeting_rect,
        ) = _fit_greeting(
            page4,
            greeting_text,
            font_path=greeting_font_path,
            sender_line_count=len(sender_lines),
            fixed_sender_y_mm=float(
                page4_profile['single_sender'][signature_variant]['start_y_pdf_mm']
            ),
        )

        _insert_textbox_exact(
            page4,
            greeting_rect,
            greeting_text,
            font_path=greeting_font_path,
            fontname="ZapfChanceryC",
            fontsize=greeting_font_size,
            align=pymupdf.TEXT_ALIGN_CENTER,
            lineheight=_greeting_pdf_lineheight(greeting_font_path),
        )

        render_source_sender_text(
            page4,
            sender_lines,
            font_path=greeting_font_path,
        )

        signature_source_validation = None

        if (
            signature_variant
            == "GRIGO"
        ):
            assert signature_overlay is not None
            _overlay_grigo_signature(
                page4,
                signature_overlay,
            )
            signature_overlay.close()

        elif (
            signature_variant
            == "HERASYMENKO"
        ):
            if signature_source_path is None:
                raise ValueError(
                    "herasymenko_signature_source_path_missing"
                )

            with pymupdf.open(
                signature_source_path
            ) as signature_source:
                signature_source_validation = (
                    _insert_herasymenko_signature(
                        page4,
                        signature_source,
                    )
                )

        else:
            raise ValueError(
                "builder_signature_variant_not_implemented:"
                + signature_variant
            )

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

        # Fix the source-font /ToUnicode semantics without changing glyphs
        # or any canonical sender/signature coordinates.
        canonical_unicode_evidence = repair_page4_canonical_unicode(out)

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
        if (
            signature_variant
            == "GRIGO"
        ):
            output_signature = _inspect_grigo_vector_only_page(
                rendered_document[3]
            )

        elif (
            signature_variant
            == "HERASYMENKO"
        ):
            if (
                signature_source_validation
                is None
            ):
                raise ValueError(
                    "herasymenko_signature_source_validation_missing"
                )

            output_signature = (
                _inspect_rendered_herasymenko_signature(
                    rendered_document[3],
                    expected_rgba_pixel_sha256=str(
                        signature_source_validation[
                            "rgba_pixel_sha256"
                        ]
                    ),
                )
            )

        else:
            raise ValueError(
                "post_render_signature_variant_not_implemented:"
                + signature_variant
            )

    source_signature_verified = _verified_signature_report_provenance(
        signature_variant=signature_variant,
        grigo_source_verified=source_signature_verified,
        source_validation=signature_source_validation,
        rendered_validation=output_signature,
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

    if recipient_logo_meta is not None:
        with pymupdf.open(pdf_path) as logo_document:
            verify_rendered_recipient_logo(
                logo_document[0],
                recipient_logo_meta["bbox_pdf_mm"],
                recipient_logo_meta["source_image_size_px"],
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
            (
                str(front["family"]) + "_PORTRAIT_"
                + signature_variant
                + "_V0_1"
            ),
        "physical_page_count":
            4,
        "page_mapping": {
            "1": "PAGE_1_FRONT",
            "2": "PAGE_4_BACK",
            "3": "PAGE_2_INSIDE_IMAGE",
            "4": "PAGE_3_INSIDE_GREETING",
        },
        "front_family":
            str(front["family"]),
        "front_occasion":
            front_occasion_meta,
        "inside_image_mode":
            "PORTRAIT",
        "signature_variant":
            signature_variant,
        "occasion_text_regenerated":
            True,
        "greeting_text_regenerated":
            True,
        "sender_text_regenerated":
            True,
        "canonical_sender_source": "SHA256_VERIFIED_PRIVATE_PDF_PAGE4",
        "canonical_sender_registry": "canonical_sender_blocks_v0_1.yaml",
        "intake_sender_text_rendered": False,
        "canonical_sender_line_count": len(sender_lines),
        "canonical_sender_pdf_unicode": canonical_unicode_evidence,
        "signature_component_validation":
            output_signature,
        "signature_component_source_validation":
            signature_source_validation,
        "signature_vector_preserved_from_reference":
            signature_variant
            == "GRIGO",
        "signature_exact_private_source_used":
            signature_variant
            == "HERASYMENKO",
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
            (
                "DETERMINISTIC_BASE_PLUS_EXACT_TEXT_AND_"
                + (
                    "GRIGO_VECTOR_CLIP"
                    if signature_variant
                    == "GRIGO"
                    else "HERASYMENKO_EXACT_IMAGE_COMPONENT"
                )
            ),
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
            portrait_meta[
                "composition"
            ],
        "page3_post_render_soft_mask":
            page3_soft_mask_evidence,
        "greeting_font_size_pt":
            greeting_font_size,
        "sender_start_y_mm":
            sender_start_y_mm,
        "page4_watermark_opacity": 0.5,
        "page4_watermark_geometry": "EXACT_REFERENCE_BBOX",
        "page4_sender_order": [item['id'] for item in sender_lines],
        "page4_sender_geometry_profile": "CANONICAL_SOURCE_CANDIDATE_INTERNAL_REVIEW",
        "page4_signature_source_authenticated": source_signature_verified,
        "page4_hidden_template_sender_paths": 0 if signature_variant == 'GRIGO' else None,
        "page4_greeting_blank_rows_removed": (
            greeting_text != greeting_text_original.strip()
        ),
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

    if recipient_logo_meta is not None:
        report["recipient_branding"] = {
            **recipient_logo_meta,
            "source_asset_id": str(_mapping(front["recipient_branding"])["asset_id"]),
            "asset_sha256": str(_mapping(front["recipient_branding"])["asset_sha256"]),
            "artifact_verified": True,
            "canonical_geometry_verified": True,
            "post_render_identity": "EXACT_PDF_BBOX_AND_NATIVE_PIXEL_SIZE",
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
            required_ids=(
                _required_resource_ids_for_bundle(
                    bundle
                )
            ),
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
        "renderer_slices": sorted(
            {
                str(
                    item[
                        "report"
                    ][
                        "renderer_slice"
                    ]
                )
                for item in results
            }
        ),
        "signature_variants": sorted(
            {
                str(
                    item[
                        "report"
                    ][
                        "signature_variant"
                    ]
                )
                for item in results
            }
        ),
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

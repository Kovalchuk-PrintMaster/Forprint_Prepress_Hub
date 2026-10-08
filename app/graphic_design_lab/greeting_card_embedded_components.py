
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pymupdf


REFERENCE_RESOURCE_ID = (
    "template.greeting_card.dolinska.v1"
)
HERASYMENKO_SOURCE_RESOURCE_ID = (
    "source.greeting_card.signature.herasymenko.v1"
)
DUAL_SOURCE_RESOURCE_ID = (
    "source.greeting_card.signature.dual_grigo_herasymenko.v1"
)

SENDER_LOGO_COMPONENT_ID = (
    "component.front.sender_logo.embedded.v1"
)
GRIGO_SIGNATURE_COMPONENT_ID = (
    "component.signature.grigo.embedded_vector.v1"
)
HERASYMENKO_SIGNATURE_COMPONENT_ID = (
    "component.signature.herasymenko.embedded_image.v1"
)
DUAL_SIGNATURE_COMPONENT_ID = (
    "component.signature.dual_grigo_herasymenko.embedded_composite.v1"
)

SENDER_LOGO_IMAGE_DIGEST_HEX = (
    "78b87a6195270a66b0e32de814f8f597"
)

GRIGO_SIGNATURE_VECTOR_SHA256 = (
    "8a50d63892577d3a61fdd76503a036c1"
    "6423085e9025d0f84e87032acb276580"
)
GRIGO_SIGNATURE_BBOX_MM = (
    103.465,
    213.348,
    155.203,
    247.531,
)
GRIGO_SIGNATURE_DRAWING_COUNT = 7

HERASYMENKO_SIGNATURE_IMAGE_DIGEST_HEX = (
    "18225bc81e1d5e6337539614421b2ac6"
)
HERASYMENKO_SIGNATURE_EXTRACTED_SHA256 = (
    "2d7bc1b4f30adf646222da75731e6310"
    "70c6cc40a653fb9bfdce9d181fe51406"
)
HERASYMENKO_SIGNATURE_PIXEL_SIZE = (
    536,
    700,
)
HERASYMENKO_SIGNATURE_BBOX_MM = (
    82.877,
    214.875,
    128.258,
    274.141,
)

DUAL_GRIGO_DRAWING_INDICES = (
    103,
    104,
    105,
    106,
    107,
    108,
    109,
)
DUAL_GRIGO_VECTOR_SHA256 = (
    "00dd0946e9d3fd4ec9ff4f8bad05ee29"
    "4618270f51e437eb5f0f3d7f69771e21"
)
DUAL_GRIGO_BBOX_MM = (
    88.186,
    196.983,
    139.923,
    231.166,
)
DUAL_HERASYMENKO_BBOX_MM = (
    96.048,
    219.891,
    141.429,
    279.158,
)
DUAL_SIGNATURE_COMPOSITE_SHA256 = (
    "4ab2cd819f743b4e08ea44a76b26d1e"
    "0036806270618343df6e697c485726f5b"
)

SUPPORTED_SIGNATURE_VARIANTS = (
    "GRIGO",
    "HERASYMENKO",
    "DUAL_GRIGO_HERASYMENKO",
)

MM_PER_PT = 25.4 / 72.0
BBOX_TOLERANCE_MM = 0.03


def _digest_hex(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).hex()
    return str(value)


def _rect_mm(rect: pymupdf.Rect) -> list[float]:
    return [
        round(float(rect.x0) * MM_PER_PT, 3),
        round(float(rect.y0) * MM_PER_PT, 3),
        round(float(rect.x1) * MM_PER_PT, 3),
        round(float(rect.y1) * MM_PER_PT, 3),
    ]


def _bbox_matches(
    actual: list[float],
    expected: tuple[float, float, float, float],
) -> bool:
    return len(actual) == 4 and all(
        abs(float(actual[index]) - float(expected[index]))
        <= BBOX_TOLERANCE_MM
        for index in range(4)
    )


def _drawing_has_fill(
    drawing: Mapping[str, Any],
) -> bool:
    return (
        "f" in str(
            drawing.get("type") or ""
        ).lower()
        or drawing.get("fill") is not None
    )


def _cluster_union(
    drawings: list[dict[str, Any]],
) -> pymupdf.Rect:
    if not drawings:
        raise ValueError(
            "signature_vector_cluster_missing"
        )

    union = pymupdf.Rect(
        drawings[0]["rect"]
    )

    for drawing in drawings[1:]:
        union.include_rect(
            pymupdf.Rect(
                drawing["rect"]
            )
        )

    return union


def _normalize_obj(
    value: Any,
    *,
    union: pymupdf.Rect,
) -> Any:
    ux0 = float(union.x0)
    uy0 = float(union.y0)
    width = max(
        float(union.width),
        1e-9,
    )
    height = max(
        float(union.height),
        1e-9,
    )

    if isinstance(
        value,
        pymupdf.Point,
    ):
        return [
            round(
                (float(value.x) - ux0)
                / width,
                6,
            ),
            round(
                (float(value.y) - uy0)
                / height,
                6,
            ),
        ]

    if isinstance(
        value,
        pymupdf.Rect,
    ):
        return [
            round(
                (float(value.x0) - ux0)
                / width,
                6,
            ),
            round(
                (float(value.y0) - uy0)
                / height,
                6,
            ),
            round(
                (float(value.x1) - ux0)
                / width,
                6,
            ),
            round(
                (float(value.y1) - uy0)
                / height,
                6,
            ),
        ]

    if isinstance(
        value,
        pymupdf.Quad,
    ):
        return [
            _normalize_obj(
                value.ul,
                union=union,
            ),
            _normalize_obj(
                value.ur,
                union=union,
            ),
            _normalize_obj(
                value.ll,
                union=union,
            ),
            _normalize_obj(
                value.lr,
                union=union,
            ),
        ]

    if isinstance(
        value,
        (tuple, list),
    ):
        return [
            _normalize_obj(
                item,
                union=union,
            )
            for item in value
        ]

    if isinstance(
        value,
        Mapping,
    ):
        result: dict[str, Any] = {}

        for key, item in sorted(
            value.items(),
            key=lambda pair: str(
                pair[0]
            ),
        ):
            if key in {
                "seqno",
                "layer",
                "rect",
            }:
                continue

            result[str(key)] = (
                _normalize_obj(
                    item,
                    union=union,
                )
            )

        return result

    if isinstance(
        value,
        float,
    ):
        return round(
            value,
            6,
        )

    return value


def _signature_cluster_sha256(
    drawings: list[dict[str, Any]],
    *,
    union: pymupdf.Rect,
) -> str:
    normalized = []

    for drawing in sorted(
        drawings,
        key=lambda item: (
            float(
                item["rect"].y0
            ),
            float(
                item["rect"].x0
            ),
            float(
                item["rect"].y1
            ),
            float(
                item["rect"].x1
            ),
        ),
    ):
        normalized.append(
            _normalize_obj(
                {
                    "items": (
                        drawing.get(
                            "items"
                        )
                    ),
                    "type": (
                        drawing.get(
                            "type"
                        )
                    ),
                    "fill": (
                        drawing.get(
                            "fill"
                        )
                    ),
                    "color": (
                        drawing.get(
                            "color"
                        )
                    ),
                    "width": (
                        drawing.get(
                            "width"
                        )
                    ),
                    "dashes": (
                        drawing.get(
                            "dashes"
                        )
                    ),
                    "lineCap": (
                        drawing.get(
                            "lineCap"
                        )
                    ),
                    "lineJoin": (
                        drawing.get(
                            "lineJoin"
                        )
                    ),
                    "closePath": (
                        drawing.get(
                            "closePath"
                        )
                    ),
                    "fill_opacity": (
                        drawing.get(
                            "fill_opacity"
                        )
                    ),
                    "stroke_opacity": (
                        drawing.get(
                            "stroke_opacity"
                        )
                    ),
                },
                union=union,
            )
        )

    payload = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
    ).encode(
        "utf-8"
    )

    return hashlib.sha256(
        payload
    ).hexdigest()


def _select_grigo_signature_drawings(
    page: pymupdf.Page,
) -> list[dict[str, Any]]:
    page_width = float(
        page.rect.width
    )
    page_height = float(
        page.rect.height
    )
    selected = []

    for drawing in (
        page.get_drawings()
    ):
        rect = pymupdf.Rect(
            drawing["rect"]
        )

        if (
            rect.width <= 0
            or rect.height <= 0
        ):
            continue

        center_x = (
            float(rect.x0)
            + float(rect.x1)
        ) / 2.0
        center_y = (
            float(rect.y0)
            + float(rect.y1)
        ) / 2.0

        if not _drawing_has_fill(
            drawing
        ):
            continue

        if (
            center_y
            <= page_height * 0.66
        ):
            continue

        if (
            center_x
            <= page_width * 0.45
        ):
            continue

        if (
            rect.width
            >= page_width * 0.45
        ):
            continue

        if (
            rect.height
            >= page_height * 0.35
        ):
            continue

        selected.append(
            dict(drawing)
        )

    return selected


def _inspect_sender_logo(
    page: pymupdf.Page,
) -> dict[str, Any]:
    matches = [
        info
        for info in (
            page.get_image_info(
                hashes=True,
                xrefs=True,
            )
        )
        if (
            _digest_hex(
                info.get(
                    "digest"
                )
            )
            == (
                SENDER_LOGO_IMAGE_DIGEST_HEX
            )
        )
    ]

    if len(matches) != 1:
        raise ValueError(
            "sender_logo_embedded_component_count_mismatch:"
            f"{len(matches)}"
        )

    info = matches[0]

    return {
        "component_id": (
            SENDER_LOGO_COMPONENT_ID
        ),
        "kind": (
            "embedded_image"
        ),
        "physical_page": 1,
        "xref": int(
            info.get(
                "xref"
            )
            or 0
        ),
        "pymupdf_image_digest_hex": (
            SENDER_LOGO_IMAGE_DIGEST_HEX
        ),
        "bbox_mm": _rect_mm(
            pymupdf.Rect(
                info["bbox"]
            )
        ),
        "status": "PASS",
    }


def _inspect_grigo_signature(
    page: pymupdf.Page,
) -> dict[str, Any]:
    drawings = (
        _select_grigo_signature_drawings(
            page
        )
    )

    if (
        len(drawings)
        != GRIGO_SIGNATURE_DRAWING_COUNT
    ):
        raise ValueError(
            "grigo_signature_drawing_count_mismatch:"
            f"{len(drawings)}"
        )

    union = _cluster_union(
        drawings
    )
    bbox_mm = _rect_mm(
        union
    )

    if not _bbox_matches(
        bbox_mm,
        GRIGO_SIGNATURE_BBOX_MM,
    ):
        raise ValueError(
            "grigo_signature_bbox_mismatch:"
            + ",".join(
                str(value)
                for value in bbox_mm
            )
        )

    digest = (
        _signature_cluster_sha256(
            drawings,
            union=union,
        )
    )

    if (
        digest
        != GRIGO_SIGNATURE_VECTOR_SHA256
    ):
        raise ValueError(
            "grigo_signature_vector_hash_mismatch:"
            + digest
        )

    return {
        "component_id": (
            GRIGO_SIGNATURE_COMPONENT_ID
        ),
        "kind": (
            "embedded_vector_cluster"
        ),
        "signature_variant_id": (
            "GRIGO"
        ),
        "physical_page": 4,
        "bbox_mm": bbox_mm,
        "drawing_count": (
            len(drawings)
        ),
        "normalized_sha256": (
            digest
        ),
        "status": "PASS",
    }


def _inspect_signature_image(
    page: pymupdf.Page,
    *,
    expected_bbox_mm: tuple[
        float,
        float,
        float,
        float,
    ],
) -> dict[str, Any]:
    matches = []

    for info in page.get_image_info(
        hashes=True,
        xrefs=True,
    ):
        if (
            _digest_hex(
                info.get(
                    "digest"
                )
            )
            != (
                HERASYMENKO_SIGNATURE_IMAGE_DIGEST_HEX
            )
        ):
            continue

        if (
            int(
                info.get(
                    "width"
                )
                or 0
            ),
            int(
                info.get(
                    "height"
                )
                or 0
            ),
        ) != (
            HERASYMENKO_SIGNATURE_PIXEL_SIZE
        ):
            continue

        matches.append(
            info
        )

    if len(matches) != 1:
        raise ValueError(
            "herasymenko_signature_image_count_mismatch:"
            f"{len(matches)}"
        )

    info = matches[0]
    bbox_mm = _rect_mm(
        pymupdf.Rect(
            info["bbox"]
        )
    )

    if not _bbox_matches(
        bbox_mm,
        expected_bbox_mm,
    ):
        raise ValueError(
            "herasymenko_signature_bbox_mismatch:"
            + ",".join(
                str(value)
                for value in bbox_mm
            )
        )

    xref = int(
        info.get(
            "xref"
        )
        or 0
    )

    if xref <= 0:
        raise ValueError(
            "herasymenko_signature_xref_missing"
        )

    extracted = (
        page.parent.extract_image(
            xref
        )["image"]
    )
    extracted_sha256 = (
        hashlib.sha256(
            extracted
        ).hexdigest()
    )

    if (
        extracted_sha256
        != (
            HERASYMENKO_SIGNATURE_EXTRACTED_SHA256
        )
    ):
        raise ValueError(
            "herasymenko_signature_extracted_hash_mismatch:"
            + extracted_sha256
        )

    return {
        "kind": (
            "embedded_image"
        ),
        "physical_page": 4,
        "xref": xref,
        "pymupdf_image_digest_hex": (
            HERASYMENKO_SIGNATURE_IMAGE_DIGEST_HEX
        ),
        "extracted_sha256": (
            extracted_sha256
        ),
        "pixel_size": list(
            HERASYMENKO_SIGNATURE_PIXEL_SIZE
        ),
        "bbox_mm": bbox_mm,
        "status": "PASS",
    }


def _inspect_herasymenko_signature(
    page: pymupdf.Page,
) -> dict[str, Any]:
    item = _inspect_signature_image(
        page,
        expected_bbox_mm=(
            HERASYMENKO_SIGNATURE_BBOX_MM
        ),
    )

    item.update(
        {
            "component_id": (
                HERASYMENKO_SIGNATURE_COMPONENT_ID
            ),
            "signature_variant_id": (
                "HERASYMENKO"
            ),
        }
    )

    return item


def _inspect_dual_signature(
    page: pymupdf.Page,
) -> dict[str, Any]:
    all_drawings = (
        page.get_drawings()
    )

    try:
        drawings = [
            dict(
                all_drawings[
                    index
                ]
            )
            for index in (
                DUAL_GRIGO_DRAWING_INDICES
            )
        ]
    except IndexError as exc:
        raise ValueError(
            "dual_grigo_drawing_indices_missing"
        ) from exc

    if not all(
        _drawing_has_fill(
            drawing
        )
        for drawing in drawings
    ):
        raise ValueError(
            "dual_grigo_expected_filled_drawings"
        )

    union = _cluster_union(
        drawings
    )
    grigo_bbox_mm = (
        _rect_mm(
            union
        )
    )

    if not _bbox_matches(
        grigo_bbox_mm,
        DUAL_GRIGO_BBOX_MM,
    ):
        raise ValueError(
            "dual_grigo_bbox_mismatch:"
            + ",".join(
                str(value)
                for value in grigo_bbox_mm
            )
        )

    grigo_sha256 = (
        _signature_cluster_sha256(
            drawings,
            union=union,
        )
    )

    if (
        grigo_sha256
        != (
            DUAL_GRIGO_VECTOR_SHA256
        )
    ):
        raise ValueError(
            "dual_grigo_vector_hash_mismatch:"
            + grigo_sha256
        )

    grigo = {
        "component_id": (
            "component.signature.dual."
            "grigo_vector.embedded.v1"
        ),
        "kind": (
            "embedded_vector_cluster"
        ),
        "physical_page": 4,
        "drawing_indices": list(
            DUAL_GRIGO_DRAWING_INDICES
        ),
        "drawing_count": (
            len(drawings)
        ),
        "bbox_mm": (
            grigo_bbox_mm
        ),
        "normalized_sha256": (
            grigo_sha256
        ),
        "status": "PASS",
    }

    herasymenko = (
        _inspect_signature_image(
            page,
            expected_bbox_mm=(
                DUAL_HERASYMENKO_BBOX_MM
            ),
        )
    )
    herasymenko[
        "component_id"
    ] = (
        "component.signature.dual."
        "herasymenko_image.embedded.v1"
    )

    composite_payload = {
        "grigo_vector": {
            "bbox_mm": (
                grigo[
                    "bbox_mm"
                ]
            ),
            "normalized_sha256": (
                grigo[
                    "normalized_sha256"
                ]
            ),
            "drawing_count": (
                grigo[
                    "drawing_count"
                ]
            ),
        },
        "herasymenko_image": {
            "bbox_mm": (
                herasymenko[
                    "bbox_mm"
                ]
            ),
            "image_digest_hex": (
                herasymenko[
                    "pymupdf_image_digest_hex"
                ]
            ),
            "extracted_sha256": (
                herasymenko[
                    "extracted_sha256"
                ]
            ),
            "width": (
                herasymenko[
                    "pixel_size"
                ][0]
            ),
            "height": (
                herasymenko[
                    "pixel_size"
                ][1]
            ),
        },
    }

    composite_sha256 = (
        hashlib.sha256(
            json.dumps(
                composite_payload,
                sort_keys=True,
                separators=(
                    ",",
                    ":",
                ),
            ).encode(
                "utf-8"
            )
        ).hexdigest()
    )

    if (
        composite_sha256
        != (
            DUAL_SIGNATURE_COMPOSITE_SHA256
        )
    ):
        raise ValueError(
            "dual_signature_composite_hash_mismatch:"
            + composite_sha256
        )

    return {
        "component_id": (
            DUAL_SIGNATURE_COMPONENT_ID
        ),
        "kind": (
            "embedded_composite"
        ),
        "signature_variant_id": (
            "DUAL_GRIGO_HERASYMENKO"
        ),
        "physical_page": 4,
        "component_count": 2,
        "composite_sha256": (
            composite_sha256
        ),
        "components": [
            grigo,
            herasymenko,
        ],
        "status": "PASS",
    }


def required_resource_ids_for_signature_variant(
    signature_variant_id: str,
) -> tuple[str, ...]:
    if (
        signature_variant_id
        == "GRIGO"
    ):
        return (
            REFERENCE_RESOURCE_ID,
        )

    if (
        signature_variant_id
        == "HERASYMENKO"
    ):
        return (
            REFERENCE_RESOURCE_ID,
            HERASYMENKO_SOURCE_RESOURCE_ID,
        )

    if (
        signature_variant_id
        == (
            "DUAL_GRIGO_HERASYMENKO"
        )
    ):
        return (
            REFERENCE_RESOURCE_ID,
            DUAL_SOURCE_RESOURCE_ID,
        )

    raise ValueError(
        "signature_variant_not_bound_v1:"
        + str(
            signature_variant_id
        )
    )


def _path_for(
    resolved_resources: Mapping[
        str,
        Mapping[str, Any],
    ],
    resource_id: str,
) -> Path:
    item = resolved_resources.get(
        resource_id
    )

    if not isinstance(
        item,
        Mapping,
    ):
        raise ValueError(
            "resolved_resource_missing:"
            + resource_id
        )

    value = item.get(
        "path"
    )

    if isinstance(
        value,
        Path,
    ):
        path = value
    elif isinstance(
        value,
        str,
    ):
        path = Path(
            value
        )
    else:
        raise ValueError(
            "resolved_resource_path_missing:"
            + resource_id
        )

    path = path.resolve()

    if not path.is_file():
        raise ValueError(
            "resolved_resource_path_missing:"
            + resource_id
        )

    return path


def resolve_embedded_components(
    resolved_resources: Mapping[
        str,
        Mapping[str, Any],
    ],
    *,
    signature_variant_id: str,
) -> dict[str, dict[str, Any]]:
    required_resource_ids_for_signature_variant(
        signature_variant_id
    )

    canonical_path = _path_for(
        resolved_resources,
        REFERENCE_RESOURCE_ID,
    )

    with pymupdf.open(
        canonical_path
    ) as doc:
        if doc.page_count != 4:
            raise ValueError(
                "reference_pdf_page_count_mismatch:"
                f"{doc.page_count}"
            )

        sender_logo = (
            _inspect_sender_logo(
                doc[0]
            )
        )

    if (
        signature_variant_id
        == "GRIGO"
    ):
        signature_source_id = (
            REFERENCE_RESOURCE_ID
        )
        signature_source_path = (
            canonical_path
        )

        with pymupdf.open(
            signature_source_path
        ) as doc:
            signature = (
                _inspect_grigo_signature(
                    doc[3]
                )
            )

    elif (
        signature_variant_id
        == "HERASYMENKO"
    ):
        signature_source_id = (
            HERASYMENKO_SOURCE_RESOURCE_ID
        )
        signature_source_path = (
            _path_for(
                resolved_resources,
                signature_source_id,
            )
        )

        with pymupdf.open(
            signature_source_path
        ) as doc:
            signature = (
                _inspect_herasymenko_signature(
                    doc[3]
                )
            )

    else:
        signature_source_id = (
            DUAL_SOURCE_RESOURCE_ID
        )
        signature_source_path = (
            _path_for(
                resolved_resources,
                signature_source_id,
            )
        )

        with pymupdf.open(
            signature_source_path
        ) as doc:
            signature = (
                _inspect_dual_signature(
                    doc[3]
                )
            )

    sender_logo[
        "source_resource_id"
    ] = REFERENCE_RESOURCE_ID
    sender_logo[
        "source_pdf_path"
    ] = canonical_path

    signature[
        "source_resource_id"
    ] = signature_source_id
    signature[
        "source_pdf_path"
    ] = signature_source_path

    return {
        "front_sender_logo": (
            sender_logo
        ),
        "signature": (
            signature
        ),
    }


def _public_value(
    value: Any,
) -> Any:
    if isinstance(
        value,
        Path,
    ):
        return "<redacted-private-path>"

    if isinstance(
        value,
        Mapping,
    ):
        result = {}

        for key, item in (
            value.items()
        ):
            if str(
                key
            ).endswith(
                "_path"
            ):
                continue

            result[str(key)] = (
                _public_value(
                    item
                )
            )

        return result

    if isinstance(
        value,
        list,
    ):
        return [
            _public_value(
                item
            )
            for item in value
        ]

    return value


def public_component_summary(
    resolved: Mapping[
        str,
        Mapping[str, Any],
    ],
) -> dict[str, dict[str, Any]]:
    return {
        str(key): (
            _public_value(
                value
            )
        )
        for key, value in (
            resolved.items()
        )
    }

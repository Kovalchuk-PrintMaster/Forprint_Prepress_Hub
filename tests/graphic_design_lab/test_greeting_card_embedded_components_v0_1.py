
from pathlib import Path

import pymupdf
import pytest

import app.graphic_design_lab.greeting_card_embedded_components as components


def test_all_current_signature_variants_are_bound():
    assert (
        components.SUPPORTED_SIGNATURE_VARIANTS
        == (
            "GRIGO",
            "HERASYMENKO",
            "DUAL_GRIGO_HERASYMENKO",
        )
    )


def test_exact_component_fingerprints_are_registered():
    assert (
        components.GRIGO_SIGNATURE_VECTOR_SHA256
        == (
            "8a50d63892577d3a61fdd76503a036c1"
            "6423085e9025d0f84e87032acb276580"
        )
    )

    assert (
        components.HERASYMENKO_SIGNATURE_EXTRACTED_SHA256
        == (
            "2d7bc1b4f30adf646222da75731e6310"
            "70c6cc40a653fb9bfdce9d181fe51406"
        )
    )

    assert (
        components.DUAL_GRIGO_VECTOR_SHA256
        == (
            "00dd0946e9d3fd4ec9ff4f8bad05ee29"
            "4618270f51e437eb5f0f3d7f69771e21"
        )
    )

    assert (
        components.DUAL_SIGNATURE_COMPOSITE_SHA256
        == (
            "4ab2cd819f743b4e08ea44a76b26d1e"
            "0036806270618343df6e697c485726f5b"
        )
    )


@pytest.mark.parametrize(
    ("variant_id", "expected"),
    [
        (
            "GRIGO",
            (
                "template.greeting_card.dolinska.v1",
            ),
        ),
        (
            "HERASYMENKO",
            (
                "template.greeting_card.dolinska.v1",
                "source.greeting_card.signature.herasymenko.v1",
            ),
        ),
        (
            "DUAL_GRIGO_HERASYMENKO",
            (
                "template.greeting_card.dolinska.v1",
                (
                    "source.greeting_card.signature."
                    "dual_grigo_herasymenko.v1"
                ),
            ),
        ),
    ],
)
def test_variant_resource_requirements_are_explicit(
    variant_id,
    expected,
):
    assert (
        components.required_resource_ids_for_signature_variant(
            variant_id
        )
        == expected
    )


def test_unknown_signature_variant_fails_closed():
    with pytest.raises(
        ValueError,
        match="signature_variant_not_bound_v1",
    ):
        components.required_resource_ids_for_signature_variant(
            "UNKNOWN"
        )


def test_public_summary_redacts_private_paths_recursively():
    resolved = {
        "front_sender_logo": {
            "source_pdf_path": Path(
                "/private/reference.pdf"
            ),
            "status": "PASS",
        },
        "signature": {
            "source_pdf_path": Path(
                "/private/signature.pdf"
            ),
            "components": [
                {
                    "status": "PASS",
                }
            ],
        },
    }

    public = (
        components.public_component_summary(
            resolved
        )
    )

    assert (
        "source_pdf_path"
        not in public[
            "front_sender_logo"
        ]
    )
    assert (
        "source_pdf_path"
        not in public[
            "signature"
        ]
    )


def test_signature_cluster_hash_is_translation_invariant():
    first = [
        {
            "rect": pymupdf.Rect(
                100,
                200,
                120,
                220,
            ),
            "items": [
                (
                    "l",
                    pymupdf.Point(
                        100,
                        200,
                    ),
                    pymupdf.Point(
                        120,
                        220,
                    ),
                )
            ],
            "type": "f",
            "fill": (
                0.0,
                0.0,
                0.0,
            ),
            "color": None,
            "width": None,
            "dashes": "[] 0",
            "lineCap": None,
            "lineJoin": None,
            "closePath": True,
            "fill_opacity": 1.0,
            "stroke_opacity": 1.0,
        }
    ]

    second = [
        {
            **first[0],
            "rect": pymupdf.Rect(
                150,
                250,
                170,
                270,
            ),
            "items": [
                (
                    "l",
                    pymupdf.Point(
                        150,
                        250,
                    ),
                    pymupdf.Point(
                        170,
                        270,
                    ),
                )
            ],
        }
    ]

    union_first = (
        components._cluster_union(
            first
        )
    )
    union_second = (
        components._cluster_union(
            second
        )
    )

    assert (
        components._signature_cluster_sha256(
            first,
            union=union_first,
        )
        == (
            components._signature_cluster_sha256(
                second,
                union=union_second,
            )
        )
    )

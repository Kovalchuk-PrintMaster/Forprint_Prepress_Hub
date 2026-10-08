
#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import yaml


REPO = Path(
    __file__
).resolve().parents[3]
sys.path.insert(
    0,
    str(REPO),
)

from app.graphic_design_lab.greeting_card_embedded_components import (  # noqa: E402
    SUPPORTED_SIGNATURE_VARIANTS,
    public_component_summary,
    required_resource_ids_for_signature_variant,
    resolve_embedded_components,
)
from app.graphic_design_lab.greeting_card_private_resources import (  # noqa: E402
    validate_and_resolve_private_resources,
)


def parse_args() -> argparse.Namespace:
    parser = (
        argparse.ArgumentParser()
    )
    parser.add_argument(
        "--manifest",
        required=True,
    )
    parser.add_argument(
        "--signature-variant",
        default="ALL",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = Path(
        args.manifest
    )

    if not manifest_path.is_file():
        print(
            "GDL_GREETING_CARD_EMBEDDED_COMPONENTS=FAIL"
        )
        print(
            "ERROR=private_resource_manifest_missing"
        )
        print(
            "PRIVATE_PATHS_PRINTED=false"
        )
        return 2

    if (
        args.signature_variant
        == "ALL"
    ):
        variants = list(
            SUPPORTED_SIGNATURE_VARIANTS
        )
    else:
        variants = [
            args.signature_variant
        ]

    required_ids = set()

    try:
        for variant in variants:
            required_ids.update(
                required_resource_ids_for_signature_variant(
                    variant
                )
            )

        manifest = yaml.safe_load(
            manifest_path.read_text(
                encoding="utf-8"
            )
        )

        resources = (
            validate_and_resolve_private_resources(
                manifest,
                required_ids=sorted(
                    required_ids
                ),
            )
        )

        resolved_by_variant = {}

        for variant in variants:
            resolved = (
                resolve_embedded_components(
                    resources,
                    signature_variant_id=(
                        variant
                    ),
                )
            )

            resolved_by_variant[
                variant
            ] = (
                public_component_summary(
                    resolved
                )
            )

    except Exception as exc:
        print(
            "GDL_GREETING_CARD_EMBEDDED_COMPONENTS=FAIL"
        )
        print(
            f"ERROR={type(exc).__name__}:{exc}"
        )
        print(
            "PRIVATE_PATHS_PRINTED=false"
        )
        return 2

    print(
        "GDL_GREETING_CARD_EMBEDDED_COMPONENTS=PASS"
    )
    print(
        f"SIGNATURE_VARIANT_COUNT={len(variants)}"
    )
    print(
        "SENDER_LOGO_SOURCE="
        "CANONICAL_REFERENCE_EMBEDDED_COMPONENT"
    )

    for variant in variants:
        signature = (
            resolved_by_variant[
                variant
            ][
                "signature"
            ]
        )

        print(
            f"SIGNATURE_VARIANT={variant}"
        )
        print(
            "SIGNATURE_KIND="
            + str(
                signature.get(
                    "kind"
                )
            )
        )

        if (
            "normalized_sha256"
            in signature
        ):
            print(
                "SIGNATURE_VECTOR_SHA256="
                + str(
                    signature[
                        "normalized_sha256"
                    ]
                )
            )

        if (
            "extracted_sha256"
            in signature
        ):
            print(
                "SIGNATURE_IMAGE_SHA256="
                + str(
                    signature[
                        "extracted_sha256"
                    ]
                )
            )

        if (
            "composite_sha256"
            in signature
        ):
            print(
                "SIGNATURE_COMPOSITE_SHA256="
                + str(
                    signature[
                        "composite_sha256"
                    ]
                )
            )

    print(
        "SILENT_SIGNATURE_FALLBACK=false"
    )
    print(
        "FILENAME_BASED_SIGNATURE_SELECTION=false"
    )
    print(
        "PRIVATE_PATHS_PRINTED=false"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )

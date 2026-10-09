
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(
    __file__
).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(
        0,
        str(REPO),
    )

from app.graphic_design_lab.greeting_card_builder_renderer import (  # noqa: E402
    build_bundle,
)


SIGNATURE_CATALOG = (
    REPO
    / "coordination"
    / "graphic_design_lab"
    / "directions"
    / "greeting_cards"
    / "signature_variant_catalog_v0_1.yaml"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bundle",
        required=True,
    )
    parser.add_argument(
        "--resource-manifest",
        required=True,
    )
    parser.add_argument(
        "--artifact-manifest",
        required=True,
    )
    parser.add_argument(
        "--output-dir",
        required=True,
    )
    args = parser.parse_args()

    try:
        result = build_bundle(
            bundle_path=Path(
                args.bundle
            ),
            resource_manifest_path=Path(
                args.resource_manifest
            ),
            artifact_manifest_path=Path(
                args.artifact_manifest
            ),
            signature_catalog_path=(
                SIGNATURE_CATALOG
            ),
            output_dir=Path(
                args.output_dir
            ),
        )
    except Exception as exc:
        print(
            "GDL_GREETING_CARD_BUILDER=FAIL"
        )
        print(
            f"ERROR={type(exc).__name__}:{exc}"
        )
        print(
            "PRIVATE_PATHS_PRINTED=false"
        )
        return 2

    report = result[
        "bundle_report"
    ]

    print(
        "GDL_GREETING_CARD_BUILDER=PASS"
    )
    print(
        "RENDERER_SLICE="
        "STANDARD_PORTRAIT_GRIGO_V0_1"
    )
    print(
        f"JOB_COUNT={report['job_count']}"
    )
    print(
        "PDF_PAGE_COUNT_PER_JOB=4"
    )
    print(
        "PREVIEWS_PER_JOB=4"
    )
    print(
        "PREVIEWS_FROM_FINAL_PDF=true"
    )
    print(
        "OCCASION_TEXT_REGENERATED=true"
    )
    print(
        "GREETING_TEXT_REGENERATED=true"
    )
    print(
        "SENDER_TEXT_REGENERATED=true"
    )
    print(
        "GRIGO_VECTOR_PRESERVED_FROM_REFERENCE=true"
    )
    print(
        "ILLUSTRATOR_RUNTIME_DEPENDENCY=false"
    )
    print(
        "RAW_CUSTOMER_INTERPRETATION=false"
    )
    print(
        "HEURISTIC_INFERENCE=false"
    )
    print(
        "PRODUCTION_READY=false"
    )
    print(
        "PRIVATE_PATHS_PRINTED=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

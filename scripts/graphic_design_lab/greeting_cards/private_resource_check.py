
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


REPO = Path(__file__).resolve().parents[3]

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.graphic_design_lab.greeting_card_private_resources import (  # noqa: E402
    public_resolution_summary,
    validate_and_resolve_private_resources,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        required=True,
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest).expanduser()

    if not manifest_path.is_absolute():
        manifest_path = (
            Path.cwd() / manifest_path
        ).resolve()

    if not manifest_path.is_file():
        print(
            "GDL_GREETING_CARD_PRIVATE_RESOURCES=FAIL"
        )
        print(
            "ERROR=private_resource_manifest_missing"
        )
        print(
            "PRIVATE_PATHS_PRINTED=false"
        )
        return 2

    manifest = yaml.safe_load(
        manifest_path.read_text(encoding="utf-8")
    )

    try:
        resolved = (
            validate_and_resolve_private_resources(
                manifest
            )
        )
    except Exception as exc:
        print(
            "GDL_GREETING_CARD_PRIVATE_RESOURCES=FAIL"
        )
        print(
            f"ERROR={type(exc).__name__}:{exc}"
        )
        print(
            "PRIVATE_PATHS_PRINTED=false"
        )
        return 2

    public = public_resolution_summary(
        resolved
    )

    print(
        "GDL_GREETING_CARD_PRIVATE_RESOURCES=PASS"
    )
    print(
        f"RESOURCE_COUNT={len(public)}"
    )

    for resource_id in sorted(public):
        item = public[resource_id]
        print(
            f"RESOURCE={resource_id}"
        )
        print(
            f"KIND={item['kind']}"
        )
        print(
            f"SHA256={item['sha256']}"
        )

        if "font_family" in item:
            print(
                f"FONT_FAMILY={item['font_family']}"
            )
            print(
                f"REQUIRED_GLYPHS={item['required_glyphs']}"
            )

        if "page_count" in item:
            print(
                f"PAGE_COUNT={item['page_count']}"
            )

    print(
        "SUBSTITUTION_ALLOWED=false"
    )
    print(
        "FUZZY_RESOURCE_SEARCH=false"
    )
    print(
        "PRIVATE_PATHS_PRINTED=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

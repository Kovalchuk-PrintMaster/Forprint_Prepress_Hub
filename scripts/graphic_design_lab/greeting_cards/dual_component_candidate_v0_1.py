#!/usr/bin/env python3
"""Private component-only DUAL proof; NEVER client/production Builder output."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.graphic_design_lab.greeting_card_dual_component_candidate_v0_1 import (  # noqa: E402
    run_candidate,
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--output-root", required=True, type=Path)
    args = p.parse_args()
    try:
        result = run_candidate(args.manifest, args.output_root)
    except Exception as error:
        print("GDL_GC09_DUAL_COMPONENT_CANDIDATE=BLOCKED")
        print("ERROR_CODE=" + type(error).__name__)
        print("PRIVATE_PATHS_PRINTED=false")
        return 2
    print("GDL_GC09_DUAL_COMPONENT_CANDIDATE=PASS_REQUIRES_VISUAL_REVIEW")
    print("SOURCE_COMPONENTS=" + str(result["component_count"]))
    print("NATIVE_VECTORS=" + str(result["output"]["output_vector_count"]))
    print("RGBA_IDENTITY=PASS")
    print("SOFT_MASK=PASS")
    print("CANONICAL_SENDER_SOURCE=" + result["canonical_sender_source"]["status"])
    print("FULL_CARD_RENDERED=false")
    print("DUAL_RUNTIME_ENABLED=false")
    print("PRODUCTION_READY=false")
    print("PRIVATE_PATHS_PRINTED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

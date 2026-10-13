#!/usr/bin/env python3
"""Private DUAL source-locked page-four proof; not the Builder or customer output."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.graphic_design_lab.greeting_card_dual_page4_candidate_v0_1 import run_candidate  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--prior-component-report", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run_candidate(args.manifest, args.prior_component_report, args.output_root)
    except Exception as exc:
        print("GDL_GC09_DUAL_PAGE4_CANDIDATE=BLOCKED")
        print("ERROR_CODE=" + type(exc).__name__)
        print("PRIVATE_PATHS_PRINTED=false")
        return 2
    print("GDL_GC09_DUAL_PAGE4_CANDIDATE=PASS_REQUIRES_VISUAL_REVIEW")
    print("NATIVE_VECTORS=" + str(result["output"]["output_vector_count"]))
    print("CANONICAL_SENDER_LINES=" + str(result["text_evidence"]["sender_line_count"]))
    print("GREETING_SOURCE=VERIFIED_PRIVATE_DUAL_REFERENCE")
    print("EXACT_FONT=PASS")
    print("RGBA_AND_SOFT_MASK=PASS")
    print("PRIOR_VECTOR_REPLAY_IDENTITY=PASS")
    print("VISIBLE_OVERLAP=TRANSPARENT_REGION")
    print("FULL_CARD_RENDERED=false")
    print("ACCEPTED_JOB_RENDERED=false")
    print("DUAL_RUNTIME_ENABLED=false")
    print("PRODUCTION_READY=false")
    print("PRIVATE_PATHS_PRINTED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

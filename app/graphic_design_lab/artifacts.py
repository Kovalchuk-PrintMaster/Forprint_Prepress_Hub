"""Artifact-manifest helpers for Graphic Design Lab validation outputs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .compiler import CompiledSvg


def build_artifact_manifest(
    *,
    document_id: str,
    revision_id: str,
    artifacts: list[CompiledSvg],
    output_role: str,
) -> dict[str, Any]:
    return {
        "schema_version": "forprint_graphic_design_lab_artifact_manifest_v0_1",
        "document_id": document_id,
        "revision_id": revision_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output_role": output_role,
        "artifacts": [
            {
                "kind": "editable_svg",
                "spread_id": item.spread_id,
                "filename": item.filename,
                "sha256": item.sha256,
            }
            for item in artifacts
        ],
        "preview_available": False,
        "review_pdf_available": False,
        "production_ready": False,
    }

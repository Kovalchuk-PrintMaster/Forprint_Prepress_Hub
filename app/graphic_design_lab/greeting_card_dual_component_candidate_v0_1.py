"""GC-E2E-09C: private DUAL signature *component-only* replay proof.

This is deliberately NOT accepted Constructor/Builder execution, not a greeting
card, and not an authorization to enable the DUAL signature variant at runtime.
Existing source fingerprint validation is required before any replay. Only the
seven identified source vector paths and the exact masked signature image are
copied; source page background, text, hidden vectors and frames are excluded.
"""
from __future__ import annotations

import hashlib
import io
import json
from math import floor, ceil
from pathlib import Path
from typing import Any

import pymupdf
import yaml
from PIL import Image

from app.graphic_design_lab.greeting_card_embedded_components import (
    DUAL_GRIGO_BBOX_MM,
    DUAL_GRIGO_DRAWING_INDICES,
    DUAL_HERASYMENKO_BBOX_MM,
    HERASYMENKO_SIGNATURE_IMAGE_DIGEST_HEX,
    _inspect_dual_signature,
    _signature_cluster_sha256,
    _cluster_union,
)
from app.graphic_design_lab.greeting_card_builder_renderer import (
    MM_PER_PT,
    _find_image,
    _insert_digest_image,
    _pdf_image_rgba_pixel_identity,
    _image_soft_mask_xref,
)
from app.graphic_design_lab.greeting_card_pdf_primitives import (
    normalize_image_soft_mask_colorspaces,
)
from app.graphic_design_lab.greeting_card_private_resources import (
    RESOURCE_SIGNATURE_DUAL,
    validate_and_resolve_private_resources,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "gdl_gc09_dual_component_candidate_v0_1"
REGISTRY_PATH = (
    ROOT / "coordination/graphic_design_lab/directions/greeting_cards/"
    "canonical_sender_blocks_v0_1.yaml"
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bbox_mm(rect: pymupdf.Rect) -> list[float]:
    return [round(float(value) * MM_PER_PT, 3) for value in rect]


def _bbox_equal(actual: list[float], expected: tuple[float, ...], tol: float = .06) -> bool:
    return len(actual) == 4 and all(abs(a - b) <= tol for a, b in zip(actual, expected))


def checked_output_root(path: Path) -> Path:
    root = path.expanduser().resolve()
    tmp = (ROOT / "tmp").resolve()
    if root == tmp or tmp not in root.parents:
        raise ValueError("candidate_output_outside_repo_tmp")
    if root.exists():
        raise ValueError("candidate_output_already_exists")
    return root


def _canonical_dual_sender_source_check(page: pymupdf.Page, source_sha256: str) -> dict[str, Any]:
    """Require registered source text and geometry; do not render sender here."""
    registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    if registry.get("schema_version") != "gdl_greeting_card_canonical_sender_blocks_v0_1":
        raise ValueError("dual_sender_registry_schema_invalid")
    row = registry["variants"]["DUAL_GRIGO_HERASYMENKO"]
    if row.get("source_sha256") != source_sha256:
        raise ValueError("dual_sender_source_digest_mismatch")
    actual = []
    for block in page.get_text("dict", sort=True).get("blocks", []):
        if block.get("type") != 0 or block["bbox"][1] * MM_PER_PT < 198.0:
            continue
        for line in block.get("lines", []):
            spans = [s for s in line.get("spans", []) if str(s.get("text", "")).strip()]
            if spans:
                actual.append((
                    "".join(str(s.get("text", "")) for s in spans).strip(),
                    _bbox_mm(pymupdf.Rect(line["bbox"])),
                ))
    texts = [item[0] for item in actual]
    boxes = [item[1] for item in actual]
    if texts != row["texts"] or boxes != row["bboxes_pdf_mm"]:
        raise ValueError("dual_sender_source_text_or_geometry_mismatch")
    actual_hash = hashlib.sha256("\n".join(texts).encode("utf-8")).hexdigest()
    if actual_hash != row["text_sha256"]:
        raise ValueError("dual_sender_text_sha256_mismatch")
    return {"status": "PASS", "row_count": len(actual), "source_text_sha256": actual_hash}


def _verify_transparent_sender_overlap(
    page: pymupdf.Page, image_info: dict[str, Any],
    sender_boxes_mm: list[list[float]],
) -> dict[str, Any]:
    """Reject any visible-ink overlap; transparent source box overlap is okay."""
    image_box = pymupdf.Rect(image_info["bbox"])
    overlaps = []
    for idx, values in enumerate(sender_boxes_mm, 1):
        region = pymupdf.Rect([float(v) / MM_PER_PT for v in values]) & image_box
        if not region.is_empty:
            overlaps.append((idx, region))
    if len(overlaps) != 1 or overlaps[0][0] != 5:
        raise ValueError("dual_source_overlap_geometry_changed")
    smask_xref = _image_soft_mask_xref(page, int(image_info["xref"]))
    if smask_xref <= 0:
        raise ValueError("dual_source_overlap_soft_mask_missing")
    data = page.parent.extract_image(smask_xref)["image"]
    with Image.open(io.BytesIO(data)) as im:
        mask = im.convert("L")
        row_index, hit = overlaps[0]
        box = (
            max(0, floor((hit.x0-image_box.x0)/image_box.width*mask.width)),
            max(0, floor((hit.y0-image_box.y0)/image_box.height*mask.height)),
            min(mask.width, ceil((hit.x1-image_box.x0)/image_box.width*mask.width)),
            min(mask.height, ceil((hit.y1-image_box.y0)/image_box.height*mask.height)),
        )
        crop = mask.crop(box)
        if crop.width <= 0 or crop.height <= 0 or crop.getextrema()[1] != 0:
            raise ValueError("dual_source_visible_signature_sender_overlap")
        return {"status": "TRANSPARENT_REGION", "sender_row": row_index,
                "inspected_alpha_pixels": crop.width * crop.height,
                "max_alpha": 0}


def replay_vector_paths(target_page: pymupdf.Page, drawings: list[dict[str, Any]]) -> None:
    """Write only native vector operations; no source PDF Form XObject."""
    if len(drawings) != 7:
        raise ValueError("dual_grigo_vector_path_count_invalid")
    for drawing in drawings:
        if drawing.get("type") != "f" or drawing.get("fill") is None:
            raise ValueError("dual_grigo_vector_fill_invalid")
        shape = target_page.new_shape()
        for operation in drawing.get("items", []):
            if operation[0] == "l":
                shape.draw_line(operation[1], operation[2])
            elif operation[0] == "c":
                shape.draw_bezier(*operation[1:5])
            else:
                raise ValueError("dual_grigo_unsupported_vector_operation")
        shape.finish(
            width=float(drawing.get("width") or 1),
            color=drawing.get("color"),
            fill=drawing["fill"],
            closePath=True,
            even_odd=bool(drawing.get("even_odd")),
            fill_opacity=float(drawing.get("fill_opacity") if drawing.get("fill_opacity") is not None else 1.0),
        )
        shape.commit(overlay=True)


def _checked_output(page: pymupdf.Page, expected_rgba_sha: str) -> dict[str, Any]:
    vectors = page.get_drawings()
    if len(vectors) != 7:
        raise ValueError("dual_output_native_vector_count_mismatch")
    vector_box = _bbox_mm(_cluster_union(vectors))
    if not _bbox_equal(vector_box, DUAL_GRIGO_BBOX_MM):
        raise ValueError("dual_output_vector_geometry_mismatch")
    images = [
        info for info in page.get_image_info(hashes=True, xrefs=True)
        if tuple((int(info.get("width", 0)), int(info.get("height", 0)))) == (536, 700)
        and _bbox_equal(_bbox_mm(pymupdf.Rect(info["bbox"])), DUAL_HERASYMENKO_BBOX_MM)
    ]
    if len(images) != 1:
        raise ValueError("dual_output_signature_image_count_mismatch")
    image = images[0]
    identity = _pdf_image_rgba_pixel_identity(page, int(image["xref"]))
    if identity["rgba_pixel_sha256"] != expected_rgba_sha:
        raise ValueError("dual_output_signature_rgba_identity_mismatch")
    if identity["soft_mask_xref"] <= 0 or identity["soft_mask_colorspace"] != "/DeviceGray":
        raise ValueError("dual_output_soft_mask_identity_invalid")
    if page.get_text("text").strip():
        raise ValueError("dual_component_only_output_contains_text")
    return {
        "output_vector_count": len(vectors),
        "output_vector_bbox_mm": vector_box,
        "output_native_vector_sha256": _signature_cluster_sha256(vectors, union=_cluster_union(vectors)),
        "output_rgba_pixel_sha256": identity["rgba_pixel_sha256"],
        "output_soft_mask": "PASS",
    }


def run_candidate(resource_manifest_path: Path, output_root: Path) -> dict[str, Any]:
    """Create strictly private signature-only page + preview, never a full card."""
    output_root = checked_output_root(output_root)
    manifest_path = resource_manifest_path.expanduser().resolve()
    before = _sha256_file(manifest_path)
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    resources = validate_and_resolve_private_resources(
        manifest, required_ids=[RESOURCE_SIGNATURE_DUAL]
    )
    source_path = resources[RESOURCE_SIGNATURE_DUAL]["path"]
    source_sha = _sha256_file(source_path)
    with pymupdf.open(source_path) as source:
        if source.page_count != 4:
            raise ValueError("dual_candidate_source_must_have_four_pages")
        source_page = source[3]
        verified = _inspect_dual_signature(source_page)
        if verified.get("status") != "PASS" or verified.get("component_count") != 2:
            raise ValueError("dual_candidate_source_not_verified")
        sender_audit = _canonical_dual_sender_source_check(source_page, source_sha)
        drawing_list = source_page.get_drawings()
        selected = [drawing_list[i] for i in DUAL_GRIGO_DRAWING_INDICES]
        signature_image = _find_image(source_page, HERASYMENKO_SIGNATURE_IMAGE_DIGEST_HEX)
        if signature_image is None:
            raise ValueError("dual_candidate_signature_image_missing")
        source_rgba = _pdf_image_rgba_pixel_identity(source_page, int(signature_image["xref"]))
        if source_rgba["soft_mask_xref"] <= 0:
            raise ValueError("dual_candidate_source_soft_mask_missing")
        canonical_registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
        transparent_overlap = _verify_transparent_sender_overlap(
            source_page, signature_image,
            canonical_registry["variants"]["DUAL_GRIGO_HERASYMENKO"]["bboxes_pdf_mm"],
        )
        output_root.mkdir(parents=True, exist_ok=False)
        pdf_path = output_root / "DUAL_COMPONENT_ONLY_NOT_FULL_CARD.pdf"
        preview_path = output_root / "DUAL_COMPONENT_ONLY_NOT_FULL_CARD.png"
        report_path = output_root / "candidate_report.json"
        proof = pymupdf.open()
        target = proof.new_page(width=source_page.rect.width, height=source_page.rect.height)
        replay_vector_paths(target, selected)
        destination = pymupdf.Rect([n / MM_PER_PT for n in DUAL_HERASYMENKO_BBOX_MM])
        _insert_digest_image(
            source, source_page, target, HERASYMENKO_SIGNATURE_IMAGE_DIGEST_HEX,
            destination=destination,
        )
        normalize_image_soft_mask_colorspaces(proof)
        proof.save(pdf_path, garbage=4, deflate=True, clean=True)
        proof.close()
    with pymupdf.open(pdf_path) as document:
        if document.page_count != 1:
            raise ValueError("dual_candidate_output_page_count_invalid")
        output_evidence = _checked_output(document[0], source_rgba["rgba_pixel_sha256"])
        pix = document[0].get_pixmap(matrix=pymupdf.Matrix(120 / 72, 120 / 72), alpha=False)
        pix.save(preview_path)
    if _sha256_file(manifest_path) != before or _sha256_file(source_path) != source_sha:
        raise ValueError("dual_candidate_source_mutation_detected")
    report = {
        "schema_version": SCHEMA,
        "status": "ISOLATED_DUAL_COMPONENT_CANDIDATE_NOT_BUILDER_OUTPUT",
        "source_signature_component_sha256": verified["composite_sha256"],
        "source_pdf_sha256": source_sha,
        "canonical_sender_source": sender_audit,
        "source_signature_sender_overlap": transparent_overlap,
        "component_count": 2,
        "source_grigo_vectors": 7,
        "output": output_evidence,
        "proof_pdf_sha256": _sha256_file(pdf_path),
        "proof_png_sha256": _sha256_file(preview_path),
        "dual_runtime_enabled": False,
        "production_ready": False,
        "customer_approved": False,
        "client_published": False,
        "has_full_card_layout": False,
        "sender_text_rendered_in_proof": False,
        "visual_review_required": True,
    }
    report_path.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return report

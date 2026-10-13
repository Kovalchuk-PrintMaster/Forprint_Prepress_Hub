"""GC-E2E-09C: private, source-locked DUAL page-four composition candidate.

Not the Builder runtime, an accepted job, a full card, or permission to publish.
Use only SHA256-validated private sources and the previous isolated DUAL proof.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pymupdf
import yaml

from app.graphic_design_lab.greeting_card_canonical_sender_v0_1 import (
    MM_PER_PT,
    render_source_sender_text,
)
from app.graphic_design_lab.greeting_card_dual_component_candidate_v0_1 import (
    _canonical_dual_sender_source_check,
    _sha256_file,
    _verify_transparent_sender_overlap,
    checked_output_root,
    replay_vector_paths,
)
from app.graphic_design_lab.greeting_card_embedded_components import (
    DUAL_GRIGO_DRAWING_INDICES,
    DUAL_HERASYMENKO_BBOX_MM,
    HERASYMENKO_SIGNATURE_IMAGE_DIGEST_HEX,
    _inspect_dual_signature,
)
from app.graphic_design_lab.greeting_card_builder_renderer import (
    COMMON_IMAGE_DIGESTS,
    _find_image,
    _insert_digest_image,
    _insert_page4_watermark_half_opacity,
    _insert_reference_digest_at_source_geometry,
    _new_matching_page,
    _pdf_image_rgba_pixel_identity,
)
from app.graphic_design_lab.greeting_card_pdf_primitives import (
    normalize_image_soft_mask_colorspaces,
)
from app.graphic_design_lab.greeting_card_private_resources import (
    RESOURCE_GREETING_FONT,
    RESOURCE_REFERENCE_PDF,
    RESOURCE_SIGNATURE_DUAL,
    validate_and_resolve_private_resources,
)

SCHEMA = "gdl_gc09_dual_page4_candidate_v0_1"
PROOF_PDF = "DUAL_PAGE4_ONLY_NOT_FULL_CARD.pdf"
PROOF_PNG = "DUAL_PAGE4_ONLY_NOT_FULL_CARD.png"
PROOF_REPORT = "candidate_report.json"
ISOLATED_PDF = "DUAL_COMPONENT_ONLY_NOT_FULL_CARD.pdf"


def canonical_rows(page: pymupdf.Page) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Gather immutable source spans without adopting any Intake text authority."""
    greeting: list[dict[str, Any]] = []
    sender: list[dict[str, Any]] = []
    for block in page.get_text("dict", sort=True).get("blocks", []):
        if block.get("type") != 0:
            continue
        is_sender = float(block["bbox"][1]) * MM_PER_PT >= 198.0
        for line in block.get("lines", []):
            spans = [dict(s) for s in line.get("spans", []) if str(s.get("text", "")).strip()]
            if not spans:
                continue
            item = {
                "text": "".join(str(s["text"]) for s in spans).strip(),
                "bbox_mm": [round(float(n) * MM_PER_PT, 3) for n in line["bbox"]],
                "spans": spans,
            }
            (sender if is_sender else greeting).append(item)
    return greeting, sender


def checked_prior_proof(report_path: Path, expected_source: str, expected_component: str) -> dict[str, Any]:
    """Pin the earlier signed-off technical proof; don't merely trust a JSON flag."""
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("dual_prior_proof_unreadable") from exc
    if not isinstance(report, dict) or report.get("status") != "ISOLATED_DUAL_COMPONENT_CANDIDATE_NOT_BUILDER_OUTPUT":
        raise ValueError("dual_prior_proof_status_invalid")
    if report.get("source_pdf_sha256") != expected_source or report.get("source_signature_component_sha256") != expected_component:
        raise ValueError("dual_prior_proof_source_identity_mismatch")
    if report.get("component_count") != 2 or report.get("source_grigo_vectors") != 7:
        raise ValueError("dual_prior_proof_component_count_mismatch")
    output = report.get("output")
    if not isinstance(output, dict) or output.get("output_vector_count") != 7 or output.get("output_soft_mask") != "PASS":
        raise ValueError("dual_prior_proof_output_invalid")
    if report.get("canonical_sender_source", {}).get("status") != "PASS":
        raise ValueError("dual_prior_proof_sender_invalid")
    if report.get("source_signature_sender_overlap", {}).get("status") != "TRANSPARENT_REGION":
        raise ValueError("dual_prior_proof_overlap_invalid")
    for key in ("dual_runtime_enabled", "production_ready", "customer_approved", "client_published", "has_full_card_layout", "sender_text_rendered_in_proof"):
        if report.get(key) is not False:
            raise ValueError("dual_prior_proof_authority_invalid:" + key)
    for key, kind in (("output_native_vector_sha256", "vector"), ("output_rgba_pixel_sha256", "image")):
        value = output.get(key)
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("dual_prior_proof_" + kind + "_digest_invalid")
    artifact = report_path.parent / ISOLATED_PDF
    if not artifact.is_file() or _sha256_file(artifact) != report.get("proof_pdf_sha256"):
        raise ValueError("dual_prior_proof_pdf_identity_mismatch")
    prior_png = report_path.parent / "DUAL_COMPONENT_ONLY_NOT_FULL_CARD.png"
    if not prior_png.is_file() or _sha256_file(prior_png) != report.get("proof_png_sha256"):
        raise ValueError("dual_prior_proof_png_identity_mismatch")
    return report


def validate_canonical_text_rows(
    greeting: list[dict[str, Any]], sender: list[dict[str, Any]],
    expected_sender: dict[str, Any],
) -> dict[str, Any]:
    if not greeting:
        raise ValueError("dual_page4_source_greeting_missing")
    if len(sender) != 6 or [item["text"] for item in sender] != expected_sender["texts"]:
        raise ValueError("dual_page4_sender_text_mismatch")
    if [item["bbox_mm"] for item in sender] != expected_sender["bboxes_pdf_mm"]:
        raise ValueError("dual_page4_sender_geometry_mismatch")
    sender_hash = hashlib.sha256("\n".join(item["text"] for item in sender).encode("utf-8")).hexdigest()
    if sender_hash != expected_sender["text_sha256"]:
        raise ValueError("dual_page4_sender_hash_mismatch")
    for item in [*greeting, *sender]:
        for span in item["spans"]:
            if not isinstance(span.get("origin"), (list, tuple)) or len(span["origin"]) != 2:
                raise ValueError("dual_page4_missing_native_text_origins")
            if float(span.get("size", 0)) <= 0:
                raise ValueError("dual_page4_invalid_font_size")
    return {"greeting_line_count": len(greeting), "sender_line_count": len(sender), "sender_text_sha256": sender_hash}


def run_candidate(manifest_path: Path, isolated_report_path: Path, output_root: Path) -> dict[str, Any]:
    """Create isolated page 4 from canonical private PDF and approved proof.

    The greeting is taken from the verified DUAL SOURCE PDF, not from a customer
    bundle: this proves source geometry only, not job-specific greeting semantics.
    """
    output_root = checked_output_root(output_root)
    manifest_path = manifest_path.expanduser().resolve()
    isolated_report_path = isolated_report_path.expanduser().resolve()
    if not isolated_report_path.is_file():
        raise ValueError("dual_prior_proof_report_missing")
    tracked_sources = [manifest_path, isolated_report_path,
                       isolated_report_path.parent / ISOLATED_PDF,
                       isolated_report_path.parent / "DUAL_COMPONENT_ONLY_NOT_FULL_CARD.png"]
    before = {str(p): _sha256_file(p) for p in tracked_sources}
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    resources = validate_and_resolve_private_resources(
        manifest, required_ids=[RESOURCE_GREETING_FONT, RESOURCE_REFERENCE_PDF, RESOURCE_SIGNATURE_DUAL],
    )
    reference_path = resources[RESOURCE_REFERENCE_PDF]["path"]
    source_path = resources[RESOURCE_SIGNATURE_DUAL]["path"]
    font_path = resources[RESOURCE_GREETING_FONT]["path"]
    tracked_sources.extend((reference_path, source_path, font_path))
    before.update({str(p): _sha256_file(p) for p in (reference_path, source_path, font_path)})
    source_sha = _sha256_file(source_path)

    with pymupdf.open(source_path) as dual, pymupdf.open(reference_path) as reference:
        if dual.page_count != 4 or reference.page_count != 4:
            raise ValueError("dual_page4_source_page_count_mismatch")
        page = dual[3]
        source_check = _inspect_dual_signature(page)
        if source_check.get("status") != "PASS" or source_check.get("component_count") != 2:
            raise ValueError("dual_page4_source_component_invalid")
        prior = checked_prior_proof(isolated_report_path, source_sha, source_check["composite_sha256"])
        source_sender_check = _canonical_dual_sender_source_check(page, source_sha)
        if source_sender_check.get("row_count") != 6:
            raise ValueError("dual_page4_sender_source_count_invalid")
        sender_registry = yaml.safe_load(
            (Path(__file__).resolve().parents[2] / "coordination/graphic_design_lab/directions/greeting_cards/canonical_sender_blocks_v0_1.yaml").read_text(encoding="utf-8")
        )["variants"]["DUAL_GRIGO_HERASYMENKO"]
        greeting, sender = canonical_rows(page)
        text_evidence = validate_canonical_text_rows(greeting, sender, sender_registry)
        image = _find_image(page, HERASYMENKO_SIGNATURE_IMAGE_DIGEST_HEX)
        if image is None:
            raise ValueError("dual_page4_image_missing")
        source_rgba = _pdf_image_rgba_pixel_identity(page, int(image["xref"]))
        if source_rgba["rgba_pixel_sha256"] != prior["output"]["output_rgba_pixel_sha256"]:
            raise ValueError("dual_page4_prior_rgba_mismatch")
        source_overlap = _verify_transparent_sender_overlap(page, image, sender_registry["bboxes_pdf_mm"])
        selected_drawings = [page.get_drawings()[i] for i in DUAL_GRIGO_DRAWING_INDICES]

        if abs(page.rect.width - reference[3].rect.width) > .01 or abs(page.rect.height - reference[3].rect.height) > .01:
            raise ValueError("dual_page4_reference_geometry_mismatch")
        proof = pymupdf.open()
        try:
            target = _new_matching_page(proof, reference[3])
            for digest in (COMMON_IMAGE_DIGESTS["background.paper"], COMMON_IMAGE_DIGESTS["frame.ornate"]):
                _insert_reference_digest_at_source_geometry(reference, reference[3], target, digest)
            _insert_page4_watermark_half_opacity(reference, reference[3], target)
            render_source_sender_text(target, greeting, font_path=font_path)
            render_source_sender_text(target, sender, font_path=font_path)
            replay_vector_paths(target, selected_drawings)
            _insert_digest_image(
                dual, page, target, HERASYMENKO_SIGNATURE_IMAGE_DIGEST_HEX,
                destination=pymupdf.Rect([n / MM_PER_PT for n in DUAL_HERASYMENKO_BBOX_MM]),
            )
            normalize_image_soft_mask_colorspaces(proof)
            output_root.mkdir(parents=True, exist_ok=False)
            pdf_path = output_root / PROOF_PDF
            png_path = output_root / PROOF_PNG
            proof.save(pdf_path, garbage=4, deflate=True, clean=True)
        finally:
            proof.close()

    with pymupdf.open(pdf_path) as result:
        if result.page_count != 1:
            raise ValueError("dual_page4_output_page_count_invalid")
        output_page = result[0]
        output = _checked_output_with_text(output_page, prior["output"]["output_rgba_pixel_sha256"])
        if output["output_native_vector_sha256"] != prior["output"]["output_native_vector_sha256"]:
            raise ValueError("dual_page4_vector_replay_identity_mismatch")
        masks = [x for x in output_page.get_image_info(hashes=True, xrefs=True) if (int(x.get("width", 0)), int(x.get("height", 0))) == (536, 700)]
        if len(masks) != 1:
            raise ValueError("dual_page4_signature_image_count_invalid")
        final_overlap = _verify_transparent_sender_overlap(output_page, masks[0], sender_registry["bboxes_pdf_mm"])
        if final_overlap["status"] != source_overlap["status"]:
            raise ValueError("dual_page4_overlap_changed")
        font_names = {str(row[4]) for row in output_page.get_fonts(full=True)}
        if "ZapfChanceryC" not in font_names:
            raise ValueError("dual_page4_exact_font_missing")
        if not output_page.get_text("text").strip():
            raise ValueError("dual_page4_live_text_missing")
        pix = output_page.get_pixmap(matrix=pymupdf.Matrix(120 / 72, 120 / 72), alpha=False)
        pix.save(png_path)
    after = {str(p): _sha256_file(p) for p in tracked_sources}
    if after != before:
        raise ValueError("dual_page4_private_source_mutation")
    report = {
        "schema_version": SCHEMA,
        "status": "DUAL_PAGE4_SOURCE_COMPOSITION_CANDIDATE_REQUIRES_VISUAL_REVIEW",
        "source_pdf_sha256": source_sha,
        "source_signature_composite_sha256": source_check["composite_sha256"],
        "prior_component_proof_sha256": before[str(isolated_report_path)],
        "text_source": "SHA256_VERIFIED_DUAL_REFERENCE_PDF_NOT_ACCEPTED_JOB",
        "text_evidence": text_evidence,
        "source_overlap": source_overlap,
        "output_overlap": final_overlap,
        "output": output,
        "pdf_sha256": _sha256_file(pdf_path),
        "png_sha256": _sha256_file(png_path),
        "visual_review_required": True,
        "dual_runtime_enabled": False,
        "production_ready": False,
        "customer_approved": False,
        "client_published": False,
        "full_card_rendered": False,
        "accepted_job_rendered": False,
        "repository_mutated": False,
    }
    (output_root / PROOF_REPORT).write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return report


def _checked_output_with_text(page: pymupdf.Page, expected_rgba_sha: str) -> dict[str, Any]:
    """Reuse component signature validation while retaining page-four text."""
    from app.graphic_design_lab.greeting_card_dual_component_candidate_v0_1 import _bbox_equal, _bbox_mm
    from app.graphic_design_lab.greeting_card_embedded_components import (
        DUAL_GRIGO_BBOX_MM, _cluster_union, _signature_cluster_sha256,
    )
    from app.graphic_design_lab.greeting_card_builder_renderer import _pdf_image_rgba_pixel_identity

    vectors = page.get_drawings()
    if len(vectors) != 7:
        raise ValueError("dual_page4_native_vector_count_mismatch")
    bbox = _bbox_mm(_cluster_union(vectors))
    if not _bbox_equal(bbox, DUAL_GRIGO_BBOX_MM):
        raise ValueError("dual_page4_native_vector_bbox_mismatch")
    imgs = [i for i in page.get_image_info(hashes=True, xrefs=True)
            if (int(i.get("width", 0)), int(i.get("height", 0))) == (536, 700)
            and _bbox_equal(_bbox_mm(pymupdf.Rect(i["bbox"])), DUAL_HERASYMENKO_BBOX_MM)]
    if len(imgs) != 1:
        raise ValueError("dual_page4_signature_image_identity_missing")
    identity = _pdf_image_rgba_pixel_identity(page, int(imgs[0]["xref"]))
    if identity["rgba_pixel_sha256"] != expected_rgba_sha:
        raise ValueError("dual_page4_rgba_identity_mismatch")
    if identity["soft_mask_xref"] <= 0 or identity["soft_mask_colorspace"] != "/DeviceGray":
        raise ValueError("dual_page4_soft_mask_invalid")
    return {
        "status": "PASS",
        "output_vector_count": 7,
        "output_vector_bbox_mm": bbox,
        "output_native_vector_sha256": _signature_cluster_sha256(vectors, union=_cluster_union(vectors)),
        "output_rgba_pixel_sha256": identity["rgba_pixel_sha256"],
        "soft_mask": "PASS",
    }

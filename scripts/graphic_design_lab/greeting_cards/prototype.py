#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pymupdf
import yaml
from PIL import Image, ImageChops, ImageDraw

REPO = Path(__file__).resolve().parents[3]

SKELETON = (
    REPO
    / "coordination/graphic_design_lab/directions/greeting_cards/"
    / "product_skeleton_v0_1.yaml"
)
FREEZE = (
    REPO
    / "coordination/graphic_design_lab/directions/greeting_cards/"
    / "structural_design_freeze_v0_1.yaml"
)
OUTPUT_DEFAULT = REPO / "tmp/gdl_prototypes/greeting_card_v0_2"

COMMON_DIGESTS = {
    "background.paper": "7e00983a508f9c59fb6148e9d33a52ca",
    "frame.ornate": "b136196cfb1dcc996333e75707257946",
    "watermark.emblem": "216f5696fab35f44f4b18c8efe82cefa",
    "front.sender_logo": "78b87a6195270a66b0e32de814f8f597",
}

MM_PER_PT = 25.4 / 72.0
PT_PER_MM = 72.0 / 25.4

AUTHORING_LAYER_HINTS = re.compile(
    r"(danger\s*zone|guide|guides|non[-_\s]*print|technical\s*guide)",
    re.I,
)


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    ).stdout.rstrip()


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def digest_hex(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).hex()
    return str(value)


def rect_from_mm(values: list[float]) -> pymupdf.Rect:
    return pymupdf.Rect(*(float(v) * PT_PER_MM for v in values))


def rect_to_mm(rect: pymupdf.Rect | None) -> list[float] | None:
    if rect is None:
        return None
    return [
        round(float(rect.x0) * MM_PER_PT, 3),
        round(float(rect.y0) * MM_PER_PT, 3),
        round(float(rect.x1) * MM_PER_PT, 3),
        round(float(rect.y1) * MM_PER_PT, 3),
    ]



FRONT_FAMILY_UNRESOLVED = "UNRESOLVED"


def bbox_max_delta_mm(
    observed: list[float],
    canonical: list[float],
) -> float:
    if len(observed) != 4 or len(canonical) != 4:
        raise ValueError("front-family bbox must contain four coordinates")
    return max(
        abs(float(observed[i]) - float(canonical[i]))
        for i in range(4)
    )


def bbox_mean_delta_mm(
    observed: list[float],
    canonical: list[float],
) -> float:
    if len(observed) != 4 or len(canonical) != 4:
        raise ValueError("front-family bbox must contain four coordinates")
    return sum(
        abs(float(observed[i]) - float(canonical[i]))
        for i in range(4)
    ) / 4.0


def rects_intersect_mm(
    left: list[float],
    right: list[float],
) -> bool:
    return not (
        left[2] <= right[0]
        or left[0] >= right[2]
        or left[3] <= right[1]
        or left[1] >= right[3]
    )


def classify_front_family_from_bbox(
    observed_bbox_mm: list[float],
    skeleton: dict[str, Any],
) -> dict[str, Any]:
    front = skeleton["variant_model"]["front"]
    classifier = front.get("classifier", {})

    max_delta_allowed = float(
        classifier.get("max_coordinate_delta_mm", 6.0)
    )
    ambiguity_margin = float(
        classifier.get("ambiguity_margin_mm", 4.0)
    )

    scores = []
    for family in front["semantic_families"]:
        canonical_bbox = [
            float(value)
            for value in family["sender_logo_bbox_mm"]
        ]
        scores.append(
            {
                "family": family["id"],
                "canonical_sender_logo_bbox_mm": canonical_bbox,
                "max_delta_mm": round(
                    bbox_max_delta_mm(
                        observed_bbox_mm,
                        canonical_bbox,
                    ),
                    4,
                ),
                "mean_delta_mm": round(
                    bbox_mean_delta_mm(
                        observed_bbox_mm,
                        canonical_bbox,
                    ),
                    4,
                ),
            }
        )

    scores.sort(
        key=lambda item: (
            item["max_delta_mm"],
            item["mean_delta_mm"],
            item["family"],
        )
    )

    best = scores[0]
    second = scores[1] if len(scores) > 1 else None
    margin = (
        round(
            second["max_delta_mm"] - best["max_delta_mm"],
            4,
        )
        if second is not None
        else None
    )

    resolved = (
        best["max_delta_mm"] <= max_delta_allowed
        and (
            margin is None
            or margin >= ambiguity_margin
        )
    )

    return {
        "family": (
            best["family"]
            if resolved
            else FRONT_FAMILY_UNRESOLVED
        ),
        "resolved": resolved,
        "observed_sender_logo_bbox_mm": [
            round(float(value), 3)
            for value in observed_bbox_mm
        ],
        "best_family": best["family"],
        "best_max_delta_mm": best["max_delta_mm"],
        "second_best_margin_mm": margin,
        "max_coordinate_delta_mm": max_delta_allowed,
        "ambiguity_margin_mm": ambiguity_margin,
        "scores": scores,
    }


def page_text_spans(
    page: pymupdf.Page,
) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    data = page.get_text("dict")

    for block in data.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = str(span.get("text") or "").strip()
                bbox = span.get("bbox")
                if not text or not bbox:
                    continue
                spans.append(
                    {
                        "text": text,
                        "bbox_mm": rect_to_mm(
                            pymupdf.Rect(bbox)
                        ),
                    }
                )

    return spans


def semantic_front_evidence(
    page: pymupdf.Page,
    skeleton: dict[str, Any],
) -> dict[str, Any]:
    front = skeleton["variant_model"]["front"]
    families = {
        item["id"]: item
        for item in front["semantic_families"]
    }

    overlay = families["RECIPIENT_BRANDING_OVERLAY"]
    bilingual = families["BILINGUAL_OCCASION"]

    recipient_zone = [
        float(value)
        for value in overlay["recipient_branding_zone_mm"]
    ]
    occasion_zone = [
        float(value)
        for value in bilingual["occasion_bbox_mm"]
    ]

    spans = page_text_spans(page)
    recipient_text = [
        item["text"]
        for item in spans
        if item["bbox_mm"] is not None
        and rects_intersect_mm(
            item["bbox_mm"],
            recipient_zone,
        )
    ]
    occasion_text = " ".join(
        item["text"]
        for item in spans
        if item["bbox_mm"] is not None
        and rects_intersect_mm(
            item["bbox_mm"],
            occasion_zone,
        )
    )

    common = set(COMMON_DIGESTS.values())
    extra_image_digests = sorted(
        {
            item["digest_hex"]
            for item in page_image_info(page)
            if item["digest_hex"] not in common
        }
    )

    has_cyrillic = bool(
        re.search(
            r"[А-Яа-яІіЇїЄєҐґ]",
            occasion_text,
        )
    )
    has_latin = bool(
        re.search(
            r"[A-Za-z]",
            occasion_text,
        )
    )

    return {
        "recipient_branding_text_count": len(
            recipient_text
        ),
        "recipient_branding_text_preview": (
            recipient_text[:3]
        ),
        "extra_page1_image_count": len(
            extra_image_digests
        ),
        "extra_page1_image_digests": (
            extra_image_digests
        ),
        "occasion_has_cyrillic": has_cyrillic,
        "occasion_has_latin": has_latin,
        "bilingual_occasion_signal": (
            has_cyrillic and has_latin
        ),
    }


def classify_front_family(
    page: pymupdf.Page,
    skeleton: dict[str, Any],
) -> dict[str, Any]:
    logo = find_image(
        page,
        COMMON_DIGESTS["front.sender_logo"],
        required=False,
    )

    if logo is None:
        return {
            "family": FRONT_FAMILY_UNRESOLVED,
            "resolved": False,
            "reason": "sender_logo_digest_missing",
            "semantic_evidence": semantic_front_evidence(
                page,
                skeleton,
            ),
        }

    observed_bbox = rect_to_mm(
        logo["bbox_rect"]
    )
    assert observed_bbox is not None

    result = classify_front_family_from_bbox(
        observed_bbox,
        skeleton,
    )
    result["semantic_evidence"] = semantic_front_evidence(
        page,
        skeleton,
    )
    result["reason"] = (
        "nearest_canonical_sender_logo_geometry"
        if result["resolved"]
        else "geometry_threshold_or_ambiguity"
    )
    return result


def resolved_front_family_sender_logo_geometry(
    classification: dict[str, Any],
    skeleton: dict[str, Any],
) -> tuple[str, list[float]]:
    """Resolve the canonical sender-logo geometry for a classified front family."""
    if classification.get("resolved") is not True:
        raise ValueError("front family must be resolved before compositor dispatch")

    family_id = str(classification.get("family") or "")
    families = {
        str(item["id"]): item
        for item in skeleton["variant_model"]["front"]["semantic_families"]
    }

    family = families.get(family_id)
    if family is None:
        raise ValueError(f"unknown resolved front family: {family_id}")

    bbox = family.get("sender_logo_bbox_mm")
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise ValueError(
            f"front family {family_id} has invalid sender_logo_bbox_mm"
        )

    return family_id, [float(value) for value in bbox]


def expected_front_family_counts(
    skeleton: dict[str, Any],
) -> dict[str, int]:
    return {
        item["id"]: int(item["observed_jobs"])
        for item
        in skeleton["variant_model"]["front"][
            "semantic_families"
        ]
    }


def run_corpus_validation(
    *,
    client_root: Path,
    sample_dir: str,
    output: Path,
    skeleton: dict[str, Any],
) -> None:
    corpus_dir = client_root / sample_dir
    pdfs = sorted(corpus_dir.glob("*.pdf"))

    expected_counts = expected_front_family_counts(
        skeleton
    )
    expected_total = sum(expected_counts.values())

    results: list[dict[str, Any]] = []
    observed_counts = {
        key: 0
        for key in expected_counts
    }
    unresolved = []

    for pdf_path in pdfs:
        item: dict[str, Any] = {
            "file_name": pdf_path.name,
        }

        try:
            doc = pymupdf.open(pdf_path)
            item["page_count"] = doc.page_count

            if doc.page_count != 4:
                item["family"] = FRONT_FAMILY_UNRESOLVED
                item["resolved"] = False
                item["reason"] = (
                    "unexpected_page_count"
                )
            else:
                classification = classify_front_family(
                    doc[0],
                    skeleton,
                )
                item.update(classification)

            doc.close()
        except Exception as exc:
            item["family"] = FRONT_FAMILY_UNRESOLVED
            item["resolved"] = False
            item["reason"] = (
                f"classification_error:{type(exc).__name__}"
            )
            item["error"] = str(exc)

        family = item["family"]
        if family in observed_counts:
            observed_counts[family] += 1
        else:
            unresolved.append(pdf_path.name)

        results.append(item)

    count_match = (
        observed_counts == expected_counts
    )
    corpus_size_match = (
        len(pdfs) == expected_total
    )
    all_resolved = (
        len(unresolved) == 0
        and all(
            item.get("resolved") is True
            for item in results
        )
    )

    status = (
        "PASS"
        if (
            count_match
            and corpus_size_match
            and all_resolved
        )
        else "FAIL"
    )

    output.mkdir(
        parents=True,
        exist_ok=True,
    )
    report_json = (
        output
        / "front_family_corpus_report_v0_1.json"
    )
    report_md = (
        output
        / "front_family_corpus_report_v0_1.md"
    )

    report = {
        "schema_version":
            "gdl_greeting_card_front_family_corpus_validation_v0_1",
        "status": status,
        "source_location":
            "EXTERNAL_PRIVATE_CLIENT_WORKSPACE",
        "source_modified": False,
        "sample_dir": sample_dir,
        "expected_pdf_count": expected_total,
        "observed_pdf_count": len(pdfs),
        "expected_counts": expected_counts,
        "observed_counts": observed_counts,
        "all_resolved": all_resolved,
        "count_match": count_match,
        "corpus_size_match": corpus_size_match,
        "results": results,
        "boundaries": {
            "client_mutation": False,
            "git_mutation": False,
            "blueprint_mutation": False,
            "filename_based_classification": False,
        },
    }

    report_json.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    lines = [
        "# Greeting Card Front-Family Corpus Validation v0.1",
        "",
        f"Status: `{status}`",
        "",
        f"Expected PDFs: `{expected_total}`",
        f"Observed PDFs: `{len(pdfs)}`",
        "",
        "## Counts",
        "",
    ]
    for family in sorted(expected_counts):
        lines.append(
            f"- {family}: "
            f"expected `{expected_counts[family]}`, "
            f"observed `{observed_counts[family]}`"
        )

    lines += [
        "",
        "## Files",
        "",
    ]
    for item in results:
        lines.append(
            f"- `{item['file_name']}` -> "
            f"`{item['family']}`"
        )

    report_md.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 100)
    print("FRONT FAMILY CORPUS VALIDATION")
    print("=" * 100)
    print(f"CORPUS_PDF_COUNT={len(pdfs)}")
    print(f"EXPECTED_PDF_COUNT={expected_total}")

    for family in sorted(expected_counts):
        print(
            f"FAMILY_COUNT_{family}="
            f"{observed_counts[family]}"
        )
        print(
            f"FAMILY_EXPECTED_{family}="
            f"{expected_counts[family]}"
        )

    for item in results:
        print(
            f"FRONT_FAMILY={item['family']}"
            f"	FILE={item['file_name']}"
        )

    print(
        f"REPORT_JSON={report_json.relative_to(REPO)}"
    )
    print(
        f"REPORT_MD={report_md.relative_to(REPO)}"
    )
    print(
        f"ALL_RESOLVED="
        f"{str(all_resolved).lower()}"
    )
    print(
        f"COUNT_MATCH="
        f"{str(count_match).lower()}"
    )
    print(
        f"CORPUS_SIZE_MATCH="
        f"{str(corpus_size_match).lower()}"
    )
    print(
        "FILENAME_BASED_CLASSIFICATION=false"
    )
    print("CLIENT_MUTATION=false")
    print("GIT_MUTATION=false")
    print("BLUEPRINT_MUTATION=false")

    if status != "PASS":
        raise SystemExit(
            "STOP=front_family_corpus_validation_failed"
        )

    print(
        "GDL_GREETING_CARD_FRONT_FAMILY_CORPUS_VALIDATION=PASS"
    )


def page_image_info(page: pymupdf.Page) -> list[dict[str, Any]]:
    items = []
    for info in page.get_image_info(hashes=True, xrefs=True):
        item = dict(info)
        item["digest_hex"] = digest_hex(item.get("digest"))
        item["bbox_rect"] = pymupdf.Rect(item["bbox"])
        items.append(item)
    return items


def find_image(
    page: pymupdf.Page,
    digest: str,
    *,
    required: bool = True,
) -> dict[str, Any] | None:
    matches = [
        item
        for item in page_image_info(page)
        if item["digest_hex"] == digest
    ]
    if not matches:
        if required:
            raise RuntimeError(
                f"image digest not found page={page.number + 1} digest={digest}"
            )
        return None
    return matches[0]


def xref_smask(page: pymupdf.Page, xref: int) -> int:
    for item in page.get_images(full=True):
        if int(item[0]) == int(xref):
            return int(item[1] or 0)
    return 0


def raw_image_payload(
    doc: pymupdf.Document,
    page: pymupdf.Page,
    xref: int,
) -> tuple[bytes, bytes | None]:
    extracted = doc.extract_image(xref)
    stream = extracted["image"]

    mask = None
    smask = xref_smask(page, xref)
    if smask > 0:
        try:
            mask = doc.extract_image(smask)["image"]
        except Exception:
            mask = None

    return stream, mask


def copy_page_boxes(src: pymupdf.Page, dst: pymupdf.Page) -> None:
    for getter_name, setter_name in (
        ("cropbox", "set_cropbox"),
        ("bleedbox", "set_bleedbox"),
        ("trimbox", "set_trimbox"),
        ("artbox", "set_artbox"),
    ):
        setter = getattr(dst, setter_name, None)
        if setter is None:
            continue
        try:
            setter(getattr(src, getter_name))
        except Exception:
            pass


def new_matching_page(
    out: pymupdf.Document,
    src: pymupdf.Page,
) -> pymupdf.Page:
    page = out.new_page(
        width=float(src.mediabox.width),
        height=float(src.mediabox.height),
    )
    copy_page_boxes(src, page)
    return page


def insert_digest_image(
    src_doc: pymupdf.Document,
    src_page: pymupdf.Page,
    dst_page: pymupdf.Page,
    digest: str,
    *,
    dest_rect: pymupdf.Rect | None = None,
) -> dict[str, Any]:
    info = find_image(src_page, digest)
    assert info is not None

    xref = int(info["xref"])
    stream, mask = raw_image_payload(src_doc, src_page, xref)
    rect = dest_rect or info["bbox_rect"]

    kwargs: dict[str, Any] = {
        "stream": stream,
        "keep_proportion": False,
        "overlay": True,
    }
    if mask:
        kwargs["mask"] = mask

    dst_page.insert_image(rect, **kwargs)

    return {
        "digest": digest,
        "source_xref": xref,
        "source_bbox_mm": rect_to_mm(info["bbox_rect"]),
        "dest_bbox_mm": rect_to_mm(rect),
        "raw_source_stream_reused": True,
        "source_soft_mask_reused": bool(mask),
    }


def ocg_name_from_xref(
    doc: pymupdf.Document,
    xref: int,
    ocgs: dict[int, dict[str, Any]] | None = None,
) -> str:
    info = (ocgs or {}).get(int(xref), {})
    name = str(info.get("name") or "")
    if name:
        return name

    try:
        raw = doc.xref_object(int(xref))
    except Exception:
        return ""

    match = re.search(r"/Name\s*\((.*?)\)", raw, re.S)
    if not match:
        return ""

    return match.group(1).strip()


def marked_content_remove(
    data: bytes,
    property_name: str,
) -> tuple[bytes, int]:
    prop = re.escape(property_name.encode("latin1"))
    start_pattern = re.compile(
        rb"/OC\s*/" + prop + rb"\s+BDC"
    )
    token_pattern = re.compile(rb"\b(?:BDC|BMC|EMC)\b")

    removed = 0
    cursor = 0
    chunks: list[bytes] = []

    while True:
        match = start_pattern.search(data, cursor)
        if match is None:
            chunks.append(data[cursor:])
            break

        chunks.append(data[cursor:match.start()])
        depth = 1
        end_pos = None

        for token in token_pattern.finditer(data, match.end()):
            op = token.group(0)
            if op in (b"BDC", b"BMC"):
                depth += 1
            else:
                depth -= 1
                if depth == 0:
                    end_pos = token.end()
                    break

        if end_pos is None:
            # Defensive: do not corrupt stream if syntax cannot be bounded.
            chunks.append(data[match.start():])
            cursor = len(data)
            break

        removed += 1
        cursor = end_pos

    return b"".join(chunks), removed


def strip_authoring_layers(
    doc: pymupdf.Document,
) -> list[dict[str, Any]]:
    ocgs = doc.get_ocgs() or {}
    props_to_strip: dict[str, dict[str, Any]] = {}

    for page in doc:
        try:
            oc_items = page.get_oc_items()
        except Exception:
            oc_items = []

        for prop_name, xref, oc_type in oc_items:
            layer_name = ocg_name_from_xref(
                doc,
                int(xref),
                ocgs,
            )
            if AUTHORING_LAYER_HINTS.search(layer_name):
                props_to_strip[str(prop_name)] = {
                    "property_name": str(prop_name),
                    "xref": int(xref),
                    "type": str(oc_type),
                    "layer_name": layer_name,
                }

    removals = []
    if not props_to_strip:
        return removals

    for xref in range(1, doc.xref_length()):
        try:
            stream = doc.xref_stream(xref)
        except Exception:
            continue
        if not stream:
            continue

        updated = stream
        stream_removed = []

        for prop_name, meta in props_to_strip.items():
            if (
                b"/OC" not in updated
                or prop_name.encode("latin1") not in updated
            ):
                continue

            updated2, count = marked_content_remove(
                updated,
                prop_name,
            )
            if count:
                updated = updated2
                stream_removed.append(
                    {
                        **meta,
                        "stream_xref": xref,
                        "block_count": count,
                    }
                )

        if stream_removed:
            doc.update_stream(xref, updated)
            removals.extend(stream_removed)

    return removals


def clone_page_filtered(
    src_doc: pymupdf.Document,
    page_index: int,
    *,
    remove_digests: set[str],
) -> tuple[pymupdf.Document, dict[str, Any]]:
    overlay = pymupdf.open()
    overlay.insert_pdf(
        src_doc,
        from_page=page_index,
        to_page=page_index,
    )

    authoring_layers_removed = strip_authoring_layers(overlay)

    page = overlay[0]
    xrefs_to_delete = sorted(
        {
            int(item["xref"])
            for item in page_image_info(page)
            if item["digest_hex"] in remove_digests
            and int(item.get("xref") or 0) > 0
        }
    )

    for xref in xrefs_to_delete:
        page.delete_image(xref)

    return overlay, {
        "authoring_layers_removed": authoring_layers_removed,
        "deleted_image_xrefs": xrefs_to_delete,
    }


def portrait_digest_on_page3(page: pymupdf.Page) -> str:
    common = set(COMMON_DIGESTS.values())
    variable = [
        item["digest_hex"]
        for item in page_image_info(page)
        if item["digest_hex"] not in common
    ]
    unique = sorted(set(variable))
    if len(unique) != 1:
        raise RuntimeError(
            f"expected exactly one page-3 portrait digest, found {unique}"
        )
    return unique[0]


def render_page(
    page: pymupdf.Page,
    dpi: int,
) -> Image.Image:
    matrix = pymupdf.Matrix(dpi / 72.0, dpi / 72.0)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    return Image.frombytes(
        "RGB",
        [pix.width, pix.height],
        pix.samples,
    )


def image_diff_metrics(
    a: Image.Image,
    b: Image.Image,
    width_mm: float,
    height_mm: float,
) -> dict[str, Any]:
    if a.size != b.size:
        raise RuntimeError(
            f"render size mismatch {a.size} != {b.size}"
        )

    diff = ImageChops.difference(
        a.convert("RGB"),
        b.convert("RGB"),
    )
    gray = diff.convert("L")
    total = gray.width * gray.height

    bands: dict[int, float] = {}
    bbox_mm = None

    for threshold_value in (3, 10, 20, 40):
        mask = gray.point(
            lambda p, t=threshold_value: 255 if p > t else 0
        )
        hist = mask.histogram()
        changed = int(hist[255])
        bands[threshold_value] = (
            round(changed / total, 8)
            if total
            else 0.0
        )

        if threshold_value == 3:
            bbox = mask.getbbox()
            if bbox:
                x0, y0, x1, y1 = bbox
                bbox_mm = [
                    round(x0 * width_mm / mask.width, 3),
                    round(y0 * height_mm / mask.height, 3),
                    round(x1 * width_mm / mask.width, 3),
                    round(y1 * height_mm / mask.height, 3),
                ]

    histogram = gray.histogram()
    weighted = sum(
        value * count
        for value, count in enumerate(histogram)
    )
    mean_abs_rgb_delta = (
        round(weighted / total, 4)
        if total
        else 0.0
    )

    return {
        "changed_pixel_ratio": bands[3],
        "changed_pixel_ratio_gt10": bands[10],
        "changed_pixel_ratio_gt20": bands[20],
        "changed_pixel_ratio_gt40": bands[40],
        "mean_abs_rgb_delta": mean_abs_rgb_delta,
        "diff_bbox_mm": bbox_mm,
    }

def make_contact_sheet(
    reference_paths: list[Path],
    prototype_paths: list[Path],
    out_path: Path,
) -> None:
    rows = []
    target_w = 430

    for ref_path, proto_path in zip(
        reference_paths,
        prototype_paths,
    ):
        ref = Image.open(ref_path).convert("RGB")
        proto = Image.open(proto_path).convert("RGB")

        rratio = target_w / ref.width
        pratio = target_w / proto.width
        ref = ref.resize(
            (target_w, int(ref.height * rratio))
        )
        proto = proto.resize(
            (target_w, int(proto.height * pratio))
        )
        rows.append((ref, proto))

    pad = 20
    label_h = 34
    row_h = max(
        max(ref.height, proto.height)
        for ref, proto in rows
    ) + label_h

    width = target_w * 2 + pad * 3
    height = row_h * 4 + pad * 5

    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)

    for i, (ref, proto) in enumerate(rows):
        y = pad + i * (row_h + pad)
        draw.text(
            (pad, y + 8),
            f"PAGE {i + 1} REFERENCE",
            fill="black",
        )
        draw.text(
            (pad * 2 + target_w, y + 8),
            f"PAGE {i + 1} PROTOTYPE V0.2",
            fill="black",
        )

        sheet.paste(ref, (pad, y + label_h))
        sheet.paste(
            proto,
            (pad * 2 + target_w, y + label_h),
        )

    sheet.save(out_path, format="PNG")


def normalize_image_soft_mask_colorspaces(
    doc: pymupdf.Document,
) -> list[int]:
    """Normalize image soft-mask color spaces for strict PDF renderers.

    PyMuPDF can create an image /SMask whose ColorSpace is an indirect
    grayscale ICCBased object. PyMuPDF renders it, while Acrobat / Poppler
    may reject it as bad image parameters. Normalize image soft masks to
    /DeviceGray without changing their pixel streams.
    """
    smask_xrefs: set[int] = set()

    for xref in range(1, doc.xref_length()):
        try:
            obj = doc.xref_object(xref)
        except Exception:
            continue

        if "/SMask" not in obj:
            continue

        for match in re.finditer(
            r"/SMask\s+(\d+)\s+0\s+R",
            obj,
        ):
            smask_xrefs.add(int(match.group(1)))

    normalized: list[int] = []

    for smask_xref in sorted(smask_xrefs):
        try:
            obj = doc.xref_object(smask_xref)
        except Exception:
            continue

        if "/Subtype /Image" not in obj:
            continue

        kind, value = doc.xref_get_key(
            smask_xref,
            "ColorSpace",
        )

        if kind == "name" and value == "/DeviceGray":
            continue

        doc.xref_set_key(
            smask_xref,
            "ColorSpace",
            "/DeviceGray",
        )
        normalized.append(smask_xref)

    return normalized


def run_external_checks(pdf_path: Path) -> dict[str, Any]:
    checks: dict[str, Any] = {}

    for name, command in (
        ("qpdf", ["qpdf", "--check", str(pdf_path)]),
        ("pdfinfo", ["pdfinfo", "-box", str(pdf_path)]),
    ):
        cp = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        checks[name] = {
            "exit_code": cp.returncode,
            "output": cp.stdout.strip(),
        }

    with tempfile.TemporaryDirectory(
        prefix="gdl_pdf_compat_",
        dir=str(pdf_path.parent),
    ) as tmpdir:
        prefix = Path(tmpdir) / "page"
        cp = subprocess.run(
            [
                "pdftoppm",
                "-png",
                "-r",
                "24",
                str(pdf_path),
                str(prefix),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        output = cp.stdout.strip()
        syntax_error = bool(
            re.search(
                r"(?:Syntax Error|Error:)",
                output,
                re.I,
            )
        )
        checks["pdftoppm"] = {
            "exit_code": cp.returncode,
            "output": output,
            "syntax_error": syntax_error,
        }

    return checks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--mode",
        choices=("prototype", "corpus-validate"),
        default="prototype",
    )
    ap.add_argument("--client-root", required=True)
    ap.add_argument("--sample-dir", default="20.09.26")
    ap.add_argument("--reference", default="dolinska.pdf")
    ap.add_argument("--output", default=str(OUTPUT_DEFAULT))
    ap.add_argument("--dpi", type=int, default=144)
    args = ap.parse_args()

    print("GDL_GREETING_CARD_PROJECT_PROTOTYPE=START")
    print("MODE=READ_ONLY_CLIENT_DETERMINISTIC_PROTOTYPE_CORRECTION")
    print("CLIENT_MUTATION=false")
    print("GIT_MUTATION=false")
    print("BLUEPRINT_MUTATION=false")
    print("TEXT_REGENERATION_PERFORMED=false")
    print("AUTHORING_NOISE_FILTER=ENABLED")

    head = git("rev-parse", "HEAD")
    upstream = git("rev-parse", "@{u}")
    status = git("status", "--short")

    print(f"HEAD={head}")
    print(f"UPSTREAM={upstream}")
    print(
        f"HEAD_EQUALS_UPSTREAM={str(head == upstream).lower()}"
    )
    print(f"WORKTREE_CLEAN={str(status == '').lower()}")

    if status:
        raise SystemExit("STOP=prepress_worktree_not_clean")

    for path in (SKELETON, FREEZE):
        if not path.is_file():
            raise SystemExit(
                f"STOP=missing_canonical_input:"
                f"{path.relative_to(REPO)}"
            )

    skeleton = load_yaml(SKELETON)
    freeze = load_yaml(FREEZE)

    if freeze.get("established") is not True:
        raise SystemExit(
            "STOP=structural_freeze_not_established"
        )

    client_root = Path(args.client_root).resolve()

    output = Path(args.output)
    if not output.is_absolute():
        output = (REPO / output).resolve()

    try:
        output.relative_to(REPO)
    except ValueError:
        raise SystemExit(
            "STOP=output_must_be_inside_prepress_repo"
        )

    if args.mode == "corpus-validate":
        run_corpus_validation(
            client_root=client_root,
            sample_dir=args.sample_dir,
            output=output,
            skeleton=skeleton,
        )
        return

    source_pdf = (
        client_root
        / args.sample_dir
        / args.reference
    )
    if not source_pdf.is_file():
        raise SystemExit(
            f"STOP=reference_pdf_missing:{source_pdf}"
        )

    output.mkdir(parents=True, exist_ok=True)

    prototype_pdf = (
        output / "prototype_standard_v0_2.pdf"
    )
    report_json = (
        output / "prototype_report_v0_2.json"
    )
    report_md = (
        output / "prototype_report_v0_2.md"
    )

    src = pymupdf.open(source_pdf)
    if src.page_count != 4:
        raise SystemExit(
            f"STOP=unexpected_reference_page_count:"
            f"{src.page_count}"
        )

    p1, p2, p3, p4 = (
        src[0],
        src[1],
        src[2],
        src[3],
    )

    portrait_digest = portrait_digest_on_page3(p3)

    front_family_classification = classify_front_family(
        src[0],
        skeleton,
    )
    try:
        (
            front_family_id,
            front_family_sender_logo_bbox_mm,
        ) = resolved_front_family_sender_logo_geometry(
            front_family_classification,
            skeleton,
        )
    except ValueError as exc:
        raise SystemExit(
            f"STOP=front_family_compositor_dispatch:{exc}"
        ) from exc

    front_family_logo_rect = rect_from_mm(
        front_family_sender_logo_bbox_mm
    )

    out = pymupdf.open()

    assembly: dict[str, Any] = {
        "reference_pdf": args.reference,
        "front_family": front_family_id,
        "front_family_classification": front_family_classification,
        "front_sender_logo_bbox_mm": [
            round(float(value), 3)
            for value in front_family_sender_logo_bbox_mm
        ],
        "text_regeneration_performed": False,
        "authoring_noise_filter": True,
        "pages": [],
    }

    # PAGE 1: preserve unchanged reference content and only normalize
    # the sender-logo component that already has canonical geometry.
    page1_doc, page1_meta = clone_page_filtered(
        src,
        0,
        remove_digests={
            COMMON_DIGESTS["front.sender_logo"],
        },
    )
    page1 = page1_doc[0]
    p1_ops = [
        insert_digest_image(
            src,
            p1,
            page1,
            COMMON_DIGESTS["front.sender_logo"],
            dest_rect=front_family_logo_rect,
        )
    ]
    out.insert_pdf(page1_doc)
    page1_doc.close()

    assembly["pages"].append(
        {
            "physical_page": 1,
            "logical_page": "PAGE_1_FRONT",
            "mode":
                "PRESERVED_REFERENCE_PAGE_PLUS_CANONICAL_SENDER_LOGO",
            "operations": p1_ops,
            "reference_filter": page1_meta,
        }
    )

    # PAGE 2: locked reuse-only page transplant.
    # Preserve original PDF transparency / blend semantics exactly.
    page2_doc, page2_meta = clone_page_filtered(
        src,
        1,
        remove_digests=set(),
    )
    out.insert_pdf(page2_doc)
    page2_doc.close()

    assembly["pages"].append(
        {
            "physical_page": 2,
            "logical_page": "PAGE_4_BACK",
            "mode": "LOCKED_REUSE_ONLY_PAGE_TRANSPLANT",
            "reference_filter": page2_meta,
        }
    )

    # PAGE 3: deterministic base, preserve source portrait clipping/mask layer.
    dst3 = new_matching_page(out, p3)
    p3_ops = [
        insert_digest_image(
            src,
            p3,
            dst3,
            COMMON_DIGESTS["background.paper"],
        ),
    ]

    portrait_overlay, portrait_meta = clone_page_filtered(
        src,
        2,
        remove_digests={
            COMMON_DIGESTS["background.paper"],
            COMMON_DIGESTS["frame.ornate"],
        },
    )
    dst3.show_pdf_page(
        dst3.rect,
        portrait_overlay,
        0,
        overlay=True,
    )
    portrait_overlay.close()

    p3_ops.append(
        insert_digest_image(
            src,
            p3,
            dst3,
            COMMON_DIGESTS["frame.ornate"],
        )
    )

    assembly["pages"].append(
        {
            "physical_page": 3,
            "logical_page": "PAGE_2_INSIDE_IMAGE",
            "mode":
                "DETERMINISTIC_BASE_PLUS_PRESERVED_PORTRAIT_MASK_LAYER",
            "portrait_digest": portrait_digest,
            "operations": p3_ops,
            "portrait_overlay_filter": portrait_meta,
        }
    )

    # PAGE 4: preserve the exact embedded-font/vector/transparency page
    # until text regeneration becomes executable. Remove only the hidden
    # page-3 portrait leftover already proven to have zero rendered value.
    page4_doc, page4_meta = clone_page_filtered(
        src,
        3,
        remove_digests={
            portrait_digest,
        },
    )
    out.insert_pdf(page4_doc)
    page4_doc.close()

    assembly["pages"].append(
        {
            "physical_page": 4,
            "logical_page": "PAGE_3_INSIDE_GREETING",
            "mode":
                "PRESERVED_REFERENCE_PAGE_MINUS_HIDDEN_AUTHORING_OBJECT",
            "hidden_page3_portrait_removed": True,
            "reference_filter": page4_meta,
        }
    )

    out.set_metadata(
        {
            "title":
                "ForPrint GDL Greeting Card Deterministic Prototype v0.2",
            "author": "ForPrint Graphic Design Lab",
            "subject":
                "Noise-filtered structural-freeze prototype",
        }
    )

    normalized_smask_xrefs = (
        normalize_image_soft_mask_colorspaces(out)
    )
    assembly["soft_mask_devicegray_normalized_xrefs"] = (
        normalized_smask_xrefs
    )

    out.save(
        prototype_pdf,
        garbage=4,
        deflate=True,
        clean=True,
    )
    out.close()

    generated = pymupdf.open(prototype_pdf)

    comparison = []
    ref_paths = []
    proto_paths = []

    for idx in range(4):
        source_img = render_page(
            src[idx],
            args.dpi,
        )
        proto_img = render_page(
            generated[idx],
            args.dpi,
        )

        ref_path = output / f"reference_page_{idx + 1}.png"
        proto_path = output / f"prototype_page_{idx + 1}.png"

        source_img.save(ref_path, format="PNG")
        proto_img.save(proto_path, format="PNG")

        ref_paths.append(ref_path)
        proto_paths.append(proto_path)

        metrics = image_diff_metrics(
            source_img,
            proto_img,
            float(generated[idx].rect.width) * MM_PER_PT,
            float(generated[idx].rect.height) * MM_PER_PT,
        )
        metrics["physical_page"] = idx + 1
        comparison.append(metrics)

    contact_sheet = (
        output
        / "reference_vs_prototype_contact_sheet.png"
    )
    make_contact_sheet(
        ref_paths,
        proto_paths,
        contact_sheet,
    )

    generated.close()
    src.close()

    checks = run_external_checks(prototype_pdf)

    removed_layers = []
    for page_meta in assembly["pages"]:
        for key in (
            "overlay_filter",
            "portrait_overlay_filter",
            "reference_filter",
        ):
            for item in page_meta.get(
                key,
                {},
            ).get(
                "authoring_layers_removed",
                [],
            ):
                removed_layers.append(item)

    report = {
        "schema_version":
            "gdl_greeting_card_first_deterministic_prototype_v0_2",
        "status": "PROTOTYPE_GENERATED_REVIEW_REQUIRED",
        "repo_head": head,
        "reference": {
            "file_name": args.reference,
            "source_location":
                "EXTERNAL_PRIVATE_CLIENT_WORKSPACE",
            "source_modified": False,
        },
        "assembly": assembly,
        "authoring_layers_removed": removed_layers,
        "page_comparison": comparison,
        "external_checks": checks,
        "boundaries": {
            "structural_design_freeze_established": True,
            "text_regeneration_performed": False,
            "font_substitution_performed": False,
            "production_ready": False,
            "client_mutation": False,
            "git_mutation": False,
            "blueprint_mutation": False,
        },
    }

    report_json.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    lines = [
        "# Greeting Card Prototype v0.2",
        "",
        "Corrections from v0.1:",
        "",
        "- unchanged page content is preserved as native PDF until deterministic regeneration is owned by the project;",
        "- page 1 changes only the sender-logo placement selected from the resolved front-family canonical geometry;",
        "- page 2 uses locked reuse-only PDF page transplant;",
        "- page 3 remains the first true deterministic compositor proof with preserved portrait clipping/mask;",
        "- page 4 preserves exact fonts/vector/transparency and removes only the hidden portrait leftover;",
        "- comparison now reports perceptual thresholds instead of relying on one >3 pixel-delta ratio.",
        "",
        "Page diff ratios:",
        "",
    ]

    for item in comparison:
        lines.append(
            f"- page {item['physical_page']}: "
            f"{item['changed_pixel_ratio']}"
        )

    report_md.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    qpdf_ok = checks["qpdf"]["exit_code"] == 0
    pdfinfo_ok = checks["pdfinfo"]["exit_code"] == 0
    pdftoppm_ok = (
        checks["pdftoppm"]["exit_code"] == 0
        and checks["pdftoppm"]["syntax_error"] is False
    )

    print()
    print("=" * 100)
    print("PROTOTYPE V0.2 SUMMARY")
    print("=" * 100)
    print(f"PROTOTYPE_PDF={prototype_pdf.relative_to(REPO)}")
    print(
        f"CONTACT_SHEET={contact_sheet.relative_to(REPO)}"
    )
    print(f"REPORT_JSON={report_json.relative_to(REPO)}")
    print(f"REPORT_MD={report_md.relative_to(REPO)}")
    print(
        f"AUTHORING_LAYER_BLOCKS_REMOVED={len(removed_layers)}"
    )

    for item in comparison:
        print(
            f"PAGE{item['physical_page']}_DIFF_RATIO="
            f"{item['changed_pixel_ratio']}"
        )
        print(
            f"PAGE{item['physical_page']}_DIFF_RATIO_GT20="
            f"{item['changed_pixel_ratio_gt20']}"
        )
        print(
            f"PAGE{item['physical_page']}_MEAN_ABS_DELTA="
            f"{item['mean_abs_rgb_delta']}"
        )

    print(
        f"QPDF_CHECK={'PASS' if qpdf_ok else 'FAIL'}"
    )
    print(
        f"PDFINFO_CHECK={'PASS' if pdfinfo_ok else 'FAIL'}"
    )
    print(
        f"PDFTOPPM_CHECK={'PASS' if pdftoppm_ok else 'FAIL'}"
    )
    print(
        "SMASK_DEVICEGRAY_NORMALIZED_COUNT="
        + str(len(normalized_smask_xrefs))
    )
    print("TEXT_REGENERATION_PERFORMED=false")
    print("FONT_SUBSTITUTION_PERFORMED=false")
    print("VISUAL_REVIEW_REQUIRED=true")
    print("PRODUCTION_READY=false")
    print("CLIENT_MUTATION=false")
    print("GIT_MUTATION=false")
    print("BLUEPRINT_MUTATION=false")

    if not qpdf_ok or not pdfinfo_ok or not pdftoppm_ok:
        raise SystemExit(
            "STOP=prototype_pdf_cross_renderer_check_failed"
        )

    print(
        "GDL_GREETING_CARD_PROJECT_PROTOTYPE=PASS"
    )


if __name__ == "__main__":
    main()

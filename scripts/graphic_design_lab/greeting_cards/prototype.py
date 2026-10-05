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
    source_pdf = (
        client_root
        / args.sample_dir
        / args.reference
    )
    if not source_pdf.is_file():
        raise SystemExit(
            f"STOP=reference_pdf_missing:{source_pdf}"
        )

    output = Path(args.output)
    if not output.is_absolute():
        output = (REPO / output).resolve()

    try:
        output.relative_to(REPO)
    except ValueError:
        raise SystemExit(
            "STOP=output_must_be_inside_prepress_repo"
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

    front_families = {
        item["id"]: item
        for item
        in skeleton["variant_model"]["front"][
            "semantic_families"
        ]
    }
    standard = front_families["STANDARD"]
    standard_logo_rect = rect_from_mm(
        standard["sender_logo_bbox_mm"]
    )

    out = pymupdf.open()

    assembly: dict[str, Any] = {
        "reference_pdf": args.reference,
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
            dest_rect=standard_logo_rect,
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
        "- page 1 changes only the canonically owned sender-logo placement;",
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

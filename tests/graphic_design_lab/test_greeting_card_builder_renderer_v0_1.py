
from __future__ import annotations

import hashlib

import pymupdf
import pytest
from PIL import Image

from app.graphic_design_lab.greeting_card_pdf_primitives import (
    marked_content_remove,
    normalize_image_soft_mask_colorspaces,
)
from app.graphic_design_lab.greeting_card_builder_renderer import (
    ARTIFACT_MANIFEST_SCHEMA,
    SUPPORTED_FRONT_FAMILIES,
    SUPPORTED_IMAGE_MODES,
    SUPPORTED_SIGNATURE_VARIANTS,
    STANDARD_BIRTHDAY_DISPLAY_TEXT,
    STANDARD_BIRTHDAY_LINES,
    _alpha_profile_bytes,
    _artifact_manifest_entry,
    _image_soft_mask_xref,
    _validate_first_slice_job,
    normalize_portrait_bytes,
    render_previews_from_final_pdf,
    strip_page_text_blocks,
)


def test_first_slice_is_explicit_and_bounded():
    assert SUPPORTED_FRONT_FAMILIES == (
        "STANDARD",
    )
    assert SUPPORTED_IMAGE_MODES == (
        "PORTRAIT",
    )
    assert SUPPORTED_SIGNATURE_VARIANTS == (
        "GRIGO",
    )


def test_standard_birthday_occasion_has_exact_two_line_layout():
    assert (
        STANDARD_BIRTHDAY_DISPLAY_TEXT
        == "Привітання з нагоди Дня Народження!"
    )
    assert STANDARD_BIRTHDAY_LINES == (
        "Привітання з нагоди",
        "Дня Народження!",
    )


def test_artifact_manifest_resolves_exact_hash(
    tmp_path,
):
    asset = tmp_path / "portrait.png"
    asset.write_bytes(
        b"sanitized-portrait"
    )
    digest = hashlib.sha256(
        asset.read_bytes()
    ).hexdigest()

    manifest = {
        "schema_version":
            ARTIFACT_MANIFEST_SCHEMA,
        "artifacts": {
            "artifact-r001": {
                "source_asset_id":
                    "portrait-001",
                "path":
                    str(asset.resolve()),
                "sha256":
                    digest,
            }
        },
    }

    resolved = _artifact_manifest_entry(
        manifest,
        artifact_ref="artifact-r001",
        source_asset_id="portrait-001",
        expected_sha256=digest,
    )

    assert resolved == asset.resolve()


def test_artifact_manifest_hash_mismatch_fails_closed(
    tmp_path,
):
    asset = tmp_path / "portrait.png"
    asset.write_bytes(
        b"sanitized-portrait"
    )

    manifest = {
        "schema_version":
            ARTIFACT_MANIFEST_SCHEMA,
        "artifacts": {
            "artifact-r001": {
                "source_asset_id":
                    "portrait-001",
                "path":
                    str(asset.resolve()),
                "sha256":
                    "0" * 64,
            }
        },
    }

    with pytest.raises(
        ValueError,
        match="sha256_mismatch",
    ):
        _artifact_manifest_entry(
            manifest,
            artifact_ref="artifact-r001",
            source_asset_id="portrait-001",
            expected_sha256="0" * 64,
        )


def test_strip_page_text_blocks_preserves_page_and_removes_text():
    document = pymupdf.open()
    page = document.new_page(
        width=300,
        height=400,
    )
    page.insert_text(
        (30, 50),
        "REMOVE ME",
    )

    before = page.get_text(
        "text"
    )
    assert "REMOVE ME" in before

    removed = strip_page_text_blocks(
        document,
        page_index=0,
    )
    assert removed >= 1

    after = document[0].get_text(
        "text"
    )
    assert "REMOVE ME" not in after
    assert document.page_count == 1
    document.close()


def test_strip_page_text_blocks_does_not_modify_image_stream(
    tmp_path,
):
    image_path = tmp_path / "image.png"
    Image.new(
        "RGB",
        (64, 64),
        "white",
    ).save(
        image_path
    )

    document = pymupdf.open()
    page = document.new_page(
        width=300,
        height=400,
    )
    page.insert_image(
        pymupdf.Rect(
            20,
            20,
            120,
            120,
        ),
        filename=str(
            image_path
        ),
    )
    page.insert_text(
        (30, 180),
        "REMOVE ME",
    )

    images = page.get_images(
        full=True
    )
    assert len(images) == 1
    image_xref = int(
        images[0][0]
    )
    before = document.xref_stream(
        image_xref
    )

    removed = strip_page_text_blocks(
        document,
        page_index=0,
    )
    assert removed >= 1

    after = document.xref_stream(
        image_xref
    )
    assert after == before
    assert "REMOVE ME" not in (
        document[0].get_text(
            "text"
        )
    )

    document.close()


def test_portrait_normalization_is_exact_size(
    tmp_path,
):
    source = tmp_path / "source.png"
    Image.new(
        "RGB",
        (300, 500),
        "white",
    ).save(
        source
    )

    payload = normalize_portrait_bytes(
        source,
        width=120,
        height=160,
    )

    target = tmp_path / "normalized.png"
    target.write_bytes(
        payload
    )

    with Image.open(
        target
    ) as image:
        assert image.size == (
            120,
            160,
        )


def test_portrait_normalization_preserves_partial_alpha(
    tmp_path,
):
    source = tmp_path / "alpha.png"
    image = Image.new(
        "RGBA",
        (120, 120),
        (0, 0, 0, 0),
    )
    for x in range(20, 100):
        for y in range(20, 100):
            image.putpixel(
                (x, y),
                (20, 40, 80, 128),
            )
    image.save(source)

    payload = normalize_portrait_bytes(
        source,
        width=160,
        height=160,
    )
    profile = _alpha_profile_bytes(payload)
    assert profile["has_transparency"] is True
    assert profile["partial_alpha_pixels"] > 0


def test_transparent_png_insert_creates_pdf_soft_mask(
    tmp_path,
):
    source = tmp_path / "alpha.png"
    image = Image.new(
        "RGBA",
        (64, 64),
        (0, 0, 0, 0),
    )
    for x in range(8, 56):
        for y in range(8, 56):
            image.putpixel(
                (x, y),
                (30, 60, 90, 180),
            )
    image.save(source)

    doc = pymupdf.open()
    page = doc.new_page(width=200, height=200)
    xref = page.insert_image(
        pymupdf.Rect(20, 20, 180, 180),
        stream=source.read_bytes(),
        keep_proportion=False,
        overlay=True,
    )
    assert _image_soft_mask_xref(page, int(xref)) > 0
    doc.close()


def test_preview_generation_reads_final_pdf_only(
    tmp_path,
):
    pdf = tmp_path / "final.pdf"
    doc = pymupdf.open()

    for index in range(4):
        page = doc.new_page(
            width=214 * 72 / 25.4,
            height=301 * 72 / 25.4,
        )
        page.insert_text(
            (30, 40),
            f"PAGE {index + 1}",
        )

    doc.save(
        pdf
    )
    doc.close()

    previews = (
        render_previews_from_final_pdf(
            pdf,
            tmp_path / "preview",
            stem="sample",
            dpi=48,
        )
    )

    assert len(previews) == 4
    assert all(
        path.is_file()
        for path in previews
    )


class FakeSoftMaskDoc:
    def __init__(self):
        self.objects = {
            1:
                "<< /Type /XObject /Subtype /Image /SMask 3 0 R >>",
            2:
                "<< /Type /XObject /Subtype /Image /SMask 4 0 R >>",
            3:
                "<< /Type /XObject /Subtype /Image /ColorSpace 7 0 R >>",
            4:
                "<< /Type /XObject /Subtype /Image /ColorSpace /DeviceGray >>",
            7:
                "[ /ICCBased 8 0 R ]",
            8:
                "<< /N 1 /Alternate /DeviceGray >>",
        }
        self.color_spaces = {
            3:
                ("xref", "7 0 R"),
            4:
                ("name", "/DeviceGray"),
        }
        self.set_calls = []

    def xref_length(self):
        return 9

    def xref_object(
        self,
        xref,
    ):
        return self.objects.get(
            xref,
            "",
        )

    def xref_get_key(
        self,
        xref,
        key,
    ):
        assert key == "ColorSpace"
        return self.color_spaces.get(
            xref,
            ("null", "null"),
        )

    def xref_set_key(
        self,
        xref,
        key,
        value,
    ):
        self.set_calls.append(
            (
                xref,
                key,
                value,
            )
        )
        self.color_spaces[
            xref
        ] = (
            "name",
            value,
        )


def test_authoring_marked_content_remove_handles_nested_blocks():
    payload = (
        b"q "
        b"/OC /MC6 BDC "
        b"1 0 0 RG "
        b"/Span BMC 0 0 m 10 10 l S EMC "
        b"EMC "
        b"Q"
    )

    cleaned, count = (
        marked_content_remove(
            payload,
            "MC6",
        )
    )

    assert count == 1
    assert b"/OC /MC6 BDC" not in cleaned
    assert b"1 0 0 RG" not in cleaned
    assert cleaned == b"q  Q"


def test_soft_mask_colorspace_normalization_is_reused():
    document = FakeSoftMaskDoc()

    changed = (
        normalize_image_soft_mask_colorspaces(
            document
        )
    )

    assert changed == [3]
    assert document.set_calls == [
        (
            3,
            "ColorSpace",
            "/DeviceGray",
        ),
    ]


def base_job():
    return {
        "job_id":
            "sanitized-job",
        "branding_selection": {
            "presence": "ABSENT",
        },
        "builder_v1": {
            "front": {
                "family": "STANDARD",
            },
            "inside_image": {
                "mode": "PORTRAIT",
            },
            "sender_text": {
                "signature_variant_id":
                    "GRIGO",
            },
        },
    }


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        (
            "front",
            "RECIPIENT_BRANDING_OVERLAY",
            "front_family_not_implemented",
        ),
        (
            "image",
            "DEFAULT_ASSET",
            "inside_image_mode_not_implemented",
        ),
        (
            "signature",
            "HERASYMENKO",
            "signature_variant_not_implemented",
        ),
    ],
)
def test_other_first_slice_variants_fail_closed(
    field,
    value,
    match,
):
    job = base_job()

    if field == "front":
        job["builder_v1"]["front"][
            "family"
        ] = value
    elif field == "image":
        job["builder_v1"]["inside_image"][
            "mode"
        ] = value
    else:
        job["builder_v1"]["sender_text"][
            "signature_variant_id"
        ] = value

    with pytest.raises(
        ValueError,
        match=match,
    ):
        _validate_first_slice_job(
            job
        )


def test_post_render_portrait_identity_uses_reference_geometry(tmp_path):
    import pymupdf
    from PIL import Image

    from app.graphic_design_lab.greeting_card_builder_renderer import (
        _page_portrait_soft_mask_evidence,
    )

    background = tmp_path / "background.png"
    portrait = tmp_path / "portrait.png"
    frame = tmp_path / "frame.png"
    pdf_path = tmp_path / "page3.pdf"

    Image.new(
        "RGB",
        (300, 400),
        (245, 245, 240),
    ).save(background)

    Image.new(
        "RGBA",
        (64, 64),
        (30, 60, 90, 160),
    ).save(portrait)

    Image.new(
        "RGBA",
        (300, 400),
        (120, 80, 20, 80),
    ).save(frame)

    document = pymupdf.open()
    page = document.new_page(
        width=200,
        height=260,
    )

    page.insert_image(
        page.rect,
        filename=str(background),
        keep_proportion=False,
    )

    portrait_rect = pymupdf.Rect(
        35,
        45,
        165,
        175,
    )

    page.insert_image(
        portrait_rect,
        filename=str(portrait),
        keep_proportion=False,
        overlay=True,
    )

    page.insert_image(
        pymupdf.Rect(
            5,
            5,
            195,
            255,
        ),
        filename=str(frame),
        keep_proportion=False,
        overlay=True,
    )

    document.save(
        pdf_path,
        garbage=4,
        deflate=True,
        clean=True,
    )
    document.close()

    evidence = _page_portrait_soft_mask_evidence(
        pdf_path,
        page_index=0,
        transparency_required=True,
        expected_pixel_size=[64, 64],
        expected_bbox_pt=[
            35.0,
            45.0,
            165.0,
            175.0,
        ],
    )

    assert evidence["page_image_count"] == 3
    assert evidence["portrait_candidate_count"] == 1
    assert (
        evidence["portrait_identity"]
        == "REFERENCE_PIXEL_SIZE_AND_BBOX"
    )
    assert evidence["soft_mask_xref"] > 0
    assert evidence["soft_mask_colorspace"] == "/DeviceGray"
    assert evidence["soft_mask_valid"] is True


def test_replace_image_preserves_reference_placement(tmp_path):
    import io

    import pymupdf
    from PIL import Image

    first = Image.new(
        "RGBA",
        (80, 80),
        (120, 40, 20, 180),
    )
    first_bytes = io.BytesIO()
    first.save(first_bytes, format="PNG")

    second = Image.new(
        "RGBA",
        (80, 80),
        (20, 70, 140, 128),
    )
    second_bytes = io.BytesIO()
    second.save(second_bytes, format="PNG")

    document = pymupdf.open()
    page = document.new_page(
        width=200,
        height=200,
    )

    xref = int(
        page.insert_image(
            pymupdf.Rect(
                25,
                25,
                175,
                175,
            ),
            stream=first_bytes.getvalue(),
            keep_proportion=False,
        )
    )

    before = [
        tuple(
            round(float(value), 6)
            for value in (
                rect.x0,
                rect.y0,
                rect.x1,
                rect.y1,
            )
        )
        for rect in page.get_image_rects(xref)
    ]

    page.replace_image(
        xref,
        stream=second_bytes.getvalue(),
    )

    after = [
        tuple(
            round(float(value), 6)
            for value in (
                rect.x0,
                rect.y0,
                rect.x1,
                rect.y1,
            )
        )
        for rect in page.get_image_rects(xref)
    ]

    document.close()

    assert before
    assert after == before

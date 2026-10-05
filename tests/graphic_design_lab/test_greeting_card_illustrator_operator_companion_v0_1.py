from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = (
    REPO
    / "scripts"
    / "graphic_design_lab"
    / "greeting_cards"
    / "illustrator_operator_companion_v0_1.jsx"
)


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_operator_companion_script_exists() -> None:
    assert SCRIPT.is_file()


def test_operator_companion_keeps_four_page_layers_and_two_by_two_layout() -> None:
    text = source()
    for name in (
        "01 - Front Cover",
        "02 - Back Cover",
        "03 - Inside Photo",
        "04 - Inside Greeting",
    ):
        assert name in text
    assert "ARTBOARD_LAYOUT=2x2" in text
    assert "GRID_GAP_MM=10" in text


def test_operator_companion_declares_flat_logical_block_model() -> None:
    text = source()
    for name in (
        "01 - Sender Logo",
        "02 - Recipient Branding",
        "03 - Greeting Title",
        "01 - Main Artwork",
        "01 - Photo",
        "01 - Greeting Text",
        "02 - Signature",
        "03 - Decorative Artwork",
        "04 - Ornamental Frame",
        "05 - Background",
        "99 - Technical - Page Clipping Boundary",
    ):
        assert name in text
    assert "LOGICAL_BLOCK_MODEL=FLAT_LOGICAL_BLOCKS_V0_2" in text
    assert "PAGE_CONTENT_WRAPPER_NAME_USED=false" in text


def test_operator_companion_removes_redundant_outer_wrapper_only_when_safe() -> None:
    text = source()
    assert "normalizePageContainer" in text
    assert "isClippedGroup(current)" in text
    assert "REDUNDANT_PAGE_WRAPPERS_REMOVED=" in text
    assert "CLIPPED_CONTAINERS_PRESERVED=" in text
    assert 'setName(pageRoots[p], "Page Content")' not in text


def test_operator_companion_groups_greeting_lines_without_rebuilding_text() -> None:
    text = source()
    assert '"01 - Greeting Text"' in text
    assert "Live text imported from PDF; editable when the required font is available." in text
    assert "FRONT_TITLE_LIVE_TEXT_REGENERATION=false" in text
    assert "GREETING_TEXT_LOGICAL_GROUP=true" in text


def test_operator_companion_preserves_clipping_and_outlined_source_artwork() -> None:
    text = source()
    assert "SOURCE_PDF_MUTATION=false" in text
    assert "IMPORTED_OUTLINED_TEXT_PRESERVED=true" in text
    assert "CLIPPING_GROUPS_PRESERVED=true" in text
    assert "OPERATOR_COMPANION_CANONICAL_PRODUCTION_ARTIFACT=false" in text


def test_operator_companion_keeps_photo_as_one_operator_block() -> None:
    text = source()
    assert '"01 - Photo"' in text
    assert '"Image and Clipping Mask"' in text
    assert "PHOTO_LOGICAL_GROUP=true" in text


def test_operator_companion_classifies_handwritten_signature_separately_from_watermark() -> None:
    text = source()
    assert '"Handwritten Signature"' in text
    assert "geom.centerY > pageHeight * 0.66" in text
    assert "geom.width < pageWidth * 0.42" in text
    assert "geom.height < pageHeight * 0.32" in text
    assert '"03 - Decorative Artwork"' in text


def test_operator_companion_uses_bounded_semantic_grouping_helpers() -> None:
    text = source()
    assert "createLogicalGroup" in text
    assert "collectStaticAndTechnical" in text
    assert "structureFrontCover" in text
    assert "structureBackCover" in text
    assert "structureInsidePhoto" in text
    assert "structureInsideGreeting" in text
def test_operator_companion_contains_no_customer_specific_cyrillic_literals() -> None:
    text = source()

    cyrillic = (
        "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ"
        "абвгґдеєжзиіїйклмнопрстуфхцчшщьюя"
    )

    assert not any(
        ch in text
        for ch in cyrillic
    )


def test_operator_companion_uses_geometry_for_signature_text_split() -> None:
    text = source()

    assert "signatureTextSplitIndex" in text
    assert "pageHeight * 0.55" in text
    assert "pageHeight * 0.72" in text
    assert "Signature Text " in text
    assert "signatureRole" not in text

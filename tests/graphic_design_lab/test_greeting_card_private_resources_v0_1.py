
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

import app.graphic_design_lab.greeting_card_private_resources as resources


def manifest_for(
    path: Path,
    resource_id: str,
):
    return {
        "schema_version": resources.MANIFEST_SCHEMA,
        "resources": {
            resource_id: {
                "path": str(path.resolve()),
            }
        },
    }


def patched_expected(
    resource_id: str,
    *,
    digest: str,
):
    expected = deepcopy(
        resources.EXPECTED_RESOURCES
    )
    expected[resource_id]["sha256"] = digest
    return expected


def test_discovered_v1_resource_fingerprints_are_exact():
    assert (
        resources.EXPECTED_RESOURCES[
            resources.RESOURCE_FRONT_FONT
        ]["sha256"]
        == (
            "a6f6dacb871be365ad93fe1aab09332f"
            "768cd2aa35fdfca8e0053a38f5a2662b"
        )
    )

    assert (
        resources.EXPECTED_RESOURCES[
            resources.RESOURCE_GREETING_FONT
        ]["sha256"]
        == (
            "628f8ed5839ae3e6ab7406d365e275ea"
            "82c563912a92d2e57fb548b6149e9025"
        )
    )

    assert (
        resources.EXPECTED_RESOURCES[
            resources.RESOURCE_REFERENCE_PDF
        ]["sha256"]
        == (
            "66ed88de51ce621fcc0067263e6fc7403"
            "92a1a0e9ee39e88514089451b1f2e85"
        )
    )

    assert (
        resources.EXPECTED_RESOURCES[
            resources.RESOURCE_DEFAULT_FLOWERS
        ]["sha256"]
        == (
            "d9113f8d6f9627f9b106f5550e6187a"
            "aa562139fef6122e4834e7d4f2f3bbd67"
        )
    )


def test_missing_binding_fails_closed():
    with pytest.raises(
        ValueError,
        match="binding_missing",
    ):
        resources.validate_and_resolve_private_resources(
            {
                "schema_version": resources.MANIFEST_SCHEMA,
                "resources": {},
            },
            required_ids=[
                resources.RESOURCE_FRONT_FONT
            ],
        )


def test_relative_path_is_forbidden():
    manifest = {
        "schema_version": resources.MANIFEST_SCHEMA,
        "resources": {
            resources.RESOURCE_DEFAULT_FLOWERS: {
                "path": "relative/flowers.png",
            }
        },
    }

    with pytest.raises(
        ValueError,
        match="path_must_be_absolute",
    ):
        resources.validate_and_resolve_private_resources(
            manifest,
            required_ids=[
                resources.RESOURCE_DEFAULT_FLOWERS
            ],
        )


def test_hash_mismatch_stops_before_font_probe(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "font.ttf"
    path.write_bytes(b"wrong-font-bytes")

    def must_not_probe(_path):
        raise AssertionError(
            "font probe must not run after hash mismatch"
        )

    monkeypatch.setattr(
        resources,
        "_inspect_font",
        must_not_probe,
    )

    with pytest.raises(
        ValueError,
        match="sha256_mismatch",
    ):
        resources.validate_and_resolve_private_resources(
            manifest_for(
                path,
                resources.RESOURCE_FRONT_FONT,
            ),
            required_ids=[
                resources.RESOURCE_FRONT_FONT
            ],
        )


def test_exact_font_identity_and_glyph_gate(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "font.ttf"
    payload = b"sanitized-font-fixture"
    path.write_bytes(payload)
    digest = sha256(payload).hexdigest()

    monkeypatch.setattr(
        resources,
        "EXPECTED_RESOURCES",
        patched_expected(
            resources.RESOURCE_FRONT_FONT,
            digest=digest,
        ),
    )

    required_text = (
        resources.EXPECTED_RESOURCES[
            resources.RESOURCE_FRONT_FONT
        ]["required_text"]
    )

    monkeypatch.setattr(
        resources,
        "_inspect_font",
        lambda _path: {
            "families": ["Monotype Corsiva"],
            "full_names": ["Monotype Corsiva"],
            "versions": ["Version 2.35"],
            "postscript_names": [
                "MonotypeCorsiva"
            ],
            "codepoints": {
                ord(char)
                for char in required_text
                if not char.isspace()
            },
        },
    )

    result = (
        resources.validate_and_resolve_private_resources(
            manifest_for(
                path,
                resources.RESOURCE_FRONT_FONT,
            ),
            required_ids=[
                resources.RESOURCE_FRONT_FONT
            ],
        )
    )

    item = result[
        resources.RESOURCE_FRONT_FONT
    ]

    assert item["status"] == "PASS"
    assert item["required_glyphs"] == "PASS"
    assert item["path"] == path.resolve()

    public = resources.public_resolution_summary(
        result
    )
    assert "path" not in public[
        resources.RESOURCE_FRONT_FONT
    ]


def test_font_identity_mismatch_fails_closed(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "font.ttf"
    payload = b"sanitized-font-fixture"
    path.write_bytes(payload)
    digest = sha256(payload).hexdigest()

    monkeypatch.setattr(
        resources,
        "EXPECTED_RESOURCES",
        patched_expected(
            resources.RESOURCE_FRONT_FONT,
            digest=digest,
        ),
    )

    monkeypatch.setattr(
        resources,
        "_inspect_font",
        lambda _path: {
            "families": ["Wrong Family"],
            "full_names": ["Wrong Family"],
            "versions": ["Version 2.35"],
            "postscript_names": [
                "WrongPostScriptName"
            ],
            "codepoints": set(range(32, 2048)),
        },
    )

    with pytest.raises(
        ValueError,
        match="font_family_mismatch",
    ):
        resources.validate_and_resolve_private_resources(
            manifest_for(
                path,
                resources.RESOURCE_FRONT_FONT,
            ),
            required_ids=[
                resources.RESOURCE_FRONT_FONT
            ],
        )


def test_reference_pdf_requires_four_pages(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "reference.pdf"
    payload = b"sanitized-pdf-fixture"
    path.write_bytes(payload)
    digest = sha256(payload).hexdigest()

    monkeypatch.setattr(
        resources,
        "EXPECTED_RESOURCES",
        patched_expected(
            resources.RESOURCE_REFERENCE_PDF,
            digest=digest,
        ),
    )

    monkeypatch.setattr(
        resources,
        "_inspect_pdf",
        lambda _path: {
            "page_count": 1,
            "page_sizes_pt": [
                (1254.0, 1254.0)
            ],
        },
    )

    with pytest.raises(
        ValueError,
        match="page_count_mismatch",
    ):
        resources.validate_and_resolve_private_resources(
            manifest_for(
                path,
                resources.RESOURCE_REFERENCE_PDF,
            ),
            required_ids=[
                resources.RESOURCE_REFERENCE_PDF
            ],
        )


def test_unknown_resource_id_is_rejected():
    with pytest.raises(
        ValueError,
        match="unknown_resource_id",
    ):
        resources.validate_and_resolve_private_resources(
            {
                "schema_version": resources.MANIFEST_SCHEMA,
                "resources": {
                    "unknown.resource": {
                        "path": "/tmp/nope",
                    }
                },
            },
            required_ids=[],
        )

def test_signature_source_pdf_fingerprints_are_exact():
    assert (
        resources.EXPECTED_RESOURCES[
            resources.RESOURCE_SIGNATURE_HERASYMENKO
        ]["sha256"]
        == "a5392be1234c026d1200cad288a3b4989f506f8eb32522dcbe6236bb221722a8"
    )

    assert (
        resources.EXPECTED_RESOURCES[
            resources.RESOURCE_SIGNATURE_HERASYMENKO
        ]["page_count"]
        == 4
    )

    assert (
        resources.EXPECTED_RESOURCES[
            resources.RESOURCE_SIGNATURE_DUAL
        ]["sha256"]
        == "2cdff2f2c9a243c2189067675a9f093c0807df30ccae0f57eecc4003b271130c"
    )

    assert (
        resources.EXPECTED_RESOURCES[
            resources.RESOURCE_SIGNATURE_DUAL
        ]["page_count"]
        == 4
    )

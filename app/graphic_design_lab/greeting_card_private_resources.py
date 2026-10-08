
from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import pymupdf
from fontTools.ttLib import TTFont


MANIFEST_SCHEMA = (
    "gdl_greeting_card_private_resource_manifest_v0_1"
)

RESOURCE_FRONT_FONT = (
    "font.front_occasion.monotype_corsiva.v1"
)
RESOURCE_GREETING_FONT = (
    "font.greeting_sender.zapf_chancery_c.v1"
)
RESOURCE_REFERENCE_PDF = (
    "template.greeting_card.dolinska.v1"
)
RESOURCE_DEFAULT_FLOWERS = (
    "asset.flowers.default.v1"
)

REQUIRED_UKRAINIAN_TEXT = (
    "Привітання з нагоди Дня Народження!"
    "Привітання з Ювілеєм!"
    "З найщирішими побажаннями"
    "ІЇЄҐіїєґ"
)

EXPECTED_RESOURCES: dict[str, dict[str, Any]] = {
    RESOURCE_FRONT_FONT: {
        "kind": "font",
        "sha256": (
            "a6f6dacb871be365ad93fe1aab09332f"
            "768cd2aa35fdfca8e0053a38f5a2662b"
        ),
        "family": "Monotype Corsiva",
        "postscript_name": "MonotypeCorsiva",
        "version": "Version 2.35",
        "required_text": REQUIRED_UKRAINIAN_TEXT,
    },
    RESOURCE_GREETING_FONT: {
        "kind": "font",
        "sha256": (
            "628f8ed5839ae3e6ab7406d365e275ea"
            "82c563912a92d2e57fb548b6149e9025"
        ),
        "family": "ZapfChanceryC",
        "postscript_name": "ZapfChanceryC",
        "required_text": REQUIRED_UKRAINIAN_TEXT,
    },
    RESOURCE_REFERENCE_PDF: {
        "kind": "pdf",
        "sha256": (
            "66ed88de51ce621fcc0067263e6fc7403"
            "92a1a0e9ee39e88514089451b1f2e85"
        ),
        "page_count": 4,
    },
    RESOURCE_DEFAULT_FLOWERS: {
        "kind": "image",
        "sha256": (
            "d9113f8d6f9627f9b106f5550e6187a"
            "aa562139fef6122e4834e7d4f2f3bbd67"
        ),
    },
}

DEFAULT_REQUIRED_RESOURCE_IDS = tuple(EXPECTED_RESOURCES.keys())


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(
            lambda: stream.read(1024 * 1024),
            b"",
        ):
            digest.update(block)
    return digest.hexdigest()


def _font_names(
    font: TTFont,
    *,
    name_ids: set[int],
) -> dict[int, set[str]]:
    names: dict[int, set[str]] = {}
    for record in font["name"].names:
        if record.nameID not in name_ids:
            continue
        try:
            value = record.toUnicode().strip()
        except Exception:
            continue
        if value:
            names.setdefault(record.nameID, set()).add(value)
    return names


def _inspect_font(path: Path) -> dict[str, Any]:
    font = TTFont(path, lazy=True)
    try:
        names = _font_names(
            font,
            name_ids={1, 4, 5, 6, 16},
        )
        cmap: set[int] = set()
        for table in font["cmap"].tables:
            cmap.update(table.cmap.keys())

        return {
            "families": sorted(
                names.get(1, set())
                | names.get(16, set())
            ),
            "full_names": sorted(names.get(4, set())),
            "versions": sorted(names.get(5, set())),
            "postscript_names": sorted(names.get(6, set())),
            "codepoints": cmap,
        }
    finally:
        font.close()


def _inspect_pdf(path: Path) -> dict[str, Any]:
    with pymupdf.open(path) as document:
        return {
            "page_count": document.page_count,
            "page_sizes_pt": [
                (
                    round(page.rect.width, 3),
                    round(page.rect.height, 3),
                )
                for page in document
            ],
        }


def _manifest_resources(
    manifest: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    data = _mapping(manifest)

    if data.get("schema_version") != MANIFEST_SCHEMA:
        errors.append("manifest.schema_version:unsupported")

    resources = _mapping(data.get("resources"))

    for resource_id in sorted(
        set(resources) - set(EXPECTED_RESOURCES)
    ):
        errors.append(
            f"{resource_id}:unknown_resource_id"
        )

    return resources, errors


def validate_and_resolve_private_resources(
    manifest: Mapping[str, Any],
    *,
    required_ids: Iterable[str] | None = None,
) -> dict[str, dict[str, Any]]:
    resources, errors = _manifest_resources(manifest)

    requested = (
        list(DEFAULT_REQUIRED_RESOURCE_IDS)
        if required_ids is None
        else list(required_ids)
    )

    for resource_id in requested:
        if resource_id not in EXPECTED_RESOURCES:
            errors.append(
                f"{resource_id}:unknown_required_resource_id"
            )

    resolved: dict[str, dict[str, Any]] = {}

    for resource_id in requested:
        expected = EXPECTED_RESOURCES.get(resource_id)
        if expected is None:
            continue

        binding = _mapping(resources.get(resource_id))
        if not binding:
            errors.append(
                f"{resource_id}:binding_missing"
            )
            continue

        raw_path = binding.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            errors.append(
                f"{resource_id}:path_required"
            )
            continue

        path = Path(raw_path)
        if not path.is_absolute():
            errors.append(
                f"{resource_id}:path_must_be_absolute"
            )
            continue

        if not path.is_file():
            errors.append(
                f"{resource_id}:file_missing"
            )
            continue

        actual_sha256 = sha256_file(path)
        if actual_sha256 != expected["sha256"]:
            errors.append(
                f"{resource_id}:sha256_mismatch"
            )
            continue

        report: dict[str, Any] = {
            "resource_id": resource_id,
            "kind": expected["kind"],
            "sha256": actual_sha256,
            "status": "PASS",
            # Runtime-only absolute path. It is intentionally absent from
            # tracked contracts and must be redacted from operator reports.
            "path": path.resolve(),
        }

        if expected["kind"] == "font":
            font_info = _inspect_font(path)
            families = set(font_info["families"])
            postscript_names = set(
                font_info["postscript_names"]
            )
            versions = set(font_info["versions"])

            if expected["family"] not in families:
                errors.append(
                    f"{resource_id}:font_family_mismatch"
                )

            if (
                expected["postscript_name"]
                not in postscript_names
            ):
                errors.append(
                    f"{resource_id}:postscript_name_mismatch"
                )

            expected_version = expected.get("version")
            if (
                expected_version is not None
                and expected_version not in versions
            ):
                errors.append(
                    f"{resource_id}:font_version_mismatch"
                )

            codepoints = set(font_info["codepoints"])
            missing = sorted(
                {
                    ord(char)
                    for char in expected["required_text"]
                    if (
                        not char.isspace()
                        and ord(char) not in codepoints
                    )
                }
            )

            if missing:
                errors.append(
                    f"{resource_id}:required_glyphs_missing"
                )

            report.update(
                {
                    "font_family": expected["family"],
                    "postscript_name": (
                        expected["postscript_name"]
                    ),
                    "required_glyphs": (
                        "PASS" if not missing else "FAIL"
                    ),
                }
            )

        elif expected["kind"] == "pdf":
            pdf_info = _inspect_pdf(path)

            if (
                pdf_info["page_count"]
                != expected["page_count"]
            ):
                errors.append(
                    f"{resource_id}:page_count_mismatch"
                )

            report.update(
                {
                    "page_count": pdf_info["page_count"],
                    "page_sizes_pt": (
                        pdf_info["page_sizes_pt"]
                    ),
                }
            )

        resolved[resource_id] = report

    if errors:
        raise ValueError(
            "private_resource_validation_failed:"
            + ";".join(errors)
        )

    return resolved


def public_resolution_summary(
    resolved: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Return a path-redacted summary suitable for logs and reports."""
    summary: dict[str, dict[str, Any]] = {}

    for resource_id, raw_item in resolved.items():
        item = _mapping(raw_item)
        item.pop("path", None)
        summary[resource_id] = item

    return summary

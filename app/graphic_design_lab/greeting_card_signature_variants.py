from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

CATALOG_SCHEMA = "gdl_greeting_card_signature_variant_catalog_v0_1"
COUPLED_OBJECT_IDS = (
    "inside_text.sender_block",
    "inside_text.signature",
)


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def validate_signature_variant_catalog(
    catalog: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []

    if not isinstance(catalog, Mapping):
        return ["signature_catalog:must_be_mapping"]

    if catalog.get("schema_version") != CATALOG_SCHEMA:
        errors.append("signature_catalog.schema_version:unsupported")

    if catalog.get("extensibility") != "OPEN_CATALOG":
        errors.append(
            "signature_catalog.extensibility:must_be_OPEN_CATALOG"
        )

    variants = _list(catalog.get("variants"))
    if not variants:
        errors.append(
            "signature_catalog.variants:must_be_nonempty_list"
        )
        return errors

    seen_ids: set[str] = set()

    for index, raw in enumerate(variants):
        prefix = f"signature_catalog.variants[{index}]"
        item = _mapping(raw)

        variant_id = item.get("variant_id")
        sender_variant = item.get("sender_variant")
        component_count = item.get("signature_component_count")
        coupled = tuple(_list(item.get("coupled_object_ids")))

        if not isinstance(variant_id, str) or not variant_id:
            errors.append(f"{prefix}.variant_id:required")
        elif variant_id in seen_ids:
            errors.append(f"{prefix}.variant_id:duplicate")
        else:
            seen_ids.add(variant_id)

        # sender_variant is layout semantics, not signatory identity.
        # Future catalog rows may reuse the same layout variant.
        if not isinstance(sender_variant, str) or not sender_variant:
            errors.append(f"{prefix}.sender_variant:required")

        if (
            not isinstance(component_count, int)
            or isinstance(component_count, bool)
            or component_count < 1
        ):
            errors.append(
                f"{prefix}.signature_component_count:invalid"
            )

        if coupled != COUPLED_OBJECT_IDS:
            errors.append(
                f"{prefix}.coupled_object_ids:"
                "must_match_sender_block_and_signature"
            )

    return errors


def resolve_signature_configuration(
    catalog: Mapping[str, Any],
    *,
    variant_id: str,
    sender_variant: str | None = None,
) -> dict[str, Any]:
    errors = validate_signature_variant_catalog(catalog)
    if errors:
        raise ValueError(
            "invalid_signature_catalog:" + ";".join(errors)
        )

    matches = [
        _mapping(item)
        for item in _list(catalog.get("variants"))
        if _mapping(item).get("variant_id") == variant_id
    ]

    if len(matches) != 1:
        raise ValueError(
            "signature_configuration_missing_for_variant_id:"
            + variant_id
        )

    selected = deepcopy(matches[0])

    if (
        sender_variant is not None
        and selected.get("sender_variant") != sender_variant
    ):
        raise ValueError(
            "signature_sender_variant_mismatch:"
            f"{variant_id}:{sender_variant}"
        )

    return selected

"""Deterministic validation helpers for Graphic Design Lab contracts.

All physical paths are supplied by the caller. This module contains no storage
backend selection and no rendering/provider logic.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _require(mapping: Mapping[str, Any], keys: list[str], prefix: str, errors: list[str]) -> None:
    for key in keys:
        if key not in mapping:
            errors.append(f"{prefix}.missing:{key}")


def _positive_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def validate_product_profile(profile: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    _require(
        profile,
        ["schema_version", "product_profile_id", "product_type", "physical_defaults", "layout_rules", "constraints"],
        "profile",
        errors,
    )
    physical = profile.get("physical_defaults")
    if isinstance(physical, Mapping):
        _require(physical, ["units", "page_width_mm", "page_height_mm", "orientation"], "profile.physical_defaults", errors)
        if physical.get("units") != "mm":
            errors.append("profile.physical_defaults.units:must_be_mm")
        for key in ("page_width_mm", "page_height_mm"):
            if not _positive_number(physical.get(key)):
                errors.append(f"profile.physical_defaults.{key}:must_be_positive")
    elif "physical_defaults" in profile:
        errors.append("profile.physical_defaults:must_be_mapping")

    palette = profile.get("month_colors_cmyk", {})
    if palette:
        if not isinstance(palette, Mapping):
            errors.append("profile.month_colors_cmyk:must_be_mapping")
        else:
            for month, cmyk in palette.items():
                if not isinstance(cmyk, list) or len(cmyk) != 4:
                    errors.append(f"profile.month_colors_cmyk.{month}:must_be_four_components")
                    continue
                if any(not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0 or v > 100 for v in cmyk):
                    errors.append(f"profile.month_colors_cmyk.{month}:component_out_of_range")
    return errors


def validate_design_spec(
    spec: Mapping[str, Any],
    design_contract: Mapping[str, Any],
    product_profile: Mapping[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []

    _require(spec, list(design_contract.get("required_top_level", [])), "spec", errors)

    if spec.get("schema_version") != design_contract.get("spec_schema_version"):
        errors.append("spec.schema_version:unsupported")

    document = spec.get("document")
    if not isinstance(document, Mapping):
        errors.append("spec.document:must_be_mapping")
        return errors

    _require(document, list(design_contract.get("document", {}).get("required", [])), "spec.document", errors)
    if document.get("units") != "mm":
        errors.append("spec.document.units:must_be_mm")

    page = document.get("page")
    if isinstance(page, Mapping):
        page_rules = design_contract.get("document", {}).get("page", {})
        _require(page, list(page_rules.get("required", [])), "spec.document.page", errors)
        for key in page_rules.get("positive_numeric", []):
            if not _positive_number(page.get(key)):
                errors.append(f"spec.document.page.{key}:must_be_positive")
        if page.get("orientation") not in page_rules.get("orientation_allowed", []):
            errors.append("spec.document.page.orientation:unsupported")
    else:
        errors.append("spec.document.page:must_be_mapping")

    binding = document.get("binding")
    if isinstance(binding, Mapping):
        _require(binding, ["type"], "spec.document.binding", errors)
        if binding.get("type") not in design_contract.get("document", {}).get("binding", {}).get("allowed_types", []):
            errors.append("spec.document.binding.type:unsupported")
    else:
        errors.append("spec.document.binding:must_be_mapping")

    spreads = spec.get("spreads")
    if not isinstance(spreads, list) or not spreads:
        errors.append("spec.spreads:must_be_nonempty_list")
        return errors

    supported_types = set(design_contract.get("object", {}).get("supported_types", []))
    spread_kinds = set(design_contract.get("spread", {}).get("kinds", []))
    seen_spread_ids: set[str] = set()
    seen_object_ids: set[str] = set()

    for sidx, spread in enumerate(spreads):
        prefix = f"spec.spreads[{sidx}]"
        if not isinstance(spread, Mapping):
            errors.append(f"{prefix}:must_be_mapping")
            continue
        _require(spread, ["id", "kind", "objects"], prefix, errors)
        spread_id = spread.get("id")
        if not isinstance(spread_id, str) or not spread_id:
            errors.append(f"{prefix}.id:must_be_nonempty_string")
        elif spread_id in seen_spread_ids:
            errors.append(f"{prefix}.id:duplicate")
        else:
            seen_spread_ids.add(spread_id)

        if spread.get("kind") not in spread_kinds:
            errors.append(f"{prefix}.kind:unsupported")

        objects = spread.get("objects")
        if not isinstance(objects, list):
            errors.append(f"{prefix}.objects:must_be_list")
            continue

        for oidx, obj in enumerate(objects):
            oprefix = f"{prefix}.objects[{oidx}]"
            if not isinstance(obj, Mapping):
                errors.append(f"{oprefix}:must_be_mapping")
                continue
            _require(obj, ["id", "type"], oprefix, errors)
            object_id = obj.get("id")
            if not isinstance(object_id, str) or not object_id:
                errors.append(f"{oprefix}.id:must_be_nonempty_string")
            elif object_id in seen_object_ids:
                errors.append(f"{oprefix}.id:duplicate")
            else:
                seen_object_ids.add(object_id)

            if obj.get("type") not in supported_types:
                errors.append(f"{oprefix}.type:unsupported")

    output_intent = spec.get("output_intent")
    if isinstance(output_intent, Mapping):
        out_rules = design_contract.get("output_intent", {})
        _require(output_intent, list(out_rules.get("required", [])), "spec.output_intent", errors)
        if output_intent.get("editable_interchange") not in out_rules.get("editable_interchange_allowed", []):
            errors.append("spec.output_intent.editable_interchange:unsupported")
        if output_intent.get("preview_output") not in out_rules.get("preview_output_allowed", []):
            errors.append("spec.output_intent.preview_output:unsupported")
        if output_intent.get("review_output") not in out_rules.get("review_output_allowed", []):
            errors.append("spec.output_intent.review_output:unsupported")
    else:
        errors.append("spec.output_intent:must_be_mapping")

    if product_profile:
        profile_errors = validate_product_profile(product_profile)
        errors.extend(f"profile:{error}" for error in profile_errors)

        physical = product_profile.get("physical_defaults", {})
        if isinstance(page, Mapping) and isinstance(physical, Mapping):
            if page.get("width_mm") != physical.get("page_width_mm"):
                errors.append("spec.document.page.width_mm:profile_mismatch")
            if page.get("height_mm") != physical.get("page_height_mm"):
                errors.append("spec.document.page.height_mm:profile_mismatch")
            if page.get("orientation") != physical.get("orientation"):
                errors.append("spec.document.page.orientation:profile_mismatch")

        if spec.get("product_type") != product_profile.get("product_type"):
            errors.append("spec.product_type:profile_mismatch")

    return errors

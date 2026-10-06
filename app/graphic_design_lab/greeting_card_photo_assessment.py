from __future__ import annotations

from collections.abc import Mapping
from typing import Any

ASSESSMENT_SCHEMA = "gdl_greeting_card_photo_assessment_package_v0_1"
ASSESSMENT_STATES = {
    "PASS_THROUGH",
    "DETERMINISTIC_TEMPLATE_NORMALIZATION",
    "CREATOR_TRANSFORMATION_REQUIRED",
    "HUMAN_REVIEW_REQUIRED",
}
BINDING_STATES = {"CONFIRMED", "PROPOSED", "UNRESOLVED"}
DETERMINISTIC_OPERATIONS = {
    "normalize_orientation",
    "crop_to_canonical_frame",
    "scale_without_content_synthesis",
    "apply_template_mask",
    "resolution_check",
}
CREATOR_OPERATIONS = {
    "recover_detail",
    "normalize_contrast",
    "normalize_natural_skin_color",
    "remove_background",
    "cleanup",
    "tonal_repair",
    "sharpness_or_quality_recovery",
    "canvas_extension",
}
DIRECTED_APPEARANCE_EDITS = {
    "skin_smoothing",
    "face_reshaping",
    "age_change",
    "body_reshaping",
    "beautification",
}
CREATOR_OUTPUT_TYPES = {"NORMALIZED_PORTRAIT_ASSET", "RESTORED_RASTER_ASSET"}
REQUIRED_FORBIDDEN_CHANGES = {
    "document_geometry",
    "canonical_page_mapping",
    "locked_back_page",
    "canonical_text_slots",
    "canonical_z_order",
    "production_export_rules",
    "greeting_text",
    "recipient_identity",
}


def _has_confidence(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            "confidence" in str(key).lower() or _has_confidence(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_has_confidence(item) for item in value)
    return False


def _require_mapping(errors: list[str], value: Any, prefix: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        errors.append(f"{prefix}:must_be_mapping")
        return {}
    return dict(value)


def _require_list(errors: list[str], value: Any, prefix: str) -> list[Any]:
    if not isinstance(value, list):
        errors.append(f"{prefix}:must_be_list")
        return []
    return value


def _validate_creator_task(
    task: Mapping[str, Any],
    *,
    assessment: Mapping[str, Any],
    source_assets: Mapping[str, Mapping[str, Any]],
    prefix: str,
) -> list[str]:
    errors: list[str] = []
    required = {
        "task_id",
        "job_id",
        "assessment_id",
        "source_asset",
        "target_role",
        "requested_operations",
        "directed_appearance_edits",
        "explicit_appearance_request_ref",
        "preservation",
        "forbidden_changes",
        "output",
        "traceability",
        "creator_execution_authorized",
        "provider_execution_required",
    }
    missing = sorted(required.difference(task))
    errors.extend(f"{prefix}.{field}:missing" for field in missing)

    if task.get("job_id") != assessment.get("job_id"):
        errors.append(f"{prefix}.job_id:mismatch")
    if task.get("assessment_id") != assessment.get("assessment_id"):
        errors.append(f"{prefix}.assessment_id:mismatch")
    if task.get("target_role") != "inside_image.portrait":
        errors.append(f"{prefix}.target_role:must_be_inside_image_portrait")
    if task.get("creator_execution_authorized") is not False:
        errors.append(f"{prefix}.creator_execution_authorized:must_be_false")
    if task.get("provider_execution_required") is not False:
        errors.append(f"{prefix}.provider_execution_required:must_be_false")

    source = _require_mapping(errors, task.get("source_asset"), f"{prefix}.source_asset")
    source_id = source.get("asset_id")
    if source_id != assessment.get("asset_id"):
        errors.append(f"{prefix}.source_asset.asset_id:assessment_mismatch")
    if source_id not in source_assets:
        errors.append(f"{prefix}.source_asset.asset_id:unknown")
    elif source.get("source_ref") != source_assets[source_id].get("source_ref"):
        errors.append(f"{prefix}.source_asset.source_ref:inventory_mismatch")

    operations = _require_list(errors, task.get("requested_operations"), f"{prefix}.requested_operations")
    if not operations:
        errors.append(f"{prefix}.requested_operations:must_not_be_empty")
    unknown_ops = sorted(set(operations).difference(CREATOR_OPERATIONS))
    errors.extend(f"{prefix}.requested_operations:unsupported:{op}" for op in unknown_ops)

    directed = _require_list(
        errors,
        task.get("directed_appearance_edits"),
        f"{prefix}.directed_appearance_edits",
    )
    unknown_directed = sorted(set(directed).difference(DIRECTED_APPEARANCE_EDITS))
    errors.extend(f"{prefix}.directed_appearance_edits:unsupported:{op}" for op in unknown_directed)
    explicit_ref = task.get("explicit_appearance_request_ref")
    if directed and (not isinstance(explicit_ref, str) or not explicit_ref.strip()):
        errors.append(f"{prefix}.directed_appearance_edits:explicit_request_required")
    if not directed and explicit_ref not in (None, ""):
        errors.append(f"{prefix}.explicit_appearance_request_ref:must_be_null_without_edits")

    preservation = _require_mapping(errors, task.get("preservation"), f"{prefix}.preservation")
    if preservation.get("likeness") != "REQUIRED":
        errors.append(f"{prefix}.preservation.likeness:must_be_REQUIRED")
    if preservation.get("realistic_appearance") != "REQUIRED":
        errors.append(f"{prefix}.preservation.realistic_appearance:must_be_REQUIRED")
    if preservation.get("identity_change") != "FORBIDDEN":
        errors.append(f"{prefix}.preservation.identity_change:must_be_FORBIDDEN")

    forbidden = set(_require_list(errors, task.get("forbidden_changes"), f"{prefix}.forbidden_changes"))
    missing_forbidden = sorted(REQUIRED_FORBIDDEN_CHANGES.difference(forbidden))
    errors.extend(f"{prefix}.forbidden_changes:missing:{item}" for item in missing_forbidden)

    output = _require_mapping(errors, task.get("output"), f"{prefix}.output")
    if output.get("output_type") not in CREATOR_OUTPUT_TYPES:
        errors.append(f"{prefix}.output.output_type:unsupported")
    if output.get("return_asset_must_trace_to_source") is not True:
        errors.append(f"{prefix}.output.return_asset_must_trace_to_source:must_be_true")
    if output.get("heavy_artifact_in_git") is not False:
        errors.append(f"{prefix}.output.heavy_artifact_in_git:must_be_false")

    traceability = _require_mapping(errors, task.get("traceability"), f"{prefix}.traceability")
    if traceability.get("job_id") != assessment.get("job_id"):
        errors.append(f"{prefix}.traceability.job_id:mismatch")
    if traceability.get("assessment_id") != assessment.get("assessment_id"):
        errors.append(f"{prefix}.traceability.assessment_id:mismatch")
    if traceability.get("source_asset_id") != assessment.get("asset_id"):
        errors.append(f"{prefix}.traceability.source_asset_id:mismatch")

    return errors


def validate_photo_assessment_package(package: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(package, Mapping):
        return ["package:must_be_mapping"]
    if package.get("schema_version") != ASSESSMENT_SCHEMA:
        errors.append("package.schema_version:unsupported")
    if _has_confidence(package):
        errors.append("package:numeric_or_named_confidence_forbidden")
    if package.get("creator_execution_authorized") is not False:
        errors.append("package.creator_execution_authorized:must_be_false")
    if package.get("provider_execution_required") is not False:
        errors.append("package.provider_execution_required:must_be_false")

    inventory = _require_list(errors, package.get("source_inventory"), "package.source_inventory")
    source_assets: dict[str, Mapping[str, Any]] = {}
    for index, raw in enumerate(inventory):
        item = _require_mapping(errors, raw, f"package.source_inventory[{index}]")
        asset_id = item.get("asset_id")
        if not isinstance(asset_id, str) or not asset_id:
            errors.append(f"package.source_inventory[{index}].asset_id:required")
            continue
        if asset_id in source_assets:
            errors.append(f"package.source_inventory[{index}].asset_id:duplicate")
        source_assets[asset_id] = item
        if not isinstance(item.get("source_ref"), str) or not item.get("source_ref"):
            errors.append(f"package.source_inventory[{index}].source_ref:required")

    assessments = _require_list(errors, package.get("assessments"), "package.assessments")
    if not assessments:
        errors.append("package.assessments:must_be_nonempty")

    seen_ids: set[str] = set()
    for index, raw in enumerate(assessments):
        prefix = f"package.assessments[{index}]"
        item = _require_mapping(errors, raw, prefix)
        assessment_id = item.get("assessment_id")
        if not isinstance(assessment_id, str) or not assessment_id:
            errors.append(f"{prefix}.assessment_id:required")
        elif assessment_id in seen_ids:
            errors.append(f"{prefix}.assessment_id:duplicate")
        else:
            seen_ids.add(assessment_id)

        for field in ("job_id", "asset_id", "portrait_binding_state", "assessment_state"):
            if not isinstance(item.get(field), str) or not item.get(field):
                errors.append(f"{prefix}.{field}:required")

        asset_id = item.get("asset_id")
        if asset_id not in source_assets:
            errors.append(f"{prefix}.asset_id:unknown")

        binding_state = item.get("portrait_binding_state")
        state = item.get("assessment_state")
        if binding_state not in BINDING_STATES:
            errors.append(f"{prefix}.portrait_binding_state:unsupported")
        if state not in ASSESSMENT_STATES:
            errors.append(f"{prefix}.assessment_state:unsupported")

        human = item.get("human_confirmation_required")
        if not isinstance(human, bool):
            errors.append(f"{prefix}.human_confirmation_required:must_be_boolean")

        deterministic = _require_list(
            errors,
            item.get("deterministic_operations"),
            f"{prefix}.deterministic_operations",
        )
        creator_ops = _require_list(
            errors,
            item.get("creator_operations"),
            f"{prefix}.creator_operations",
        )
        unknown_deterministic = sorted(set(deterministic).difference(DETERMINISTIC_OPERATIONS))
        errors.extend(f"{prefix}.deterministic_operations:unsupported:{op}" for op in unknown_deterministic)
        unknown_creator = sorted(set(creator_ops).difference(CREATOR_OPERATIONS))
        errors.extend(f"{prefix}.creator_operations:unsupported:{op}" for op in unknown_creator)

        task = item.get("creator_task")
        if binding_state in {"PROPOSED", "UNRESOLVED"}:
            if state != "HUMAN_REVIEW_REQUIRED":
                errors.append(f"{prefix}:ambiguous_binding_requires_human_review")
            if human is not True:
                errors.append(f"{prefix}:ambiguous_binding_requires_confirmation")
            if task is not None:
                errors.append(f"{prefix}:ambiguous_binding_forbids_creator_task")

        if state == "PASS_THROUGH":
            if deterministic or creator_ops:
                errors.append(f"{prefix}:pass_through_forbids_operations")
            if task is not None:
                errors.append(f"{prefix}:pass_through_forbids_creator_task")
            if human is not False:
                errors.append(f"{prefix}:pass_through_must_not_require_confirmation")

        elif state == "DETERMINISTIC_TEMPLATE_NORMALIZATION":
            if not deterministic:
                errors.append(f"{prefix}:deterministic_state_requires_operations")
            if creator_ops:
                errors.append(f"{prefix}:deterministic_state_forbids_creator_operations")
            if task is not None:
                errors.append(f"{prefix}:deterministic_state_forbids_creator_task")
            if binding_state != "CONFIRMED":
                errors.append(f"{prefix}:deterministic_state_requires_confirmed_binding")
            if human is not False:
                errors.append(f"{prefix}:deterministic_state_must_not_require_confirmation")

        elif state == "CREATOR_TRANSFORMATION_REQUIRED":
            if binding_state != "CONFIRMED":
                errors.append(f"{prefix}:creator_state_requires_confirmed_binding")
            if deterministic:
                errors.append(f"{prefix}:creator_state_forbids_template_operations")
            if not creator_ops:
                errors.append(f"{prefix}:creator_state_requires_operations")
            if not isinstance(task, Mapping):
                errors.append(f"{prefix}:creator_state_requires_task")
            else:
                errors.extend(
                    _validate_creator_task(
                        task,
                        assessment=item,
                        source_assets=source_assets,
                        prefix=f"{prefix}.creator_task",
                    )
                )
            if human is not False:
                errors.append(f"{prefix}:creator_state_must_not_require_confirmation")

        elif state == "HUMAN_REVIEW_REQUIRED":
            if task is not None:
                errors.append(f"{prefix}:human_review_forbids_creator_task")
            if human is not True:
                errors.append(f"{prefix}:human_review_requires_confirmation")

    return errors

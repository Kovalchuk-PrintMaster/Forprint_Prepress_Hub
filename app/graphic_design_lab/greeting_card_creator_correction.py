from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

CORRECTION_SCHEMA = "gdl_greeting_card_creator_correction_v0_1"
CYCLE_SCHEMA = "gdl_greeting_card_creator_correction_cycle_v0_1"

CANONICAL_TARGET_OBJECT_ID = "inside_image.portrait"
CANONICAL_TARGET_ROLE = "inside_image.portrait"
CANONICAL_PATCH_OPERATION = "REPLACE_CONTENT"

REQUIRED_AUTHORITY_FALSE = (
    "provider_execution_performed",
    "gdl_runtime_initialized",
    "production_write_enabled",
    "automatic_customer_messaging",
    "automatic_design_approval",
)


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _has_confidence(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            "confidence" in str(key).lower() or _has_confidence(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_has_confidence(item) for item in value)
    return False


def _failed_checks(review_record: Mapping[str, Any]) -> list[str]:
    checks = _mapping(review_record.get("portrait_checks"))
    return sorted(
        check_id
        for check_id, state in checks.items()
        if state == "FAIL"
    )


def _task_trace(creator_task: Mapping[str, Any]) -> dict[str, Any]:
    source = _mapping(creator_task.get("source_asset"))
    return {
        "task_id": creator_task.get("task_id"),
        "job_id": creator_task.get("job_id"),
        "assessment_id": creator_task.get("assessment_id"),
        "source_asset_id": source.get("asset_id"),
    }


def compile_creator_correction_patch(
    failed_review: Mapping[str, Any],
    creator_task: Mapping[str, Any],
    revision_contract: Mapping[str, Any],
    *,
    revision_id: str,
    parent_revision_id: str,
) -> dict[str, Any]:
    review = deepcopy(dict(failed_review))
    task = deepcopy(dict(creator_task))

    if review.get("outcome") != "FAIL":
        raise ValueError("failed_review_outcome_must_be_FAIL")
    if review.get("correction_required") is not True:
        raise ValueError("failed_review_must_require_correction")
    if review.get("accepted_for_constructor_bundle") is not False:
        raise ValueError("failed_review_must_not_be_accepted")

    failed_checks = _failed_checks(review)
    if not failed_checks:
        raise ValueError("failed_review_requires_at_least_one_failed_check")

    if task.get("target_role") != CANONICAL_TARGET_ROLE:
        raise ValueError("creator_task_target_role_must_be_inside_image_portrait")

    requested_operations = list(_list(task.get("requested_operations")))
    forbidden_changes = list(_list(task.get("forbidden_changes")))
    trace = _task_trace(task)

    patch = {
        "schema_version": CORRECTION_SCHEMA,
        "revision_contract_ref": (
            "contracts/graphic_design_lab/revision_patch_v0_1.yaml"
        ),
        "revision_id": revision_id,
        "parent_revision_id": parent_revision_id,
        "change_request": {
            "type": "BOUNDED_CREATOR_CORRECTION",
            "failed_review_id": review.get("review_id"),
            "failed_checks": failed_checks,
            "instruction": (
                "Correct only the failed bounded portrait review checks and "
                "preserve all original Creator task boundaries."
            ),
        },
        "patches": [
            {
                "patch_id": f"{revision_id}__portrait_replace_content",
                "operation": CANONICAL_PATCH_OPERATION,
                "target_object_id": CANONICAL_TARGET_OBJECT_ID,
                "path": "accepted_visual_asset",
                "before": "FAILED_CREATOR_RESULT_REVISION",
                "after": "CORRECTED_CREATOR_RESULT_REVISION_REQUIRED",
                "reason": ",".join(failed_checks),
            }
        ],
        "human_review_state": "review_requested",
        "creator_scope": {
            "target_role": task.get("target_role"),
            "requested_operations": requested_operations,
            "forbidden_changes": forbidden_changes,
            "scope_expansion": False,
            "full_regeneration": False,
        },
        "traceability": trace,
        "authority": {
            "provider_execution_performed": False,
            "gdl_runtime_initialized": False,
            "production_write_enabled": False,
            "automatic_customer_messaging": False,
            "automatic_design_approval": False,
        },
    }

    errors = validate_creator_correction_patch(
        patch,
        creator_task=task,
        revision_contract=revision_contract,
    )
    if errors:
        raise ValueError("invalid_compiled_correction:" + ";".join(errors))

    return patch


def validate_creator_correction_patch(
    patch: Mapping[str, Any],
    *,
    creator_task: Mapping[str, Any],
    revision_contract: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    if not isinstance(patch, Mapping):
        return ["correction:must_be_mapping"]

    if patch.get("schema_version") != CORRECTION_SCHEMA:
        errors.append("correction.schema_version:unsupported")
    if _has_confidence(patch):
        errors.append("correction:numeric_or_named_confidence_forbidden")

    revision_rules = _mapping(revision_contract.get("revision"))
    required_revision = set(_list(revision_rules.get("required")))
    missing = sorted(required_revision.difference(patch))
    errors.extend(
        f"correction.{field}:missing"
        for field in missing
    )

    for field in ("revision_id", "parent_revision_id"):
        value = patch.get(field)
        if not isinstance(value, str) or not value:
            errors.append(f"correction.{field}:required")

    allowed_review_states = set(
        _list(revision_rules.get("human_review_states"))
    )
    if patch.get("human_review_state") not in allowed_review_states:
        errors.append("correction.human_review_state:unsupported")

    change_request = _mapping(patch.get("change_request"))
    if change_request.get("type") != "BOUNDED_CREATOR_CORRECTION":
        errors.append("correction.change_request.type:unsupported")
    failed_checks = _list(change_request.get("failed_checks"))
    if not failed_checks:
        errors.append("correction.change_request.failed_checks:required")

    patch_rules = _mapping(revision_contract.get("patch"))
    required_patch = set(_list(patch_rules.get("required")))
    allowed_operations = set(_list(patch_rules.get("operations")))

    patches = _list(patch.get("patches"))
    if len(patches) != 1:
        errors.append("correction.patches:exactly_one_required")

    for index, raw_item in enumerate(patches):
        item = _mapping(raw_item)
        missing_patch = sorted(required_patch.difference(item))
        errors.extend(
            f"correction.patches[{index}].{field}:missing"
            for field in missing_patch
        )
        if item.get("operation") not in allowed_operations:
            errors.append(
                f"correction.patches[{index}].operation:unsupported"
            )
        if item.get("operation") != CANONICAL_PATCH_OPERATION:
            errors.append(
                f"correction.patches[{index}].operation:"
                "must_be_REPLACE_CONTENT"
            )
        if item.get("target_object_id") != CANONICAL_TARGET_OBJECT_ID:
            errors.append(
                f"correction.patches[{index}].target_object_id:"
                "must_be_inside_image_portrait"
            )

    task = deepcopy(dict(creator_task))
    scope = _mapping(patch.get("creator_scope"))
    if scope.get("target_role") != task.get("target_role"):
        errors.append("correction.creator_scope.target_role:mismatch")
    if scope.get("target_role") != CANONICAL_TARGET_ROLE:
        errors.append(
            "correction.creator_scope.target_role:"
            "must_be_inside_image_portrait"
        )

    original_operations = list(_list(task.get("requested_operations")))
    if list(_list(scope.get("requested_operations"))) != original_operations:
        errors.append(
            "correction.creator_scope.requested_operations:"
            "scope_expansion_or_reordering_forbidden"
        )

    original_forbidden = list(_list(task.get("forbidden_changes")))
    if list(_list(scope.get("forbidden_changes"))) != original_forbidden:
        errors.append(
            "correction.creator_scope.forbidden_changes:"
            "must_match_original_task"
        )

    if scope.get("scope_expansion") is not False:
        errors.append("correction.creator_scope.scope_expansion:must_be_false")
    if scope.get("full_regeneration") is not False:
        errors.append("correction.creator_scope.full_regeneration:must_be_false")

    if _mapping(patch.get("traceability")) != _task_trace(task):
        errors.append("correction.traceability:mismatch")

    authority = _mapping(patch.get("authority"))
    for field in REQUIRED_AUTHORITY_FALSE:
        if authority.get(field) is not False:
            errors.append(f"correction.authority.{field}:must_be_false")

    return errors


def build_correction_cycle_record(
    failed_review: Mapping[str, Any],
    correction_patch: Mapping[str, Any],
    corrected_review: Mapping[str, Any],
) -> dict[str, Any]:
    failed = deepcopy(dict(failed_review))
    correction = deepcopy(dict(correction_patch))
    corrected = deepcopy(dict(corrected_review))

    if failed.get("outcome") != "FAIL":
        raise ValueError("cycle_requires_failed_review")
    if corrected.get("outcome") != "PASS":
        raise ValueError("cycle_requires_corrected_PASS_review")
    if failed.get("task_traceability") != corrected.get("task_traceability"):
        raise ValueError("cycle_task_traceability_mismatch")

    failed_identity = _mapping(failed.get("result_identity"))
    corrected_identity = _mapping(corrected.get("result_identity"))

    failed_revision = failed_identity.get("revision")
    corrected_revision = corrected_identity.get("revision")
    if (
        not isinstance(failed_revision, int)
        or not isinstance(corrected_revision, int)
        or corrected_revision != failed_revision + 1
    ):
        raise ValueError("cycle_revision_must_increment_by_one")

    if correction.get("parent_revision_id") != failed_identity.get("result_id"):
        raise ValueError("cycle_parent_revision_id_mismatch")
    if correction.get("revision_id") != corrected_identity.get("result_id"):
        raise ValueError("cycle_revision_id_mismatch")

    history = (
        list(_list(failed.get("revision_history")))
        + list(_list(corrected.get("revision_history")))
    )

    return {
        "schema_version": CYCLE_SCHEMA,
        "state": "PASS_AFTER_CORRECTION",
        "task_traceability": deepcopy(failed.get("task_traceability")),
        "failed_review": {
            "review_id": failed.get("review_id"),
            "result_id": failed_identity.get("result_id"),
            "revision": failed_revision,
            "outcome": failed.get("outcome"),
        },
        "correction": {
            "revision_id": correction.get("revision_id"),
            "parent_revision_id": correction.get("parent_revision_id"),
            "target_object_id": CANONICAL_TARGET_OBJECT_ID,
            "operation": CANONICAL_PATCH_OPERATION,
            "no_scope_expansion": (
                _mapping(correction.get("creator_scope")).get(
                    "scope_expansion"
                )
                is False
            ),
        },
        "corrected_review": {
            "review_id": corrected.get("review_id"),
            "result_id": corrected_identity.get("result_id"),
            "revision": corrected_revision,
            "outcome": corrected.get("outcome"),
        },
        "revision_history": history,
        "accepted_artifact_refs": list(
            _list(corrected.get("accepted_artifact_refs"))
        ),
        "accepted_for_constructor_bundle": (
            corrected.get("accepted_for_constructor_bundle") is True
        ),
        "customer_forwarding_allowed": False,
        "authority": {
            "provider_execution_performed": False,
            "gdl_runtime_initialized": False,
            "production_write_enabled": False,
            "automatic_customer_messaging": False,
            "automatic_design_approval": False,
        },
    }


def validate_correction_cycle_record(
    record: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, Mapping):
        return ["cycle:must_be_mapping"]

    if record.get("schema_version") != CYCLE_SCHEMA:
        errors.append("cycle.schema_version:unsupported")
    if record.get("state") != "PASS_AFTER_CORRECTION":
        errors.append("cycle.state:must_be_PASS_AFTER_CORRECTION")
    if _has_confidence(record):
        errors.append("cycle:numeric_or_named_confidence_forbidden")

    failed = _mapping(record.get("failed_review"))
    corrected = _mapping(record.get("corrected_review"))
    correction = _mapping(record.get("correction"))

    if failed.get("outcome") != "FAIL":
        errors.append("cycle.failed_review.outcome:must_be_FAIL")
    if corrected.get("outcome") != "PASS":
        errors.append("cycle.corrected_review.outcome:must_be_PASS")
    if correction.get("target_object_id") != CANONICAL_TARGET_OBJECT_ID:
        errors.append(
            "cycle.correction.target_object_id:"
            "must_be_inside_image_portrait"
        )
    if correction.get("operation") != CANONICAL_PATCH_OPERATION:
        errors.append("cycle.correction.operation:must_be_REPLACE_CONTENT")
    if correction.get("no_scope_expansion") is not True:
        errors.append("cycle.correction.no_scope_expansion:must_be_true")

    failed_revision = failed.get("revision")
    corrected_revision = corrected.get("revision")
    if (
        not isinstance(failed_revision, int)
        or not isinstance(corrected_revision, int)
        or corrected_revision != failed_revision + 1
    ):
        errors.append("cycle.revision_history:revision_increment_invalid")

    history = _list(record.get("revision_history"))
    if len(history) != 2:
        errors.append("cycle.revision_history:must_have_two_entries")
    else:
        if _mapping(history[0]).get("review_outcome") != "FAIL":
            errors.append(
                "cycle.revision_history[0].review_outcome:must_be_FAIL"
            )
        if _mapping(history[1]).get("review_outcome") != "PASS":
            errors.append(
                "cycle.revision_history[1].review_outcome:must_be_PASS"
            )

    accepted = _list(record.get("accepted_artifact_refs"))
    if not accepted:
        errors.append("cycle.accepted_artifact_refs:must_not_be_empty")
    if record.get("accepted_for_constructor_bundle") is not True:
        errors.append(
            "cycle.accepted_for_constructor_bundle:must_be_true"
        )
    if record.get("customer_forwarding_allowed") is not False:
        errors.append("cycle.customer_forwarding_allowed:must_be_false")

    authority = _mapping(record.get("authority"))
    for field in REQUIRED_AUTHORITY_FALSE:
        if authority.get(field) is not False:
            errors.append(f"cycle.authority.{field}:must_be_false")

    return errors

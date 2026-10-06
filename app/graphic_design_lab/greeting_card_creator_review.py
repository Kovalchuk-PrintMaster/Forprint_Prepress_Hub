from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from app.graphic_design_lab.result_package import validate_creator_result_package

REVIEW_SCHEMA = "gdl_greeting_card_creator_review_v0_1"

REVIEW_OUTCOMES = {"PASS", "FAIL", "BLOCKED"}
PORTRAIT_CHECK_STATES = {"PASS", "FAIL", "BLOCKED"}
GLOBAL_GATE_STATES = {"PASS", "PARTIAL", "FAIL", "NOT_APPLICABLE"}

REQUIRED_PORTRAIT_CHECKS = (
    "requested_operations_satisfied",
    "likeness_preserved",
    "realistic_appearance_preserved",
    "forbidden_changes_absent",
    "artifact_cleanliness",
    "constructor_asset_usable",
)

GENERIC_GATE_CHECKS = (
    "source_fidelity",
    "scope_completeness",
    "no_invented_customer_content",
    "language_consistency",
    "identity_integrity",
    "artifact_cleanliness",
    "structure_truthfulness",
    "unresolved_truthfulness",
    "design_continuity",
    "output_classification",
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


def _task_trace(creator_task: Mapping[str, Any]) -> dict[str, Any]:
    source = _mapping(creator_task.get("source_asset"))
    return {
        "task_id": creator_task.get("task_id"),
        "job_id": creator_task.get("job_id"),
        "assessment_id": creator_task.get("assessment_id"),
        "source_asset_id": source.get("asset_id"),
    }


def _result_trace(result_package: Mapping[str, Any]) -> dict[str, Any]:
    source = _mapping(result_package.get("source"))
    return _mapping(source.get("greeting_card_task_traceability"))


def _traceability_errors(
    creator_task: Mapping[str, Any],
    result_package: Mapping[str, Any],
) -> list[str]:
    expected = _task_trace(creator_task)
    observed = _result_trace(result_package)
    errors: list[str] = []
    for key, value in expected.items():
        if observed.get(key) != value:
            errors.append(f"task_traceability.{key}:mismatch")
    return errors


def _global_gate_projection(
    *,
    portrait_checks: Mapping[str, str],
    result_package: Mapping[str, Any],
    structural_pass: bool,
) -> dict[str, str]:
    observed = _mapping(result_package.get("observed_result"))

    def projected(check_id: str) -> str:
        value = portrait_checks.get(check_id)
        if value == "PASS":
            return "PASS"
        if value == "FAIL":
            return "FAIL"
        if value == "BLOCKED":
            return "PARTIAL"
        return "FAIL"

    unresolved_clear = not any(
        _list(observed.get(field))
        for field in ("unresolved_items", "missing_confirmations")
    )

    return {
        "source_fidelity": projected("likeness_preserved"),
        "scope_completeness": projected("requested_operations_satisfied"),
        "no_invented_customer_content": projected("forbidden_changes_absent"),
        "language_consistency": "NOT_APPLICABLE",
        "identity_integrity": projected("likeness_preserved"),
        "artifact_cleanliness": projected("artifact_cleanliness"),
        "structure_truthfulness": "NOT_APPLICABLE",
        "unresolved_truthfulness": "PASS" if unresolved_clear else "FAIL",
        "design_continuity": projected("forbidden_changes_absent"),
        "output_classification": "PASS" if structural_pass else "FAIL",
    }


def build_creator_review_record(
    creator_task: Mapping[str, Any],
    result_package: Mapping[str, Any],
    result_contract: Mapping[str, Any],
    *,
    review_id: str,
    reviewer_source: str,
    portrait_checks: Mapping[str, str],
    review_note: str | None = None,
) -> dict[str, Any]:
    task = deepcopy(dict(creator_task))
    package = deepcopy(dict(result_package))
    checks = dict(portrait_checks)

    structural_errors = validate_creator_result_package(
        package,
        dict(result_contract),
    )
    structural_errors.extend(_traceability_errors(task, package))

    readiness = _mapping(package.get("readiness"))
    observed = _mapping(package.get("observed_result"))
    fidelity = _mapping(package.get("content_fidelity"))

    if readiness.get("internal_review") != "REVIEWABLE":
        structural_errors.append("result.internal_review:must_be_REVIEWABLE")
    if readiness.get("technical_validity") != "VALID":
        structural_errors.append("result.technical_validity:must_be_VALID")
    if observed.get("result_state") != "COMPLETE":
        structural_errors.append("result.result_state:must_be_COMPLETE")
    if observed.get("requirements_coverage") != "COMPLETE":
        structural_errors.append("result.requirements_coverage:must_be_COMPLETE")
    if observed.get("known_deviations"):
        structural_errors.append("result.known_deviations:must_be_empty")
    if fidelity.get("status") != "PASS":
        structural_errors.append("result.content_fidelity:must_be_PASS")

    missing_checks = [
        check_id for check_id in REQUIRED_PORTRAIT_CHECKS
        if check_id not in checks
    ]
    invalid_checks = [
        check_id for check_id, state in checks.items()
        if state not in PORTRAIT_CHECK_STATES
    ]

    structural_pass = not structural_errors and not missing_checks and not invalid_checks

    if not structural_pass:
        outcome = "BLOCKED"
    elif any(checks[item] == "BLOCKED" for item in REQUIRED_PORTRAIT_CHECKS):
        outcome = "BLOCKED"
    elif any(checks[item] == "FAIL" for item in REQUIRED_PORTRAIT_CHECKS):
        outcome = "FAIL"
    else:
        outcome = "PASS"

    accepted_artifact_refs: list[str] = []
    if outcome == "PASS":
        for artifact in _list(package.get("artifacts")):
            artifact_map = _mapping(artifact)
            if (
                artifact_map.get("role") == "restored_portrait"
                and artifact_map.get("availability") == "AVAILABLE"
            ):
                artifact_ref = artifact_map.get("artifact_ref")
                if isinstance(artifact_ref, str) and artifact_ref:
                    accepted_artifact_refs.append(artifact_ref)

    provenance = _mapping(package.get("provenance"))

    return {
        "schema_version": REVIEW_SCHEMA,
        "review_id": review_id,
        "reviewer_source": reviewer_source,
        "review_note": review_note,
        "generic_reuse": {
            "internal_review_loop": (
                "coordination/graphic_design_lab/workflow/"
                "internal_review_loop_v0_1.yaml"
            ),
            "global_review_gate": (
                "coordination/graphic_design_lab/review/"
                "global_review_gate_v0_1.yaml"
            ),
            "creator_result_package": (
                "contracts/graphic_design_lab/"
                "creator_result_package_v0_1.yaml"
            ),
            "revision_patch": (
                "contracts/graphic_design_lab/revision_patch_v0_1.yaml"
            ),
        },
        "task_traceability": _task_trace(task),
        "result_identity": {
            "package_id": package.get("package_id"),
            "result_id": package.get("result_id"),
            "revision": package.get("revision"),
            "provenance_sha256": provenance.get("sha256"),
        },
        "structural_gate": {
            "state": "PASS" if structural_pass else "FAIL",
            "errors": (
                structural_errors
                + [f"portrait_check_missing:{item}" for item in missing_checks]
                + [f"portrait_check_invalid:{item}" for item in invalid_checks]
            ),
        },
        "portrait_checks": checks,
        "global_review_gate": _global_gate_projection(
            portrait_checks=checks,
            result_package=package,
            structural_pass=structural_pass,
        ),
        "outcome": outcome,
        "accepted_artifact_refs": accepted_artifact_refs,
        "correction_required": outcome == "FAIL",
        "blocked": outcome == "BLOCKED",
        "accepted_for_constructor_bundle": outcome == "PASS",
        "customer_forwarding_allowed": False,
        "revision_history": [
            {
                "result_id": package.get("result_id"),
                "revision": package.get("revision"),
                "provenance_sha256": provenance.get("sha256"),
                "review_outcome": outcome,
            }
        ],
        "authority": {
            "provider_execution_performed": False,
            "gdl_runtime_initialized": False,
            "production_write_enabled": False,
            "automatic_customer_messaging": False,
            "automatic_design_approval": False,
        },
    }


def validate_creator_review_record(record: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, Mapping):
        return ["review:must_be_mapping"]

    if record.get("schema_version") != REVIEW_SCHEMA:
        errors.append("review.schema_version:unsupported")
    if _has_confidence(record):
        errors.append("review:numeric_or_named_confidence_forbidden")

    for field in ("review_id", "reviewer_source"):
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"review.{field}:required")

    trace = _mapping(record.get("task_traceability"))
    for field in ("task_id", "job_id", "assessment_id", "source_asset_id"):
        value = trace.get(field)
        if not isinstance(value, str) or not value:
            errors.append(f"review.task_traceability.{field}:required")

    identity = _mapping(record.get("result_identity"))
    for field in ("package_id", "result_id"):
        value = identity.get(field)
        if not isinstance(value, str) or not value:
            errors.append(f"review.result_identity.{field}:required")

    revision = identity.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        errors.append("review.result_identity.revision:invalid")

    digest = identity.get("provenance_sha256")
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(ch not in "0123456789abcdefABCDEF" for ch in digest)
    ):
        errors.append("review.result_identity.provenance_sha256:invalid")

    structural = _mapping(record.get("structural_gate"))
    if structural.get("state") not in {"PASS", "FAIL"}:
        errors.append("review.structural_gate.state:invalid")
    if not isinstance(structural.get("errors"), list):
        errors.append("review.structural_gate.errors:must_be_list")

    checks = _mapping(record.get("portrait_checks"))
    for check_id in REQUIRED_PORTRAIT_CHECKS:
        if checks.get(check_id) not in PORTRAIT_CHECK_STATES:
            errors.append(f"review.portrait_checks.{check_id}:invalid")

    global_gate = _mapping(record.get("global_review_gate"))
    for check_id in GENERIC_GATE_CHECKS:
        if global_gate.get(check_id) not in GLOBAL_GATE_STATES:
            errors.append(f"review.global_review_gate.{check_id}:invalid")

    outcome = record.get("outcome")
    if outcome not in REVIEW_OUTCOMES:
        errors.append("review.outcome:invalid")

    accepted = record.get("accepted_artifact_refs")
    if not isinstance(accepted, list):
        errors.append("review.accepted_artifact_refs:must_be_list")
        accepted = []

    history = record.get("revision_history")
    if not isinstance(history, list):
        errors.append("review.revision_history:must_be_list")
    elif not history:
        errors.append("review.revision_history:must_not_be_empty")

    if record.get("customer_forwarding_allowed") is not False:
        errors.append("review.customer_forwarding_allowed:must_be_false")

    if outcome == "PASS":
        if structural.get("state") != "PASS":
            errors.append("review.pass_requires_structural_gate_pass")
        if not accepted:
            errors.append("review.pass_requires_accepted_artifact")
        if record.get("correction_required") is not False:
            errors.append("review.pass_forbids_correction_required")
        if record.get("blocked") is not False:
            errors.append("review.pass_forbids_blocked")
        if record.get("accepted_for_constructor_bundle") is not True:
            errors.append("review.pass_requires_constructor_bundle_acceptance")

    if outcome == "FAIL":
        if accepted:
            errors.append("review.fail_forbids_accepted_artifact")
        if record.get("correction_required") is not True:
            errors.append("review.fail_requires_correction")
        if record.get("accepted_for_constructor_bundle") is not False:
            errors.append("review.fail_forbids_constructor_bundle_acceptance")

    if outcome == "BLOCKED":
        if accepted:
            errors.append("review.blocked_forbids_accepted_artifact")
        if record.get("blocked") is not True:
            errors.append("review.blocked_requires_blocked_true")
        if record.get("accepted_for_constructor_bundle") is not False:
            errors.append("review.blocked_forbids_constructor_bundle_acceptance")

    authority = _mapping(record.get("authority"))
    for field in (
        "provider_execution_performed",
        "gdl_runtime_initialized",
        "production_write_enabled",
        "automatic_customer_messaging",
        "automatic_design_approval",
    ):
        if authority.get(field) is not False:
            errors.append(f"review.authority.{field}:must_be_false")

    return errors

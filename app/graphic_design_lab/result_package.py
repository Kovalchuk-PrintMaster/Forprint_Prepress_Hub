from __future__ import annotations

import copy
import hashlib
import json
from typing import Any


PACKAGE_SCHEMA_VERSION = "forprint_creator_result_package_v0_1"


def _canonical_provenance_payload(package: dict[str, Any]) -> dict[str, Any]:
    return {
        "package_id": package.get("package_id"),
        "result_id": package.get("result_id"),
        "revision": package.get("revision"),
        "source": package.get("source"),
        "expected_result": package.get("expected_result"),
        "artifacts": [
            {
                "artifact_ref": artifact.get("artifact_ref"),
                "role": artifact.get("role"),
                "external_ref": artifact.get("external_ref"),
                "media_type": artifact.get("media_type"),
            }
            for artifact in package.get("artifacts", [])
        ],
    }


def compute_creator_result_provenance_sha256(package: dict[str, Any]) -> str:
    payload = _canonical_provenance_payload(package)
    encoded = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_creator_result_package(raw: dict[str, Any]) -> dict[str, Any]:
    """Return a deterministic normalized copy with provenance digest populated."""
    package = copy.deepcopy(raw)
    package.setdefault("schema_version", PACKAGE_SCHEMA_VERSION)
    package.setdefault("provenance", {})
    package["provenance"]["algorithm"] = "sha256_canonical_json_v0_1"
    package["provenance"]["sha256"] = compute_creator_result_provenance_sha256(package)
    return package


def _require_mapping(errors: list[str], data: Any, name: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        errors.append(f"{name}_must_be_mapping")
        return {}
    return data


def _require_list(errors: list[str], data: Any, name: str) -> list[Any]:
    if not isinstance(data, list):
        errors.append(f"{name}_must_be_list")
        return []
    return data


def _enum(errors: list[str], value: Any, allowed: list[str], error: str) -> None:
    if value not in allowed:
        errors.append(error)


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(ch in "0123456789abcdefABCDEF" for ch in value)


def validate_creator_result_package(
    package: dict[str, Any],
    contract: dict[str, Any],
) -> list[str]:
    """Validate result-package structure and readiness without executing a provider."""
    errors: list[str] = []

    if not isinstance(package, dict):
        return ["package_must_be_mapping"]

    for field in contract.get("required_top_level_fields", []):
        if field not in package:
            errors.append(f"missing_required_field:{field}")

    if package.get("schema_version") != contract.get("package_schema_version"):
        errors.append("unexpected_schema_version")

    for field in ("package_id", "result_id"):
        value = package.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field}_must_be_nonempty_string")

    revision = package.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        errors.append("revision_must_be_positive_integer")

    source = _require_mapping(errors, package.get("source"), "source")
    handoff = _require_mapping(errors, source.get("creator_handoff"), "source.creator_handoff")
    for field in ("handoff_id", "schema_version", "revision"):
        if field not in handoff:
            errors.append(f"source_creator_handoff_missing:{field}")

    prompt = _require_mapping(errors, source.get("creator_prompt"), "source.creator_prompt")
    for field in ("prompt_id", "prompt_version", "prompt_sha256"):
        if field not in prompt:
            errors.append(f"source_creator_prompt_missing:{field}")
    if "prompt_sha256" in prompt and not _is_sha256(prompt.get("prompt_sha256")):
        errors.append("source_creator_prompt_sha256_invalid")

    expected = _require_mapping(errors, package.get("expected_result"), "expected_result")
    if not isinstance(expected.get("target"), str) or not expected.get("target", "").strip():
        errors.append("expected_result_target_required")
    required_roles = _require_list(
        errors,
        expected.get("required_artifact_roles"),
        "expected_result.required_artifact_roles",
    )

    observed = _require_mapping(errors, package.get("observed_result"), "observed_result")
    enums = contract.get("enums", {})
    _enum(errors, observed.get("result_state"), enums.get("result_state", []), "result_state_invalid")
    _enum(
        errors,
        observed.get("requirements_coverage"),
        enums.get("requirements_coverage", []),
        "requirements_coverage_invalid",
    )
    for field in ("known_deviations", "unresolved_items", "missing_confirmations"):
        _require_list(errors, observed.get(field), f"observed_result.{field}")

    artifacts = _require_list(errors, package.get("artifacts"), "artifacts")
    if not artifacts:
        errors.append("artifacts_must_not_be_empty")

    seen_refs: set[str] = set()
    present_roles: set[str] = set()
    customer_review_artifact = False

    for index, raw_artifact in enumerate(artifacts):
        artifact = _require_mapping(errors, raw_artifact, f"artifacts[{index}]")
        artifact_ref = artifact.get("artifact_ref")
        if not isinstance(artifact_ref, str) or not artifact_ref.strip():
            errors.append(f"artifact_ref_required:{index}")
        elif artifact_ref in seen_refs:
            errors.append(f"artifact_ref_duplicate:{artifact_ref}")
        else:
            seen_refs.add(artifact_ref)

        role = artifact.get("role")
        if isinstance(role, str) and role.strip():
            present_roles.add(role)
        else:
            errors.append(f"artifact_role_required:{index}")

        external_ref = _require_mapping(
            errors,
            artifact.get("external_ref"),
            f"artifacts[{index}].external_ref",
        )
        for field in ("storage_role", "artifact_ref"):
            value = external_ref.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"artifact_external_ref_missing:{index}:{field}")

        media_type = artifact.get("media_type")
        if not isinstance(media_type, str) or not media_type.strip():
            errors.append(f"artifact_media_type_required:{index}")

        _enum(
            errors,
            artifact.get("availability"),
            enums.get("artifact_availability", []),
            f"artifact_availability_invalid:{index}",
        )

        suitability = _require_list(
            errors,
            artifact.get("suitability"),
            f"artifacts[{index}].suitability",
        )
        for item in suitability:
            _enum(
                errors,
                item,
                enums.get("artifact_suitability", []),
                f"artifact_suitability_invalid:{index}:{item}",
            )

        if artifact.get("availability") == "AVAILABLE" and "CUSTOMER_REVIEW" in suitability:
            customer_review_artifact = True

        if artifact.get("repository_contains_heavy_artifact") is not False:
            errors.append("heavy_artifact_in_repository_forbidden")

    for role in required_roles:
        if role not in present_roles:
            errors.append(f"required_artifact_role_missing:{role}")

    fidelity = _require_mapping(errors, package.get("content_fidelity"), "content_fidelity")
    _enum(
        errors,
        fidelity.get("status"),
        enums.get("content_fidelity", []),
        "content_fidelity_status_invalid",
    )
    if fidelity.get("factual_check_required") not in (True, False):
        errors.append("content_fidelity_factual_check_required_must_be_boolean")
    _require_list(errors, fidelity.get("known_deviations"), "content_fidelity.known_deviations")

    readiness = _require_mapping(errors, package.get("readiness"), "readiness")
    enum_checks = (
        ("technical_validity", "technical_validity", "technical_validity_invalid"),
        ("internal_review", "internal_review", "internal_review_invalid"),
        ("customer_forwarding", "customer_forwarding", "customer_forwarding_invalid"),
        ("design_approval", "design_approval", "design_approval_invalid"),
        ("production_readiness", "production_readiness", "production_readiness_invalid"),
    )
    for field, enum_key, error in enum_checks:
        _enum(errors, readiness.get(field), enums.get(enum_key, []), error)

    outcomes = _require_mapping(errors, package.get("outcomes"), "outcomes")
    _enum(
        errors,
        outcomes.get("operator_acceptance"),
        enums.get("acceptance", []),
        "operator_acceptance_invalid",
    )
    _enum(
        errors,
        outcomes.get("customer_acceptance"),
        enums.get("acceptance", []),
        "customer_acceptance_invalid",
    )
    _enum(
        errors,
        outcomes.get("customer_explicit_satisfaction"),
        enums.get("explicit_satisfaction", []),
        "customer_explicit_satisfaction_invalid",
    )

    privacy = _require_mapping(errors, package.get("privacy"), "privacy")
    if privacy.get("pii_allowed_in_git") is not False:
        errors.append("pii_allowed_in_git_must_be_false")
    if privacy.get("pii_present_in_package") is not False:
        errors.append("pii_present_in_package_forbidden")
    if privacy.get("heavy_artifacts_in_git") is not False:
        errors.append("heavy_artifacts_in_git_must_be_false")

    authority = _require_mapping(errors, package.get("authority"), "authority")
    authority_require_false = (
        ("provider_execution_required", "provider_execution_required_must_remain_false"),
        ("provider_execution_performed", "provider_execution_must_remain_false"),
        ("gdl_runtime_initialized", "gdl_runtime_initialization_must_remain_false"),
        ("production_write_enabled", "production_write_must_remain_false"),
        ("automatic_customer_messaging", "automatic_customer_messaging_must_remain_false"),
        ("automatic_design_approval", "automatic_design_approval_must_remain_false"),
    )
    for field, error in authority_require_false:
        if authority.get(field) is not False:
            errors.append(error)

    provenance = _require_mapping(errors, package.get("provenance"), "provenance")
    if provenance.get("algorithm") != "sha256_canonical_json_v0_1":
        errors.append("provenance_algorithm_invalid")
    if provenance.get("sha256") != compute_creator_result_provenance_sha256(package):
        errors.append("provenance_sha256_mismatch")

    if readiness.get("customer_forwarding") == "READY":
        if observed.get("result_state") != "COMPLETE":
            errors.append("customer_forwarding_requires_complete_result")
        if readiness.get("technical_validity") != "VALID":
            errors.append("customer_forwarding_requires_technical_validity")
        if readiness.get("internal_review") != "REVIEWABLE":
            errors.append("customer_forwarding_requires_reviewable_state")
        if fidelity.get("status") != "PASS":
            errors.append("customer_forwarding_requires_content_fidelity_pass")
        if observed.get("requirements_coverage") != "COMPLETE":
            errors.append("customer_forwarding_requires_complete_requirements_coverage")
        if observed.get("known_deviations"):
            errors.append("customer_forwarding_requires_no_known_deviations")
        if observed.get("missing_confirmations"):
            errors.append("customer_forwarding_requires_no_missing_confirmations")
        if not customer_review_artifact:
            errors.append("customer_forwarding_requires_customer_review_artifact")

    if (
        observed.get("result_state") in {"PARTIAL", "STYLE_ONLY", "BLOCKED"}
        and readiness.get("customer_forwarding") == "READY"
    ):
        errors.append("customer_forwarding_requires_complete_result")

    return sorted(set(errors))


def summarize_creator_result_package(package: dict[str, Any]) -> str:
    readiness = package.get("readiness", {})
    observed = package.get("observed_result", {})
    fidelity = package.get("content_fidelity", {})
    return "\n".join(
        [
            f"Creator Result Package: {package.get('package_id', '<missing>')}",
            f"Result: {package.get('result_id', '<missing>')} revision {package.get('revision', '<missing>')}",
            f"Result state: {observed.get('result_state', '<missing>')}",
            f"Requirements coverage: {observed.get('requirements_coverage', '<missing>')}",
            f"Content fidelity: {fidelity.get('status', '<missing>')}",
            f"Technical validity: {readiness.get('technical_validity', '<missing>')}",
            f"Internal review: {readiness.get('internal_review', '<missing>')}",
            f"Customer forwarding: {readiness.get('customer_forwarding', '<missing>')}",
            f"Design approval: {readiness.get('design_approval', '<missing>')}",
            f"Production readiness: {readiness.get('production_readiness', '<missing>')}",
        ]
    )

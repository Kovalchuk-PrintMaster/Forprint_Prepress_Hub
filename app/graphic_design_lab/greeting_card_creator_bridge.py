from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any, Mapping

from app.graphic_design_lab.result_package import validate_creator_result_package

BRIDGE_SCHEMA = "gdl_greeting_card_creator_bridge_package_v0_1"
EXECUTION_MODE = "HUMAN_COPY_PASTE_BRIDGE"
EVIDENCE_CLASSES = {"SANITIZED_REHEARSAL_ONLY", "LIVE_OPERATOR_BRIDGE"}
DISPATCH_STATES = {
    "PREPARED_FOR_HUMAN_DISPATCH",
    "DISPATCHED_AWAITING_RESULT",
    "REHEARSAL_RESULT_ATTACHED",
    "LIVE_RESULT_ATTACHED",
}


def compute_prompt_sha256(prompt_text: str) -> str:
    return hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()


def _sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(ch in "0123456789abcdefABCDEF" for ch in value)
    )


def _mapping(errors: list[str], value: Any, prefix: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        errors.append(f"{prefix}:must_be_mapping")
        return {}
    return dict(value)


def _required(
    errors: list[str],
    value: Mapping[str, Any],
    fields: set[str],
    prefix: str,
) -> None:
    for field in sorted(fields.difference(value)):
        errors.append(f"{prefix}.{field}:missing")


def build_dispatch_manifest(
    creator_task: Mapping[str, Any],
    *,
    case_id: str,
    prompt_id: str,
    prompt_version: str,
    prompt_content_ref: str,
    prompt_text: str,
) -> dict[str, Any]:
    task = deepcopy(dict(creator_task))
    source = task.get("source_asset") if isinstance(task.get("source_asset"), Mapping) else {}

    return {
        "schema_version": BRIDGE_SCHEMA,
        "bridge_id": f"{task.get('task_id')}__human_bridge_v001",
        "case_id": case_id,
        "execution_mode": EXECUTION_MODE,
        "evidence_class": "LIVE_OPERATOR_BRIDGE",
        "creator_task": task,
        "prompt_record": {
            "prompt_id": prompt_id,
            "case_id": case_id,
            "role": "CREATOR",
            "prompt_type": "BOUNDED_PORTRAIT_TRANSFORMATION",
            "format": "HYBRID",
            "content_ref": prompt_content_ref,
            "source_context_refs": [
                f"task://{task.get('task_id')}",
                f"assessment://{task.get('assessment_id')}",
            ],
            "result_ref": "PENDING_EXTERNAL_RESULT",
            "prompt_version": prompt_version,
            "prompt_sha256": compute_prompt_sha256(prompt_text),
        },
        "dispatch": {
            "state": "PREPARED_FOR_HUMAN_DISPATCH",
            "human_operator_required": True,
            "creator_execution_observed": False,
            "provider_execution_performed": False,
        },
        "result_attachment": {
            "attached": False,
            "actual_creator_result": False,
            "result_ref": None,
            "creator_result_package": None,
        },
        "traceability": {
            "task_id": task.get("task_id"),
            "job_id": task.get("job_id"),
            "assessment_id": task.get("assessment_id"),
            "source_asset_id": source.get("asset_id"),
        },
        "completion_gate": {
            "gc_e2e_04_completion_eligible": False,
            "reason": "actual_creator_result_not_attached",
        },
        "authority": {
            "provider_execution_performed": False,
            "gdl_runtime_initialized": False,
            "production_write_enabled": False,
            "full_card_composition_authorized": False,
        },
    }


def validate_creator_bridge_package(
    package: Mapping[str, Any],
    *,
    result_contract: Mapping[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(package, Mapping):
        return ["bridge:must_be_mapping"]

    _required(
        errors,
        package,
        {
            "schema_version",
            "bridge_id",
            "case_id",
            "execution_mode",
            "evidence_class",
            "creator_task",
            "prompt_record",
            "dispatch",
            "result_attachment",
            "traceability",
            "completion_gate",
            "authority",
        },
        "bridge",
    )

    if package.get("schema_version") != BRIDGE_SCHEMA:
        errors.append("bridge.schema_version:unsupported")
    if package.get("execution_mode") != EXECUTION_MODE:
        errors.append("bridge.execution_mode:unsupported")
    evidence_class = package.get("evidence_class")
    if evidence_class not in EVIDENCE_CLASSES:
        errors.append("bridge.evidence_class:unsupported")

    task = _mapping(errors, package.get("creator_task"), "bridge.creator_task")
    _required(
        errors,
        task,
        {
            "task_id",
            "job_id",
            "assessment_id",
            "source_asset",
            "target_role",
            "requested_operations",
            "preservation",
            "forbidden_changes",
            "output",
            "traceability",
            "creator_execution_authorized",
            "provider_execution_required",
        },
        "bridge.creator_task",
    )
    if task.get("target_role") != "inside_image.portrait":
        errors.append("bridge.creator_task.target_role:must_be_inside_image_portrait")
    if task.get("creator_execution_authorized") is not False:
        errors.append("bridge.creator_task.creator_execution_authorized:must_be_false")
    if task.get("provider_execution_required") is not False:
        errors.append("bridge.creator_task.provider_execution_required:must_be_false")

    preservation = _mapping(
        errors, task.get("preservation"), "bridge.creator_task.preservation"
    )
    if preservation.get("likeness") != "REQUIRED":
        errors.append("bridge.creator_task.preservation.likeness:must_be_REQUIRED")
    if preservation.get("realistic_appearance") != "REQUIRED":
        errors.append(
            "bridge.creator_task.preservation.realistic_appearance:must_be_REQUIRED"
        )
    if preservation.get("identity_change") != "FORBIDDEN":
        errors.append(
            "bridge.creator_task.preservation.identity_change:must_be_FORBIDDEN"
        )

    source = _mapping(
        errors, task.get("source_asset"), "bridge.creator_task.source_asset"
    )
    trace = _mapping(errors, package.get("traceability"), "bridge.traceability")
    expected_trace = {
        "task_id": task.get("task_id"),
        "job_id": task.get("job_id"),
        "assessment_id": task.get("assessment_id"),
        "source_asset_id": source.get("asset_id"),
    }
    for key, expected in expected_trace.items():
        if trace.get(key) != expected:
            errors.append(f"bridge.traceability.{key}:mismatch")

    prompt = _mapping(errors, package.get("prompt_record"), "bridge.prompt_record")
    _required(
        errors,
        prompt,
        {
            "prompt_id",
            "case_id",
            "role",
            "prompt_type",
            "format",
            "content_ref",
            "source_context_refs",
            "result_ref",
            "prompt_version",
            "prompt_sha256",
        },
        "bridge.prompt_record",
    )
    if prompt.get("case_id") != package.get("case_id"):
        errors.append("bridge.prompt_record.case_id:mismatch")
    if prompt.get("role") != "CREATOR":
        errors.append("bridge.prompt_record.role:must_be_CREATOR")
    if prompt.get("format") not in {"STRUCTURED", "HYBRID"}:
        errors.append("bridge.prompt_record.format:unsupported")
    if not _sha256(prompt.get("prompt_sha256")):
        errors.append("bridge.prompt_record.prompt_sha256:invalid")

    dispatch = _mapping(errors, package.get("dispatch"), "bridge.dispatch")
    if dispatch.get("state") not in DISPATCH_STATES:
        errors.append("bridge.dispatch.state:unsupported")
    if dispatch.get("human_operator_required") is not True:
        errors.append("bridge.dispatch.human_operator_required:must_be_true")
    if dispatch.get("provider_execution_performed") is not False:
        errors.append("bridge.dispatch.provider_execution_performed:must_be_false")

    attachment = _mapping(
        errors, package.get("result_attachment"), "bridge.result_attachment"
    )
    attached = attachment.get("attached")
    actual_result = attachment.get("actual_creator_result")
    if not isinstance(attached, bool):
        errors.append("bridge.result_attachment.attached:must_be_boolean")
    if not isinstance(actual_result, bool):
        errors.append(
            "bridge.result_attachment.actual_creator_result:must_be_boolean"
        )

    result_package = attachment.get("creator_result_package")
    if attached:
        if not isinstance(result_package, Mapping):
            errors.append(
                "bridge.result_attachment.creator_result_package:required_when_attached"
            )
        elif result_contract is not None:
            rp_errors = validate_creator_result_package(
                dict(result_package), dict(result_contract)
            )
            errors.extend(
                f"bridge.creator_result_package:{item}" for item in rp_errors
            )

        if isinstance(result_package, Mapping):
            source_block = result_package.get("source")
            if isinstance(source_block, Mapping):
                prompt_ref = source_block.get("creator_prompt")
                if isinstance(prompt_ref, Mapping):
                    if prompt_ref.get("prompt_id") != prompt.get("prompt_id"):
                        errors.append("bridge.creator_result_package.prompt_id:mismatch")
                    if prompt_ref.get("prompt_version") != prompt.get(
                        "prompt_version"
                    ):
                        errors.append(
                            "bridge.creator_result_package.prompt_version:mismatch"
                        )
                    if prompt_ref.get("prompt_sha256") != prompt.get(
                        "prompt_sha256"
                    ):
                        errors.append(
                            "bridge.creator_result_package.prompt_sha256:mismatch"
                        )

                task_trace = source_block.get(
                    "greeting_card_task_traceability"
                )
                if not isinstance(task_trace, Mapping):
                    errors.append(
                        "bridge.creator_result_package.task_traceability:missing"
                    )
                else:
                    for key, expected in expected_trace.items():
                        if task_trace.get(key) != expected:
                            errors.append(
                                "bridge.creator_result_package."
                                f"task_traceability.{key}:mismatch"
                            )

            artifacts = result_package.get("artifacts")
            if not isinstance(artifacts, list) or not artifacts:
                errors.append(
                    "bridge.creator_result_package.artifacts:must_be_nonempty"
                )
            else:
                for index, artifact in enumerate(artifacts):
                    if not isinstance(artifact, Mapping):
                        errors.append(
                            "bridge.creator_result_package."
                            f"artifacts[{index}]:must_be_mapping"
                        )
                        continue
                    if (
                        artifact.get("repository_contains_heavy_artifact")
                        is not False
                    ):
                        errors.append(
                            "bridge.creator_result_package."
                            f"artifacts[{index}]:heavy_git_artifact_forbidden"
                        )
                    artifact_trace = artifact.get(
                        "greeting_card_task_traceability"
                    )
                    if not isinstance(artifact_trace, Mapping):
                        errors.append(
                            "bridge.creator_result_package."
                            f"artifacts[{index}].task_traceability:missing"
                        )
                    else:
                        if artifact_trace.get("task_id") != task.get("task_id"):
                            errors.append(
                                "bridge.creator_result_package."
                                f"artifacts[{index}].task_id:mismatch"
                            )
                        if artifact_trace.get(
                            "source_asset_id"
                        ) != source.get("asset_id"):
                            errors.append(
                                "bridge.creator_result_package."
                                f"artifacts[{index}].source_asset_id:mismatch"
                            )
    else:
        if result_package is not None:
            errors.append(
                "bridge.result_attachment."
                "creator_result_package:must_be_null_when_not_attached"
            )
        if attachment.get("result_ref") not in (None, ""):
            errors.append(
                "bridge.result_attachment.result_ref:must_be_null_when_not_attached"
            )

    authority = _mapping(errors, package.get("authority"), "bridge.authority")
    for field in (
        "provider_execution_performed",
        "gdl_runtime_initialized",
        "production_write_enabled",
        "full_card_composition_authorized",
    ):
        if authority.get(field) is not False:
            errors.append(f"bridge.authority.{field}:must_be_false")

    creator_observed = dispatch.get("creator_execution_observed")
    if not isinstance(creator_observed, bool):
        errors.append(
            "bridge.dispatch.creator_execution_observed:must_be_boolean"
        )

    completion = _mapping(
        errors, package.get("completion_gate"), "bridge.completion_gate"
    )
    eligible = completion.get("gc_e2e_04_completion_eligible")
    if not isinstance(eligible, bool):
        errors.append(
            "bridge.completion_gate."
            "gc_e2e_04_completion_eligible:must_be_boolean"
        )

    if evidence_class == "SANITIZED_REHEARSAL_ONLY":
        if creator_observed is not False:
            errors.append(
                "bridge.rehearsal:creator_execution_observed_must_be_false"
            )
        if actual_result is not False:
            errors.append(
                "bridge.rehearsal:actual_creator_result_must_be_false"
            )
        if eligible is not False:
            errors.append(
                "bridge.rehearsal:gc_e2e_04_completion_forbidden"
            )

    if eligible is True:
        if evidence_class != "LIVE_OPERATOR_BRIDGE":
            errors.append("bridge.completion:live_evidence_required")
        if attached is not True or actual_result is not True:
            errors.append(
                "bridge.completion:actual_result_attachment_required"
            )
        if creator_observed is not True:
            errors.append(
                "bridge.completion:creator_execution_observation_required"
            )
        if dispatch.get("state") != "LIVE_RESULT_ATTACHED":
            errors.append(
                "bridge.completion:live_result_attached_state_required"
            )

    return errors

"""Deterministic Guided Intake and Creator Handoff support for GDL v0.1.

This module is pre-Design-Spec. It does not initialize Graphic Design Lab
runtime, select/execute providers, ingest live customer files, or create a
Creator Result Package.

Asset/reference identity and provenance remain owned by asset_reference_v0_1.
Mappings here carry references only.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

PLAYBOOK_SCHEMA = "forprint_product_playbook_v0_1"
GUIDED_INTAKE_SCHEMA = "forprint_guided_intake_v0_1"
CREATOR_HANDOFF_SCHEMA = "forprint_creator_handoff_v0_1"

MAPPING_STATES = {"CONFIRMED", "PROPOSED", "UNRESOLVED"}
SOURCE_KINDS = {"asset", "reference", "none"}
CONFIRMED_SOURCES = {
    "customer_assignment",
    "operator_assignment",
    "previously_confirmed",
}


def _require(
    mapping: Mapping[str, Any],
    keys: list[str],
    prefix: str,
    errors: list[str],
) -> None:
    for key in keys:
        if key not in mapping:
            errors.append(f"{prefix}.{key}:required")


def _has_confidence(mapping: Mapping[str, Any]) -> bool:
    return any("confidence" in str(key).lower() for key in mapping)


def _validate_question_value(
    question: Mapping[str, Any],
    value: Any,
    prefix: str,
    errors: list[str],
) -> None:
    answer_type = question.get("answer_type")

    if answer_type == "text":
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{prefix}:must_be_nonempty_text")
        return

    if answer_type == "choice":
        choices = question.get("choices")
        if not isinstance(choices, list) or value not in choices:
            errors.append(f"{prefix}:not_in_declared_choices")
        return

    if answer_type == "boolean":
        if not isinstance(value, bool):
            errors.append(f"{prefix}:must_be_boolean")
        return

    errors.append(f"{prefix}:unsupported_answer_type")


def _identity_sets(
    assets: list[Mapping[str, Any]],
    references: list[Mapping[str, Any]],
) -> tuple[set[str], set[str]]:
    asset_ids = {
        str(item.get("asset_id"))
        for item in assets
        if isinstance(item, Mapping) and item.get("asset_id")
    }
    reference_ids = {
        str(item.get("reference_id"))
        for item in references
        if isinstance(item, Mapping) and item.get("reference_id")
    }
    return asset_ids, reference_ids


def validate_product_playbook(playbook: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    _require(
        playbook,
        [
            "schema_version",
            "product_playbook_id",
            "product_type",
            "questions",
            "asset_roles",
            "creator_instructions",
            "final_open_question",
            "required_creator_outputs",
        ],
        "playbook",
        errors,
    )
    if playbook.get("schema_version") != PLAYBOOK_SCHEMA:
        errors.append("playbook.schema_version:unsupported")

    questions = playbook.get("questions")
    if not isinstance(questions, list) or not questions:
        errors.append("playbook.questions:must_be_nonempty_list")
        questions = []

    question_ids: list[str] = []
    for index, question in enumerate(questions):
        prefix = f"playbook.questions[{index}]"
        if not isinstance(question, Mapping):
            errors.append(f"{prefix}:must_be_mapping")
            continue
        _require(
            question,
            ["question_id", "prompt", "required", "answer_type", "normalized_field"],
            prefix,
            errors,
        )
        if isinstance(question.get("question_id"), str):
            question_ids.append(str(question["question_id"]))
        if not isinstance(question.get("required"), bool):
            errors.append(f"{prefix}.required:must_be_boolean")
        answer_type = question.get("answer_type")
        if answer_type not in {"text", "choice", "boolean"}:
            errors.append(f"{prefix}.answer_type:unsupported")
        if answer_type == "choice":
            choices = question.get("choices")
            if not isinstance(choices, list) or not choices:
                errors.append(f"{prefix}.choices:required_for_choice")

    if len(question_ids) != len(set(question_ids)):
        errors.append("playbook.questions:duplicate_question_id")

    roles = playbook.get("asset_roles")
    if not isinstance(roles, list) or not roles:
        errors.append("playbook.asset_roles:must_be_nonempty_list")
        roles = []

    role_ids: list[str] = []
    for index, role in enumerate(roles):
        prefix = f"playbook.asset_roles[{index}]"
        if not isinstance(role, Mapping):
            errors.append(f"{prefix}:must_be_mapping")
            continue
        _require(role, ["role_id", "required", "accepted_source_kinds"], prefix, errors)
        if isinstance(role.get("role_id"), str):
            role_ids.append(str(role["role_id"]))
        if not isinstance(role.get("required"), bool):
            errors.append(f"{prefix}.required:must_be_boolean")
        kinds = role.get("accepted_source_kinds")
        if not isinstance(kinds, list) or not kinds:
            errors.append(f"{prefix}.accepted_source_kinds:must_be_nonempty_list")
        elif not set(kinds).issubset({"asset", "reference"}):
            errors.append(f"{prefix}.accepted_source_kinds:unsupported")

    if len(role_ids) != len(set(role_ids)):
        errors.append("playbook.asset_roles:duplicate_role_id")

    if not isinstance(playbook.get("creator_instructions"), list):
        errors.append("playbook.creator_instructions:must_be_list")
    if not isinstance(playbook.get("required_creator_outputs"), list):
        errors.append("playbook.required_creator_outputs:must_be_list")

    final_open = playbook.get("final_open_question")
    if not isinstance(final_open, Mapping):
        errors.append("playbook.final_open_question:must_be_mapping")
    else:
        _require(final_open, ["enabled", "prompt"], "playbook.final_open_question", errors)
        if not isinstance(final_open.get("enabled"), bool):
            errors.append("playbook.final_open_question.enabled:must_be_boolean")
        prompt = final_open.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            errors.append("playbook.final_open_question.prompt:must_be_nonempty_text")

    if any(
        key in playbook
        for key in ("customer_id", "customer_name", "order_id", "customer_instance")
    ):
        errors.append("playbook:customer_specific_state_forbidden")

    return errors


def _validate_mapping(
    mapping: Mapping[str, Any],
    *,
    prefix: str,
    role_specs: Mapping[str, Mapping[str, Any]],
    asset_ids: set[str],
    reference_ids: set[str],
    errors: list[str],
) -> None:
    _require(
        mapping,
        [
            "role_id",
            "source_kind",
            "source_id",
            "mapping_state",
            "mapping_source",
            "human_confirmation_required",
        ],
        prefix,
        errors,
    )

    if _has_confidence(mapping):
        errors.append(f"{prefix}:confidence_forbidden")

    role_id = mapping.get("role_id")
    role_spec = role_specs.get(str(role_id))
    if role_spec is None:
        errors.append(f"{prefix}.role_id:unknown")

    source_kind = mapping.get("source_kind")
    source_id = mapping.get("source_id")

    if role_spec is not None and source_kind in {"asset", "reference"}:
        accepted = role_spec.get("accepted_source_kinds", [])
        if source_kind not in accepted:
            errors.append(f"{prefix}.source_kind:not_accepted_for_role")
    if source_kind not in SOURCE_KINDS:
        errors.append(f"{prefix}.source_kind:unsupported")
    elif source_kind == "asset" and source_id not in asset_ids:
        errors.append(f"{prefix}.source_id:unknown_asset")
    elif source_kind == "reference" and source_id not in reference_ids:
        errors.append(f"{prefix}.source_id:unknown_reference")
    elif source_kind == "none" and source_id is not None:
        errors.append(f"{prefix}.source_id:must_be_null_for_none")

    state = mapping.get("mapping_state")
    if state not in MAPPING_STATES:
        errors.append(f"{prefix}.mapping_state:unsupported")

    human_required = mapping.get("human_confirmation_required")
    if not isinstance(human_required, bool):
        errors.append(f"{prefix}.human_confirmation_required:must_be_boolean")
        return

    mapping_source = mapping.get("mapping_source")
    if state == "CONFIRMED":
        if source_kind == "none" or source_id is None:
            errors.append(f"{prefix}:confirmed_requires_source_reference")
        if mapping_source not in CONFIRMED_SOURCES:
            errors.append(f"{prefix}:confirmed_requires_explicit_deterministic_basis")
        if human_required:
            errors.append(f"{prefix}:confirmed_must_not_require_confirmation")
    elif state == "PROPOSED":
        if source_kind == "none" or source_id is None:
            errors.append(f"{prefix}:proposed_requires_candidate_reference")
        if not human_required:
            errors.append(f"{prefix}:proposed_requires_human_confirmation")
    elif state == "UNRESOLVED" and not human_required:
        errors.append(f"{prefix}:unresolved_requires_human_confirmation")


def normalize_guided_intake(
    playbook: Mapping[str, Any],
    raw_input: Mapping[str, Any],
) -> dict[str, Any]:
    playbook_errors = validate_product_playbook(playbook)
    if playbook_errors:
        raise ValueError("Invalid Product Playbook: " + "; ".join(playbook_errors))

    request_id = raw_input.get("request_id")
    if not isinstance(request_id, str) or not request_id:
        raise ValueError("raw_input.request_id is required")

    answers = raw_input.get("answers", {})
    assets = raw_input.get("assets", [])
    references = raw_input.get("references", [])
    mappings = raw_input.get("mappings", [])

    if not isinstance(answers, Mapping):
        raise ValueError("raw_input.answers must be a mapping")
    if not isinstance(assets, list):
        raise ValueError("raw_input.assets must be a list")
    if not isinstance(references, list):
        raise ValueError("raw_input.references must be a list")
    if not isinstance(mappings, list):
        raise ValueError("raw_input.mappings must be a list")

    answered_questions: list[dict[str, Any]] = []
    unresolved_questions: list[dict[str, Any]] = []
    normalized_answers: dict[str, Any] = {}
    answer_errors: list[str] = []

    for question in playbook["questions"]:
        question_id = str(question["question_id"])
        normalized_field = str(question["normalized_field"])
        if question_id in answers and answers[question_id] not in (None, ""):
            value = deepcopy(answers[question_id])
            _validate_question_value(
                question,
                value,
                f"raw_input.answers.{question_id}",
                answer_errors,
            )
            answered_questions.append({"question_id": question_id, "value": value})
            normalized_answers[normalized_field] = value
        elif question.get("required") is True:
            unresolved_questions.append(
                {
                    "question_id": question_id,
                    "reason": "required_answer_missing",
                    "human_confirmation_required": True,
                }
            )

    if answer_errors:
        raise ValueError("Invalid Guided Intake Answers: " + "; ".join(answer_errors))

    normalized_mappings = []
    for mapping in mappings:
        if not isinstance(mapping, Mapping):
            continue
        item = {
            "role_id": mapping.get("role_id"),
            "source_kind": mapping.get("source_kind"),
            "source_id": mapping.get("source_id"),
            "mapping_state": mapping.get("mapping_state"),
            "mapping_source": mapping.get("mapping_source"),
            "human_confirmation_required": mapping.get(
                "human_confirmation_required"
            ),
        }
        if mapping.get("note") not in (None, ""):
            item["note"] = mapping.get("note")
        normalized_mappings.append(item)

    normalized_mappings.sort(
        key=lambda item: (
            str(item.get("role_id", "")),
            str(item.get("source_kind", "")),
            str(item.get("source_id", "")),
        )
    )

    result = {
        "schema_version": GUIDED_INTAKE_SCHEMA,
        "guided_intake_id": f"{request_id}__guided_intake_v0_1",
        "request_id": request_id,
        "product_playbook_id": playbook["product_playbook_id"],
        "product_type": playbook["product_type"],
        "normalized_request": {
            "customer_notes": str(raw_input.get("customer_notes", "")),
            "answers": normalized_answers,
        },
        "answered_questions": answered_questions,
        "unresolved_questions": unresolved_questions,
        "asset_mappings": normalized_mappings,
    }

    errors = validate_guided_intake(
        result,
        playbook=playbook,
        assets=assets,
        references=references,
    )
    if errors:
        raise ValueError("Invalid Guided Intake: " + "; ".join(errors))
    return result


def validate_guided_intake(
    intake: Mapping[str, Any],
    *,
    playbook: Mapping[str, Any],
    assets: list[Mapping[str, Any]],
    references: list[Mapping[str, Any]],
) -> list[str]:
    errors: list[str] = []
    _require(
        intake,
        [
            "schema_version",
            "guided_intake_id",
            "request_id",
            "product_playbook_id",
            "product_type",
            "normalized_request",
            "answered_questions",
            "unresolved_questions",
            "asset_mappings",
        ],
        "guided_intake",
        errors,
    )

    if intake.get("schema_version") != GUIDED_INTAKE_SCHEMA:
        errors.append("guided_intake.schema_version:unsupported")
    if intake.get("product_playbook_id") != playbook.get("product_playbook_id"):
        errors.append("guided_intake.product_playbook_id:mismatch")
    if intake.get("product_type") != playbook.get("product_type"):
        errors.append("guided_intake.product_type:mismatch")

    questions = {
        str(question["question_id"]): question
        for question in playbook.get("questions", [])
        if isinstance(question, Mapping) and question.get("question_id")
    }

    normalized_request = intake.get("normalized_request")
    if not isinstance(normalized_request, Mapping):
        errors.append("guided_intake.normalized_request:must_be_mapping")
        normalized_answers: Mapping[str, Any] = {}
    else:
        candidate_answers = normalized_request.get("answers")
        if not isinstance(candidate_answers, Mapping):
            errors.append("guided_intake.normalized_request.answers:must_be_mapping")
            normalized_answers = {}
        else:
            normalized_answers = candidate_answers

    answered_questions = intake.get("answered_questions")
    if not isinstance(answered_questions, list):
        errors.append("guided_intake.answered_questions:must_be_list")
        answered_questions = []

    seen_question_ids: set[str] = set()
    for index, answered in enumerate(answered_questions):
        prefix = f"guided_intake.answered_questions[{index}]"
        if not isinstance(answered, Mapping):
            errors.append(f"{prefix}:must_be_mapping")
            continue
        _require(answered, ["question_id", "value"], prefix, errors)
        question_id = answered.get("question_id")
        question = questions.get(str(question_id))
        if question is None:
            errors.append(f"{prefix}.question_id:unknown")
            continue
        if str(question_id) in seen_question_ids:
            errors.append(f"{prefix}.question_id:duplicate")
        seen_question_ids.add(str(question_id))

        value = answered.get("value")
        _validate_question_value(question, value, f"{prefix}.value", errors)
        normalized_field = str(question.get("normalized_field", ""))
        if normalized_answers.get(normalized_field) != value:
            errors.append(f"{prefix}:normalized_answer_mismatch")

    roles = {
        str(role["role_id"]): role
        for role in playbook.get("asset_roles", [])
        if isinstance(role, Mapping) and role.get("role_id")
    }
    asset_ids, reference_ids = _identity_sets(assets, references)

    mappings = intake.get("asset_mappings")
    if not isinstance(mappings, list):
        errors.append("guided_intake.asset_mappings:must_be_list")
        mappings = []

    seen_roles: set[str] = set()
    for index, mapping in enumerate(mappings):
        prefix = f"guided_intake.asset_mappings[{index}]"
        if not isinstance(mapping, Mapping):
            errors.append(f"{prefix}:must_be_mapping")
            continue
        _validate_mapping(
            mapping,
            prefix=prefix,
            role_specs=roles,
            asset_ids=asset_ids,
            reference_ids=reference_ids,
            errors=errors,
        )
        role_id = mapping.get("role_id")
        if isinstance(role_id, str):
            if role_id in seen_roles:
                errors.append(f"{prefix}.role_id:duplicate")
            seen_roles.add(role_id)

    for role_id, role in roles.items():
        if role.get("required") is True and role_id not in seen_roles:
            errors.append(f"guided_intake.asset_mappings:{role_id}:required_role_missing")

    if not isinstance(intake.get("unresolved_questions"), list):
        errors.append("guided_intake.unresolved_questions:must_be_list")

    return errors


def build_creator_handoff(
    playbook: Mapping[str, Any],
    guided_intake: Mapping[str, Any],
    *,
    assets: list[Mapping[str, Any]],
    references: list[Mapping[str, Any]],
) -> dict[str, Any]:
    errors = validate_guided_intake(
        guided_intake,
        playbook=playbook,
        assets=assets,
        references=references,
    )
    if errors:
        raise ValueError("Invalid Guided Intake: " + "; ".join(errors))

    mappings = deepcopy(guided_intake["asset_mappings"])
    mappings.sort(
        key=lambda item: (
            str(item.get("role_id", "")),
            str(item.get("source_kind", "")),
            str(item.get("source_id", "")),
        )
    )

    handoff = {
        "schema_version": CREATOR_HANDOFF_SCHEMA,
        "handoff_id": (
            f"{guided_intake['guided_intake_id']}__creator_handoff_v0_1"
        ),
        "guided_intake_id": guided_intake["guided_intake_id"],
        "product_playbook_id": playbook["product_playbook_id"],
        "product_type": playbook["product_type"],
        "creator_brief": {
            "customer_notes": guided_intake["normalized_request"].get(
                "customer_notes", ""
            ),
            "creator_instructions": deepcopy(playbook["creator_instructions"]),
            "final_open_question": deepcopy(playbook["final_open_question"]),
            "human_confirmation_required": any(
                item.get("human_confirmation_required") is True
                for item in mappings
            ),
        },
        "design_request": deepcopy(guided_intake["normalized_request"]),
        "asset_manifest": [
            {
                "role_id": item.get("role_id"),
                "source_kind": item.get("source_kind"),
                "source_id": item.get("source_id"),
                "mapping_state": item.get("mapping_state"),
                "human_confirmation_required": item.get(
                    "human_confirmation_required"
                ),
                **(
                    {"note": item.get("note")}
                    if item.get("note") not in (None, "")
                    else {}
                ),
            }
            for item in mappings
        ],
        "unresolved_questions": deepcopy(guided_intake["unresolved_questions"]),
        "required_outputs": deepcopy(playbook["required_creator_outputs"]),
        "creator_execution_authorized": False,
        "provider_execution_required": False,
    }

    handoff_errors = validate_creator_handoff(
        handoff,
        playbook=playbook,
        assets=assets,
        references=references,
    )
    if handoff_errors:
        raise ValueError("Invalid Creator Handoff: " + "; ".join(handoff_errors))
    return handoff


def validate_creator_handoff(
    handoff: Mapping[str, Any],
    *,
    playbook: Mapping[str, Any],
    assets: list[Mapping[str, Any]],
    references: list[Mapping[str, Any]],
) -> list[str]:
    errors: list[str] = []
    _require(
        handoff,
        [
            "schema_version",
            "handoff_id",
            "guided_intake_id",
            "product_playbook_id",
            "product_type",
            "creator_brief",
            "design_request",
            "asset_manifest",
            "unresolved_questions",
            "required_outputs",
            "creator_execution_authorized",
            "provider_execution_required",
        ],
        "creator_handoff",
        errors,
    )

    if handoff.get("schema_version") != CREATOR_HANDOFF_SCHEMA:
        errors.append("creator_handoff.schema_version:unsupported")
    if handoff.get("product_playbook_id") != playbook.get("product_playbook_id"):
        errors.append("creator_handoff.product_playbook_id:mismatch")
    if handoff.get("product_type") != playbook.get("product_type"):
        errors.append("creator_handoff.product_type:mismatch")
    if handoff.get("creator_execution_authorized") is not False:
        errors.append("creator_handoff.creator_execution_authorized:must_be_false")
    if handoff.get("provider_execution_required") is not False:
        errors.append("creator_handoff.provider_execution_required:must_be_false")

    asset_ids, reference_ids = _identity_sets(assets, references)
    allowed_roles = {
        str(role.get("role_id"))
        for role in playbook.get("asset_roles", [])
        if isinstance(role, Mapping) and role.get("role_id")
    }

    manifest = handoff.get("asset_manifest")
    if not isinstance(manifest, list):
        errors.append("creator_handoff.asset_manifest:must_be_list")
        manifest = []

    for index, item in enumerate(manifest):
        prefix = f"creator_handoff.asset_manifest[{index}]"
        if not isinstance(item, Mapping):
            errors.append(f"{prefix}:must_be_mapping")
            continue
        if _has_confidence(item):
            errors.append(f"{prefix}:confidence_forbidden")
        if "provenance" in item or "fingerprint_sha256" in item:
            errors.append(f"{prefix}:embedded_identity_or_provenance_forbidden")
        if item.get("role_id") not in allowed_roles:
            errors.append(f"{prefix}.role_id:unknown")

        source_kind = item.get("source_kind")
        source_id = item.get("source_id")
        if source_kind == "asset" and source_id not in asset_ids:
            errors.append(f"{prefix}.source_id:unknown_asset")
        elif source_kind == "reference" and source_id not in reference_ids:
            errors.append(f"{prefix}.source_id:unknown_reference")
        elif source_kind == "none" and source_id is not None:
            errors.append(f"{prefix}.source_id:must_be_null_for_none")
        elif source_kind not in SOURCE_KINDS:
            errors.append(f"{prefix}.source_kind:unsupported")

        state = item.get("mapping_state")
        human_required = item.get("human_confirmation_required")
        if state not in MAPPING_STATES:
            errors.append(f"{prefix}.mapping_state:unsupported")
        elif state in {"PROPOSED", "UNRESOLVED"} and human_required is not True:
            errors.append(f"{prefix}:ambiguous_state_requires_human_confirmation")
        elif state == "CONFIRMED" and human_required is not False:
            errors.append(f"{prefix}:confirmed_must_not_require_confirmation")

    return errors

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

BATCH_SCHEMA = "gdl_greeting_card_normalized_batch_v0_1"
BINDING_STATES = {"CONFIRMED", "PROPOSED", "UNRESOLVED"}
CONFIRMED_BASES = {
    "customer_assignment",
    "operator_assignment",
    "previously_confirmed",
    "unique_exact_alias_registry",
}
ASSET_BINDING_ROLES = {"portrait", "recipient_branding", "signature"}
SENDER_VARIANTS = {
    "SINGLE_PRIMARY",
    "SINGLE_SECONDARY",
    "DUAL_SENDER",
    "BILINGUAL_SENDER_BLOCK",
}


def _require(
    mapping: Mapping[str, Any],
    keys: tuple[str, ...],
    prefix: str,
    errors: list[str],
) -> None:
    for key in keys:
        if key not in mapping:
            errors.append(f"{prefix}.{key}:required")


def _has_confidence_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            "confidence" in str(key).lower() or _has_confidence_key(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_has_confidence_key(item) for item in value)
    return False


def _asset_ids(source_inventory: Mapping[str, Any]) -> set[str]:
    assets = source_inventory.get("assets", [])
    if not isinstance(assets, list):
        return set()
    return {
        str(item["asset_id"])
        for item in assets
        if isinstance(item, Mapping) and item.get("asset_id")
    }


def _entity_ids(entity_registry: Mapping[str, Any]) -> set[str]:
    entities = entity_registry.get("entities", [])
    if not isinstance(entities, list):
        return set()
    return {
        str(item["entity_id"])
        for item in entities
        if isinstance(item, Mapping) and item.get("entity_id")
    }


def _validate_state(
    binding: Mapping[str, Any],
    *,
    prefix: str,
    target_present: bool,
    errors: list[str],
) -> None:
    _require(
        binding,
        ("state", "basis", "human_confirmation_required"),
        prefix,
        errors,
    )
    state = binding.get("state")
    basis = binding.get("basis")
    human = binding.get("human_confirmation_required")

    if state not in BINDING_STATES:
        errors.append(f"{prefix}.state:unsupported")
        return

    if not isinstance(human, bool):
        errors.append(
            f"{prefix}.human_confirmation_required:must_be_boolean"
        )
        return

    if state == "CONFIRMED":
        if not target_present:
            errors.append(f"{prefix}:confirmed_requires_target")
        if basis not in CONFIRMED_BASES:
            errors.append(
                f"{prefix}:confirmed_requires_deterministic_basis"
            )
        if human:
            errors.append(
                f"{prefix}:confirmed_must_not_require_confirmation"
            )
    elif state == "PROPOSED":
        if not target_present:
            errors.append(f"{prefix}:proposed_requires_candidate")
        if not human:
            errors.append(
                f"{prefix}:proposed_requires_human_confirmation"
            )
    elif not human:
        errors.append(
            f"{prefix}:unresolved_requires_human_confirmation"
        )


def validate_greeting_card_normalized_batch(
    batch: Mapping[str, Any],
    *,
    source_inventory: Mapping[str, Any],
    entity_registry: Mapping[str, Any],
) -> list[str]:
    """Validate Intake-produced normalized recurring greeting-card jobs."""

    errors: list[str] = []
    _require(
        batch,
        (
            "schema_version",
            "batch_id",
            "request_id",
            "product_playbook_id",
            "product_type",
            "jobs",
        ),
        "batch",
        errors,
    )

    if batch.get("schema_version") != BATCH_SCHEMA:
        errors.append("batch.schema_version:unsupported")
    if batch.get("product_playbook_id") != "recurring_greeting_card_v0_1":
        errors.append("batch.product_playbook_id:mismatch")
    if batch.get("product_type") != "greeting_card":
        errors.append("batch.product_type:mismatch")
    if _has_confidence_key(batch):
        errors.append("batch:numeric_or_named_confidence_forbidden")

    asset_ids = _asset_ids(source_inventory)
    entity_ids = _entity_ids(entity_registry)

    jobs = batch.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        errors.append("batch.jobs:must_be_nonempty_list")
        return errors

    seen_job_ids: set[str] = set()

    for index, job in enumerate(jobs):
        prefix = f"batch.jobs[{index}]"
        if not isinstance(job, Mapping):
            errors.append(f"{prefix}:must_be_mapping")
            continue

        _require(
            job,
            (
                "job_id",
                "raw_recipient_name",
                "candidate_entity_id",
                "occasion",
                "greeting_text_source",
                "sender_variant",
                "supplied_assets",
                "special_requests",
                "uncertainties",
                "bindings",
            ),
            prefix,
            errors,
        )

        job_id = job.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            errors.append(f"{prefix}.job_id:must_be_nonempty_text")
        elif job_id in seen_job_ids:
            errors.append(f"{prefix}.job_id:duplicate")
        else:
            seen_job_ids.add(job_id)

        raw_name = job.get("raw_recipient_name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            errors.append(
                f"{prefix}.raw_recipient_name:must_be_nonempty_text"
            )

        occasion = job.get("occasion")
        if not isinstance(occasion, str) or not occasion.strip():
            errors.append(f"{prefix}.occasion:must_be_nonempty_text")

        supplied_assets = job.get("supplied_assets")
        if not isinstance(supplied_assets, list):
            errors.append(f"{prefix}.supplied_assets:must_be_list")
            supplied_assets = []
        else:
            for asset_id in supplied_assets:
                if asset_id not in asset_ids:
                    errors.append(
                        f"{prefix}.supplied_assets:unknown_asset:{asset_id}"
                    )

        if not isinstance(job.get("special_requests"), list):
            errors.append(f"{prefix}.special_requests:must_be_list")

        uncertainties = job.get("uncertainties")
        if not isinstance(uncertainties, list):
            errors.append(f"{prefix}.uncertainties:must_be_list")
            uncertainties = []

        bindings = job.get("bindings")
        if not isinstance(bindings, Mapping):
            errors.append(f"{prefix}.bindings:must_be_mapping")
            continue

        roles = (
            "recipient_entity",
            "greeting_text",
            "portrait",
            "recipient_branding",
            "signature",
            "sender_variant",
        )
        _require(bindings, roles, f"{prefix}.bindings", errors)

        recipient = bindings.get("recipient_entity", {})
        if isinstance(recipient, Mapping):
            entity_id = recipient.get("entity_id")
            _validate_state(
                recipient,
                prefix=f"{prefix}.bindings.recipient_entity",
                target_present=bool(entity_id),
                errors=errors,
            )
            if entity_id is not None and entity_id not in entity_ids:
                errors.append(
                    f"{prefix}.bindings.recipient_entity:"
                    f"unknown_entity:{entity_id}"
                )
            if job.get("candidate_entity_id") != entity_id:
                errors.append(
                    f"{prefix}.candidate_entity_id:"
                    "must_match_recipient_binding"
                )
        else:
            errors.append(
                f"{prefix}.bindings.recipient_entity:must_be_mapping"
            )

        greeting = bindings.get("greeting_text", {})
        if isinstance(greeting, Mapping):
            text = greeting.get("text")
            _validate_state(
                greeting,
                prefix=f"{prefix}.bindings.greeting_text",
                target_present=isinstance(text, str) and bool(text.strip()),
                errors=errors,
            )
            if greeting.get("source_ref") != job.get(
                "greeting_text_source"
            ):
                errors.append(
                    f"{prefix}.greeting_text_source:"
                    "must_match_greeting_binding"
                )
        else:
            errors.append(
                f"{prefix}.bindings.greeting_text:must_be_mapping"
            )

        for role in sorted(ASSET_BINDING_ROLES):
            binding = bindings.get(role, {})
            binding_prefix = f"{prefix}.bindings.{role}"
            if not isinstance(binding, Mapping):
                errors.append(f"{binding_prefix}:must_be_mapping")
                continue

            source_id = binding.get("source_id")
            _validate_state(
                binding,
                prefix=binding_prefix,
                target_present=bool(source_id),
                errors=errors,
            )
            if source_id is not None:
                if source_id not in asset_ids:
                    errors.append(
                        f"{binding_prefix}:unknown_asset:{source_id}"
                    )
                if source_id not in supplied_assets:
                    errors.append(
                        f"{binding_prefix}:"
                        "asset_not_declared_in_job_supplied_assets"
                    )

        sender = bindings.get("sender_variant", {})
        if isinstance(sender, Mapping):
            value = sender.get("value")
            _validate_state(
                sender,
                prefix=f"{prefix}.bindings.sender_variant",
                target_present=bool(value),
                errors=errors,
            )
            if value is not None and value not in SENDER_VARIANTS:
                errors.append(
                    f"{prefix}.bindings.sender_variant:"
                    f"unsupported_value:{value}"
                )
            if job.get("sender_variant") != value:
                errors.append(
                    f"{prefix}.sender_variant:"
                    "must_match_sender_binding"
                )
        else:
            errors.append(
                f"{prefix}.bindings.sender_variant:must_be_mapping"
            )

        ambiguous = any(
            isinstance(bindings.get(role), Mapping)
            and bindings[role].get("state") in {"PROPOSED", "UNRESOLVED"}
            for role in roles
        )
        if ambiguous and not uncertainties:
            errors.append(
                f"{prefix}.uncertainties:"
                "required_when_binding_is_ambiguous"
            )

    return errors

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from app.graphic_design_lab.greeting_card_batch import (
    validate_greeting_card_normalized_batch,
)
from app.graphic_design_lab.greeting_card_creator_review import (
    validate_creator_review_record,
)
from app.graphic_design_lab.greeting_card_signature_variants import (
    resolve_signature_configuration,
    validate_signature_variant_catalog,
)

BUNDLE_SCHEMA = "gdl_greeting_card_accepted_constructor_bundle_v0_1"
PROVENANCE_ALGORITHM = "sha256_canonical_json_v0_1"

REQUIRED_BINDING_ROLES = (
    "recipient_entity",
    "greeting_text",
    "portrait",
    "recipient_branding",
    "signature",
    "sender_variant",
)

KNOWN_FRONT_FAMILIES = {
    "STANDARD",
    "RECIPIENT_BRANDING_OVERLAY",
    "BILINGUAL_OCCASION",
}

SUPPORTED_ACCEPTANCE_BASES = {
    "CREATOR_INTERNAL_REVIEW_PASS",
}

AUTHORITY_FALSE_FIELDS = (
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


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _canonical_payload(bundle: Mapping[str, Any]) -> dict[str, Any]:
    payload = deepcopy(dict(bundle))
    provenance = _mapping(payload.get("provenance_manifest"))
    provenance["bundle_sha256"] = ""
    payload["provenance_manifest"] = provenance
    return payload


def compute_bundle_sha256(bundle: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        _canonical_payload(bundle),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def accepted_visual_from_creator_review(
    review_record: Mapping[str, Any],
) -> dict[str, Any]:
    review = deepcopy(dict(review_record))
    errors = validate_creator_review_record(review)
    if errors:
        raise ValueError(
            "creator_review_invalid:" + ";".join(errors)
        )

    if review.get("outcome") != "PASS":
        raise ValueError("creator_review_must_be_PASS")
    if review.get("accepted_for_constructor_bundle") is not True:
        raise ValueError(
            "creator_review_must_accept_constructor_bundle"
        )

    accepted = _list(review.get("accepted_artifact_refs"))
    if len(accepted) != 1:
        raise ValueError(
            "creator_review_requires_exactly_one_accepted_portrait"
        )

    trace = _mapping(review.get("task_traceability"))
    identity = _mapping(review.get("result_identity"))

    return {
        "job_id": trace.get("job_id"),
        "target_object_id": "inside_image.portrait",
        "source_asset_id": trace.get("source_asset_id"),
        "artifact_ref": accepted[0],
        "acceptance_basis": "CREATOR_INTERNAL_REVIEW_PASS",
        "review_id": review.get("review_id"),
        "result_id": identity.get("result_id"),
        "revision": identity.get("revision"),
        "provenance_sha256": identity.get("provenance_sha256"),
    }


def _require_confirmed_binding(
    binding: Mapping[str, Any],
    *,
    job_id: str,
    role: str,
) -> None:
    if binding.get("state") != "CONFIRMED":
        raise ValueError(
            f"constructor_binding_not_confirmed:{job_id}:{role}"
        )
    if binding.get("human_confirmation_required") is not False:
        raise ValueError(
            "constructor_binding_still_requires_confirmation:"
            f"{job_id}:{role}"
        )


def _branding_selection(
    binding: Mapping[str, Any],
    *,
    job_id: str,
) -> dict[str, Any]:
    source_id = binding.get("source_id")
    presence = binding.get("presence")

    if presence not in {"PRESENT", "ABSENT"}:
        raise ValueError(
            f"branding_presence_must_be_explicit:{job_id}"
        )
    if presence == "PRESENT" and not source_id:
        raise ValueError(
            f"branding_present_requires_source:{job_id}"
        )
    if presence == "ABSENT" and source_id is not None:
        raise ValueError(
            f"branding_absent_forbids_source:{job_id}"
        )

    return {
        "target_object_id": "front.recipient_branding",
        "presence": presence,
        "source_asset_id": source_id,
    }


def _semantic_family_hint(
    hint: Mapping[str, Any] | None,
    *,
    job_id: str,
) -> dict[str, Any] | None:
    if hint is None:
        return None

    item = _mapping(hint)
    family_id = item.get("family_id")
    basis = item.get("basis")

    if family_id not in KNOWN_FRONT_FAMILIES:
        raise ValueError(
            f"semantic_family_hint_invalid:{job_id}:{family_id}"
        )
    if not isinstance(basis, str) or not basis:
        raise ValueError(
            f"semantic_family_hint_basis_required:{job_id}"
        )

    return {
        "family_id": family_id,
        "basis": basis,
        "state": "RESOLVED",
    }


def _normalize_intake_review(
    review: Mapping[str, Any],
    *,
    source_batch_id: Any,
) -> dict[str, Any]:
    item = _mapping(review)

    if item.get("state") != "PASS":
        raise ValueError("intake_review_state_must_be_PASS")

    for field in ("review_id", "reviewer_source", "basis"):
        value = item.get(field)
        if not isinstance(value, str) or not value:
            raise ValueError(
                f"intake_review_{field}_required"
            )

    if item.get("basis") != "OPERATOR_REVIEWED_NORMALIZED_BATCH":
        raise ValueError("intake_review_basis_unsupported")

    if item.get("source_batch_id") != source_batch_id:
        raise ValueError("intake_review_source_batch_mismatch")

    if _has_confidence(item):
        raise ValueError("intake_review_confidence_forbidden")

    return {
        "review_id": item["review_id"],
        "reviewer_source": item["reviewer_source"],
        "basis": item["basis"],
        "state": "PASS",
        "source_batch_id": item["source_batch_id"],
    }


def build_accepted_constructor_bundle(
    normalized_batch: Mapping[str, Any],
    *,
    source_inventory: Mapping[str, Any],
    entity_registry: Mapping[str, Any],
    accepted_visuals_by_job: Mapping[str, Mapping[str, Any]],
    signature_catalog: Mapping[str, Any],
    intake_review: Mapping[str, Any],
    bundle_id: str,
    semantic_family_hints_by_job: (
        Mapping[str, Mapping[str, Any]] | None
    ) = None,
) -> dict[str, Any]:
    batch = deepcopy(dict(normalized_batch))
    inventory = deepcopy(dict(source_inventory))
    entities = deepcopy(dict(entity_registry))
    accepted_visuals = {
        str(job_id): deepcopy(dict(value))
        for job_id, value in accepted_visuals_by_job.items()
    }
    hints = {
        str(job_id): deepcopy(dict(value))
        for job_id, value in (
            semantic_family_hints_by_job or {}
        ).items()
    }

    batch_errors = validate_greeting_card_normalized_batch(
        batch,
        source_inventory=inventory,
        entity_registry=entities,
    )
    if batch_errors:
        raise ValueError(
            "normalized_batch_invalid:" + ";".join(batch_errors)
        )

    catalog_errors = validate_signature_variant_catalog(
        signature_catalog
    )
    if catalog_errors:
        raise ValueError(
            "signature_catalog_invalid:" + ";".join(catalog_errors)
        )

    normalized_intake_review = _normalize_intake_review(
        intake_review,
        source_batch_id=batch.get("batch_id"),
    )
    if not isinstance(bundle_id, str) or not bundle_id:
        raise ValueError("bundle_id_required")

    bundle_jobs: list[dict[str, Any]] = []

    for raw_job in _list(batch.get("jobs")):
        job = _mapping(raw_job)
        job_id = str(job.get("job_id"))
        bindings = _mapping(job.get("bindings"))

        if _list(job.get("uncertainties")):
            raise ValueError(
                f"constructor_job_uncertainties_must_be_empty:{job_id}"
            )

        for role in REQUIRED_BINDING_ROLES:
            _require_confirmed_binding(
                _mapping(bindings.get(role)),
                job_id=job_id,
                role=role,
            )

        recipient = _mapping(bindings.get("recipient_entity"))
        greeting = _mapping(bindings.get("greeting_text"))
        portrait = _mapping(bindings.get("portrait"))
        branding = _mapping(bindings.get("recipient_branding"))
        signature = _mapping(bindings.get("signature"))
        sender = _mapping(bindings.get("sender_variant"))

        entity_id = recipient.get("entity_id")
        greeting_text = greeting.get("text")
        portrait_source_id = portrait.get("source_id")
        signature_source_id = signature.get("source_id")
        signature_variant_id = signature.get("variant_id")
        sender_variant = sender.get("value")

        if not isinstance(entity_id, str) or not entity_id:
            raise ValueError(
                f"constructor_recipient_entity_required:{job_id}"
            )
        if not isinstance(greeting_text, str) or not greeting_text.strip():
            raise ValueError(
                f"constructor_greeting_text_required:{job_id}"
            )
        if not isinstance(portrait_source_id, str) or not portrait_source_id:
            raise ValueError(
                f"constructor_portrait_source_required:{job_id}"
            )
        if not isinstance(signature_source_id, str) or not signature_source_id:
            raise ValueError(
                f"constructor_signature_source_required:{job_id}"
            )
        if (
            not isinstance(signature_variant_id, str)
            or not signature_variant_id
        ):
            raise ValueError(
                f"constructor_signature_variant_id_required:{job_id}"
            )
        if not isinstance(sender_variant, str) or not sender_variant:
            raise ValueError(
                f"constructor_sender_variant_required:{job_id}"
            )

        signature_config = resolve_signature_configuration(
            signature_catalog,
            variant_id=signature_variant_id,
            sender_variant=sender_variant,
        )

        visual = _mapping(accepted_visuals.get(job_id))
        if not visual:
            raise ValueError(f"accepted_visual_missing:{job_id}")
        if visual.get("job_id") != job_id:
            raise ValueError(
                f"accepted_visual_job_mismatch:{job_id}"
            )
        if visual.get("target_object_id") != "inside_image.portrait":
            raise ValueError(
                f"accepted_visual_target_mismatch:{job_id}"
            )
        if visual.get("source_asset_id") != portrait_source_id:
            raise ValueError(
                f"accepted_visual_source_mismatch:{job_id}"
            )
        if not isinstance(visual.get("artifact_ref"), str):
            raise ValueError(
                f"accepted_visual_artifact_ref_required:{job_id}"
            )

        hint = _semantic_family_hint(
            hints.get(job_id),
            job_id=job_id,
        )

        exact_bindings = {
            "recipient_entity": {
                "entity_id": entity_id,
            },
            "occasion_text": {
                "target_object_id": "front.occasion_text",
                "value": job.get("occasion"),
            },
            "greeting_text": {
                "target_object_id": "inside_text.greeting",
                "value": greeting_text,
                "source_ref": greeting.get("source_ref"),
            },
            "portrait": {
                "target_object_id": "inside_image.portrait",
                "source_asset_id": portrait_source_id,
                "accepted_artifact_ref": visual.get("artifact_ref"),
            },
            "recipient_branding": _branding_selection(
                branding,
                job_id=job_id,
            ),
            "sender_block": {
                "target_object_id": "inside_text.sender_block",
                "sender_variant": sender_variant,
                "signature_variant_id": signature_variant_id,
            },
            "signature": {
                "target_object_id": "inside_text.signature",
                "source_asset_id": signature_source_id,
                "signature_variant_id": signature_variant_id,
            },
        }

        bundle_job = {
            "job_id": job_id,
            "structured_greeting_data": {
                "recipient_entity_id": entity_id,
                "occasion": job.get("occasion"),
                "greeting_text": greeting_text,
                "greeting_text_source": greeting.get("source_ref"),
            },
            "exact_person_text_asset_bindings": exact_bindings,
            "accepted_visual_assets": [visual],
            "branding_selection": exact_bindings[
                "recipient_branding"
            ],
            "signature_selection": {
                "variant_id": signature_variant_id,
                "sender_variant": sender_variant,
                "signature_source_asset_id": signature_source_id,
                "signature_component_count": signature_config.get(
                    "signature_component_count"
                ),
                "coupled_object_ids": list(
                    signature_config.get("coupled_object_ids", [])
                ),
            },
        }
        if hint is not None:
            bundle_job["semantic_family_hint"] = hint

        bundle_jobs.append(bundle_job)

    bundle = {
        "schema_version": BUNDLE_SCHEMA,
        "bundle_id": bundle_id,
        "constructor_input_class": "ACCEPTED_CONSTRUCTOR_BUNDLE",
        "source_batch_id": batch.get("batch_id"),
        "source_request_id": batch.get("request_id"),
        "product_playbook_id": batch.get("product_playbook_id"),
        "product_type": batch.get("product_type"),
        "intake_review": normalized_intake_review,
        "jobs": bundle_jobs,
        "provenance_manifest": {
            "algorithm": PROVENANCE_ALGORITHM,
            "bundle_sha256": "",
            "source_batch_id": batch.get("batch_id"),
            "intake_review_id": normalized_intake_review.get(
                "review_id"
            ),
            "accepted_visual_review_ids": sorted(
                {
                    str(item.get("review_id"))
                    for item in accepted_visuals.values()
                    if item.get("review_id")
                }
            ),
            "signature_catalog_id": signature_catalog.get(
                "catalog_id"
            ),
        },
        "authority": {
            "provider_execution_performed": False,
            "gdl_runtime_initialized": False,
            "production_write_enabled": False,
            "automatic_customer_messaging": False,
            "automatic_design_approval": False,
        },
    }

    bundle["provenance_manifest"]["bundle_sha256"] = (
        compute_bundle_sha256(bundle)
    )

    errors = validate_accepted_constructor_bundle(
        bundle,
        signature_catalog=signature_catalog,
    )
    if errors:
        raise ValueError(
            "accepted_constructor_bundle_invalid:"
            + ";".join(errors)
        )

    return bundle


def validate_accepted_constructor_bundle(
    bundle: Mapping[str, Any],
    *,
    signature_catalog: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    if not isinstance(bundle, Mapping):
        return ["bundle:must_be_mapping"]

    if bundle.get("schema_version") != BUNDLE_SCHEMA:
        errors.append("bundle.schema_version:unsupported")
    if bundle.get("constructor_input_class") != (
        "ACCEPTED_CONSTRUCTOR_BUNDLE"
    ):
        errors.append(
            "bundle.constructor_input_class:"
            "must_be_ACCEPTED_CONSTRUCTOR_BUNDLE"
        )
    try:
        normalized_intake_review = _normalize_intake_review(
            _mapping(bundle.get("intake_review")),
            source_batch_id=bundle.get("source_batch_id"),
        )
    except ValueError as exc:
        errors.append(f"bundle.intake_review:{exc}")
    else:
        if _mapping(bundle.get("intake_review")) != (
            normalized_intake_review
        ):
            errors.append(
                "bundle.intake_review:not_canonical"
            )

    if _has_confidence(bundle):
        errors.append("bundle:numeric_or_named_confidence_forbidden")

    for field in (
        "bundle_id",
        "source_batch_id",
        "source_request_id",
        "product_playbook_id",
        "product_type",
    ):
        value = bundle.get(field)
        if not isinstance(value, str) or not value:
            errors.append(f"bundle.{field}:required")

    catalog_errors = validate_signature_variant_catalog(
        signature_catalog
    )
    errors.extend(catalog_errors)

    jobs = _list(bundle.get("jobs"))
    if not jobs:
        errors.append("bundle.jobs:must_be_nonempty_list")

    seen_job_ids: set[str] = set()

    for index, raw in enumerate(jobs):
        prefix = f"bundle.jobs[{index}]"
        job = _mapping(raw)

        job_id = job.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            errors.append(f"{prefix}.job_id:required")
        elif job_id in seen_job_ids:
            errors.append(f"{prefix}.job_id:duplicate")
        else:
            seen_job_ids.add(job_id)

        structured = _mapping(
            job.get("structured_greeting_data")
        )
        for field in (
            "recipient_entity_id",
            "occasion",
            "greeting_text",
            "greeting_text_source",
        ):
            value = structured.get(field)
            if not isinstance(value, str) or not value:
                errors.append(
                    f"{prefix}.structured_greeting_data."
                    f"{field}:required"
                )

        exact = _mapping(
            job.get("exact_person_text_asset_bindings")
        )
        required_exact = {
            "recipient_entity",
            "occasion_text",
            "greeting_text",
            "portrait",
            "recipient_branding",
            "sender_block",
            "signature",
        }
        missing_exact = sorted(
            required_exact.difference(exact)
        )
        for field in missing_exact:
            errors.append(
                f"{prefix}.exact_person_text_asset_bindings."
                f"{field}:required"
            )

        canonical_targets = {
            "occasion_text": "front.occasion_text",
            "greeting_text": "inside_text.greeting",
            "portrait": "inside_image.portrait",
            "recipient_branding": "front.recipient_branding",
            "sender_block": "inside_text.sender_block",
            "signature": "inside_text.signature",
        }
        for role, expected_target in canonical_targets.items():
            if _mapping(exact.get(role)).get(
                "target_object_id"
            ) != expected_target:
                errors.append(
                    f"{prefix}.exact_person_text_asset_bindings."
                    f"{role}.target_object_id:mismatch"
                )

        branding = _mapping(job.get("branding_selection"))
        presence = branding.get("presence")
        source_id = branding.get("source_asset_id")
        if branding.get("target_object_id") != (
            "front.recipient_branding"
        ):
            errors.append(
                f"{prefix}.branding_selection.target_object_id:"
                "mismatch"
            )
        if presence not in {"PRESENT", "ABSENT"}:
            errors.append(
                f"{prefix}.branding_selection.presence:invalid"
            )
        if presence == "PRESENT" and not source_id:
            errors.append(
                f"{prefix}.branding_selection:"
                "present_requires_source_asset"
            )
        if presence == "ABSENT" and source_id is not None:
            errors.append(
                f"{prefix}.branding_selection:"
                "absent_forbids_source_asset"
            )

        visuals = _list(job.get("accepted_visual_assets"))
        if len(visuals) != 1:
            errors.append(
                f"{prefix}.accepted_visual_assets:"
                "exactly_one_portrait_required"
            )
        else:
            visual = _mapping(visuals[0])
            if visual.get("job_id") != job_id:
                errors.append(
                    f"{prefix}.accepted_visual_assets[0]."
                    "job_id:mismatch"
                )
            if visual.get("target_object_id") != (
                "inside_image.portrait"
            ):
                errors.append(
                    f"{prefix}.accepted_visual_assets[0]."
                    "target_object_id:mismatch"
                )
            if not isinstance(
                visual.get("artifact_ref"), str
            ) or not visual.get("artifact_ref"):
                errors.append(
                    f"{prefix}.accepted_visual_assets[0]."
                    "artifact_ref:required"
                )
            if visual.get("acceptance_basis") not in (
                SUPPORTED_ACCEPTANCE_BASES
            ):
                errors.append(
                    f"{prefix}.accepted_visual_assets[0]."
                    "acceptance_basis:unsupported"
                )
            else:
                for field in ("review_id", "result_id"):
                    if not isinstance(visual.get(field), str) or not (
                        visual.get(field)
                    ):
                        errors.append(
                            f"{prefix}.accepted_visual_assets[0]."
                            f"{field}:required"
                        )
                revision = visual.get("revision")
                if (
                    not isinstance(revision, int)
                    or isinstance(revision, bool)
                    or revision < 1
                ):
                    errors.append(
                        f"{prefix}.accepted_visual_assets[0]."
                        "revision:invalid"
                    )
                if not _is_sha256(
                    visual.get("provenance_sha256")
                ):
                    errors.append(
                        f"{prefix}.accepted_visual_assets[0]."
                        "provenance_sha256:invalid"
                    )

        signature = _mapping(job.get("signature_selection"))
        variant_id = signature.get("variant_id")
        sender_variant = signature.get("sender_variant")
        try:
            config = resolve_signature_configuration(
                signature_catalog,
                variant_id=str(variant_id),
                sender_variant=str(sender_variant),
            )
        except ValueError as exc:
            errors.append(
                f"{prefix}.signature_selection:{exc}"
            )
        else:
            if signature.get("signature_component_count") != (
                config.get("signature_component_count")
            ):
                errors.append(
                    f"{prefix}.signature_selection."
                    "signature_component_count:mismatch"
                )
            if list(signature.get("coupled_object_ids", [])) != (
                list(config.get("coupled_object_ids", []))
            ):
                errors.append(
                    f"{prefix}.signature_selection."
                    "coupled_object_ids:mismatch"
                )

        if not isinstance(
            signature.get("signature_source_asset_id"), str
        ) or not signature.get("signature_source_asset_id"):
            errors.append(
                f"{prefix}.signature_selection."
                "signature_source_asset_id:required"
            )

        recipient_exact = _mapping(exact.get("recipient_entity"))
        occasion_exact = _mapping(exact.get("occasion_text"))
        greeting_exact = _mapping(exact.get("greeting_text"))
        portrait_exact = _mapping(exact.get("portrait"))
        branding_exact = _mapping(exact.get("recipient_branding"))
        sender_exact = _mapping(exact.get("sender_block"))
        signature_exact = _mapping(exact.get("signature"))

        if structured.get("recipient_entity_id") != (
            recipient_exact.get("entity_id")
        ):
            errors.append(
                f"{prefix}.structured_greeting_data."
                "recipient_entity_id:binding_mismatch"
            )
        if structured.get("occasion") != occasion_exact.get("value"):
            errors.append(
                f"{prefix}.structured_greeting_data."
                "occasion:binding_mismatch"
            )
        if structured.get("greeting_text") != greeting_exact.get("value"):
            errors.append(
                f"{prefix}.structured_greeting_data."
                "greeting_text:binding_mismatch"
            )

        if visuals:
            visual = _mapping(visuals[0])
            if portrait_exact.get("source_asset_id") != (
                visual.get("source_asset_id")
            ):
                errors.append(
                    f"{prefix}.exact_person_text_asset_bindings."
                    "portrait:source_mismatch"
                )
            if portrait_exact.get("accepted_artifact_ref") != (
                visual.get("artifact_ref")
            ):
                errors.append(
                    f"{prefix}.exact_person_text_asset_bindings."
                    "portrait:artifact_mismatch"
                )

        if branding_exact != branding:
            errors.append(
                f"{prefix}.branding_selection:"
                "exact_binding_mismatch"
            )

        if sender_exact.get("sender_variant") != sender_variant:
            errors.append(
                f"{prefix}.signature_selection."
                "sender_variant:binding_mismatch"
            )
        if sender_exact.get("signature_variant_id") != variant_id:
            errors.append(
                f"{prefix}.signature_selection."
                "variant_id:sender_binding_mismatch"
            )
        if signature_exact.get("signature_variant_id") != variant_id:
            errors.append(
                f"{prefix}.signature_selection."
                "variant_id:signature_binding_mismatch"
            )
        if signature_exact.get("source_asset_id") != (
            signature.get("signature_source_asset_id")
        ):
            errors.append(
                f"{prefix}.signature_selection."
                "signature_source_asset_id:binding_mismatch"
            )

        if "semantic_family_hint" in job:
            hint = _mapping(job.get("semantic_family_hint"))
            if hint.get("family_id") not in KNOWN_FRONT_FAMILIES:
                errors.append(
                    f"{prefix}.semantic_family_hint.family_id:"
                    "invalid"
                )
            if hint.get("state") != "RESOLVED":
                errors.append(
                    f"{prefix}.semantic_family_hint.state:"
                    "must_be_RESOLVED"
                )
            if not isinstance(hint.get("basis"), str) or not (
                hint.get("basis")
            ):
                errors.append(
                    f"{prefix}.semantic_family_hint.basis:required"
                )

    provenance = _mapping(bundle.get("provenance_manifest"))
    if provenance.get("algorithm") != PROVENANCE_ALGORITHM:
        errors.append(
            "bundle.provenance_manifest.algorithm:mismatch"
        )

    digest = provenance.get("bundle_sha256")
    if not _is_sha256(digest):
        errors.append(
            "bundle.provenance_manifest.bundle_sha256:invalid"
        )
    elif digest != compute_bundle_sha256(bundle):
        errors.append(
            "bundle.provenance_manifest.bundle_sha256:mismatch"
        )

    intake_review = _mapping(bundle.get("intake_review"))
    if provenance.get("intake_review_id") != intake_review.get(
        "review_id"
    ):
        errors.append(
            "bundle.provenance_manifest.intake_review_id:mismatch"
        )

    if provenance.get("source_batch_id") != bundle.get(
        "source_batch_id"
    ):
        errors.append(
            "bundle.provenance_manifest.source_batch_id:mismatch"
        )
    if provenance.get("signature_catalog_id") != signature_catalog.get(
        "catalog_id"
    ):
        errors.append(
            "bundle.provenance_manifest.signature_catalog_id:mismatch"
        )

    expected_review_ids = sorted(
        {
            str(_mapping(item).get("review_id"))
            for raw_job in jobs
            for item in _list(
                _mapping(raw_job).get("accepted_visual_assets")
            )
            if _mapping(item).get("acceptance_basis")
            == "CREATOR_INTERNAL_REVIEW_PASS"
            and _mapping(item).get("review_id")
        }
    )
    if provenance.get("accepted_visual_review_ids") != expected_review_ids:
        errors.append(
            "bundle.provenance_manifest."
            "accepted_visual_review_ids:mismatch"
        )

    authority = _mapping(bundle.get("authority"))
    for field in AUTHORITY_FALSE_FIELDS:
        if authority.get(field) is not False:
            errors.append(
                f"bundle.authority.{field}:must_be_false"
            )

    return errors

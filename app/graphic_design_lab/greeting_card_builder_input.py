
from __future__ import annotations

import re
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from app.graphic_design_lab.greeting_card_constructor_bundle import (
    compute_bundle_sha256,
    validate_accepted_constructor_bundle,
)

BUILDER_PAYLOAD_SCHEMA = "gdl_greeting_card_builder_payload_v0_1"
KNOWN_FRONT_FAMILIES = {
    "STANDARD",
    "RECIPIENT_BRANDING_OVERLAY",
    "BILINGUAL_OCCASION",
}
KNOWN_IMAGE_MODES = {"PORTRAIT", "DEFAULT_ASSET"}
REVISION_RE = re.compile(r"^r[0-9]{3}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def validate_builder_payload_v1(
    payload: Mapping[str, Any],
    *,
    prefix: str = "builder_v1",
) -> list[str]:
    errors: list[str] = []
    item = _mapping(payload)

    if item.get("schema_version") != BUILDER_PAYLOAD_SCHEMA:
        errors.append(f"{prefix}.schema_version:unsupported")

    revision = item.get("revision")
    if not isinstance(revision, str) or REVISION_RE.fullmatch(revision) is None:
        errors.append(f"{prefix}.revision:invalid")

    front = _mapping(item.get("front"))
    family = front.get("family")
    if family not in KNOWN_FRONT_FAMILIES:
        errors.append(f"{prefix}.front.family:invalid")

    occasion = _mapping(front.get("occasion"))
    display_text = occasion.get("display_text")
    if not isinstance(display_text, str) or not display_text.strip():
        errors.append(f"{prefix}.front.occasion.display_text:required")

    inside_image = _mapping(item.get("inside_image"))
    mode = inside_image.get("mode")
    if mode not in KNOWN_IMAGE_MODES:
        errors.append(f"{prefix}.inside_image.mode:invalid")

    asset_id = inside_image.get("asset_id")
    if not isinstance(asset_id, str) or not asset_id:
        errors.append(f"{prefix}.inside_image.asset_id:required")

    asset_sha256 = inside_image.get("asset_sha256")
    if not _valid_sha256(asset_sha256):
        errors.append(f"{prefix}.inside_image.asset_sha256:invalid")

    artifact_ref = inside_image.get("accepted_artifact_ref")
    if mode == "PORTRAIT":
        if not isinstance(artifact_ref, str) or not artifact_ref:
            errors.append(
                f"{prefix}.inside_image.accepted_artifact_ref:"
                "required_for_portrait"
            )
    elif mode == "DEFAULT_ASSET" and artifact_ref is not None:
        errors.append(
            f"{prefix}.inside_image.accepted_artifact_ref:"
            "forbidden_for_default_asset"
        )

    sender = _mapping(item.get("sender_text"))
    lines = _list(sender.get("lines"))
    if not lines:
        errors.append(f"{prefix}.sender_text.lines:must_be_nonempty")

    seen_ids: set[str] = set()
    for idx, raw in enumerate(lines):
        line = _mapping(raw)
        line_id = line.get("id")
        line_text = line.get("text")

        if not isinstance(line_id, str) or not line_id:
            errors.append(f"{prefix}.sender_text.lines[{idx}].id:required")
        elif line_id in seen_ids:
            errors.append(f"{prefix}.sender_text.lines[{idx}].id:duplicate")
        else:
            seen_ids.add(line_id)

        if not isinstance(line_text, str) or not line_text.strip():
            errors.append(f"{prefix}.sender_text.lines[{idx}].text:required")

    return errors


def validate_builder_ready_bundle_v1(
    bundle: Mapping[str, Any],
    *,
    signature_catalog: Mapping[str, Any],
) -> list[str]:
    errors = validate_accepted_constructor_bundle(
        bundle,
        signature_catalog=signature_catalog,
    )

    jobs = _list(bundle.get("jobs"))

    for idx, raw_job in enumerate(jobs):
        job = _mapping(raw_job)
        prefix = f"bundle.jobs[{idx}]"

        payload = _mapping(job.get("builder_v1"))
        errors.extend(
            validate_builder_payload_v1(
                payload,
                prefix=f"{prefix}.builder_v1",
            )
        )

        if not payload:
            continue

        structured = _mapping(job.get("structured_greeting_data"))
        exact = _mapping(job.get("exact_person_text_asset_bindings"))
        branding = _mapping(job.get("branding_selection"))
        signature = _mapping(job.get("signature_selection"))

        front = _mapping(payload.get("front"))
        family = front.get("family")
        branding_presence = branding.get("presence")

        if (
            branding_presence == "PRESENT"
            and family != "RECIPIENT_BRANDING_OVERLAY"
        ):
            errors.append(
                f"{prefix}.builder_v1.front.family:"
                "branding_present_requires_overlay_family"
            )

        if (
            branding_presence == "ABSENT"
            and family == "RECIPIENT_BRANDING_OVERLAY"
        ):
            errors.append(
                f"{prefix}.builder_v1.front.family:"
                "branding_absent_forbids_overlay_family"
            )

        occasion = _mapping(front.get("occasion"))
        if occasion.get("kind") != structured.get("occasion"):
            errors.append(
                f"{prefix}.builder_v1.front.occasion.kind:"
                "must_match_structured_occasion"
            )

        image = _mapping(payload.get("inside_image"))
        exact_portrait = _mapping(exact.get("portrait"))
        base_source_id = exact_portrait.get("source_asset_id")

        if image.get("asset_id") != base_source_id:
            errors.append(
                f"{prefix}.builder_v1.inside_image.asset_id:"
                "must_match_exact_portrait_binding"
            )

        visuals = _list(job.get("accepted_visual_assets"))
        visual = _mapping(visuals[0]) if len(visuals) == 1 else {}

        if image.get("mode") == "PORTRAIT":
            if image.get("accepted_artifact_ref") != visual.get("artifact_ref"):
                errors.append(
                    f"{prefix}.builder_v1.inside_image.accepted_artifact_ref:"
                    "must_match_accepted_visual"
                )

        sender = _mapping(payload.get("sender_text"))
        if (
            sender.get("signature_variant_id")
            != signature.get("variant_id")
        ):
            errors.append(
                f"{prefix}.builder_v1.sender_text.signature_variant_id:"
                "must_match_signature_selection"
            )

    recorded = _mapping(
        bundle.get("provenance_manifest")
    ).get("bundle_sha256")

    if recorded != compute_bundle_sha256(bundle):
        errors.append(
            "bundle.provenance_manifest.bundle_sha256:mismatch"
        )

    return errors


def attach_builder_payload_v1(
    bundle: Mapping[str, Any],
    *,
    payload_by_job: Mapping[str, Mapping[str, Any]],
    signature_catalog: Mapping[str, Any],
) -> dict[str, Any]:
    candidate = deepcopy(dict(bundle))

    base_errors = validate_accepted_constructor_bundle(
        candidate,
        signature_catalog=signature_catalog,
    )
    if base_errors:
        raise ValueError(
            "accepted_constructor_bundle_invalid:"
            + ";".join(base_errors)
        )

    jobs = _list(candidate.get("jobs"))
    expected_ids = {
        str(_mapping(job).get("job_id"))
        for job in jobs
    }
    supplied_ids = {str(key) for key in payload_by_job}

    if supplied_ids != expected_ids:
        missing = sorted(expected_ids.difference(supplied_ids))
        extra = sorted(supplied_ids.difference(expected_ids))
        raise ValueError(
            "builder_v1_payload_job_set_mismatch:"
            f"missing={missing}:extra={extra}"
        )

    for job in jobs:
        job_id = str(_mapping(job).get("job_id"))
        payload = deepcopy(dict(payload_by_job[job_id]))

        payload_errors = validate_builder_payload_v1(
            payload,
            prefix=f"payload_by_job.{job_id}",
        )
        if payload_errors:
            raise ValueError(
                "builder_v1_payload_invalid:"
                + ";".join(payload_errors)
            )

        job["builder_v1"] = payload

    provenance = _mapping(candidate.get("provenance_manifest"))
    provenance["bundle_sha256"] = ""
    candidate["provenance_manifest"] = provenance
    provenance["bundle_sha256"] = compute_bundle_sha256(candidate)

    errors = validate_builder_ready_bundle_v1(
        candidate,
        signature_catalog=signature_catalog,
    )
    if errors:
        raise ValueError(
            "builder_ready_bundle_invalid:"
            + ";".join(errors)
        )

    return candidate

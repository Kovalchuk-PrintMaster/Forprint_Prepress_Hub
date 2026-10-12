"""Fail-closed metadata/readiness catalog for greeting-card signatures.

This catalog deliberately does not dispatch PDF rendering. Existing GRIGO and
HERASYMENKO render implementations remain in the project-owned renderer.
A registered SOURCE_VERIFIED variant is *not* an executable capability.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

SCHEMA_VERSION = "gdl_greeting_card_signature_registry_v0_1"
VALID_STATES = frozenset({"PROPOSED", "SOURCE_VERIFIED", "MACHINE_VERIFIED"})
VALID_COMPONENT_KINDS = frozenset({"VECTOR_CLIP", "EMBEDDED_IMAGE", "COMPOSITE", "COMPOSITE_CANDIDATE"})
_ID = re.compile(r"^[A-Z][A-Z0-9_]*$")
_RESOURCE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


class SignatureRegistryError(ValueError):
    """A malformed or unapproved signature request/registration."""


class _NoDuplicateKeysLoader(yaml.SafeLoader):
    pass


def _unique_mapping(loader: yaml.SafeLoader, node: yaml.MappingNode) -> dict:
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if key in result:
            raise SignatureRegistryError("duplicate_registry_key")
        result[key] = loader.construct_object(value_node, deep=True)
    return result


_NoDuplicateKeysLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping
)


def validate_registry(data: Any) -> dict:
    """Validate semantics before using any registration as capability evidence."""
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        raise SignatureRegistryError("signature_registry_schema_invalid")
    if data.get("registry_role") != "IMPLEMENTATION_READINESS_AND_COMPONENT_METADATA":
        raise SignatureRegistryError("signature_registry_role_invalid")
    policy = data.get("policy")
    required_policy = {
        "unknown_variant": "REJECT",
        "unverified_variant": "REJECT",
        "silent_fallback": "FORBIDDEN",
        "production_promotion": "HUMAN_GATE_REQUIRED",
        "new_builder_for_each_signature": False,
    }
    if not isinstance(policy, dict) or any(policy.get(k) != v for k, v in required_policy.items()):
        raise SignatureRegistryError("signature_registry_fail_closed_policy_invalid")
    variants = data.get("variants")
    if not isinstance(variants, dict) or not variants:
        raise SignatureRegistryError("signature_registry_variants_missing")
    for variant_id, entry in variants.items():
        if not isinstance(variant_id, str) or not _ID.fullmatch(variant_id):
            raise SignatureRegistryError("signature_variant_id_invalid")
        if not isinstance(entry, dict):
            raise SignatureRegistryError("signature_variant_entry_invalid:" + variant_id)
        state = entry.get("state")
        if state not in VALID_STATES:
            raise SignatureRegistryError("signature_variant_state_invalid:" + variant_id)
        enabled = entry.get("runtime_enabled")
        if type(enabled) is not bool:
            raise SignatureRegistryError("signature_variant_runtime_flag_invalid:" + variant_id)
        resource = entry.get("source_resource_id")
        if not isinstance(resource, str) or not _RESOURCE_ID.fullmatch(resource):
            raise SignatureRegistryError("signature_variant_resource_id_invalid:" + variant_id)
        if type(entry.get("source_physical_page")) is not int or entry["source_physical_page"] != 4:
            raise SignatureRegistryError("signature_variant_source_page_invalid:" + variant_id)
        if entry.get("component_kind") not in VALID_COMPONENT_KINDS:
            raise SignatureRegistryError("signature_variant_component_kind_invalid:" + variant_id)
        if type(entry.get("signer_count")) is not int or not (1 <= entry["signer_count"] <= 8):
            raise SignatureRegistryError("signature_variant_signer_count_invalid:" + variant_id)
        if entry.get("atomic_binding") != "SIGNER_TEXT_AND_SIGNATURE":
            raise SignatureRegistryError("signature_variant_text_component_binding_invalid:" + variant_id)
        if entry.get("visual_review") != "REQUIRED" or entry.get("production_ready") is not False:
            raise SignatureRegistryError("signature_variant_production_gate_invalid:" + variant_id)
        adapter = entry.get("renderer_adapter")
        identity = entry.get("identity_profile")
        if enabled:
            if state != "MACHINE_VERIFIED":
                raise SignatureRegistryError("unverified_signature_enabled:" + variant_id)
            if not isinstance(adapter, str) or not _ID.fullmatch(adapter):
                raise SignatureRegistryError("verified_signature_adapter_missing:" + variant_id)
            if not isinstance(identity, str) or not _ID.fullmatch(identity) or identity.startswith("PENDING"):
                raise SignatureRegistryError("verified_signature_identity_missing:" + variant_id)
            if entry["component_kind"] == "COMPOSITE_CANDIDATE":
                raise SignatureRegistryError("unvalidated_composite_enabled:" + variant_id)
        else:
            if state == "MACHINE_VERIFIED":
                raise SignatureRegistryError("verified_variant_disabled_requires_review:" + variant_id)
            if adapter is not None:
                raise SignatureRegistryError("inactive_signature_must_not_have_adapter:" + variant_id)
    return data


def load_registry(path: Path) -> dict:
    """Load an exact catalog path; no fuzzy search and no private asset paths."""
    try:
        with Path(path).open("r", encoding="utf-8") as source:
            data = yaml.load(source, Loader=_NoDuplicateKeysLoader)
    except (OSError, yaml.YAMLError) as exc:
        raise SignatureRegistryError("signature_registry_unreadable") from exc
    return validate_registry(data)


def enabled_variant_ids(registry: dict) -> list[str]:
    """Derive implemented signature IDs from validated metadata."""
    validate_registry(registry)
    return [name for name, item in registry["variants"].items() if item["runtime_enabled"]]


def resolve_enabled_variant(registry: dict, requested: str) -> dict:
    """Fail closed for unknown, source-only or unverified signature selections."""
    validate_registry(registry)
    entry = registry["variants"].get(requested)
    if not entry or not entry["runtime_enabled"]:
        raise SignatureRegistryError("signature_variant_not_implemented")
    return dict(entry)

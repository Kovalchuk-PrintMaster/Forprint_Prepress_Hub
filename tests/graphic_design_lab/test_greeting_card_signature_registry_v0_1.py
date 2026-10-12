"""GC-E2E-09C registry lifecycle and fail-closed regression tests."""
import copy
from pathlib import Path

import pytest

from app.graphic_design_lab.greeting_card_signature_registry import (
    SignatureRegistryError,
    enabled_variant_ids,
    load_registry,
    resolve_enabled_variant,
    validate_registry,
)

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "coordination/graphic_design_lab/directions/greeting_cards/signature_registry_v0_1.yaml"


def current():
    return load_registry(REGISTRY)


def test_existing_two_signatures_remain_runtime_enabled():
    assert enabled_variant_ids(current()) == ["GRIGO", "HERASYMENKO"]


def test_dual_is_registered_but_not_promoted_to_renderer():
    data = current()
    assert data["variants"]["DUAL_GRIGO_HERASYMENKO"]["state"] == "SOURCE_VERIFIED"
    assert data["variants"]["DUAL_GRIGO_HERASYMENKO"]["runtime_enabled"] is False
    with pytest.raises(SignatureRegistryError, match="not_implemented"):
        resolve_enabled_variant(data, "DUAL_GRIGO_HERASYMENKO")


def test_known_single_variants_resolve():
    for name in ("GRIGO", "HERASYMENKO"):
        assert resolve_enabled_variant(current(), name)["runtime_enabled"] is True


def test_unknown_variant_has_no_fallback():
    with pytest.raises(SignatureRegistryError, match="not_implemented"):
        resolve_enabled_variant(current(), "UNREGISTERED")


def test_new_future_variant_can_be_registered_as_nonruntime():
    data = copy.deepcopy(current())
    data["variants"]["FUTURE_SIGNATURE"] = {
        "state": "PROPOSED", "runtime_enabled": False,
        "source_resource_id": "source.greeting_card.signature.future.v1",
        "source_physical_page": 4, "component_kind": "COMPOSITE_CANDIDATE",
        "signer_count": 2, "atomic_binding": "SIGNER_TEXT_AND_SIGNATURE",
        "renderer_adapter": None, "identity_profile": "PENDING_COMPONENT_ISOLATION",
        "visual_review": "REQUIRED", "production_ready": False,
    }
    assert enabled_variant_ids(data) == ["GRIGO", "HERASYMENKO"]


def test_source_verified_variant_cannot_be_enabled_by_yaml_flag():
    data = copy.deepcopy(current())
    data["variants"]["DUAL_GRIGO_HERASYMENKO"]["runtime_enabled"] = True
    with pytest.raises(SignatureRegistryError, match="unverified_signature_enabled"):
        validate_registry(data)


def test_future_variant_without_adapter_cannot_claim_machine_verified():
    data = copy.deepcopy(current())
    data["variants"]["DUAL_GRIGO_HERASYMENKO"]["state"] = "MACHINE_VERIFIED"
    data["variants"]["DUAL_GRIGO_HERASYMENKO"]["runtime_enabled"] = True
    with pytest.raises(SignatureRegistryError, match="adapter_missing"):
        validate_registry(data)


def test_verified_composite_variant_could_be_registered_after_implementation():
    # Contract-level flexibility only: a real production change must still add
    # the adapter, tests, exact component proof and full dual-PDF smoke.
    data = copy.deepcopy(current())
    dual = data["variants"]["DUAL_GRIGO_HERASYMENKO"]
    dual.update({
        "state": "MACHINE_VERIFIED", "runtime_enabled": True,
        "component_kind": "COMPOSITE",
        "renderer_adapter": "DUAL_EXACT_COMPONENT_V0_1",
        "identity_profile": "EXACT_COMPOSITE_COMPONENT",
    })
    assert enabled_variant_ids(data) == ["GRIGO", "HERASYMENKO", "DUAL_GRIGO_HERASYMENKO"]


def test_disabled_machine_verified_entry_is_not_silent():
    data = copy.deepcopy(current())
    data["variants"]["GRIGO"]["runtime_enabled"] = False
    data["variants"]["GRIGO"]["renderer_adapter"] = None
    with pytest.raises(SignatureRegistryError, match="verified_variant_disabled"):
        validate_registry(data)


def test_signature_and_signer_text_are_an_atomic_variant():
    data = copy.deepcopy(current())
    data["variants"]["DUAL_GRIGO_HERASYMENKO"]["atomic_binding"] = "SIGNATURE_ONLY"
    with pytest.raises(SignatureRegistryError, match="text_component_binding_invalid"):
        validate_registry(data)


def test_dual_represents_two_signers_not_two_independent_jobs():
    assert current()["variants"]["DUAL_GRIGO_HERASYMENKO"]["signer_count"] == 2


def test_registry_rejects_open_fallback_policy():
    data = copy.deepcopy(current())
    data["policy"]["silent_fallback"] = "ALLOW"
    with pytest.raises(SignatureRegistryError, match="fail_closed_policy"):
        validate_registry(data)


def test_registry_rejects_filesystem_paths_as_resource_ids():
    data = copy.deepcopy(current())
    data["variants"]["GRIGO"]["source_resource_id"] = "/srv/private/signature.pdf"
    with pytest.raises(SignatureRegistryError, match="resource_id_invalid"):
        validate_registry(data)


def test_registry_rejects_yaml_duplicate_keys(tmp_path):
    path = tmp_path / "duplicate.yaml"
    path.write_text("schema_version: test\nschema_version: duplicate\n", encoding="utf-8")
    with pytest.raises(SignatureRegistryError, match="duplicate_registry_key"):
        load_registry(path)


def test_signature_registry_is_indexed_in_existing_greeting_card_direction():
    import yaml
    index_path = REGISTRY.parent / "index.yaml"
    doc = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    assert "signature_registry_v0_1.yaml" in doc["documents"]


def test_registry_source_does_not_embed_private_paths():
    data = REGISTRY.read_text(encoding="utf-8")
    assert "/srv/" not in data
    assert "\\" not in data

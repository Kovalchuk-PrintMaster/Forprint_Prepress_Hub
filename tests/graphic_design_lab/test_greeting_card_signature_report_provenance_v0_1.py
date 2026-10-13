"""Synthetic per-variant report provenance, no private customer inputs."""
from __future__ import annotations

import pytest

from app.graphic_design_lab.greeting_card_builder_renderer import (
    _verified_signature_report_provenance,
)


SHA = "a" * 64
OTHER = "b" * 64


def grigo_output(**changes):
    return {
        "status": "PASS",
        "signature_variant_id": "GRIGO",
        "source_hash_validated_before_replay": True,
        **changes,
    }


def herasymenko_source(**changes):
    return {
        "status": "PASS",
        "signature_variant_id": "HERASYMENKO",
        "rgba_pixel_sha256": SHA,
        "source_soft_mask_present": True,
        **changes,
    }


def herasymenko_output(**changes):
    return {
        "status": "PASS",
        "signature_variant_id": "HERASYMENKO",
        "identity_mode": "PIXEL_SIZE_BBOX_RGBA_PIXEL_SHA256_SOFT_MASK",
        "rgba_pixel_sha256": SHA,
        "soft_mask_colorspace": "/DeviceGray",
        "soft_mask_xref": 12,
        **changes,
    }


def verified(variant="HERASYMENKO", grigo=False, source=None, output=None):
    return _verified_signature_report_provenance(
        signature_variant=variant,
        grigo_source_verified=grigo,
        source_validation=source,
        rendered_validation=output,
    )


def test_herasymenko_complete_source_and_post_render_proof_is_authenticated():
    assert verified(source=herasymenko_source(), output=herasymenko_output()) is True


def test_grigo_source_and_vector_replay_proof_is_authenticated():
    assert verified("GRIGO", True, None, grigo_output()) is True


@pytest.mark.parametrize(("source", "output"), [
    (None, herasymenko_output()),
    (herasymenko_source(status="FAIL"), herasymenko_output()),
    (herasymenko_source(), herasymenko_output(status="FAIL")),
    (herasymenko_source(), herasymenko_output(rgba_pixel_sha256=OTHER)),
    (herasymenko_source(rgba_pixel_sha256="x" * 64), herasymenko_output()),
    (herasymenko_source(), herasymenko_output(soft_mask_xref=0)),
    (herasymenko_source(), herasymenko_output(soft_mask_colorspace="/DeviceRGB")),
    (herasymenko_source(source_soft_mask_present=False), herasymenko_output()),
    (herasymenko_source(), herasymenko_output(signature_variant_id="GRIGO")),
])
def test_herasymenko_malformed_provenance_fails_closed(source, output):
    with pytest.raises(ValueError, match="signature_report_authentication_incomplete"):
        verified(source=source, output=output)


@pytest.mark.parametrize(("grigo", "output"), [
    (False, grigo_output()),
    (True, grigo_output(source_hash_validated_before_replay=False)),
    (True, grigo_output(status="FAIL")),
    (True, grigo_output(signature_variant_id="HERASYMENKO")),
])
def test_grigo_malformed_provenance_fails_closed(grigo, output):
    with pytest.raises(ValueError, match="signature_report_authentication_incomplete"):
        verified("GRIGO", grigo, None, output)


def test_other_variant_not_automatically_accepted():
    with pytest.raises(ValueError, match="signature_report_variant_unsupported"):
        verified("DUAL_GRIGO_HERASYMENKO", False, herasymenko_source(), herasymenko_output())

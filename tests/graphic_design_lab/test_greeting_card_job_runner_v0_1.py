from __future__ import annotations

import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from app.graphic_design_lab.greeting_card_constructor_bundle import (
    accepted_visual_from_creator_review,
    build_accepted_constructor_bundle,
    compute_bundle_sha256,
)
from app.graphic_design_lab.greeting_card_creator_review import (
    build_creator_review_record,
)
from app.graphic_design_lab.result_package import (
    build_creator_result_package,
)


ROOT = Path(__file__).resolve().parents[2]
RUNNER = (
    ROOT
    / "scripts"
    / "graphic_design_lab"
    / "greeting_cards"
    / "job_runner.py"
)
FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "graphic_design_lab"
    / "recurring_greeting_card_constructor_bundle_v0_1.yaml"
)
REVIEW_FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "graphic_design_lab"
    / "recurring_greeting_card_creator_review_pass_v0_1.yaml"
)
RESULT_CONTRACT = (
    ROOT
    / "contracts"
    / "graphic_design_lab"
    / "creator_result_package_v0_1.yaml"
)
SIGNATURE_CATALOG = (
    ROOT
    / "coordination"
    / "graphic_design_lab"
    / "directions"
    / "greeting_cards"
    / "signature_variant_catalog_v0_1.yaml"
)


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_runner():
    spec = importlib.util.spec_from_file_location(
        "gdl_constructor_job_runner",
        RUNNER,
    )
    assert spec
    assert spec.loader

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_bundle():
    fixture = load_yaml(FIXTURE)
    review_fixture = load_yaml(REVIEW_FIXTURE)
    contract = load_yaml(RESULT_CONTRACT)
    catalog = load_yaml(SIGNATURE_CATALOG)

    package = build_creator_result_package(
        deepcopy(review_fixture["creator_result_package_raw"])
    )
    review = build_creator_review_record(
        review_fixture["creator_task"],
        package,
        contract,
        review_id=review_fixture["review_id"],
        reviewer_source=review_fixture["reviewer_source"],
        portrait_checks=review_fixture["portrait_checks"],
        review_note=review_fixture["review_note"],
    )
    visual = accepted_visual_from_creator_review(review)

    bundle = build_accepted_constructor_bundle(
        fixture["normalized_batch"],
        source_inventory=fixture["source_inventory"],
        entity_registry=fixture["entity_registry"],
        accepted_visuals_by_job={
            fixture["normalized_batch"]["jobs"][0]["job_id"]:
                visual,
        },
        signature_catalog=catalog,
        intake_review=fixture["intake_review"],
        bundle_id=fixture["expected"]["bundle_id"],
        semantic_family_hints_by_job=fixture[
            "semantic_family_hints"
        ],
    )
    return bundle


def write_bundle(path: Path, bundle: dict) -> None:
    path.write_text(
        yaml.safe_dump(
            bundle,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_bundle_ingest_is_non_mutating_and_idempotent(tmp_path):
    runner = load_runner()
    bundle = build_bundle()
    bundle_path = tmp_path / "accepted_constructor_bundle.yaml"
    write_bundle(bundle_path, bundle)

    before = runner.sha256(bundle_path)
    first = runner.run_bundle(bundle_path)
    second = runner.run_bundle(bundle_path)
    after = runner.sha256(bundle_path)

    assert before == after
    assert first["run_id"] == second["run_id"]
    assert first["bundle_canonical_sha256"] == (
        compute_bundle_sha256(bundle)
    )
    assert first["status"] == (
        "ACCEPTED_CONSTRUCTOR_BUNDLE_INGESTED"
    )
    assert first["constructor_input_class"] == (
        "ACCEPTED_CONSTRUCTOR_BUNDLE"
    )
    assert first["source_mutation"] is False
    assert first[
        "raw_customer_material_interpretation_performed"
    ] is False
    assert first["heuristic_role_inference_performed"] is False
    assert first["normalized_batch_synthesis_performed"] is False
    assert first["ready_for_composition"] is True

    machine = (
        tmp_path
        / "_forprint_automation"
        / "jobs"
        / first["run_id"]
    )
    assert (
        machine / "constructor_input_manifest.json"
    ).is_file()
    assert (machine / "run_report.json").is_file()
    assert (
        tmp_path
        / "output"
        / "report"
        / "job_result.json"
    ).is_file()


def test_tampered_bundle_is_rejected_before_workspace_creation(
    tmp_path,
):
    runner = load_runner()
    bundle = build_bundle()
    bundle["jobs"][0]["structured_greeting_data"]["occasion"] = (
        "tampered"
    )
    bundle_path = tmp_path / "accepted_constructor_bundle.yaml"
    write_bundle(bundle_path, bundle)

    with pytest.raises(
        RuntimeError,
        match="accepted_constructor_bundle_invalid:",
    ):
        runner.run_bundle(bundle_path)

    assert not (tmp_path / "_forprint_automation").exists()
    assert not (tmp_path / "output").exists()


def test_runner_cli_is_bundle_only():
    source = RUNNER.read_text(encoding="utf-8")

    assert 'parser.add_argument(\n        "--bundle",' in source
    assert '"--job"' not in source
    assert '"--run-id"' not in source
    assert "resolve_raw_root" not in source
    assert "candidate_roles" not in source
    assert "normalized_batch.json" not in source


def test_makefile_exposes_constructor_bundle_ingest():
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert RUNNER.is_file()
    assert "gdl-greeting-card-constructor-ingest:" in makefile
    assert "GDL_GREETING_CARD_BUNDLE" in makefile
    assert "BUNDLE=/path/to/accepted_constructor_bundle" in makefile
    assert "gdl-greeting-card-job-run:" not in makefile
    assert "GDL_GREETING_CARD_JOB" not in makefile

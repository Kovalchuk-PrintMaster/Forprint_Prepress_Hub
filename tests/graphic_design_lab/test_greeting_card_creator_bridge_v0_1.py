from copy import deepcopy
from pathlib import Path

import yaml

from app.graphic_design_lab.greeting_card_creator_bridge import (
    build_dispatch_manifest,
    compute_prompt_sha256,
    validate_creator_bridge_package,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/graphic_design_lab/recurring_greeting_card_creator_bridge_v0_1.yaml"
CONTRACT = ROOT / "contracts/graphic_design_lab/creator_result_package_v0_1.yaml"
BRIDGE_CONTRACT = (
    ROOT
    / "coordination/graphic_design_lab/directions/greeting_cards/"
    "creator_dispatch_readback_bridge_contract_v0_1.yaml"
)
PROMPT = (
    ROOT
    / "coordination/graphic_design_lab/directions/greeting_cards/prompts/"
    "GDL-CREATOR-PORTRAIT-v001.md"
)
CURSOR = ROOT / "coordination/graphic_design_lab/continuity/current_execution_cursor_v0_1.yaml"
PLAN = (
    ROOT
    / "coordination/graphic_design_lab/directions/greeting_cards/"
    "end_to_end_execution_plan_v0_1.yaml"
)


def load(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def package():
    return load(FIXTURE)["bridge_package"]


def errors(value):
    return validate_creator_bridge_package(value, result_contract=load(CONTRACT))


def test_bridge_contract_reuses_human_copy_paste_boundary_without_provider_execution():
    contract = load(BRIDGE_CONTRACT)
    assert contract["execution_mode"] == "HUMAN_COPY_PASTE_BRIDGE"
    assert contract["gc_e2e_04a"]["closes_gc_e2e_04"] is False
    assert contract["authority"]["authorizes_automated_provider_execution"] is False
    assert contract["authority"]["initializes_runtime"] is False


def test_project_owned_prompt_hash_matches_contract_and_fixture():
    prompt_text = PROMPT.read_text(encoding="utf-8")
    digest = compute_prompt_sha256(prompt_text)
    assert digest == "b03e74b82af2f361b8ed20f78aa70cf623c21d1d68f8356fc3d56170a767ddf8"
    assert load(BRIDGE_CONTRACT)["prompt"]["sha256"] == digest
    assert package()["prompt_record"]["prompt_sha256"] == digest


def test_sanitized_rehearsal_package_is_valid():
    assert errors(package()) == []


def test_dispatch_builder_is_deterministic_and_does_not_claim_execution():
    p = package()
    kwargs = dict(
        case_id="sanitized_greeting_card_case_001",
        prompt_id="gdl-creator-greeting-portrait-v001",
        prompt_version="v001",
        prompt_content_ref=str(PROMPT.relative_to(ROOT)),
        prompt_text=PROMPT.read_text(encoding="utf-8"),
    )
    a = build_dispatch_manifest(p["creator_task"], **kwargs)
    b = build_dispatch_manifest(p["creator_task"], **kwargs)
    assert a == b
    assert a["dispatch"]["state"] == "PREPARED_FOR_HUMAN_DISPATCH"
    assert a["dispatch"]["creator_execution_observed"] is False
    assert a["dispatch"]["provider_execution_performed"] is False
    assert a["completion_gate"]["gc_e2e_04_completion_eligible"] is False


def test_result_package_must_trace_back_to_exact_task():
    bad = deepcopy(package())
    bad["result_attachment"]["creator_result_package"]["source"][
        "greeting_card_task_traceability"
    ]["task_id"] = "wrong_task"
    assert any("task_traceability.task_id:mismatch" in item for item in errors(bad))


def test_returned_artifact_must_trace_back_to_source_asset():
    bad = deepcopy(package())
    bad["result_attachment"]["creator_result_package"]["artifacts"][0][
        "greeting_card_task_traceability"
    ]["source_asset_id"] = "wrong_asset"
    assert any("source_asset_id:mismatch" in item for item in errors(bad))


def test_prompt_identity_mismatch_is_rejected():
    bad = deepcopy(package())
    bad["result_attachment"]["creator_result_package"]["source"]["creator_prompt"][
        "prompt_sha256"
    ] = "b" * 64
    assert any("prompt_sha256:mismatch" in item for item in errors(bad))


def test_rehearsal_cannot_claim_live_creator_execution_or_complete_gc_e2e_04():
    bad = deepcopy(package())
    bad["dispatch"]["creator_execution_observed"] = True
    bad["result_attachment"]["actual_creator_result"] = True
    bad["completion_gate"]["gc_e2e_04_completion_eligible"] = True
    got = errors(bad)
    assert "bridge.rehearsal:creator_execution_observed_must_be_false" in got
    assert "bridge.rehearsal:actual_creator_result_must_be_false" in got
    assert "bridge.rehearsal:gc_e2e_04_completion_forbidden" in got


def test_provider_runtime_and_full_card_authority_remain_disabled():
    for field in (
        "provider_execution_performed",
        "gdl_runtime_initialized",
        "production_write_enabled",
        "full_card_composition_authorized",
    ):
        bad = deepcopy(package())
        bad["authority"][field] = True
        assert f"bridge.authority.{field}:must_be_false" in errors(bad)


def test_gc_e2e_04_remains_closed_after_later_progress():
    cursor = load(CURSOR)
    task = cursor["active_tasks"][0]
    assert "GC-E2E-04" in task["completed_steps"]
    assert "GC-E2E-04A" in task["completed_subcheckpoints"]
    assert "GC-E2E-04B" in task["completed_subcheckpoints"]

    plan = load(PLAN)
    steps = {item["id"]: item for item in plan["steps"]}
    assert steps["GC-E2E-04"]["state"] == "COMPLETED_LOCAL"
    checkpoints = {
        item["id"]: item
        for item in steps["GC-E2E-04"]["execution_checkpoints"]
    }
    assert checkpoints["GC-E2E-04A"]["state"] == "COMPLETED_LOCAL"
    assert checkpoints["GC-E2E-04B"]["state"] == "COMPLETED_LOCAL"
    assert checkpoints["GC-E2E-04B"]["creator_execution_observed"] is True
    assert checkpoints["GC-E2E-04B"]["provider_execution_performed"] is False
    assert checkpoints["GC-E2E-04B"]["private_creator_artifact_in_git"] is False
    assert checkpoints["GC-E2E-04B"]["live_result_package_in_git"] is False

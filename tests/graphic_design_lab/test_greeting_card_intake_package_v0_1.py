from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "coordination/graphic_design_lab/directions/greeting_cards"
PACKAGE = BASE / "intake_package_contract_v0_1.yaml"
PROFILE = BASE / "intake_prompt_profile_v0_1.yaml"
LOADER = BASE / "prompts/GDL-INTAKE-GREETING-CARDS-v001.md"
CURSOR = ROOT / (
    "coordination/graphic_design_lab/continuity/"
    "current_execution_cursor_v0_1.yaml"
)
PLAN = BASE / "end_to_end_execution_plan_v0_1.yaml"
PROMPT_INDEX = ROOT / "coordination/graphic_design_lab/prompt_evidence/index.yaml"


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_intake_package_reuses_existing_generic_contracts():
    package = load_yaml(PACKAGE)

    assert package["status"] == "ACTIVE_EMPIRICAL_CONTRACT"
    assert package["scope"] == "GRAPHIC_DESIGN_LAB_ONLY"
    assert package["reuse"]["guided_intake_contract"]["schema"] == (
        "forprint_guided_intake_v0_1"
    )
    assert package["reuse"]["guided_intake_contract"]["disposition"] == "REUSE"
    assert package["reuse"]["existing_normalizer"]["path"] == (
        "app/graphic_design_lab/intake.py"
    )


def test_operator_dispatch_does_not_require_manual_yaml_or_renaming():
    package = load_yaml(PACKAGE)
    dispatch = package["operator_dispatch_package"]

    assert dispatch["primary_material_bundle"]["filenames_are_hints_not_authority"] is True
    assert "do_not_require_operator_to_write_yaml_before_Intake" in dispatch["rules"]
    assert "do_not_require_operator_to_rename_customer_files_for_the_system" in dispatch["rules"]


def test_loader_is_project_owned_self_sufficient_intake_instruction():
    text = LOADER.read_text(encoding="utf-8")

    required = [
        "GDL Intake Analyst",
        "recurring_greeting_card_v0_1",
        "forprint_guided_intake_v0_1",
        "CONFIRMED",
        "PROPOSED",
        "UNRESOLVED",
        "Filenames are hints, not authority",
        "intake_result.yaml",
        "source_inventory.yaml",
        "intake_summary.md",
        "INTAKE_REVIEW_READY",
        "INTAKE_NEEDS_CLARIFICATION",
        "do not edit images in Intake",
    ]

    for marker in required:
        assert marker in text


def test_prompt_profile_is_registered_for_greeting_cards():
    index = load_yaml(PROMPT_INDEX)
    rows = {
        row["direction_id"]: row
        for row in index["direction_prompt_profiles"]
    }

    assert "greeting_cards" in rows
    greeting = rows["greeting_cards"]
    assert greeting["profile"].endswith("intake_prompt_profile_v0_2.yaml")
    assert greeting["loader"].endswith("GDL-INTAKE-GREETING-CARDS-v002.md")
    assert greeting["previous_profile"].endswith(
        "intake_prompt_profile_v0_1.yaml"
    )
    assert greeting["previous_loader"].endswith(
        "GDL-INTAKE-GREETING-CARDS-v001.md"
    )


def test_gc_e2e_01_remains_closed_after_later_cursor_advances():
    cursor = load_yaml(CURSOR)
    task = cursor["active_tasks"][0]

    assert task["completed_steps"][:2] == ["GC-E2E-00", "GC-E2E-01"]
    assert task["current_step"] not in {"GC-E2E-00", "GC-E2E-01"}

    plan = load_yaml(PLAN)
    steps = {item["id"]: item for item in plan["steps"]}
    assert steps["GC-E2E-01"]["state"] == "COMPLETED_LOCAL"


def test_gc_e2e_08_job_runner_note_remains_present():
    plan = load_yaml(PLAN)
    steps = {item["id"]: item for item in plan["steps"]}
    checkpoint = steps["GC-E2E-08"]["mandatory_job_runner_reuse_checkpoint"]

    assert checkpoint["do_not_discard_silently"] is True
    assert "scripts/graphic_design_lab/greeting_cards/job_runner.py" in checkpoint["inspect_first"]

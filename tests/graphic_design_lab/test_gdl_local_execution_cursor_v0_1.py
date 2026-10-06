from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]

CURSOR = ROOT / (
    "coordination/graphic_design_lab/continuity/"
    "current_execution_cursor_v0_1.yaml"
)

PLAN = ROOT / (
    "coordination/graphic_design_lab/directions/greeting_cards/"
    "end_to_end_execution_plan_v0_1.yaml"
)

CONTEXT = ROOT / (
    "coordination/graphic_design_lab/continuity/"
    "assistant_context_contract_v0_1.yaml"
)

PROJECT_FIRST = ROOT / (
    "coordination/graphic_design_lab/continuity/"
    "project_first_working_rule_v0_1.yaml"
)


def load_yaml(path: Path):
    return yaml.safe_load(
        path.read_text(encoding="utf-8")
    )


def test_cursor_is_gdl_local_and_blueprint_read_only():
    cursor = load_yaml(CURSOR)

    assert cursor["status"] == "ACTIVE"
    assert cursor["scope"] == "GRAPHIC_DESIGN_LAB_ONLY"

    authority = cursor["authority"]

    assert authority["blueprint_access"] == "READ_ONLY_STRICT"
    assert authority["blueprint_mutation"] is False
    assert authority["parent_prepress_roadmap_mutation"] is False
    assert authority["blueprint_work_front_is_local_cursor"] is False

    rules = cursor["operating_rules"]

    assert rules["active_task_limit"] == 3
    assert rules[
        "substantial_work_requires_active_task_binding"
    ] is True
    assert rules[
        "substantial_work_requires_execution_plan_step"
    ] is True


def test_greeting_card_cursor_advances_to_gc_e2e_03():
    cursor = load_yaml(CURSOR)

    task = cursor["active_tasks"][0]

    assert task["task_id"] == (
        "GDL-TASK-GREETING-CARD-E2E-001"
    )

    assert task["state"] == "ACTIVE"
    assert task["completed_steps"] == [
        "GC-E2E-00",
        "GC-E2E-01",
        "GC-E2E-02",
    ]
    assert task["current_step"] == "GC-E2E-03"

    plan = load_yaml(PLAN)

    steps = {
        item["id"]: item
        for item in plan["steps"]
    }

    assert list(steps) == [
        f"GC-E2E-{index:02d}"
        for index in range(13)
    ]

    assert (
        steps["GC-E2E-00"]["state"]
        == "COMPLETED_LOCAL"
    )

    assert (
        steps["GC-E2E-01"]["state"]
        == "COMPLETED_LOCAL"
    )

    assert (
        steps["GC-E2E-02"]["state"]
        == "COMPLETED_LOCAL"
    )

    assert (
        steps["GC-E2E-03"]["state"]
        == "ACTIVE"
    )


def test_gc_e2e_08_requires_job_runner_reuse_reconciliation():
    plan = load_yaml(PLAN)

    steps = {
        item["id"]: item
        for item in plan["steps"]
    }

    checkpoint = steps["GC-E2E-08"][
        "mandatory_job_runner_reuse_checkpoint"
    ]

    assert checkpoint["do_not_discard_silently"] is True

    assert checkpoint[
        "do_not_create_replacement_before_inspection"
    ] is True

    assert checkpoint[
        "do_not_commit_as_canonical_raw_intake_runner_without_reconciliation"
    ] is True

    assert checkpoint["current_disposition"] == (
        "UNRESOLVED_REQUIRES_GC_E2E_08_RECONCILIATION"
    )

    assert (
        "scripts/graphic_design_lab/greeting_cards/job_runner.py"
        in checkpoint["inspect_first"]
    )

    assert (
        "tests/graphic_design_lab/"
        "test_greeting_card_job_runner_v0_1.py"
        in checkpoint["inspect_first"]
    )


def test_context_contract_requires_cursor_first():
    context = load_yaml(CONTEXT)

    assert context["first_read_order"][0].endswith(
        "current_execution_cursor_v0_1.yaml"
    )

    gate = context["local_execution_resume_gate"]

    assert gate[
        "substantial_work_requires_active_task_binding"
    ] is True

    assert gate[
        "substantial_work_requires_execution_plan_step"
    ] is True

    assert context["local_authority_boundary"][
        "blueprint_mutation_from_gdl"
    ] is False


def test_project_first_rule_contains_work_admission_gate():
    rule = load_yaml(PROJECT_FIRST)

    policy = rule[
        "local_execution_cursor_policy"
    ]

    assert policy["scope"] == "GRAPHIC_DESIGN_LAB_ONLY"
    assert policy["max_active_tasks"] == 3

    assert policy["work_admission"][
        "active_task_binding_required"
    ] is True

    assert policy["work_admission"][
        "execution_plan_step_required"
    ] is True

    assert policy["roadmap_reconciliation"][
        "live_state_check_before_material_step"
    ] is True

    assert policy["authority_boundary"][
        "blueprint_write_forbidden"
    ] is True

    assert policy["authority_boundary"][
        "parent_prepress_roadmap_write_from_gdl_forbidden"
    ] is True

from pathlib import Path
import yaml
REPO = Path(__file__).resolve().parents[2]

def load(rel):
    return yaml.safe_load((REPO / rel).read_text(encoding="utf-8"))

def test_operator_intent_is_durable():
    c = load("coordination/graphic_design_lab/continuity/assistant_context_contract_v0_1.yaml")
    p = load("coordination/graphic_design_lab/continuity/gdl_operating_principles_v0_1.yaml")
    assert "operator_intent_is_authoritative_over_assistant_architectural_inference" in c["fresh_assistant_must_know"]
    assert "silently_resolve_material_architectural_ambiguity" in c["fresh_assistant_must_not"]
    ids = {x["id"] for x in p["principles"]}
    assert "OPERATOR_INTENT_OVERRIDES_ASSISTANT_INFERENCE" in ids
    assert "MATERIAL_ARCHITECTURAL_AMBIGUITY_REQUIRES_OPERATOR_CONFIRMATION" in ids

def test_gc_e2e_09_is_pdf_builder_not_illustrator_runtime():
    plan = load("coordination/graphic_design_lab/directions/greeting_cards/end_to_end_execution_plan_v0_1.yaml")
    step = next(x for x in plan["steps"] if x["id"] == "GC-E2E-09")
    assert step["title"] == "Deterministic greeting-card composition and editable PDF assembly"
    assert step["operator_intent_correction"]["illustrator_runtime_dependency"] is False
    assert step["operator_intent_correction"]["human_editability_reference"]["script_id"] == "FORPRINT_GDL_ILLUSTRATOR_OPERATOR_COMPANION_V0_2_2B"

def test_cursor_points_to_active_gc_e2e_09_builder_subcheckpoint():
    cursor = load("coordination/graphic_design_lab/continuity/current_execution_cursor_v0_1.yaml")
    plan = load("coordination/graphic_design_lab/directions/greeting_cards/end_to_end_execution_plan_v0_1.yaml")

    task = cursor["active_tasks"][0]
    assert task["current_step"] == "GC-E2E-09"
    assert task["current_checkpoint"]["id"] == "HERASYMENKO_SIGNATURE_RENDERER_REQUIRED"
    assert "GC-E2E-09A" in task["completed_subcheckpoints"]

    step = next(
        item
        for item in plan["steps"]
        if item["id"] == "GC-E2E-09"
    )

    checkpoints = {
        item["id"]: item
        for item in step["execution_checkpoints"]
    }

    assert checkpoints["GC-E2E-09A"]["state"] == "COMPLETED_LOCAL"
    assert checkpoints["GC-E2E-09A"]["implementation_commit"] == (
        "ca8d6a44c6ede016f34ace1cc02099695c2c4e30"
    )
    assert checkpoints["GC-E2E-09B"]["state"] == "ACTIVE"
    assert checkpoints["GC-E2E-09B"]["scope"]["signature_variant"] == "HERASYMENKO"

def test_exact_titles_and_flowers_hash():
    r = load("coordination/graphic_design_lab/directions/greeting_cards/v1_resource_bindings_v0_1.yaml")
    assert r["standard_occasion_titles"]["BIRTHDAY"]["exact_visible_text"] == "Привітання з нагоди Дня Народження!"
    assert r["standard_occasion_titles"]["ANNIVERSARY"]["exact_visible_text"] == "Привітання з Ювілеєм!"
    assert r["private_assets"]["flowers.default.v1"]["sha256"] == "d9113f8d6f9627f9b106f5550e6187aaa562139fef6122e4834e7d4f2f3bbd67"
    assert r["private_assets"]["flowers.default.v1"]["tracked_in_git"] is False

def test_v1_architecture_keeps_illustrator_out_of_runtime():
    a = load("coordination/graphic_design_lab/directions/greeting_cards/v1_architecture_v0_1.yaml")
    assert a["component_boundaries"]["illustrator_jsx"]["runtime_dependency"] is False
    assert a["component_boundaries"]["builder"]["rule"] == "EXECUTE_EXACT_MACHINE_PACKAGE_DO_NOT_INTERPRET_CUSTOMER"
    assert a["outputs"]["preview_subdir"]["source"] == "GENERATED_WORKING_PDF"

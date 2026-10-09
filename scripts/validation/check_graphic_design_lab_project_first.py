#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
RULE = ROOT / "coordination/graphic_design_lab/continuity/project_first_working_rule_v0_1.yaml"
CONTEXT = ROOT / "coordination/graphic_design_lab/continuity/assistant_context_contract_v0_1.yaml"
ADDENDUM = ROOT / "coordination/graphic_design_lab/continuity/client_workflow_execution_context_addendum_v0_1.yaml"
DIRECTION = ROOT / "coordination/graphic_design_lab/directions/greeting_cards/direction_v0_1.yaml"
INDEX = ROOT / "coordination/graphic_design_lab/directions/greeting_cards/index.yaml"
RUNNER = ROOT / "scripts/graphic_design_lab/greeting_cards/prototype.py"
BUILDER = ROOT / "app/graphic_design_lab/greeting_card_builder_renderer.py"
BUILDER_CLI = ROOT / "scripts/graphic_design_lab/greeting_cards/builder.py"
BUILDER_CONTRACT = ROOT / "coordination/graphic_design_lab/directions/greeting_cards/deterministic_builder_v0_1.yaml"
MAKEFILE = ROOT / "Makefile"

def load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))

def validate(root=ROOT):
    errors=[]
    for name,path in (("rule",RULE),("context",CONTEXT),("addendum",ADDENDUM),("direction",DIRECTION),("index",INDEX),("runner",RUNNER),("builder",BUILDER),("builder_cli",BUILDER_CLI),("builder_contract",BUILDER_CONTRACT),("makefile",MAKEFILE)):
        p=root/path.relative_to(ROOT)
        if not p.is_file():
            errors.append(f"missing:{name}:{p.relative_to(root)}")
    if errors:
        return errors
    rule=load(root/RULE.relative_to(ROOT))
    context=load(root/CONTEXT.relative_to(ROOT))
    addendum=load(root/ADDENDUM.relative_to(ROOT))
    direction=load(root/DIRECTION.relative_to(ROOT))
    index=load(root/INDEX.relative_to(ROOT))
    builder_contract=load(root/BUILDER_CONTRACT.relative_to(ROOT))
    makefile=(root/MAKEFILE.relative_to(ROOT)).read_text(encoding="utf-8")
    p=rule.get("project_internal_tooling_policy",{})
    if p.get("canonical_rule") != "REPEATABLE_EXECUTION_LOGIC_LIVES_IN_PROJECT": errors.append("rule:canonical_rule")
    if p.get("chat_script_role") != "BOUNDED_BOOTSTRAP_PATCH_OR_REPAIR_ONLY": errors.append("rule:chat_script_role")
    if p.get("stable_operator_entrypoints_required") is not True: errors.append("rule:stable_entrypoint")
    if p.get("repeat_execution_from_chat_only") is not False: errors.append("rule:chat_repeat_forbidden")
    model=p.get("operator_execution_model",{})
    if model.get("target_state") != "PROJECT_EXECUTES_REPEATABLE_WORK_CHAT_SUPPLIES_INTENT_DESIGN_AND_REVIEW": errors.append("rule:operator_target_state")
    if model.get("chat_operational_logic_minimized") is not True: errors.append("rule:chat_logic_minimized")
    if model.get("normal_operator_action") != "SHORT_STABLE_PROJECT_COMMAND": errors.append("rule:short_command")
    if model.get("long_repeatable_manual_shell_sequences_preferred") is not False: errors.append("rule:no_long_repeatable_shell")
    if model.get("evidence_and_reports_generated_by_project") is not True: errors.append("rule:project_reports")
    if model.get("new_chat_functionality_should_be_integrated_into_project_before_repeat_use") is not True: errors.append("rule:promote_new_chat_logic")
    closeout=model.get("project_owned_closeout",{})
    if closeout.get("explicit_operator_authorization_required") is not True: errors.append("rule:closeout_authorization")
    if closeout.get("inspect_exact_diff_before_git_mutation") is not True: errors.append("rule:closeout_diff_review")
    if closeout.get("exact_path_stage_only") is not True: errors.append("rule:closeout_exact_stage")
    if closeout.get("broad_git_add_forbidden") is not True: errors.append("rule:closeout_no_broad_add")
    if closeout.get("may_commit_push_and_verify_when_explicitly_requested") is not True: errors.append("rule:closeout_commit_push")
    must_know=set(context.get("fresh_assistant_must_know",[]))
    must_not=set(context.get("fresh_assistant_must_not",[]))
    if "project_internal_tooling_first_execution_rule" not in must_know: errors.append("context:must_know")
    if "reimplement_repeatable_project_execution_logic_only_in_chat" not in must_not: errors.append("context:must_not_reimplement")
    if "use_ad_hoc_chat_runner_when_project_entrypoint_exists" not in must_not: errors.append("context:must_not_adhoc")
    if "incomplete_implementation_persistence_during_runtime_debugging" not in must_know: errors.append("context:must_know:implementation_persistence")
    if "project_owned_greeting_card_builder_entrypoint" not in must_know: errors.append("context:must_know:greeting_card_builder")
    if "rollback_materialized_new_capability_only_because_a_runtime_smoke_failed" not in must_not: errors.append("context:must_not:rollback_materialized_capability")
    for key in ("repository_first_operator_execution_model", "short_project_command_as_normal_repeatable_operator_interface", "project_owned_explicit_closeout_pipeline"):
        if key not in must_know: errors.append("context:must_know:"+key)
    for key in ("keep_repeatable_operational_logic_in_chat_after_validation", "return_long_manual_shell_sequences_when_a_project_entrypoint_can_own_the_work", "duplicate_project_closeout_logic_in_chat_when_a_supported_closeout_entrypoint_exists"):
        if key not in must_not: errors.append("context:must_not:"+key)
    er=addendum.get("project_internal_execution_rule",{})
    if er.get("prefer_existing_project_tool") is not True: errors.append("addendum:prefer_tool")
    if er.get("patch_project_tool_instead_of_reissuing_full_runner") is not True: errors.append("addendum:patch_tool")
    proto=direction.get("operator_entrypoints",{}).get("prototype",{})
    if proto.get("make_target") != "gdl-greeting-card-prototype": errors.append("direction:make_target")
    if proto.get("implementation_source_of_truth") != "PROJECT_REPOSITORY": errors.append("direction:source_truth")
    if "gdl-greeting-card-prototype:" not in makefile: errors.append("make:prototype")
    persistence=rule.get("incomplete_implementation_persistence_policy",{})
    if persistence.get("repository_dirty_state_is_valid_working_state") is not True: errors.append("rule:dirty_working_state")
    if persistence.get("failing_test_or_runtime_smoke_does_not_authorize_full_capability_rollback") is not True: errors.append("rule:no_full_rollback_on_smoke")
    if persistence.get("subsequent_iterations_patch_project_owned_files") is not True: errors.append("rule:patch_project_owned_files")
    if persistence.get("subsequent_chat_script_role") != "BOUNDED_REPAIR_ONLY": errors.append("rule:bounded_repair_only")
    documents=set(index.get("documents",[]))
    if index.get("deterministic_builder_contract") != "deterministic_builder_v0_1.yaml": errors.append("index:builder_contract")
    if "deterministic_builder_v0_1.yaml" not in documents: errors.append("index:builder_document")
    if builder_contract.get("schema_version") != "gdl_greeting_card_deterministic_builder_v0_1": errors.append("builder_contract:schema")
    first_slice=builder_contract.get("first_slice",{})
    if first_slice.get("front_family") != "STANDARD": errors.append("builder_contract:first_slice_front")
    if first_slice.get("inside_image_mode") != "PORTRAIT": errors.append("builder_contract:first_slice_image")
    if first_slice.get("signature_variant") != "GRIGO": errors.append("builder_contract:first_slice_signature")
    if "gdl-greeting-card-builder:" not in makefile: errors.append("make:builder")
    if "GDL_GREETING_CARD_BUILDER ?= scripts/graphic_design_lab/greeting_cards/builder.py" not in makefile: errors.append("make:builder_source")
    if "gdl-project-first-check:" not in makefile: errors.append("make:check")
    gov=next((x for x in makefile.splitlines() if x.startswith("governance-check:")),"")
    if "gdl-project-first-check" not in gov: errors.append("make:governance")
    return errors

if __name__ == '__main__':
    errors=validate(ROOT)
    if errors:
        print('PREPRESS_HUB_GDL_PROJECT_FIRST_CHECK=FAIL')
        for e in errors: print(f'ERROR={e}')
        raise SystemExit(1)
    print('PREPRESS_HUB_GDL_PROJECT_FIRST_CHECK=PASS')
    print('CANONICAL_RULE=REPEATABLE_EXECUTION_LOGIC_LIVES_IN_PROJECT')
    print('CHAT_SCRIPT_ROLE=BOUNDED_BOOTSTRAP_PATCH_OR_REPAIR_ONLY')
    print('GREETING_CARD_PROTOTYPE_RUNNER=PROJECT_OWNED')
    print('GREETING_CARD_BUILDER=PROJECT_OWNED')
    print('INCOMPLETE_IMPLEMENTATION_PERSISTENCE=ENFORCED')

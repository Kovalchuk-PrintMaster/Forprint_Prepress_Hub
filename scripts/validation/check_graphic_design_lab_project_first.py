#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
RULE = ROOT / "coordination/graphic_design_lab/continuity/project_first_working_rule_v0_1.yaml"
CONTEXT = ROOT / "coordination/graphic_design_lab/continuity/assistant_context_contract_v0_1.yaml"
ADDENDUM = ROOT / "coordination/graphic_design_lab/continuity/client_workflow_execution_context_addendum_v0_1.yaml"
DIRECTION = ROOT / "coordination/graphic_design_lab/directions/greeting_cards/direction_v0_1.yaml"
RUNNER = ROOT / "scripts/graphic_design_lab/greeting_cards/prototype.py"
MAKEFILE = ROOT / "Makefile"

def load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))

def validate(root=ROOT):
    errors=[]
    for name,path in (("rule",RULE),("context",CONTEXT),("addendum",ADDENDUM),("direction",DIRECTION),("runner",RUNNER),("makefile",MAKEFILE)):
        p=root/path.relative_to(ROOT)
        if not p.is_file():
            errors.append(f"missing:{name}:{p.relative_to(root)}")
    if errors:
        return errors
    rule=load(root/RULE.relative_to(ROOT))
    context=load(root/CONTEXT.relative_to(ROOT))
    addendum=load(root/ADDENDUM.relative_to(ROOT))
    direction=load(root/DIRECTION.relative_to(ROOT))
    makefile=(root/MAKEFILE.relative_to(ROOT)).read_text(encoding="utf-8")
    p=rule.get("project_internal_tooling_policy",{})
    if p.get("canonical_rule") != "REPEATABLE_EXECUTION_LOGIC_LIVES_IN_PROJECT": errors.append("rule:canonical_rule")
    if p.get("chat_script_role") != "BOUNDED_BOOTSTRAP_PATCH_OR_REPAIR_ONLY": errors.append("rule:chat_script_role")
    if p.get("stable_operator_entrypoints_required") is not True: errors.append("rule:stable_entrypoint")
    if p.get("repeat_execution_from_chat_only") is not False: errors.append("rule:chat_repeat_forbidden")
    must_know=set(context.get("fresh_assistant_must_know",[]))
    must_not=set(context.get("fresh_assistant_must_not",[]))
    if "project_internal_tooling_first_execution_rule" not in must_know: errors.append("context:must_know")
    if "reimplement_repeatable_project_execution_logic_only_in_chat" not in must_not: errors.append("context:must_not_reimplement")
    if "use_ad_hoc_chat_runner_when_project_entrypoint_exists" not in must_not: errors.append("context:must_not_adhoc")
    er=addendum.get("project_internal_execution_rule",{})
    if er.get("prefer_existing_project_tool") is not True: errors.append("addendum:prefer_tool")
    if er.get("patch_project_tool_instead_of_reissuing_full_runner") is not True: errors.append("addendum:patch_tool")
    proto=direction.get("operator_entrypoints",{}).get("prototype",{})
    if proto.get("make_target") != "gdl-greeting-card-prototype": errors.append("direction:make_target")
    if proto.get("implementation_source_of_truth") != "PROJECT_REPOSITORY": errors.append("direction:source_truth")
    if "gdl-greeting-card-prototype:" not in makefile: errors.append("make:prototype")
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

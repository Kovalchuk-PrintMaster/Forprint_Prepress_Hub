from __future__ import annotations
import importlib.util
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[2]
VALIDATOR=ROOT/'scripts/validation/check_graphic_design_lab_project_first.py'

def load_validator():
    spec=importlib.util.spec_from_file_location('project_first_validator',VALIDATOR)
    assert spec is not None and spec.loader is not None
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_project_first_validator_passes():
    assert load_validator().validate(ROOT)==[]

def test_repeatable_logic_lives_in_project():
    path=ROOT/'coordination/graphic_design_lab/continuity/project_first_working_rule_v0_1.yaml'
    policy=yaml.safe_load(path.read_text(encoding='utf-8'))['project_internal_tooling_policy']
    assert policy['canonical_rule']=='REPEATABLE_EXECUTION_LOGIC_LIVES_IN_PROJECT'
    assert policy['chat_script_role']=='BOUNDED_BOOTSTRAP_PATCH_OR_REPAIR_ONLY'
    assert policy['repeat_execution_from_chat_only'] is False

def test_stable_greeting_card_operator_entrypoint_exists():
    assert (ROOT/'scripts/graphic_design_lab/greeting_cards/prototype.py').is_file()
    makefile=(ROOT/'Makefile').read_text(encoding='utf-8')
    assert 'gdl-greeting-card-prototype:' in makefile
    assert 'GDL_CLIENT_ROOT' in makefile


def test_repository_first_operator_execution_model_is_explicit():
    path = ROOT/'coordination/graphic_design_lab/continuity/project_first_working_rule_v0_1.yaml'
    policy = yaml.safe_load(path.read_text(encoding='utf-8'))['project_internal_tooling_policy']
    model = policy['operator_execution_model']
    assert model['target_state'] == 'PROJECT_EXECUTES_REPEATABLE_WORK_CHAT_SUPPLIES_INTENT_DESIGN_AND_REVIEW'
    assert model['chat_operational_logic_minimized'] is True
    assert model['normal_operator_action'] == 'SHORT_STABLE_PROJECT_COMMAND'
    assert model['long_repeatable_manual_shell_sequences_preferred'] is False
    assert model['evidence_and_reports_generated_by_project'] is True
    assert model['new_chat_functionality_should_be_integrated_into_project_before_repeat_use'] is True
    closeout = model['project_owned_closeout']
    assert closeout['explicit_operator_authorization_required'] is True
    assert closeout['inspect_exact_diff_before_git_mutation'] is True
    assert closeout['exact_path_stage_only'] is True
    assert closeout['broad_git_add_forbidden'] is True
    assert closeout['may_commit_push_and_verify_when_explicitly_requested'] is True


def test_project_owned_greeting_card_builder_is_enforced():
    assert (
        ROOT
        / "app/graphic_design_lab/greeting_card_builder_renderer.py"
    ).is_file()
    assert (
        ROOT
        / "scripts/graphic_design_lab/greeting_cards/builder.py"
    ).is_file()

    index = yaml.safe_load(
        (
            ROOT
            / "coordination/graphic_design_lab/directions/greeting_cards/index.yaml"
        ).read_text(encoding="utf-8")
    )
    assert (
        index["deterministic_builder_contract"]
        == "deterministic_builder_v0_1.yaml"
    )
    assert (
        "deterministic_builder_v0_1.yaml"
        in index["documents"]
    )

    makefile = (ROOT / "Makefile").read_text(
        encoding="utf-8"
    )
    assert "gdl-greeting-card-builder:" in makefile
    assert (
        "GDL_GREETING_CARD_BUILDER ?= "
        "scripts/graphic_design_lab/greeting_cards/builder.py"
        in makefile
    )


def test_materialized_capability_survives_runtime_debugging():
    rule = yaml.safe_load(
        (
            ROOT
            / "coordination/graphic_design_lab/continuity/"
            "project_first_working_rule_v0_1.yaml"
        ).read_text(encoding="utf-8")
    )
    policy = rule[
        "incomplete_implementation_persistence_policy"
    ]

    assert (
        policy[
            "repository_dirty_state_is_valid_working_state"
        ]
        is True
    )
    assert (
        policy[
            "failing_test_or_runtime_smoke_does_not_authorize_full_capability_rollback"
        ]
        is True
    )
    assert (
        policy[
            "subsequent_iterations_patch_project_owned_files"
        ]
        is True
    )
    assert (
        policy[
            "subsequent_chat_script_role"
        ]
        == "BOUNDED_REPAIR_ONLY"
    )

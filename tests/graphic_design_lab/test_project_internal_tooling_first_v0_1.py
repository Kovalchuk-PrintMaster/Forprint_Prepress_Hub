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

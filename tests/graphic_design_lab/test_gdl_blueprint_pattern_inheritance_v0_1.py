from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
PROJECT_FIRST = (
    ROOT
    / "coordination/graphic_design_lab/continuity/"
    "project_first_working_rule_v0_1.yaml"
)
ASSISTANT_CONTEXT = (
    ROOT
    / "coordination/graphic_design_lab/continuity/"
    "assistant_context_contract_v0_1.yaml"
)
PROTOCOL = (
    ROOT
    / "coordination/graphic_design_lab/execution/"
    "accept_and_advance_protocol_v0_1.yaml"
)
TOOL = ROOT / "scripts/coordination/gdl_accept_and_advance_v0_1.py"
MAKEFILE = ROOT / "Makefile"


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_blueprint_pattern_inheritance_is_explicit_and_read_only():
    rule = load_yaml(PROJECT_FIRST)
    policy = rule["blueprint_pattern_inheritance_policy"]

    assert policy["access"] == "READ_ONLY_STRICT"
    assert (
        policy[
            "inspect_committed_blueprint_equivalent_before_new_generic_tool"
        ]
        is True
    )
    assert (
        policy[
            "inherit_semantics_safety_gates_and_operator_pattern_when_compatible"
        ]
        is True
    )
    assert policy["local_implementation_required"] is True
    assert policy["hidden_runtime_dependency_on_blueprint_forbidden"] is True
    assert policy["blueprint_mutation_from_module_forbidden"] is True
    assert policy["blind_current_step_increment_forbidden"] is True
    assert (
        policy[
            "automatic_next_step_activation_without_explicit_gate_forbidden"
        ]
        is True
    )


def test_fresh_assistant_context_requires_blueprint_inheritance_review():
    contract = load_yaml(ASSISTANT_CONTEXT)

    assert (
        "blueprint_read_only_pattern_inheritance_policy"
        in contract["fresh_assistant_must_know"]
    )
    assert (
        "invent_generic_local_coordination_tool_before_inspecting_"
        "committed_blueprint_equivalent"
        in contract["fresh_assistant_must_not"]
    )


def test_local_transition_tool_has_no_blueprint_runtime_dependency():
    protocol = load_yaml(PROTOCOL)
    source = TOOL.read_text(encoding="utf-8")
    makefile = MAKEFILE.read_text(encoding="utf-8")

    assert protocol["inheritance_disposition"] == "ADAPT_LOCALLY"
    assert protocol["runtime_dependency_on_blueprint"] is False
    assert protocol["blueprint_mutation_allowed"] is False
    assert "../forprint_system_blueprint" not in source
    assert "forprint_system_blueprint" not in source

    assert "gdl-accept-and-advance:" in makefile
    assert "gdl-transition-closeout-review:" in makefile
    assert "gdl-transition-closeout-apply:" in makefile

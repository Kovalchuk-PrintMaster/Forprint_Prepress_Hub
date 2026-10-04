from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "coordination"
    / "module_assistant_context.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "module_assistant_context_under_test",
        SCRIPT,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def permit_fixture_files(module) -> None:
    # Isolate scope-priority selection from repository/tracking safety checks.
    module.safe_candidate = lambda path, root: path.is_file()


def build_minimal_gdl_tree(root: Path) -> dict[str, Path]:
    contract = (
        root
        / "coordination"
        / "graphic_design_lab"
        / "continuity"
        / "assistant_context_contract_v0_1.yaml"
    )
    contract.parent.mkdir(parents=True, exist_ok=True)
    contract.write_text(
        "schema_version: test\n"
        "context_pack_priority_paths:\n"
        "- coordination/graphic_design_lab/execution/\n"
        "- coordination/graphic_design_lab/client_workflows/index.yaml\n"
        "- coordination/graphic_design_lab/continuity/\n",
        encoding="utf-8",
    )

    execution = (
        root
        / "coordination"
        / "graphic_design_lab"
        / "execution"
        / "execution_plan_contract_v0_1.yaml"
    )
    execution.parent.mkdir(parents=True, exist_ok=True)
    execution.write_text(
        "schema_version: execution_plan_without_topic_keyword\n",
        encoding="utf-8",
    )

    client_index = (
        root
        / "coordination"
        / "graphic_design_lab"
        / "client_workflows"
        / "index.yaml"
    )
    client_index.parent.mkdir(parents=True, exist_ok=True)
    client_index.write_text(
        "schema_version: client_workflow_without_topic_keyword\n",
        encoding="utf-8",
    )

    continuity_addendum = (
        root
        / "coordination"
        / "graphic_design_lab"
        / "continuity"
        / "client_workflow_execution_context_addendum_v0_1.yaml"
    )
    continuity_addendum.write_text(
        "schema_version: continuity_addendum_without_topic_keyword\n",
        encoding="utf-8",
    )

    return {
        "execution": execution,
        "client_index": client_index,
        "continuity_addendum": continuity_addendum,
    }


def test_scope_priority_candidates_include_contract_paths(tmp_path):
    module = load_module()
    permit_fixture_files(module)
    files = build_minimal_gdl_tree(tmp_path)

    selected = module.scope_priority_candidates(
        tmp_path,
        "graphic_design_lab",
    )
    rels = {path.relative_to(tmp_path).as_posix() for path in selected}

    assert files["execution"].relative_to(tmp_path).as_posix() in rels
    assert files["client_index"].relative_to(tmp_path).as_posix() in rels
    assert files["continuity_addendum"].relative_to(tmp_path).as_posix() in rels


def test_other_scope_does_not_force_gdl_priority_paths(tmp_path):
    module = load_module()
    permit_fixture_files(module)
    build_minimal_gdl_tree(tmp_path)

    selected = module.scope_priority_candidates(tmp_path, "bootstrap")

    assert selected == []


def test_local_candidates_three_argument_contract_is_preserved(tmp_path):
    module = load_module()
    permit_fixture_files(module)

    selected = module.local_candidates(
        tmp_path,
        "MODULE_CONTEXT",
        ["empirical"],
    )

    assert isinstance(selected, list)

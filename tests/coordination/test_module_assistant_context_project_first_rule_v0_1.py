from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "coordination" / "module_assistant_context.py"
RULE_REL = (
    "coordination/graphic_design_lab/continuity/"
    "project_first_working_rule_v0_1.yaml"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "module_assistant_context_project_first_under_test",
        SCRIPT,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_project_first_rule_is_always_local():
    module = load_module()
    assert RULE_REL in module.ALWAYS_LOCAL


def test_project_first_rule_survives_unrelated_topic_filter(tmp_path):
    module = load_module()

    rule = tmp_path / RULE_REL
    rule.parent.mkdir(parents=True, exist_ok=True)
    rule.write_text(
        "schema_version: test\n"
        "project_internal_tooling_policy:\n"
        "  canonical_rule: REPEATABLE_EXECUTION_LOGIC_LIVES_IN_PROJECT\n",
        encoding="utf-8",
    )

    module.safe_candidate = lambda path, root: path.is_file()

    selected = module.local_candidates(
        tmp_path,
        "MODULE_CONTEXT",
        ["totally_unrelated_topic"],
    )
    rels = {
        path.relative_to(tmp_path).as_posix()
        for path in selected
    }

    assert RULE_REL in rels

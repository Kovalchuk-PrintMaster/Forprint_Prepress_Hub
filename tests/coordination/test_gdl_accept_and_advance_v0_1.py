from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml

from scripts.coordination import gdl_accept_and_advance_v0_1 as gdl


class _IndentedSafeDumper(yaml.SafeDumper):
    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


def write_yaml(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.dump(
            value,
            Dumper=_IndentedSafeDumper,
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def fixture_state(tmp_path: Path) -> dict[str, Path]:
    root = tmp_path
    plan_path = root / gdl.PLAN_REL
    cursor_path = root / gdl.CURSOR_REL

    write_yaml(
        plan_path,
        {
            "steps": [
                {
                    "id": "GC-E2E-00",
                    "state": "COMPLETED_LOCAL",
                    "exit_criteria": ["foundation_done"],
                },
                {
                    "id": "GC-E2E-07",
                    "state": "ACTIVE",
                    "exit_criteria": [
                        "operator_flow",
                        "exact_bundle_path",
                    ],
                },
                {
                    "id": "GC-E2E-08",
                    "state": "COMPLETED_LOCAL",
                    "exit_criteria": ["constructor_done"],
                },
                {
                    "id": "GC-E2E-09",
                    "state": "PLANNED",
                    "depends_on": [
                        "GC-E2E-07",
                        "GC-E2E-08",
                    ],
                    "exit_criteria": ["composition_done"],
                },
                {
                    "id": "GC-E2E-10",
                    "state": "PLANNED",
                    "blocked_by": ["GC-E2E-11"],
                    "exit_criteria": ["preview_done"],
                },
                {
                    "id": "GC-E2E-11",
                    "state": "PLANNED",
                    "exit_criteria": ["export_done"],
                },
            ]
        },
    )
    write_yaml(
        cursor_path,
        {
            "active_tasks": [
                {
                    "task_id": "GDL-TASK-GREETING-CARD-E2E-001",
                    "state": "ACTIVE",
                    "completed_steps": [
                        "GC-E2E-00",
                        "GC-E2E-08",
                    ],
                    "current_step": "GC-E2E-07",
                    "completed_subcheckpoints": [],
                    "current_checkpoint": {
                        "id": "SMB_LOCAL_ONE_CLICK_LAUNCHER_REQUIRED",
                        "state": "ACTIVE",
                    },
                    "next_action": "Finish launcher proof.",
                }
            ]
        },
    )
    cursor_text = cursor_path.read_text(encoding="utf-8")
    old_cursor_tail = (
        "    next_action: Finish launcher proof.\n"
    )
    new_cursor_tail = (
        "    next_action: >\n"
        "      Finish launcher proof.\n"
        "\n"
        "    completion_criterion: >\n"
        "      Fixture launcher completion criterion.\n"
    )
    if cursor_text.count(old_cursor_tail) != 1:
        raise AssertionError(
            "fixture cursor next_action shape drift"
        )
    cursor_path.write_text(
        cursor_text.replace(
            old_cursor_tail,
            new_cursor_tail,
            1,
        ),
        encoding="utf-8",
    )

    return {
        "root": root,
        "plan": plan_path,
        "cursor": cursor_path,
    }


def request() -> dict:
    return {
        "schema_version": "gdl_accept_and_advance_request_v0_1",
        "operation_id": "gc_e2e_07_to_09",
        "explicit_operator_input": True,
        "task_id": "GDL-TASK-GREETING-CARD-E2E-001",
        "accept": {
            "decision": "ACCEPT",
            "explicit_operator_input": True,
            "step_id": "GC-E2E-07",
            "completion_evidence": {
                "exit_criteria_satisfied": {
                    "operator_flow": True,
                    "exact_bundle_path": True,
                },
                "implementation_commits": ["abc123"],
            },
        },
        "advance": {
            "mode": "activate_explicit_step",
            "explicit_operator_input": True,
            "expected_step_id": "GC-E2E-09",
            "current_checkpoint_id": (
                "DETERMINISTIC_COMPOSITION_"
                "ILLUSTRATOR_WORKER_REQUIRED"
            ),
            "next_action": (
                "Build deterministic composition and Illustrator worker."
            ),
        },
        "closeout": {
            "commit_message": (
                "chore(gdl): close launcher and activate composition"
            )
        },
    }


def test_preview_is_read_only_and_explicitly_bound(tmp_path: Path) -> None:
    paths = fixture_state(tmp_path)
    req = request()
    before = {
        "plan": paths["plan"].read_bytes(),
        "cursor": paths["cursor"].read_bytes(),
    }

    result = gdl.prepare_operation(paths["root"], req)

    assert result["result_state"] == "READY_TO_APPLY"
    assert result["accepted_step_id"] == "GC-E2E-07"
    assert result["explicit_next_step_id"] == "GC-E2E-09"
    assert result["blind_current_step_increment_performed"] is False
    assert result["automatic_next_step_activation_performed"] is False
    assert paths["plan"].read_bytes() == before["plan"]
    assert paths["cursor"].read_bytes() == before["cursor"]


def test_non_accept_is_rejected(tmp_path: Path) -> None:
    paths = fixture_state(tmp_path)
    req = request()
    req["accept"]["decision"] = "HOLD"

    with pytest.raises(
        gdl.GdlAcceptAndAdvanceError,
        match="only an explicit ACCEPT",
    ):
        gdl.prepare_operation(paths["root"], req)


def test_all_exit_criteria_require_explicit_true_evidence(
    tmp_path: Path,
) -> None:
    paths = fixture_state(tmp_path)
    req = request()
    req["accept"]["completion_evidence"][
        "exit_criteria_satisfied"
    ]["exact_bundle_path"] = False

    with pytest.raises(
        gdl.GdlAcceptAndAdvanceError,
        match="does not satisfy exit criteria",
    ):
        gdl.prepare_operation(paths["root"], req)


def test_dependency_gate_allows_step_when_current_accept_closes_dependency(
    tmp_path: Path,
) -> None:
    paths = fixture_state(tmp_path)

    result = gdl.prepare_operation(paths["root"], request())

    assert result["explicit_next_step_id"] == "GC-E2E-09"


def test_dependency_gate_blocks_ineligible_explicit_step(
    tmp_path: Path,
) -> None:
    paths = fixture_state(tmp_path)
    req = request()
    req["advance"]["expected_step_id"] = "GC-E2E-10"

    with pytest.raises(
        gdl.GdlAcceptAndAdvanceError,
        match="dependency eligibility failed",
    ):
        gdl.prepare_operation(paths["root"], req)


def test_apply_updates_plan_cursor_and_writes_evidence_and_closeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = fixture_state(tmp_path)
    monkeypatch.setattr(
        gdl,
        "_git_head",
        lambda root: "a" * 40,
    )

    result = gdl.apply_operation(
        paths["root"],
        request(),
        operator_confirmation="gc_e2e_07_to_09",
    )

    assert result["result_state"] == "ACCEPT_AND_ADVANCE_APPLIED"

    plan = load_yaml(paths["plan"])
    by_id = {item["id"]: item for item in plan["steps"]}
    assert by_id["GC-E2E-07"]["state"] == "COMPLETED_LOCAL"
    assert by_id["GC-E2E-09"]["state"] == "ACTIVE"

    cursor = load_yaml(paths["cursor"])
    task = cursor["active_tasks"][0]
    assert task["completed_steps"] == [
        "GC-E2E-00",
        "GC-E2E-07",
        "GC-E2E-08",
    ]
    assert task["current_step"] == "GC-E2E-09"
    assert task["current_checkpoint"]["state"] == "ACTIVE"

    evidence = load_yaml(paths["root"] / result["evidence_path"])
    assert evidence["dependency_eligibility"] == "PASS"
    assert evidence["git_mutation_performed"] is False
    assert evidence["blueprint_runtime_dependency"] is False

    manifest = json.loads(
        (paths["root"] / gdl.CLOSEOUT_REL).read_text(encoding="utf-8")
    )
    assert manifest["expected_head"] == "a" * 40
    assert manifest["write_set"] == [
        gdl.PLAN_REL.as_posix(),
        gdl.CURSOR_REL.as_posix(),
        (
            gdl.EVIDENCE_DIR_REL
            / "gc_e2e_07_to_09.yaml"
        ).as_posix(),
        gdl.CLOSEOUT_REL.as_posix(),
    ]


def test_apply_requires_confirmation_equal_to_operation_id(
    tmp_path: Path,
) -> None:
    paths = fixture_state(tmp_path)

    with pytest.raises(
        gdl.GdlAcceptAndAdvanceError,
        match="must equal operation_id",
    ):
        gdl.apply_operation(
            paths["root"],
            request(),
            operator_confirmation="wrong",
        )


def test_apply_is_idempotent_for_same_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = fixture_state(tmp_path)
    monkeypatch.setattr(
        gdl,
        "_git_head",
        lambda root: "b" * 40,
    )
    req = request()

    first = gdl.apply_operation(
        paths["root"],
        req,
        operator_confirmation="gc_e2e_07_to_09",
    )
    second = gdl.apply_operation(
        paths["root"],
        req,
        operator_confirmation="gc_e2e_07_to_09",
    )

    assert first["result_state"] == "ACCEPT_AND_ADVANCE_APPLIED"
    assert second["result_state"] == "ALREADY_APPLIED"


def test_same_operation_id_with_different_request_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = fixture_state(tmp_path)
    monkeypatch.setattr(
        gdl,
        "_git_head",
        lambda root: "c" * 40,
    )

    gdl.apply_operation(
        paths["root"],
        request(),
        operator_confirmation="gc_e2e_07_to_09",
    )

    changed = copy.deepcopy(request())
    changed["closeout"]["commit_message"] = "different"

    with pytest.raises(
        gdl.GdlAcceptAndAdvanceError,
        match="different request",
    ):
        gdl.apply_operation(
            paths["root"],
            changed,
            operator_confirmation="gc_e2e_07_to_09",
        )


def test_transition_failure_restores_exact_pre_transition_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = fixture_state(tmp_path)
    before_plan = paths["plan"].read_bytes()
    before_cursor = paths["cursor"].read_bytes()
    monkeypatch.setattr(
        gdl,
        "_git_head",
        lambda root: "d" * 40,
    )

    real_write_yaml = gdl._atomic_write_yaml

    def failing_write(path: Path, value: dict) -> None:
        if "accept_and_advance" in path.parts:
            raise OSError("simulated evidence failure")
        real_write_yaml(path, value)

    monkeypatch.setattr(
        gdl,
        "_atomic_write_yaml",
        failing_write,
    )

    with pytest.raises(OSError, match="simulated evidence failure"):
        gdl.apply_operation(
            paths["root"],
            request(),
            operator_confirmation="gc_e2e_07_to_09",
        )

    assert paths["plan"].read_bytes() == before_plan
    assert paths["cursor"].read_bytes() == before_cursor
    assert not (
        paths["root"]
        / gdl.EVIDENCE_DIR_REL
        / "gc_e2e_07_to_09.yaml"
    ).exists()


def test_private_live_path_markers_are_rejected(tmp_path: Path) -> None:
    paths = fixture_state(tmp_path)
    req = request()
    req["accept"]["completion_evidence"]["private"] = (
        "/srv/smb/customer"
    )

    with pytest.raises(
        gdl.GdlAcceptAndAdvanceError,
        match="forbidden private",
    ):
        gdl.prepare_operation(paths["root"], req)

from __future__ import annotations

from pathlib import Path

import yaml

from scripts.coordination.sync_prompt_state import (
    MODULE_ID,
    sync_prompt_state,
    validate_prompt_state,
)


PROMPT_ID = "prepress_gdl_guided_intake_creator_handoff_foundation_v0_1"
PROMPT_NAME = (
    "2026-09-28__forprint_prepress_hub__"
    "gdl_guided_intake_creator_handoff_foundation_v0_1.md"
)


def write_yaml(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def prepare_project(root: Path) -> dict[str, Path]:
    blueprint_module = root / "blueprint/forprint_prepress_hub"
    approved = blueprint_module / "approved"
    approved.mkdir(parents=True)

    prompt_file = approved / PROMPT_NAME
    prompt_file.write_text("# Published GDL prompt\n", encoding="utf-8")

    blueprint_index = blueprint_module / "index.yaml"
    write_yaml(
        blueprint_index,
        {
            "schema_version": "prompt_queue_v0_2",
            "module": MODULE_ID,
            "prompt_queue": [
                {
                    "prompt_id": PROMPT_ID,
                    "sequence": 1,
                    "title": "Prepress GDL Guided Intake / Creator Handoff Foundation v0.1",
                    "file": f"approved/{PROMPT_NAME}",
                    "target_module": MODULE_ID,
                    "phase": "gdl_guided_intake_creator_handoff_foundation_v0_1",
                    "priority": "high",
                    "module_execution": {
                        "status": "ready_for_module_pull",
                        "completion_commit": None,
                        "completion_report": None,
                    },
                    "blueprint_review": {
                        "status": "not_started",
                        "acceptance_commit": None,
                        "accepted_at": None,
                    },
                }
            ],
        },
    )

    local_index = root / "coordination/prompts/index.yaml"
    write_yaml(
        local_index,
        {
            "schema_version": "forprint_prompt_index_v0_1",
            "module_id": MODULE_ID,
            "status": "bootstrap_empty",
            "received": [],
            "active": [],
            "archived": [],
            "note": "Bootstrap-only prompt lifecycle placeholder.",
        },
    )

    status_yaml = root / "coordination/status/current_status.yaml"
    write_yaml(
        status_yaml,
        {
            "schema_version": "forprint_prepress_hub_status_v0_1",
            "module_id": MODULE_ID,
            "state": "SELF_ONBOARD_VERIFIED",
            "foundation_state": "FOUNDATION_REMOTE_CONTAINED",
            "continuity_commissioned": True,
            "canonical_runtime_ready": False,
            "production_write_enabled": False,
            "graphic_design_lab": "PLANNED_NOT_INITIALIZED",
            "graphic_design_lab_runtime_initialized": False,
            "current_focus": "gdl_guided_design_intake_and_creator_handoff_planning",
            "next_expected_focus": (
                "gdl_product_playbook_and_greeting_card_intake_pilot_foundation"
            ),
        },
    )

    status_md = root / "coordination/status/current_status.md"
    status_md.parent.mkdir(parents=True, exist_ok=True)
    status_md.write_text(
        "# ForPrint Prepress Hub — current status\n\n"
        "Existing planning context must be preserved.\n",
        encoding="utf-8",
    )

    return {
        "blueprint_module": blueprint_module,
        "blueprint_index": blueprint_index,
        "received": root / "coordination/prompts/received",
        "active": root / "coordination/prompts/active",
        "archived": root / "coordination/prompts/archived",
        "local_index": local_index,
        "status_yaml": status_yaml,
        "status_md": status_md,
    }


def test_sync_migrates_bootstrap_index_and_activates_prompt_idempotently(
    tmp_path: Path,
) -> None:
    paths = prepare_project(tmp_path)
    blueprint_before = snapshot(tmp_path / "blueprint")

    result = sync_prompt_state(
        module_id=MODULE_ID,
        blueprint_index_path=paths["blueprint_index"],
        blueprint_module_dir=paths["blueprint_module"],
        received_dir=paths["received"],
        active_dir=paths["active"],
        archived_dir=paths["archived"],
        local_index_path=paths["local_index"],
        status_yaml_path=paths["status_yaml"],
        status_markdown_path=paths["status_md"],
        prompt_id=PROMPT_ID,
    )

    assert result.active_prompt_id == PROMPT_ID
    assert snapshot(tmp_path / "blueprint") == blueprint_before
    assert len(list(paths["received"].glob("*.md"))) == 1
    assert len(list(paths["active"].glob("*.md"))) == 1

    index = yaml.safe_load(paths["local_index"].read_text(encoding="utf-8"))
    assert index["schema_version"] == "module_prompt_index_v0_1"
    assert index["active_prompt_id"] == PROMPT_ID
    assert len(index["prompts"]) == 1
    assert index["prompts"][0]["status"] == "active"
    assert "received" not in index
    assert "archived" not in index

    status = yaml.safe_load(paths["status_yaml"].read_text(encoding="utf-8"))
    assert status["state"] == "SELF_ONBOARD_VERIFIED"
    assert status["current_focus"] == "gdl_guided_design_intake_and_creator_handoff_planning"
    assert status["next_expected_focus"] == "gdl_product_playbook_and_greeting_card_intake_pilot_foundation"
    assert status["production_write_enabled"] is False
    assert status["graphic_design_lab_runtime_initialized"] is False
    assert status["source_prompt_id"] == PROMPT_ID
    assert status["prompt_intake"]["status"] == "active"
    assert status["prompt_intake"]["implementation_started"] is False
    assert status["prompt_intake"]["blueprint_access"] == "READ_ONLY_STRICT"

    status_md = paths["status_md"].read_text(encoding="utf-8")
    assert "Existing planning context must be preserved." in status_md
    assert "<!-- BEGIN ACTIVE_BLUEPRINT_PROMPT -->" in status_md
    assert "SYSTEM_BLUEPRINT_ACCESS_FROM_PREPRESS=READ_ONLY_STRICT" in status_md

    assert (
        validate_prompt_state(
            local_index_path=paths["local_index"],
            status_yaml_path=paths["status_yaml"],
            received_dir=paths["received"],
            active_dir=paths["active"],
        )
        == []
    )

    module_before_second_sync = snapshot(tmp_path / "coordination")
    sync_prompt_state(
        module_id=MODULE_ID,
        blueprint_index_path=paths["blueprint_index"],
        blueprint_module_dir=paths["blueprint_module"],
        received_dir=paths["received"],
        active_dir=paths["active"],
        archived_dir=paths["archived"],
        local_index_path=paths["local_index"],
        status_yaml_path=paths["status_yaml"],
        status_markdown_path=paths["status_md"],
        prompt_id=PROMPT_ID,
    )
    assert snapshot(tmp_path / "coordination") == module_before_second_sync
    assert snapshot(tmp_path / "blueprint") == blueprint_before


def test_prompt_state_rejects_multiple_active_files(tmp_path: Path) -> None:
    paths = prepare_project(tmp_path)
    sync_prompt_state(
        module_id=MODULE_ID,
        blueprint_index_path=paths["blueprint_index"],
        blueprint_module_dir=paths["blueprint_module"],
        received_dir=paths["received"],
        active_dir=paths["active"],
        archived_dir=paths["archived"],
        local_index_path=paths["local_index"],
        status_yaml_path=paths["status_yaml"],
        status_markdown_path=paths["status_md"],
        prompt_id=PROMPT_ID,
    )

    (paths["active"] / "unexpected.md").write_text("# Unexpected\n", encoding="utf-8")

    errors = validate_prompt_state(
        local_index_path=paths["local_index"],
        status_yaml_path=paths["status_yaml"],
        received_dir=paths["received"],
        active_dir=paths["active"],
    )

    assert any("exactly one Markdown prompt" in error for error in errors)


def test_nonempty_legacy_prompt_state_is_not_silently_migrated(
    tmp_path: Path,
) -> None:
    paths = prepare_project(tmp_path)
    index = yaml.safe_load(paths["local_index"].read_text(encoding="utf-8"))
    index["active"] = ["legacy-prompt"]
    write_yaml(paths["local_index"], index)

    try:
        sync_prompt_state(
            module_id=MODULE_ID,
            blueprint_index_path=paths["blueprint_index"],
            blueprint_module_dir=paths["blueprint_module"],
            received_dir=paths["received"],
            active_dir=paths["active"],
            archived_dir=paths["archived"],
            local_index_path=paths["local_index"],
            status_yaml_path=paths["status_yaml"],
            status_markdown_path=paths["status_md"],
            prompt_id=PROMPT_ID,
        )
    except ValueError as exc:
        assert "must be empty before migration" in str(exc)
    else:
        raise AssertionError("Expected legacy-state migration refusal")


def test_wrong_blueprint_module_is_rejected(tmp_path: Path) -> None:
    paths = prepare_project(tmp_path)
    index = yaml.safe_load(paths["blueprint_index"].read_text(encoding="utf-8"))
    index["module"] = "another_module"
    write_yaml(paths["blueprint_index"], index)

    try:
        sync_prompt_state(
            module_id=MODULE_ID,
            blueprint_index_path=paths["blueprint_index"],
            blueprint_module_dir=paths["blueprint_module"],
            received_dir=paths["received"],
            active_dir=paths["active"],
            archived_dir=paths["archived"],
            local_index_path=paths["local_index"],
            status_yaml_path=paths["status_yaml"],
            status_markdown_path=paths["status_md"],
            prompt_id=PROMPT_ID,
        )
    except ValueError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("Expected wrong-module refusal")

def test_sync_preserves_verified_implementation_evidence(tmp_path: Path) -> None:
    paths = prepare_project(tmp_path)

    sync_prompt_state(
        module_id=MODULE_ID,
        blueprint_index_path=paths["blueprint_index"],
        blueprint_module_dir=paths["blueprint_module"],
        received_dir=paths["received"],
        active_dir=paths["active"],
        archived_dir=paths["archived"],
        local_index_path=paths["local_index"],
        status_yaml_path=paths["status_yaml"],
        status_markdown_path=paths["status_md"],
        prompt_id=PROMPT_ID,
    )

    status = yaml.safe_load(paths["status_yaml"].read_text(encoding="utf-8"))
    status["prompt_intake"]["implementation_started"] = True
    status["prompt_intake"]["implementation_status"] = (
        "VERIFIED_LOCAL_IMPLEMENTATION_PUBLISHED"
    )
    status["prompt_intake"]["implementation_commits"] = ["7301343", "e7cf115"]
    status["prompt_intake"]["next_contour_activated"] = False
    status["prompt_intake"]["completion_report"] = (
        "coordination/reports/completion/report.md"
    )
    status["prompt_intake"]["completion_commit"] = "17a21d4"
    status["prompt_intake"]["completion_state"] = (
        "READY_FOR_BLUEPRINT_REVIEW"
    )
    write_yaml(paths["status_yaml"], status)

    sync_prompt_state(
        module_id=MODULE_ID,
        blueprint_index_path=paths["blueprint_index"],
        blueprint_module_dir=paths["blueprint_module"],
        received_dir=paths["received"],
        active_dir=paths["active"],
        archived_dir=paths["archived"],
        local_index_path=paths["local_index"],
        status_yaml_path=paths["status_yaml"],
        status_markdown_path=paths["status_md"],
        prompt_id=PROMPT_ID,
    )

    status = yaml.safe_load(paths["status_yaml"].read_text(encoding="utf-8"))
    intake = status["prompt_intake"]

    assert intake["implementation_started"] is True
    assert intake["implementation_status"] == "VERIFIED_LOCAL_IMPLEMENTATION_PUBLISHED"
    assert intake["implementation_commits"] == ["7301343", "e7cf115"]
    assert intake["next_contour_activated"] is False
    assert (
        intake["completion_report"]
        == "coordination/reports/completion/report.md"
    )
    assert intake["completion_commit"] == "17a21d4"
    assert (
        intake["completion_state"]
        == "READY_FOR_BLUEPRINT_REVIEW"
    )



def test_sync_closes_active_prompt_after_blueprint_acceptance(
    tmp_path: Path,
) -> None:
    paths = prepare_project(tmp_path)

    sync_prompt_state(
        module_id=MODULE_ID,
        blueprint_index_path=paths["blueprint_index"],
        blueprint_module_dir=paths["blueprint_module"],
        received_dir=paths["received"],
        active_dir=paths["active"],
        archived_dir=paths["archived"],
        local_index_path=paths["local_index"],
        status_yaml_path=paths["status_yaml"],
        status_markdown_path=paths["status_md"],
        prompt_id=PROMPT_ID,
    )

    blueprint = yaml.safe_load(
        paths["blueprint_index"].read_text(
            encoding="utf-8"
        )
    )

    record = [
        item
        for item in blueprint["prompt_queue"]
        if item["prompt_id"] == PROMPT_ID
    ][0]

    record["module_execution"]["status"] = (
        "completed_by_module"
    )
    record["module_execution"]["completion_report"] = (
        "coordination/reports/completion/report.md"
    )
    record["module_execution"]["completion_commit"] = (
        "5957c3a"
    )

    record["blueprint_review"]["status"] = (
        "accepted_by_blueprint"
    )
    record["blueprint_review"]["acceptance_commit"] = None
    record["blueprint_review"]["accepted_at"] = (
        "2026-09-30"
    )

    write_yaml(
        paths["blueprint_index"],
        blueprint,
    )

    sync_prompt_state(
        module_id=MODULE_ID,
        blueprint_index_path=paths["blueprint_index"],
        blueprint_module_dir=paths["blueprint_module"],
        received_dir=paths["received"],
        active_dir=paths["active"],
        archived_dir=paths["archived"],
        local_index_path=paths["local_index"],
        status_yaml_path=paths["status_yaml"],
        status_markdown_path=paths["status_md"],
    )

    index = yaml.safe_load(
        paths["local_index"].read_text(
            encoding="utf-8"
        )
    )

    assert index["active_prompt_id"] is None

    entry = [
        item
        for item in index["prompts"]
        if item["prompt_id"] == PROMPT_ID
    ][0]

    assert entry["status"] == "completed_in_module"
    assert (
        entry["module_execution_status"]
        == "completed_by_module"
    )
    assert (
        entry["blueprint_review_status"]
        == "accepted_by_blueprint"
    )
    assert entry["completion_commit"] == "5957c3a"
    assert (
        entry["completion_report"]
        == "coordination/reports/completion/report.md"
    )
    assert entry["blueprint_acceptance_commit"] is None
    assert entry["blueprint_accepted_at"] == "2026-09-30"

    assert "active_file" not in entry
    assert entry["archived_file"].startswith(
        "coordination/prompts/archived/"
    )

    assert not list(
        paths["active"].glob("*.md")
    )

    assert list(
        paths["archived"].glob("*.md")
    )

    status = yaml.safe_load(
        paths["status_yaml"].read_text(
            encoding="utf-8"
        )
    )

    assert status["status"] == "completed_in_module"
    assert (
        status["current_focus"]
        == "gdl_guided_intake_creator_handoff_foundation_accepted"
    )
    assert (
        status["next_expected_focus"]
        == "separately_authorized_next_gdl_contour"
    )
    assert (
        status["prompt_progress"]["completion"]
        == "completed"
    )
    assert (
        status["prompt_intake"]["status"]
        == "completed_in_module"
    )
    assert (
        status["prompt_intake"]["completion_state"]
        == "ACCEPTED_BY_BLUEPRINT"
    )
    assert (
        status["prompt_intake"]["blueprint_review_status"]
        == "accepted_by_blueprint"
    )
    assert (
        status["prompt_intake"]["next_contour_activated"]
        is False
    )

    errors = validate_prompt_state(
        local_index_path=paths["local_index"],
        status_yaml_path=paths["status_yaml"],
        received_dir=paths["received"],
        active_dir=paths["active"],
    )

    assert errors == []

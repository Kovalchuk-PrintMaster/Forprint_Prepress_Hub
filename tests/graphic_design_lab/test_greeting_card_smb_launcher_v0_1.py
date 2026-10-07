from __future__ import annotations

import base64
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "scripts/graphic_design_lab/greeting_cards/smb_launcher_bridge.py"
PS1 = ROOT / "scripts/graphic_design_lab/greeting_cards/windows/gdl_greeting_card_launcher.ps1"
CMD = ROOT / "scripts/graphic_design_lab/greeting_cards/windows/launch_greeting_card.cmd"


def load_bridge():
    spec = importlib.util.spec_from_file_location("gdl_smb_launcher_bridge", BRIDGE)
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def token(value: str) -> str:
    raw = base64.urlsafe_b64encode(value.encode("utf-8"))
    return raw.decode("ascii").rstrip("=")


def test_bridge_resolves_unicode_space_plus_path_inside_share(tmp_path):
    bridge = load_bridge()
    share_root = tmp_path / "share"
    bundle = (
        share_root
        / "Клієнт +380 00 000 00 00"
        / "_forprint_automation"
        / "gc_e2e_07_lab"
        / "accepted_constructor_bundle.yaml"
    )
    bundle.parent.mkdir(parents=True)
    bundle.write_text("schema_version: test\n", encoding="utf-8")
    relative = bundle.relative_to(share_root).as_posix()

    resolved = bridge.resolve_bundle_path(
        "In_Progress",
        token(relative),
        share_roots={"In_Progress": share_root},
    )
    assert resolved == bundle.resolve()


def test_bridge_rejects_parent_traversal(tmp_path):
    bridge = load_bridge()
    share_root = tmp_path / "share"
    share_root.mkdir()

    with pytest.raises(RuntimeError, match="relative_path_contains_forbidden_segment"):
        bridge.resolve_bundle_path(
            "In_Progress",
            token("../accepted_constructor_bundle.yaml"),
            share_roots={"In_Progress": share_root},
        )


def test_bridge_rejects_symlink_escape(tmp_path):
    bridge = load_bridge()
    share_root = tmp_path / "share"
    outside = tmp_path / "outside"
    share_root.mkdir()
    outside.mkdir()
    outside_bundle = outside / "accepted_constructor_bundle.yaml"
    outside_bundle.write_text("schema_version: test\n", encoding="utf-8")
    (share_root / "escape").symlink_to(outside, target_is_directory=True)

    with pytest.raises(RuntimeError, match="resolved_path_escapes_share_root"):
        bridge.resolve_bundle_path(
            "In_Progress",
            token("escape/accepted_constructor_bundle.yaml"),
            share_roots={"In_Progress": share_root},
        )


def test_bridge_targets_canonical_constructor_make_entrypoint():
    bridge = load_bridge()
    command = bridge.constructor_entrypoint_command(
        Path("/tmp/accepted_constructor_bundle.yaml")
    )
    assert command == [
        "make",
        "gdl-greeting-card-constructor-ingest",
        "BUNDLE=/tmp/accepted_constructor_bundle.yaml",
    ]

    source = BRIDGE.read_text(encoding="utf-8")
    assert "shell=True" not in source
    assert "/srv/smb/In_Progress/data" in source


def test_windows_launcher_is_location_aware_and_ssh_alias_based():
    source = PS1.read_text(encoding="utf-8")
    assert "$PSScriptRoot" in source
    assert 'SshAlias = "s01"' in source
    assert 'ShareName = "In_Progress"' in source
    assert "BatchMode=yes" in source
    assert "ToBase64String" in source
    assert "[Console]::OutputEncoding" in source
    assert '$ErrorActionPreference = "Continue"' in source
    assert "$PreviousErrorActionPreference" in source
    assert "finally {" in source
    assert "gdl-greeting-card-smb-launch" in source
    assert "/srv/smb/In_Progress/data" not in source
    assert "accepted_constructor_bundle.yaml" in source


def test_cmd_is_thin_one_click_wrapper():
    source = CMD.read_text(encoding="utf-8")
    assert "%~dp0gdl_greeting_card_launcher.ps1" in source
    assert "powershell.exe" in source
    assert "pause" in source.lower()


def test_makefile_exposes_smb_launcher_bridge():
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "gdl-greeting-card-smb-launch:" in makefile
    assert "GDL_GREETING_CARD_SMB_LAUNCH_BRIDGE" in makefile
    assert "RELATIVE_PATH_B64" in makefile

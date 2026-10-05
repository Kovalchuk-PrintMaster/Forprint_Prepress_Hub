import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

TOOL = (
    ROOT
    / "scripts"
    / "coordination"
    / "project_closeout.py"
)

MANIFEST = (
    ROOT
    / "coordination"
    / "graphic_design_lab"
    / "execution"
    / "greeting_card_operator_companion_closeout_v0_1.json"
)


def load_tool():
    spec = (
        importlib.util
        .spec_from_file_location(
            "project_closeout_tested",
            TOOL,
        )
    )

    assert spec
    assert spec.loader

    module = (
        importlib.util
        .module_from_spec(spec)
    )

    spec.loader.exec_module(
        module
    )

    return module


def test_closeout_surfaces_exist():
    assert TOOL.is_file()
    assert MANIFEST.is_file()


def test_manifest_is_exact_and_deduplicated():
    data = json.loads(
        MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    assert (
        data["workstream_id"]
        == "gdl_greeting_card_operator_companion_v022b"
    )

    assert (
        data["expected_head"]
        == "8ffecdabefddb522ce3d939c8ae0cdb2ad87770d"
    )

    assert len(
        data["write_set"]
    ) == len(
        set(data["write_set"])
    )

    assert (
        "Makefile"
        in data["write_set"]
    )


def test_apply_requires_explicit_confirmation():
    module = load_tool()

    data = json.loads(
        MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    try:
        module.apply(
            data,
            "NO",
        )

    except module.Fail as exc:
        assert (
            "EXPLICIT_CONFIRMATION_REQUIRED"
            in str(exc)
        )

    else:
        raise AssertionError(
            "apply accepted "
            "without confirmation"
        )


def test_makefile_exposes_two_phase_closeout():
    text = (
        ROOT
        / "Makefile"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "gdl-closeout-review:"
        in text
    )

    assert (
        "gdl-closeout-apply:"
        in text
    )

    assert (
        "CONFIRM=YES"
        in text
    )


def test_precommit_failure_has_exact_unstage_guard():
    text = TOOL.read_text(encoding="utf-8")

    assert "def unstage_exact(paths):" in text
    assert '"restore", "--staged", "--", *paths' in text
    assert "except Exception:" in text
    assert 'unstage_exact(' in text

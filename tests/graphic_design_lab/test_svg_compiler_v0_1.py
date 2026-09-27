from datetime import date
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

from app.graphic_design_lab.compiler import compile_document
from app.graphic_design_lab.structural_validation import validate_compiled_svg

ROOT = Path(__file__).resolve().parents[2]


def load(rel):
    return yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))


def fixture():
    return load("tests/fixtures/graphic_design_lab/dated_diary_a5_phase1_v0_1.yaml")


def test_compiler_is_deterministic():
    spec = fixture()
    first = compile_document(spec)
    second = compile_document(spec)
    assert [(x.filename, x.sha256, x.svg_text) for x in first] == [
        (x.filename, x.sha256, x.svg_text) for x in second
    ]


def test_compiler_outputs_one_svg_per_spread():
    spec = fixture()
    artifacts = compile_document(spec)
    assert len(artifacts) == len(spec["spreads"]) == 4
    assert all(item.filename.endswith(".svg") for item in artifacts)


def test_each_svg_passes_structural_validation():
    spec = fixture()
    by_id = {spread["id"]: spread for spread in spec["spreads"]}
    for artifact in compile_document(spec):
        assert validate_compiled_svg(artifact.svg_text, spec, by_id[artifact.spread_id]) == []


def test_svg_preserves_every_stable_object_id():
    spec = fixture()
    for artifact, spread in zip(compile_document(spec), spec["spreads"], strict=True):
        for obj in spread["objects"]:
            assert f'id="{obj["id"]}"' in artifact.svg_text


def test_svg_is_a5_two_page_spread():
    spec = fixture()
    for artifact in compile_document(spec):
        assert 'width="296mm"' in artifact.svg_text
        assert 'height="210mm"' in artifact.svg_text
        assert 'viewBox="0 0 296 210"' in artifact.svg_text


def test_monthly_svg_contains_calendar_dates_and_bilingual_title():
    spec = fixture()
    monthly = compile_document(spec)[0].svg_text
    assert "Жовтень" in monthly
    assert "October 2026" in monthly
    assert ">31<" in monthly


def test_weekly_svg_uses_explicit_period_for_day_labels():
    spec = fixture()
    partial = compile_document(spec)[1].svg_text
    assert "Thursday  15.10" in partial
    assert "Sunday  18.10" in partial


def test_transition_week_changes_accent_month_for_sunday():
    spec = fixture()
    transition = compile_document(spec)[3].svg_text
    assert "Sunday  01.11" in transition
    assert 'data-print-cmyk="0,38,91,23"' in transition


def test_phase1_svg_contains_no_embedded_raster():
    spec = fixture()
    assert all("<image" not in item.svg_text for item in compile_document(spec))

def test_compiler_accepts_yaml_native_date_objects():
    spec = fixture()
    assert isinstance(spec["spreads"][1]["period"]["start_date"], date)
    artifacts = compile_document(spec)
    assert len(artifacts) == 4

def test_svg_preserves_style_ref_metadata_for_transition_week():
    spec = fixture()
    transition = compile_document(spec)[3].svg_text
    root = ET.fromstring(transition)
    sunday = root.find(".//*[@id='week.transition.sunday']")
    monday = root.find(".//*[@id='week.transition.monday']")
    assert sunday is not None
    assert monday is not None
    assert sunday.get("data-style-ref") == "month.november"
    assert monday.get("data-style-ref") == "month.october"


def test_svg_preserves_print_cmyk_on_colored_semantic_groups():
    spec = fixture()
    monthly = ET.fromstring(compile_document(spec)[0].svg_text)
    calendar_group = monthly.find(".//*[@id='october.calendar.grid']")
    notes_group = monthly.find(".//*[@id='october.notes']")
    assert calendar_group is not None
    assert notes_group is not None
    assert calendar_group.get("data-print-cmyk") == "0,25,93,9"
    assert notes_group.get("data-print-cmyk") == "0,25,93,9"

    transition = ET.fromstring(compile_document(spec)[3].svg_text)
    sunday = transition.find(".//*[@id='week.transition.sunday']")
    assert sunday is not None
    assert sunday.get("data-print-cmyk") == "0,38,91,23"

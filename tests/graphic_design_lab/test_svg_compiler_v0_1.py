from datetime import date
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

from app.graphic_design_lab.compiler import compile_document
from app.graphic_design_lab.compiler.layout import layout_spread
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
    partial = ET.fromstring(compile_document(spec)[1].svg_text)

    thursday = partial.find(".//*[@id='week.partial.thursday']")
    sunday = partial.find(".//*[@id='week.partial.sunday']")
    assert thursday is not None
    assert sunday is not None

    thursday_text = [node.text for node in list(thursday) if node.tag.endswith("text")]
    sunday_text = [node.text for node in list(sunday) if node.tag.endswith("text")]
    assert "Thursday" in thursday_text
    assert "15.10" in thursday_text
    assert "Sunday" in sunday_text
    assert "18.10" in sunday_text


def test_transition_week_changes_accent_month_for_sunday():
    spec = fixture()
    root = ET.fromstring(compile_document(spec)[3].svg_text)

    sunday = root.find(".//*[@id='week.transition.sunday']")
    assert sunday is not None

    text_values = [
        node.text for node in list(sunday)
        if node.tag.endswith("text")
    ]
    assert "Sunday" in text_values
    assert "01.11" in text_values
    assert sunday.get("data-print-cmyk") == "0,38,91,23"

    accent = sunday.find("./*[@data-role='day-accent']")
    assert accent is not None
    assert accent.get("data-print-cmyk") == "0,38,91,23"


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

def test_monthly_visual_refinement_has_one_month_heading_and_exact_week_rows():
    spec = fixture()
    monthly_svg = compile_document(spec)[0].svg_text

    assert monthly_svg.count("October 2026") == 1

    root = ET.fromstring(monthly_svg)
    calendar_group = root.find(".//*[@id='october.calendar.grid']")
    assert calendar_group is not None

    text_nodes = [
        node for node in list(calendar_group)
        if node.tag.endswith("text")
    ]
    text_values = {node.text for node in text_nodes}
    assert {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"} <= text_values

    weekday_nodes = [
        node for node in text_nodes
        if node.text in {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}
    ]
    assert all(node.get("text-anchor") == "middle" for node in weekday_nodes)

    line_nodes = [
        node for node in list(calendar_group)
        if node.tag.endswith("line")
    ]
    # October 2026 occupies five actual calendar weeks:
    # 8 vertical boundaries + 6 horizontal boundaries.
    assert len(line_nodes) == 14


def test_monthly_visual_refinement_uses_binding_safe_inner_margins():
    spec = fixture()
    spread = spec["spreads"][0]
    boxes = layout_spread(spread, 148.0, 210.0)

    calendar_box = boxes["october.calendar.grid"]
    notes_box = boxes["october.notes"]

    assert calendar_box.x == 10.0
    assert calendar_box.width == 124.0
    assert calendar_box.x + calendar_box.width == 134.0

    assert notes_box.x == 162.0
    assert notes_box.width == 124.0
    assert notes_box.y == 12.0
    assert notes_box.x - 148.0 == 14.0


def test_monthly_visual_refinement_reduces_title_weight_without_semantic_change():
    spec = fixture()
    root = ET.fromstring(compile_document(spec)[0].svg_text)

    uk_group = root.find(".//*[@id='october.header.month_name_uk']")
    en_group = root.find(".//*[@id='october.header.month_name_en']")
    assert uk_group is not None
    assert en_group is not None

    uk_text = next(node for node in list(uk_group) if node.tag.endswith("text"))
    en_text = next(node for node in list(en_group) if node.tag.endswith("text"))

    assert uk_text.text == "Жовтень"
    assert en_text.text == "October 2026"
    assert uk_text.get("font-size") == "4.6"
    assert uk_text.get("font-weight") == "500"
    assert en_text.get("font-size") == "2.8"
    assert en_text.get("font-weight") == "400"


def test_compiled_svg_has_no_visible_gutter_guide():
    spec = fixture()
    for artifact in compile_document(spec):
        root = ET.fromstring(artifact.svg_text)
        assert root.find(".//*[@data-role='gutter']") is None


def test_monthly_v3_keeps_v2_geometry_and_strengthens_only_month_heading():
    spec = fixture()
    spread = spec["spreads"][0]
    boxes = layout_spread(spread, 148.0, 210.0)

    calendar_box = boxes["october.calendar.grid"]
    notes_box = boxes["october.notes"]
    assert (calendar_box.x, calendar_box.width) == (10.0, 124.0)
    assert (notes_box.x, notes_box.width, notes_box.y) == (162.0, 124.0, 12.0)

    root = ET.fromstring(compile_document(spec)[0].svg_text)
    uk_group = root.find(".//*[@id='october.header.month_name_uk']")
    en_group = root.find(".//*[@id='october.header.month_name_en']")
    assert uk_group is not None
    assert en_group is not None

    uk_text = next(node for node in list(uk_group) if node.tag.endswith("text"))
    en_text = next(node for node in list(en_group) if node.tag.endswith("text"))
    assert uk_text.text == "Жовтень"
    assert en_text.text == "October 2026"
    assert uk_text.get("font-size") == "4.6"
    assert uk_text.get("font-weight") == "500"
    assert en_text.get("font-size") == "2.8"
    assert en_text.get("font-weight") == "400"

def test_weekly_visual_refinement_uses_open_sections_not_cards():
    spec = fixture()
    full = ET.fromstring(compile_document(spec)[2].svg_text)

    for role in (
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ):
        group = full.find(f".//*[@data-role='{role}']")
        assert group is not None

        direct_rects = [node for node in list(group) if node.tag.endswith("rect")]
        assert direct_rects == []

        accent = group.find("./*[@data-role='day-accent']")
        separator = group.find("./*[@data-role='day-separator']")
        day_name = group.find("./*[@data-role='day-name']")
        day_date = group.find("./*[@data-role='day-date']")

        assert accent is not None
        assert separator is not None
        assert day_name is not None
        assert day_date is not None

        assert accent.get("stroke-width") == "0.55"
        assert separator.get("stroke-width") == "0.18"
        assert day_name.get("font-size") == "3.1"
        assert day_name.get("font-weight") == "500"
        assert day_date.get("font-size") == "2.8"
        assert day_date.get("font-weight") == "400"
        assert day_date.get("text-anchor") == "end"


def test_weekly_visual_refinement_preserves_page_split_and_binding_safe_margins():
    spec = fixture()
    full_spread = spec["spreads"][2]
    boxes = layout_spread(full_spread, 148.0, 210.0)

    monday = boxes["week.full.monday"]
    tuesday = boxes["week.full.tuesday"]
    wednesday = boxes["week.full.wednesday"]
    thursday = boxes["week.full.thursday"]
    friday = boxes["week.full.friday"]
    saturday = boxes["week.full.saturday"]
    sunday = boxes["week.full.sunday"]

    assert monday.x == tuesday.x == wednesday.x == 10.0
    assert monday.width == tuesday.width == wednesday.width == 124.0
    assert monday.x + monday.width == 134.0

    assert thursday.x == friday.x == saturday.x == sunday.x == 162.0
    assert thursday.width == friday.width == saturday.width == sunday.width == 124.0
    assert thursday.x - 148.0 == 14.0

    assert monday.height == tuesday.height == wednesday.height
    assert thursday.height == friday.height == saturday.height == sunday.height


def test_transition_week_keeps_day_specific_month_color_on_short_markers():
    spec = fixture()
    transition = ET.fromstring(compile_document(spec)[3].svg_text)

    monday = transition.find(".//*[@id='week.transition.monday']")
    sunday = transition.find(".//*[@id='week.transition.sunday']")
    assert monday is not None
    assert sunday is not None

    monday_accent = monday.find("./*[@data-role='day-accent']")
    sunday_accent = sunday.find("./*[@data-role='day-accent']")
    assert monday_accent is not None
    assert sunday_accent is not None

    assert monday_accent.get("data-print-cmyk") == "0,25,93,9"
    assert sunday_accent.get("data-print-cmyk") == "0,38,91,23"

    monday_length = float(monday_accent.get("x2")) - float(monday_accent.get("x1"))
    sunday_length = float(sunday_accent.get("x2")) - float(sunday_accent.get("x1"))
    assert monday_length == sunday_length == 10.0


def test_partial_week_renders_real_prior_days_as_deemphasized_sections():
    spec = fixture()
    partial = ET.fromstring(compile_document(spec)[1].svg_text)

    prior = partial.find(".//*[@data-role='de_emphasized_prior_days']")
    assert prior is not None

    text_nodes = [node for node in list(prior) if node.tag.endswith("text")]
    text_values = [node.text for node in text_nodes]

    assert "Monday" in text_values
    assert "12.10" in text_values
    assert "Tuesday" in text_values
    assert "13.10" in text_values
    assert "Wednesday" in text_values
    assert "14.10" in text_values
    assert "Prior days — not in diary range" not in text_values

    names = [
        node for node in text_nodes
        if node.get("data-role") == "prior-day-name"
    ]
    dates = [
        node for node in text_nodes
        if node.get("data-role") == "prior-day-date"
    ]
    assert len(names) == 3
    assert len(dates) == 3
    assert all(node.get("font-weight") == "400" for node in names)
    assert all(node.get("fill") == "#9a9a9a" for node in names)
    assert all(node.get("fill") == "#aaaaaa" for node in dates)


def test_partial_week_prior_days_have_no_active_month_accent_markers():
    spec = fixture()
    partial = ET.fromstring(compile_document(spec)[1].svg_text)

    prior = partial.find(".//*[@data-role='de_emphasized_prior_days']")
    assert prior is not None
    assert prior.find("./*[@data-role='day-accent']") is None

    separators = [
        node for node in list(prior)
        if node.get("data-role") == "prior-day-separator"
    ]
    assert len(separators) == 3
    assert all(node.get("stroke-width") == "0.18" for node in separators)

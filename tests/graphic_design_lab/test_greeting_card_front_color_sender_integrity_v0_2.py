"""GC Page1 approved color & Page4 lossless sender fields."""
from pathlib import Path
import pytest
from app.graphic_design_lab import greeting_card_builder_renderer as b


def test_page1_approved_rgb_brown_and_runtime_argument():
    assert b.FRONT_OCCASION_COLOR_RGB == (96 / 255, 57 / 255, 19 / 255)
    calls = []

    class Page:
        def insert_text(self, *args, **kwargs):
            calls.append(kwargs)

    rows = [
        {'text': label, 'origin': (100.0, 110.0 + n * 50), 'size': 52.0}
        for n, label in enumerate(b.STANDARD_BIRTHDAY_LINES)
    ]
    b._render_standard_birthday_occasion(
        Page(), b.STANDARD_BIRTHDAY_DISPLAY_TEXT,
        font_path=Path('/does-not-need-to-exist.ttf'), canonical_layout=rows,
    )
    assert len(calls) == 2
    assert all(call['color'] == b.FRONT_OCCASION_COLOR_RGB for call in calls)


def test_page4_sender_preserves_every_confirmed_role_and_relative_order():
    # Count is intentionally variable: new confirmed roles must never vanish.
    rows = [
        {'id': 'sender_role_2', 'text': 'Role two'},
        {'id': 'closing_phrase', 'text': 'Closing'},
        {'id': 'sender_role_3', 'text': 'Role three'},
        {'id': 'sender_name', 'text': 'Name'},
        {'id': 'sender_role_1', 'text': 'Role one'},
        {'id': 'sender_role_4', 'text': 'Role four'},
    ]
    actual = b._canonical_single_sender_lines(rows)
    assert [row['id'] for row in actual] == [
        'closing_phrase', 'sender_name',
        'sender_role_2', 'sender_role_3', 'sender_role_1', 'sender_role_4',
    ]
    assert sorted(tuple(row.items()) for row in actual) == sorted(tuple(row.items()) for row in rows)
    with pytest.raises(ValueError, match='sender_ids_missing_or_duplicate'):
        b._canonical_single_sender_lines(rows + [rows[0]])


def test_page4_canonical_profile_remains_a_review_candidate():
    p = b._page4_runtime_profile('GRIGO')
    assert p['status'] == 'INTERNAL_REVIEW_CANDIDATE_NOT_CUSTOMER_APPROVED'
    assert p['sender_text_policy']['missing_roles_never_invented'] is True
    assert p['sender_content_order'] == [
        'closing_phrase', 'sender_name', 'sender_role_in_original_relative_order'
    ]

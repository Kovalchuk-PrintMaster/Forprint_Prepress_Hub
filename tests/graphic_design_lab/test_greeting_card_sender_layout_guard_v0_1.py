from __future__ import annotations

import pytest

from app.graphic_design_lab import greeting_card_builder_renderer as b


def test_sender_block_conservative_envelope_is_explicit():
    assert b.SENDER_CONSERVATIVE_SAFE_BOTTOM_MM == 285.0
    assert b._sender_block_within_conservative_safe_zone(214.0, 2)
    assert b._sender_block_within_conservative_safe_zone(214.0, 8)
    assert not b._sender_block_within_conservative_safe_zone(224.0, 8)
    assert not b._sender_block_within_conservative_safe_zone(236.0, 7)


@pytest.mark.parametrize("bad", [0, -1, True, 1.2, "3"])
def test_sender_block_guard_requires_positive_integer_line_count(bad):
    with pytest.raises(ValueError, match="sender_line_count_invalid"):
        b._sender_block_within_conservative_safe_zone(214.0, bad)


def test_builder_renderer_calls_constrained_fit_with_actual_sender_lines():
    import inspect
    source = inspect.getsource(b)
    assert "sender_line_count=len(sender_lines)" in source
    fit = inspect.getsource(b._fit_greeting)
    assert "_sender_block_within_conservative_safe_zone" in fit
    assert "sender_y_mm, sender_line_count" in fit

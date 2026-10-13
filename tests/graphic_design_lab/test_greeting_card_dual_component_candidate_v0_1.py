"""No private assets; exact, fail-closed DUAL signature component candidate."""
from pathlib import Path

import pymupdf
import pytest

from app.graphic_design_lab import greeting_card_dual_component_candidate_v0_1 as proof
from app.graphic_design_lab.greeting_card_signature_registry import load_registry


def test_dual_candidate_never_enables_runtime():
    registry = load_registry(
        proof.ROOT / "coordination/graphic_design_lab/directions/"
        "greeting_cards/signature_registry_v0_1.yaml"
    )
    entry = registry["variants"]["DUAL_GRIGO_HERASYMENKO"]
    assert entry["runtime_enabled"] is False
    assert entry["renderer_adapter"] is None


def test_candidate_output_root_strictly_inside_repo_tmp(tmp_path):
    with pytest.raises(ValueError, match="candidate_output_outside_repo_tmp"):
        proof.checked_output_root(tmp_path / "not_in_project")
    with pytest.raises(ValueError, match="candidate_output_outside_repo_tmp"):
        proof.checked_output_root(proof.ROOT / "tmp")
    candidate = proof.ROOT / "tmp" / "gdl_gc09_dual_candidate_fixture_not_created"
    if candidate.exists():
        with pytest.raises(ValueError, match="candidate_output_already_exists"):
            proof.checked_output_root(candidate)
    else:
        assert proof.checked_output_root(candidate) == candidate.resolve()


def fake_drawing(target, idx):
    shape = target.new_shape()
    x = 30 + idx * 5
    shape.draw_line((x, 100), (x + 3, 104))
    shape.finish(fill=(0.1, 0.2, 0.4), color=None, closePath=True)
    shape.commit()


def test_seven_paths_replay_as_individual_native_vectors():
    source = pymupdf.open()
    try:
        page = source.new_page(width=620, height=850)
        for idx in range(7):
            fake_drawing(page, idx)
        drawings = page.get_drawings()
        assert len(drawings) == 7
        destination = pymupdf.open()
        try:
            target = destination.new_page(width=620, height=850)
            proof.replay_vector_paths(target, drawings)
            assert len(target.get_drawings()) == 7
            assert not target.get_text("text")
            assert not target.get_images(full=True)
        finally:
            destination.close()
    finally:
        source.close()


def test_wrong_count_and_unsupported_op_fail_closed():
    doc = pymupdf.open()
    try:
        page = doc.new_page()
        with pytest.raises(ValueError, match="dual_grigo_vector_path_count_invalid"):
            proof.replay_vector_paths(page, [])
        drawings = [
            {"type": "f", "fill": (0, 0, 0), "items": [("re", None)]}
            for _ in range(7)
        ]
        with pytest.raises(ValueError, match="dual_grigo_unsupported_vector_operation"):
            proof.replay_vector_paths(page, drawings)
    finally:
        doc.close()


def test_vector_bbox_comparison_has_strict_tolerance():
    assert proof._bbox_equal(list(proof.DUAL_GRIGO_BBOX_MM), proof.DUAL_GRIGO_BBOX_MM)
    shifted = list(proof.DUAL_GRIGO_BBOX_MM)
    shifted[0] += .2
    assert not proof._bbox_equal(shifted, proof.DUAL_GRIGO_BBOX_MM)


def test_overlap_check_blocks_visible_signature_ink(monkeypatch):
    import io
    from PIL import Image

    class Doc:
        def __init__(self, value):
            mask = Image.new("L", (100, 100), value)
            buffer = io.BytesIO()
            mask.save(buffer, format="PNG")
            self.content = buffer.getvalue()

        def extract_image(self, xref):
            return {"image": self.content}

    class FakePage:
        def __init__(self, alpha):
            self.parent = Doc(alpha)

    monkeypatch.setattr(proof, "_image_soft_mask_xref", lambda *_a: 99)
    info = {"bbox": pymupdf.Rect(0, 0, 100, 100), "xref": 123}
    boxes = [[200, 200, 201, 201] for _ in range(6)]
    boxes[4] = [3, 3, 8, 8]
    ok = proof._verify_transparent_sender_overlap(FakePage(0), info, boxes)
    assert ok["status"] == "TRANSPARENT_REGION"
    assert ok["max_alpha"] == 0
    with pytest.raises(ValueError, match="dual_source_visible_signature_sender_overlap"):
        proof._verify_transparent_sender_overlap(FakePage(250), info, boxes)

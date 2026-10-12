from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/validation/gdl_greeting_card_multi_job_pdf_probe_v0_1.py'
spec = importlib.util.spec_from_file_location('gdl_multi_job_probe_v0_1', SCRIPT)
assert spec and spec.loader
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def example_job():
    return {
        'job_id': 'original',
        'structured_greeting_data': {
            'greeting_text': 'Original', 'greeting_text_source': 'original-source',
        },
        'exact_person_text_asset_bindings': {
            'greeting_text': {'value': 'Original', 'source_ref': 'original-source'},
        },
        'accepted_visual_assets': [{'job_id': 'original', 'artifact_ref': 'artifact'}],
        'builder_v1': {
            'front': {'family': 'STANDARD'},
            'inside_image': {'mode': 'PORTRAIT'},
            'sender_text': {'signature_variant_id': 'HERASYMENKO', 'lines': [{'id': 'sender', 'text': 'Original'}]},
        },
    }


def test_synthetic_texts_vary():
    assert len(probe.synthetic_text(110)) <= 110
    assert probe.synthetic_text(110) != probe.synthetic_text(420)
    with pytest.raises(ValueError):
        probe.synthetic_text(0)


def test_cloned_jobs_do_not_mutate_original():
    original = example_job()
    baseline = copy.deepcopy(original)
    a = probe.prepare_job(original, ('short', 110, 2))
    b = probe.prepare_job(original, ('long', 850, 6))
    assert original == baseline
    assert a['job_id'] != b['job_id']
    assert a['accepted_visual_assets'][0]['job_id'] == a['job_id']
    assert b['exact_person_text_asset_bindings']['greeting_text']['value'] == b['structured_greeting_data']['greeting_text']
    assert len(b['builder_v1']['sender_text']['lines']) == 6
    assert len(a['builder_v1']['sender_text']['lines']) == 2
    assert a['builder_v1']['sender_text']['signature_variant_id'] == 'HERASYMENKO'


def test_rejects_sender_over_fixture_capacity():
    with pytest.raises(ValueError):
        probe.prepare_job(example_job(), ('bad', 120, 9))

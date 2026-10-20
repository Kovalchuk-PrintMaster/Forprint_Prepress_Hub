"""Synthetic-only regression for native source proof provenance; no private sources."""
from __future__ import annotations

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import zipfile

import pytest

FILE = (Path(__file__).resolve().parents[2] / 'scripts/graphic_design_lab/greeting_cards'
        / 'gc18_native_proof_source_gate_v0_1.py')
spec = importlib.util.spec_from_file_location('gc18_native_source_gate', FILE)
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


def sample_zip(tmp_path, name='proof.zip', jsx=b'#target illustrator\n// synthetic\n'):
    target = tmp_path / name
    with zipfile.ZipFile(target, 'w') as z:
        z.writestr('00_README_UA.md', 'Synthetic test only')
        z.writestr('test.jsx', jsx)
    return target, {'archive_sha256': sha256(target.read_bytes()).hexdigest(),
                    'jsx_sha256': sha256(jsx).hexdigest()}


def sample_plan(sha='a' * 64, count=2):
    tasks = []
    for n in range(count):
        binding = sha256(('job' + str(n)).encode()).hexdigest()
        tasks.append({'task_id': 'gc18-' + binding[:24],
                      'job_binding_sha256': binding,
                      'expected_outputs': list(g.OUTPUTS),
                      'worker_authorized': False})
    return {'schema_version': g.PLAN_SCHEMA,
            'state': 'DEEP_INTAKE_VERIFIED_NATIVE_CONTRACT_PENDING',
            'source_sha256': sha, 'source_job_count': count,
            'source_asset_count': 1, 'tasks': tasks,
            'admission': {'strict_intake_inspector': 'PASS',
                          'illustrator_script_pinned': False,
                          'windows_capability_verified': False,
                          'windows_session_verified': False,
                          'worker_ack_received': False},
            'dispatch_authorized': False, 'pdf_builder_invoked': False,
            'production_approved': False,
            'next_boundary': 'PIN_NATIVE_JSX_AND_WORKER_CAPABILITY_THEN_AUTHORIZED_HANDOFF'}


def test_synthetic_archive_exact_match(tmp_path):
    path, expected = sample_zip(tmp_path)
    assert g.check_archive(path, expected) == expected


def test_archive_checksum_is_required(tmp_path):
    path, expected = sample_zip(tmp_path)
    expected['archive_sha256'] = '0' * 64
    with pytest.raises(g.GateBlocked, match='proof_archive_sha256_mismatch'):
        g.check_archive(path, expected)


def test_jsx_checksum_is_required(tmp_path):
    path, expected = sample_zip(tmp_path)
    expected['jsx_sha256'] = '0' * 64
    with pytest.raises(g.GateBlocked, match='proof_jsx_sha256_mismatch'):
        g.check_archive(path, expected)


def test_unsafe_zip_path_rejected(tmp_path):
    p = tmp_path / 'unsafe.zip'
    with zipfile.ZipFile(p, 'w') as z:
        z.writestr('00_README_UA.md', 'x')
        z.writestr('../pilot.jsx', 'x')
    hashes = {'archive_sha256': sha256(p.read_bytes()).hexdigest(),
              'jsx_sha256': sha256(b'x').hexdigest()}
    with pytest.raises(g.GateBlocked, match='proof_zip_member_unsafe'):
        g.check_archive(p, hashes)


def test_extra_zip_member_rejected(tmp_path):
    p = tmp_path / 'extra.zip'
    with zipfile.ZipFile(p, 'w') as z:
        z.writestr('00_README_UA.md', 'x')
        z.writestr('pilot.jsx', 'x')
        z.writestr('payload.bin', 'x')
    hashes = {'archive_sha256': sha256(p.read_bytes()).hexdigest(),
              'jsx_sha256': sha256(b'x').hexdigest()}
    with pytest.raises(g.GateBlocked, match='proof_zip_content_invalid'):
        g.check_archive(p, hashes)


def test_symlink_zip_input_rejected(tmp_path):
    path, expected = sample_zip(tmp_path)
    link = tmp_path / 'link.zip'
    link.symlink_to(path)
    with pytest.raises(g.GateBlocked, match='source_not_regular_or_symlink'):
        g.check_archive(link, expected)


def test_plan_good():
    info = g.validate_plan(sample_plan())
    assert info == {'source_sha256': 'a'*64, 'source_job_count': 2,
                    'source_asset_count': 1}


def test_dispatch_authority_rejected():
    data = sample_plan(); data['dispatch_authorized'] = True
    with pytest.raises(g.GateBlocked, match='native_plan_authority_invalid'):
        g.validate_plan(data)


def test_worker_authority_rejected():
    data = sample_plan(); data['tasks'][0]['worker_authorized'] = True
    with pytest.raises(g.GateBlocked, match='native_plan_task_identity_or_authority_invalid'):
        g.validate_plan(data)


def test_capability_not_inferred_from_historical_proofs():
    data = sample_plan(); data['admission']['windows_capability_verified'] = True
    with pytest.raises(g.GateBlocked, match='native_plan_must_remain_unadmitted'):
        g.validate_plan(data)


def test_duplicate_binding_rejected():
    data = sample_plan(); data['tasks'][1] = dict(data['tasks'][0])
    with pytest.raises(g.GateBlocked, match='native_plan_task_identity_or_authority_invalid'):
        g.validate_plan(data)


def test_unexpected_private_payload_field_rejected():
    data = sample_plan(); data['customer_greeting_text'] = 'private example'
    with pytest.raises(g.GateBlocked, match='native_plan_schema_fields_invalid'):
        g.validate_plan(data)


def test_plan_basename_tied_to_sha(tmp_path):
    data = sample_plan(); p = tmp_path / 'wrong.json'
    p.write_text(json.dumps(data))
    with pytest.raises(g.GateBlocked, match='native_plan_file_identity_invalid'):
        g.check_plan(p)


def test_check_all_does_not_grant_admission(tmp_path, monkeypatch):
    a1, h1 = sample_zip(tmp_path, 'a1.zip', b'A1 synthetic')
    a2, h2 = sample_zip(tmp_path, 'a2.zip', b'A2 synthetic')
    monkeypatch.setitem(g.PROFILE, 'A1', h1)
    monkeypatch.setitem(g.PROFILE, 'A2', h2)
    data = sample_plan(); plan = tmp_path / (data['source_sha256']+'.json')
    plan.write_text(json.dumps(data))
    result = g.check_all(a1, a2, plan)
    assert result['native_adapter_implemented'] is False
    assert result['dispatch_authorized'] is False
    assert result['windows_worker_admitted'] is False
    assert result['source_job_count'] == 2

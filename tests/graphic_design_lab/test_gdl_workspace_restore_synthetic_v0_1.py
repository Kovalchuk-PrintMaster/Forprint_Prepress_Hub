"""GDL D09/D12 synthetic-only first-slice restore regression."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
import yaml
from scripts.graphic_design_lab.greeting_cards import workspace_restore_synthetic_v0_1 as r


def make_repo(tmp_path: Path) -> Path:
    (tmp_path / 'tmp').mkdir()
    file = tmp_path / r.CONTRACT
    file.parent.mkdir(parents=True)
    file.write_text(yaml.safe_dump({
        'schema_version': 'gdl_client_workspace_architecture_v0_1',
        'workspace_dir_name': '_forprint_automation',
        'status': 'ACTIVE_EMPIRICAL_ARCHITECTURE',
        'tree': {'jobs': [], 'previews': [], 'archive': []},
    }), encoding='utf-8')
    return tmp_path


def test_synthetic_restoration_minimal_and_independent(tmp_path):
    repo = make_repo(tmp_path)
    ws = r.create(repo, 'restorable-case-01')
    assert ws.name == '_forprint_automation'
    assert {p.name for p in ws.iterdir()} == {'input', 'output', r.PROOF}
    assert r.verify(repo, 'restorable-case-01', expect_empty=True)['status'] == 'SYNTHETIC_SKELETON_VERIFIED'
    proof = json.loads((ws / r.PROOF).read_text())
    assert proof['copied_real_client_assets'] is False
    assert proof['production_authority'] is False


def test_no_overwrite_or_cleanup(tmp_path):
    repo = make_repo(tmp_path)
    ws = r.create(repo, 'example')
    (ws / 'input' / 'keep.txt').write_bytes(b'untouched')
    with pytest.raises(r.RestoreBlocked, match='case_already_exists'):
        r.create(repo, 'example')
    assert (ws / 'input' / 'keep.txt').read_bytes() == b'untouched'


@pytest.mark.parametrize('case_id', ['', '..', '../escape', 'a/b', 'a\\b', 'case space', '.'])
def test_reject_invalid_case_id(tmp_path, case_id):
    repo = make_repo(tmp_path)
    with pytest.raises(r.RestoreBlocked):
        r.create(repo, case_id)
    assert not list((repo / 'tmp').rglob('_forprint_automation'))


def test_reject_scratch_symlink(tmp_path):
    repo = make_repo(tmp_path)
    (repo / 'tmp' / r.SCRATCH).symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(r.RestoreBlocked, match='scratch_root_unsafe'):
        r.create(repo, 'case')


def test_reject_modified_contract_and_receipt(tmp_path):
    repo = make_repo(tmp_path)
    ws = r.create(repo, 'case')
    proof = json.loads((ws / r.PROOF).read_text())
    proof['production_authority'] = True
    (ws / r.PROOF).write_text(json.dumps(proof))
    with pytest.raises(r.RestoreBlocked, match='receipt_identity_mismatch'):
        r.verify(repo, 'case')


def test_reject_workspace_symlink(tmp_path):
    repo = make_repo(tmp_path)
    ws = r.create(repo, 'case')
    (ws / 'input').rmdir()
    (ws / 'input').symlink_to(repo / 'tmp')
    with pytest.raises(r.RestoreBlocked, match='operational_directory_missing_or_unsafe'):
        r.verify(repo, 'case')


def test_verify_nonempty_workspace_allowed_after_smoke(tmp_path):
    repo = make_repo(tmp_path)
    ws = r.create(repo, 'case')
    (ws / 'input' / 'synthetic.txt').write_bytes(b'not a real client')
    assert r.verify(repo, 'case')['entry_counts']['input'] == 1
    with pytest.raises(r.RestoreBlocked, match='expected_empty_skeleton'):
        r.verify(repo, 'case', expect_empty=True)

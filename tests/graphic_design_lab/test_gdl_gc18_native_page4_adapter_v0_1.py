"""Synthetic tests. Never embed customer text or execute Illustrator."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import zipfile

import pytest

SRC = Path(__file__).resolve().parents[2] / 'scripts/graphic_design_lab/greeting_cards/gc18_native_page4_adapter_v0_1.py'
TEMPLATE = SRC.with_name('gc18_native_page4_body_template_v0_1.jsx')
SPEC = importlib.util.spec_from_file_location('gc18_native_page4_test_module', SRC)
a = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(a)

TASK = 'gc18-' + 'a' * 24
SOURCE_SHA = 'b' * 64


def identity(greeting='Санітизоване привітання\nДругий рядок!'):
    return {'task_id': TASK, 'source_sha256': SOURCE_SHA,
            'greeting': greeting, 'a1_sha256': 'c' * 64, 'a2_sha256': 'd' * 64}


def template():
    return TEMPLATE.read_text(encoding='ascii')


def test_template_is_ascii_and_only_three_placeholders():
    body = template()
    assert all(body.count(tag) == 1 for tag in a.MARKERS)
    assert 'DocumentColorSpace.RGB' in body
    assert 'adobe_frameAlignment' in body
    assert 'ZapfChanceryC' in body
    assert 'app.open(aiFile)' in body
    assert 'PDF_PNG_EXPORTED' in body
    assert not any(x in body for x in ('Бажаю Вам', 'Юрію Борисовичу'))


def test_render_has_native_text_and_no_pdf_builder():
    rendered = a.render_jsx(template(), TASK, SOURCE_SHA, 'Тест\nДругий абзац')
    assert rendered.startswith(b'\xef\xbb\xbf')
    assert b'\\u0422\\u0435\\u0441\\u0442\\r' in rendered
    assert b'__GC18_' not in rendered
    assert b'PDF_BUILDER_INVOKED' not in rendered
    assert b'PDF_PNG_EXPORTED' in rendered


def test_render_private_content_does_not_appear_in_plain_utf8():
    raw = a.render_jsx(template(), TASK, SOURCE_SHA, 'Приватний тестовий текст')
    assert 'Приватний'.encode() not in raw


@pytest.mark.parametrize('content', [' ', '\x00', 'X' * 30001])
def test_render_rejects_bad_greeting(content):
    with pytest.raises(a.NativeBlocked):
        a.render_jsx(template(), TASK, SOURCE_SHA, content)


def test_render_rejects_bad_task_identity():
    with pytest.raises(a.NativeBlocked):
        a.render_jsx(template(), 'BAD', SOURCE_SHA, 'sample')


def test_render_rejects_modified_template_without_accepted_marker():
    with pytest.raises(a.NativeBlocked):
        a.render_jsx(template().replace('__GC18_GREETING__', 'oops'), TASK, SOURCE_SHA, 'sample')


def test_prepare_writes_once_no_client_content_in_receipt(tmp_path):
    (tmp_path / 'tmp').mkdir()
    id1, digest = a.prepare_private(tmp_path, identity(), TEMPLATE)
    out = tmp_path / 'tmp' / a.PRIVATE_ROOT / TASK
    data = (out / 'native_page4_body_only.jsx').read_bytes()
    assert id1 == TASK and hashlib.sha256(data).hexdigest() == digest
    receipt = json.loads((out / 'receipt.json').read_text())
    assert 'Санітизоване' not in str(receipt)
    assert receipt['state'] == 'PRIVATE_WINDOWS_MANUAL_PROOF_CANDIDATE'
    assert receipt['production_ready'] is False
    assert receipt['dispatch_authorized'] is False
    assert receipt['pdf_png_export_ready'] is False
    assert oct((out / 'native_page4_body_only.jsx').stat().st_mode & 0o777) == '0o600'
    with pytest.raises(a.NativeBlocked, match='existing_private_proof_no_overwrite'):
        a.prepare_private(tmp_path, identity('OTHER TEXT'), TEMPLATE)
    assert (out / 'native_page4_body_only.jsx').read_bytes() == data


def test_prepare_rejects_private_root_symlink(tmp_path):
    (tmp_path / 'tmp').mkdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    (tmp_path / 'tmp' / a.PRIVATE_ROOT).symlink_to(outside, target_is_directory=True)
    with pytest.raises(a.NativeBlocked, match='private_root_unsafe'):
        a.prepare_private(tmp_path, identity(), TEMPLATE)
    assert list(outside.iterdir()) == []


def test_bad_task_position_fails_closed():
    plan = {'tasks': [{'task_id': TASK, 'worker_authorized': False}]}
    with pytest.raises(a.NativeBlocked):
        a._selected(plan, 2)
    assert a._selected(plan, 1)['task_id'] == TASK


def test_source_binding_reads_only_matching_reviewed_greeting(tmp_path, monkeypatch):
    from types import ModuleType
    package = ModuleType('scripts.graphic_design_lab.greeting_cards')
    fake = ModuleType('scripts.graphic_design_lab.greeting_cards.illustrator_task_candidates_v0_1')
    fake._sha = lambda _: SOURCE_SHA
    fake._json = lambda v: (json.dumps(v, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
    package.illustrator_task_candidates_v0_1 = fake
    names = ['scripts', 'scripts.graphic_design_lab', 'scripts.graphic_design_lab.greeting_cards']
    for name in names:
        monkeypatch.setitem(sys.modules, name, ModuleType(name) if name != names[-1] else package)
    monkeypatch.setitem(sys.modules, fake.__name__, fake)
    job = {'job_id': 'fixture-job', 'builder_v1': {'revision': 'r001'},
           'structured_greeting_data': {'greeting_text': 'Погоджений синтетичний текст'},
           'exact_person_text_asset_bindings': {'greeting_text': {'value': 'Погоджений синтетичний текст'}}}
    key = hashlib.sha256(fake._json({'source_sha256': SOURCE_SHA, 'job_id': 'fixture-job', 'revision': 'r001'})).hexdigest()
    path = tmp_path / 'handoff.zip'
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('accepted_constructor_bundle.yaml', __import__('yaml').safe_dump({'jobs': [job]}, allow_unicode=True))
    text = a._read_bound_greeting(path, SOURCE_SHA, {'job_binding_sha256': key})
    assert text == 'Погоджений синтетичний текст'
    with pytest.raises(a.NativeBlocked, match='task_to_greeting_not_unique'):
        a._read_bound_greeting(path, SOURCE_SHA, {'job_binding_sha256': 'e' * 64})


def test_check_mode_no_prepare_and_private_data_suppressed(tmp_path, monkeypatch, capsys):
    # Full chain is exercised on s01; here isolate CLI authorization and privacy.
    monkeypatch.setattr(a, 'validate_context', lambda *unused: identity('Секретний синтетичний рядок'))
    monkeypatch.setattr(a, '_regular', lambda _: True)
    monkeypatch.setattr(a, '_safe_read_bytes', lambda *_: template().encode('ascii'))
    cli = [str(SRC), '--repo', str(tmp_path), '--workspace', str(tmp_path),
           '--config', 'x', '--native-plan', 'y', '--a1-archive', 'z', '--a2-archive', 't',
           '--task-position', '1', '--mode', 'check']
    monkeypatch.setattr(sys, 'argv', cli)
    assert a.main() == 0
    assert 'Секретний' not in capsys.readouterr().out
    assert not (tmp_path / 'tmp').exists()


def test_prepare_requires_explicit_confirmation(tmp_path, monkeypatch):
    monkeypatch.setattr(a, 'validate_context', lambda *unused: identity())
    monkeypatch.setattr(sys, 'argv', [str(SRC), '--repo', str(tmp_path), '--workspace', 'x',
        '--config', 'y', '--native-plan', 'z', '--a1-archive', 'x', '--a2-archive', 'y',
        '--task-position', '1', '--mode', 'prepare'])
    assert a.main() == 2
    assert not (tmp_path / 'tmp').exists()

#!/usr/bin/env python3
"""GC18: bounded private native Illustrator Page-4 *body-only* proof.

This is not a four-page greeting card, Windows Worker, or PDF Builder.
The server validates original A1/A2 evidence, deep Intake, and immutable
native plan; it writes one private JSX *candidate* under repo/tmp only.
The JSX contains accepted customer greeting text: NEVER stage it in Git.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any
import zipfile

import yaml

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

TEMPLATE_NAME = 'gc18_native_page4_body_template_v0_1.jsx'
PRIVATE_ROOT = 'gdl_gc18_native_page4_private_proofs_v0_1'
HEX64 = re.compile(r'^[0-9a-f]{64}$')
TASK_RE = re.compile(r'^gc18-[0-9a-f]{24}$')
MARKERS = ('__GC18_TASK_ID__', '__GC18_SOURCE_SHA__', '__GC18_GREETING__')


class NativeBlocked(ValueError):
    pass


def _regular(path: Path) -> bool:
    return path.is_file() and not path.is_symlink() and stat.S_ISREG(path.stat().st_mode)


def _safe_read_bytes(path: Path, limit: int) -> bytes:
    if not _regular(path) or path.stat().st_size > limit:
        raise NativeBlocked('file_missing_unsafe_or_large')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise NativeBlocked('source_file_not_regular')
        with os.fdopen(fd, 'rb') as inp:
            fd = -1
            data = inp.read(limit + 1)
            if len(data) > limit:
                raise NativeBlocked('source_file_too_large')
            return data
    finally:
        if fd >= 0:
            os.close(fd)


def _selected(plan: dict[str, Any], index: int) -> dict[str, Any]:
    tasks = plan['tasks']
    if type(index) is not int or index < 1 or index > len(tasks):
        raise NativeBlocked('task_position_out_of_range')
    task = tasks[index - 1]
    if not TASK_RE.fullmatch(task['task_id']) or task['worker_authorized'] is not False:
        raise NativeBlocked('task_not_review_only')
    return task


def _read_bound_greeting(source: Path, expected_sha: str, task: dict[str, Any]) -> str:
    """Never trust filename/job order. Bind text to exact reviewed task digest."""
    from scripts.graphic_design_lab.greeting_cards import illustrator_task_candidates_v0_1 as gc18

    if not _regular(source) or gc18._sha(source) != expected_sha:
        raise NativeBlocked('source_changed_or_unsafe')
    fd = os.open(source, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise NativeBlocked('source_not_regular')
        with os.fdopen(fd, 'rb') as inp:
            fd = -1
            with zipfile.ZipFile(inp) as zf:
                info = zf.getinfo('accepted_constructor_bundle.yaml')
                if info.file_size > 5 * 1024 * 1024:
                    raise NativeBlocked('accepted_bundle_too_large')
                raw = yaml.safe_load(zf.read(info))
    finally:
        if fd >= 0:
            os.close(fd)
    if not isinstance(raw, dict) or not isinstance(raw.get('jobs'), list):
        raise NativeBlocked('accepted_bundle_structure_invalid')
    matched: list[str] = []
    for job in raw['jobs']:
        if not isinstance(job, dict) or not isinstance(job.get('builder_v1'), dict):
            raise NativeBlocked('accepted_job_invalid')
        job_id = job.get('job_id')
        revision = job['builder_v1'].get('revision')
        if not isinstance(job_id, str) or not isinstance(revision, str):
            raise NativeBlocked('accepted_job_identity_invalid')
        binding = sha256(gc18._json({'source_sha256': expected_sha,
                                     'job_id': job_id, 'revision': revision})).hexdigest()
        if binding != task['job_binding_sha256']:
            continue
        structured = job.get('structured_greeting_data') or {}
        exact = (job.get('exact_person_text_asset_bindings') or {}).get('greeting_text') or {}
        greeting = structured.get('greeting_text')
        if (not isinstance(greeting, str) or not greeting.strip()
                or exact.get('value') != greeting or '\x00' in greeting
                or len(greeting) > 30_000):
            raise NativeBlocked('greeting_binding_invalid')
        matched.append(greeting)
    if gc18._sha(source) != expected_sha:
        raise NativeBlocked('source_changed_after_read')
    if len(matched) != 1:
        raise NativeBlocked('task_to_greeting_not_unique')
    return matched[0]


def validate_context(repo: Path, workspace: Path, config: Path, plan_file: Path,
                     a1: Path, a2: Path, task_position: int) -> dict[str, Any]:
    from scripts.graphic_design_lab.greeting_cards import illustrator_task_candidates_v0_1 as gc18
    from scripts.graphic_design_lab.greeting_cards import gc18_native_proof_source_gate_v0_1 as gate

    repo = repo.resolve(strict=True)
    tmp = repo / 'tmp'
    if not tmp.is_dir() or tmp.is_symlink():
        raise NativeBlocked('repo_tmp_missing_or_unsafe')
    if not _regular(config) or not _regular(plan_file):
        raise NativeBlocked('config_or_plan_unsafe')
    gate.check_all(a1, a2, plan_file)
    plan = json.loads(_safe_read_bytes(plan_file, 1024 * 1024).decode('utf-8'))
    task = _selected(plan, task_position)
    rows = gc18.inventory(workspace)
    candidates = [r for r in rows if r.get('source_sha256') == plan['source_sha256']
                  and r['status'] == 'CANDIDATE_AWAITING_DEEP_ACCEPTANCE']
    if len(candidates) != 1:
        raise NativeBlocked('source_candidate_missing_or_ambiguous')
    proof = gc18.deep_preflight(repo, workspace, candidates[0], config, include_job_keys=True)
    if proof['synthetic'] or proof['jobs'] != plan['source_job_count'] or proof['assets'] != plan['source_asset_count']:
        raise NativeBlocked('deep_intake_identity_mismatch')
    if proof['job_descriptors'] != plan['tasks']:
        raise NativeBlocked('native_plan_changed_or_stale')
    source = workspace / 'input' / candidates[0]['source_name']
    greeting = _read_bound_greeting(source, plan['source_sha256'], task)
    return {'task_id': task['task_id'], 'source_sha256': plan['source_sha256'],
            'greeting': greeting, 'task_count': len(plan['tasks']),
            'a1_sha256': gate.PROFILE['A1']['jsx_sha256'],
            'a2_sha256': gate.PROFILE['A2']['jsx_sha256']}


def render_jsx(template: str, task_id: str, source_sha: str, greeting: str) -> bytes:
    if not TASK_RE.fullmatch(task_id) or not HEX64.fullmatch(source_sha):
        raise NativeBlocked('task_or_source_id_invalid')
    if not greeting.strip() or '\x00' in greeting or len(greeting) > 30_000:
        raise NativeBlocked('greeting_invalid')
    for m in MARKERS:
        if template.count(m) != 1:
            raise NativeBlocked('jsx_template_marker_missing_or_duplicate')
    normalized = greeting.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\r')
    literals = (json.dumps(task_id), json.dumps(source_sha),
                json.dumps(normalized, ensure_ascii=True))
    for marker, literal in zip(MARKERS, literals):
        template = template.replace(marker, literal)
    if any(m in template for m in MARKERS):
        raise NativeBlocked('jsx_template_unresolved')
    # UTF-8 with BOM follows Illustrator ExtendScript compatibility guidance.
    return b'\xef\xbb\xbf' + template.encode('ascii')


def prepare_private(repo: Path, identity: dict[str, Any], template_file: Path) -> tuple[str, str]:
    template_bytes = _safe_read_bytes(template_file, 100_000)
    if not template_bytes.isascii():
        raise NativeBlocked('template_requires_ascii')
    generated = render_jsx(template_bytes.decode('ascii'), identity['task_id'],
                           identity['source_sha256'], identity['greeting'])
    directory = repo.resolve(strict=True) / 'tmp' / PRIVATE_ROOT
    if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
        raise NativeBlocked('private_root_unsafe')
    directory.mkdir(mode=0o700, exist_ok=True)
    if directory.is_symlink():
        raise NativeBlocked('private_root_symlink')
    dest = directory / identity['task_id']
    if dest.exists() or dest.is_symlink():
        raise NativeBlocked('existing_private_proof_no_overwrite')
    dest.mkdir(mode=0o700)
    os.chmod(dest, 0o700)
    script = dest / 'native_page4_body_only.jsx'
    receipt = dest / 'receipt.json'
    metadata = {'schema_version': 'gdl_gc18_private_native_page4_body_proof_v0_1',
                'task_id': identity['task_id'], 'source_sha256': identity['source_sha256'],
                'original_a1_jsx_sha256': identity['a1_sha256'],
                'original_a2_jsx_sha256': identity['a2_sha256'],
                'template_sha256': sha256(template_bytes).hexdigest(),
                'private_jsx_sha256': sha256(generated).hexdigest(),
                'greeting_sha256': sha256(identity['greeting'].encode('utf-8')).hexdigest(),
                'state': 'PRIVATE_WINDOWS_MANUAL_PROOF_CANDIDATE',
                'scope': 'P04_BODY_ONLY', 'dispatch_authorized': False,
                'windows_worker_admitted': False, 'pdf_builder_invoked': False,
                'production_ready': False, 'pdf_png_export_ready': False}
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_NOFOLLOW', 0)
    for target, payload in ((script, generated),
                            (receipt, (json.dumps(metadata, sort_keys=True, indent=2) + '\n').encode('utf-8'))):
        fd = os.open(target, flags, 0o600)
        with os.fdopen(fd, 'wb') as out:
            out.write(payload)
    return identity['task_id'], metadata['private_jsx_sha256']


def main() -> int:
    p = argparse.ArgumentParser(description='GC18 private native Page4 body-only manual proof candidate')
    for name in ('repo', 'workspace', 'config', 'native-plan', 'a1-archive', 'a2-archive'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--task-position', type=int, required=True)
    p.add_argument('--mode', choices=('check', 'prepare'), required=True)
    p.add_argument('--confirm-private-prototype', action='store_true')
    args = p.parse_args()
    try:
        if args.mode == 'prepare' and not args.confirm_private_prototype:
            raise NativeBlocked('explicit_private_prototype_confirmation_required')
        identity = validate_context(args.repo, args.workspace, args.config,
                                    args.native_plan, args.a1_archive, args.a2_archive,
                                    args.task_position)
        template = (args.repo / 'scripts/graphic_design_lab/greeting_cards' / TEMPLATE_NAME)
        if not _regular(template):
            raise NativeBlocked('native_template_missing')
        # Perform same template substitution during read-only check for fail-closed safety.
        expected = render_jsx(_safe_read_bytes(template, 100_000).decode('ascii'),
                              identity['task_id'], identity['source_sha256'], identity['greeting'])
        if args.mode == 'prepare':
            ident, digest = prepare_private(args.repo, identity, template)
            if digest != sha256(expected).hexdigest():
                raise NativeBlocked('generated_jsx_identity_conflict')
            print('GC18_NATIVE_PAGE4_BODY_ADAPTER=PRIVATE_CANDIDATE_PREPARED')
            print('PRIVATE_JSX_SHA256=' + digest)
        else:
            ident = identity['task_id']
            print('GC18_NATIVE_PAGE4_BODY_ADAPTER=CHECK_PASS')
        print('TASK_ID=' + ident)
        print('SOURCE_SHA256=' + identity['source_sha256'])
        print('SCOPE=P04_BODY_ONLY')
        print('CUSTOMER_TEXT_PRINTED=false')
        print('WINDOWS_DISPATCH=false')
        print('PDF_BUILDER_INVOKED=false')
        print('CLIENT_WORKSPACE_MUTATED=false')
        print('PRODUCTION_READY=false')
        return 0
    except (NativeBlocked, OSError, ValueError, KeyError, TypeError, UnicodeError, zipfile.BadZipFile) as exc:
        print('GC18_NATIVE_PAGE4_BODY_ADAPTER=BLOCKED')
        print('ERROR_CLASS=' + (str(exc) if isinstance(exc, NativeBlocked) else type(exc).__name__))
        print('PRIVATE_TEXT_PRINTED=false')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

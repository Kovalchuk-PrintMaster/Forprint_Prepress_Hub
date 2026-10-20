#!/usr/bin/env python3
"""Read-only recovery gate for GC18-A1/A2 *historical* Illustrator proofs.

Confirms exact private proof sources and a review-only GC18 task plan.
Never loads code into Illustrator; does not grant dispatch, approval, or readiness.
No file names, client text, or filesystem paths appear in stdout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any
import zipfile

PROFILE = {
    'A1': {
        'archive_sha256': '9ccfda6ee5aabe7092310a77cd2ffe6d5df6f9216ff4ecbd39dff1d9b64996b3',
        'jsx_sha256': 'dbda0127c8c62b35365d170c46001387f92da7bd65114ccdce6343843d2e96df',
    },
    'A2': {
        'archive_sha256': '787d59a5c964413a2094ee4f42ada171bb7628ec13043b4c8ee9c92911295fbc',
        'jsx_sha256': '3feb08e40e910b07502d84866b43426e82e36529686a6f3563279cebd5018b9d',
    },
}
PLAN_SCHEMA = 'gdl_gc18_illustrator_native_task_plan_v0_1'
HEX64 = re.compile(r'^[0-9a-f]{64}$')
TASK_ID = re.compile(r'^gc18-[0-9a-f]{24}$')
MAX_ARCHIVE = 4 * 1024 * 1024
MAX_MEMBER = 128 * 1024
OUTPUTS = ['editable_ai', 'review_pdf', 'page_png', 'worker_result']
PLAN_KEYS = {
    'schema_version', 'state', 'source_sha256', 'source_job_count',
    'source_asset_count', 'tasks', 'admission', 'dispatch_authorized',
    'pdf_builder_invoked', 'production_approved', 'next_boundary',
}
TASK_KEYS = {'task_id', 'job_binding_sha256', 'expected_outputs', 'worker_authorized'}
ADMISSION = {
    'strict_intake_inspector', 'illustrator_script_pinned',
    'windows_capability_verified', 'windows_session_verified', 'worker_ack_received',
}

class GateBlocked(ValueError):
    pass


def file_digest(path: Path) -> str:
    if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        raise GateBlocked('source_not_regular_or_symlink')
    if path.stat().st_size > MAX_ARCHIVE:
        raise GateBlocked('source_exceeds_size_limit')
    h = hashlib.sha256()
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise GateBlocked('source_not_regular_or_symlink')
        with os.fdopen(fd, 'rb') as f:
            fd = -1
            for chunk in iter(lambda: f.read(1024 * 1024), b''):
                h.update(chunk)
    finally:
        if fd >= 0:
            os.close(fd)
    return h.hexdigest()


def check_archive(path: Path, expected: dict[str, str]) -> dict[str, str]:
    if file_digest(path) != expected['archive_sha256']:
        raise GateBlocked('proof_archive_sha256_mismatch')
    try:
        with zipfile.ZipFile(path) as z:
            infos = z.infolist()
            if len(infos) != 2:
                raise GateBlocked('proof_zip_content_invalid')
            names: set[str] = set()
            jsx_data = None
            for item in infos:
                name = item.filename
                if (not name or name in names or name.startswith('/')
                        or '/' in name or '\\' in name or ':' in name
                        or name in ('.', '..') or item.is_dir()):
                    raise GateBlocked('proof_zip_member_unsafe')
                mode = (item.external_attr >> 16) & 0o170000
                if mode not in (0, 0o100000) or item.file_size > MAX_MEMBER:
                    raise GateBlocked('proof_zip_member_unsafe')
                names.add(name)
                if name.endswith('.jsx'):
                    if jsx_data is not None:
                        raise GateBlocked('proof_jsx_count_invalid')
                    jsx_data = z.read(item)
                elif name != '00_README_UA.md':
                    raise GateBlocked('proof_zip_unexpected_content')
            if jsx_data is None or '00_README_UA.md' not in names:
                raise GateBlocked('proof_jsx_count_invalid')
            if z.testzip() is not None:
                raise GateBlocked('proof_zip_content_invalid')
            if hashlib.sha256(jsx_data).hexdigest() != expected['jsx_sha256']:
                raise GateBlocked('proof_jsx_sha256_mismatch')
    except (zipfile.BadZipFile, RuntimeError, EOFError) as exc:
        raise GateBlocked('proof_zip_invalid') from exc
    if file_digest(path) != expected['archive_sha256']:
        raise GateBlocked('proof_archive_changed_during_check')
    return {'archive_sha256': expected['archive_sha256'], 'jsx_sha256': expected['jsx_sha256']}


def validate_plan(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != PLAN_KEYS:
        raise GateBlocked('native_plan_schema_fields_invalid')
    if raw['schema_version'] != PLAN_SCHEMA or raw['state'] != 'DEEP_INTAKE_VERIFIED_NATIVE_CONTRACT_PENDING':
        raise GateBlocked('native_plan_state_invalid')
    if (not isinstance(raw['source_sha256'], str) or not HEX64.fullmatch(raw['source_sha256'])
            or type(raw['source_job_count']) is not int or not (1 <= raw['source_job_count'] <= 100)
            or type(raw['source_asset_count']) is not int or raw['source_asset_count'] < 0):
        raise GateBlocked('native_plan_source_identity_invalid')
    if (raw['dispatch_authorized'] is not False or raw['pdf_builder_invoked'] is not False
            or raw['production_approved'] is not False
            or raw['next_boundary'] != 'PIN_NATIVE_JSX_AND_WORKER_CAPABILITY_THEN_AUTHORIZED_HANDOFF'):
        raise GateBlocked('native_plan_authority_invalid')
    adm = raw['admission']
    if not isinstance(adm, dict) or set(adm) != ADMISSION or adm['strict_intake_inspector'] != 'PASS':
        raise GateBlocked('native_plan_admission_invalid')
    if any(adm[key] is not False for key in ADMISSION - {'strict_intake_inspector'}):
        raise GateBlocked('native_plan_must_remain_unadmitted')
    tasks = raw['tasks']
    if not isinstance(tasks, list) or len(tasks) != raw['source_job_count']:
        raise GateBlocked('native_plan_task_count_invalid')
    ids = set()
    job_bindings = set()
    for t in tasks:
        if not isinstance(t, dict) or set(t) != TASK_KEYS:
            raise GateBlocked('native_plan_task_fields_invalid')
        tid, bind = t['task_id'], t['job_binding_sha256']
        if (not isinstance(tid, str) or not TASK_ID.fullmatch(tid)
                or not isinstance(bind, str) or not HEX64.fullmatch(bind)
                or tid != 'gc18-' + bind[:24] or tid in ids or bind in job_bindings
                or t['worker_authorized'] is not False or t['expected_outputs'] != OUTPUTS):
            raise GateBlocked('native_plan_task_identity_or_authority_invalid')
        ids.add(tid); job_bindings.add(bind)
    return {'source_sha256': raw['source_sha256'], 'source_job_count': len(tasks),
            'source_asset_count': raw['source_asset_count']}


def check_plan(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024 * 1024:
        raise GateBlocked('native_plan_missing_or_unsafe')
    try:
        doc = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, UnicodeError, OSError) as exc:
        raise GateBlocked('native_plan_json_invalid') from exc
    result = validate_plan(doc)
    if path.name != result['source_sha256'] + '.json':
        raise GateBlocked('native_plan_file_identity_invalid')
    return result


def check_all(a1: Path, a2: Path, plan: Path) -> dict[str, Any]:
    if a1.resolve() == a2.resolve():
        raise GateBlocked('native_proof_archives_not_independent')
    p1 = check_archive(a1, PROFILE['A1'])
    p2 = check_archive(a2, PROFILE['A2'])
    p3 = check_plan(plan)
    return {'a1_archive_sha256': p1['archive_sha256'], 'a1_jsx_sha256': p1['jsx_sha256'],
            'a2_archive_sha256': p2['archive_sha256'], 'a2_jsx_sha256': p2['jsx_sha256'],
            **p3, 'native_adapter_implemented': False, 'windows_worker_admitted': False,
            'dispatch_authorized': False, 'pdf_builder_invoked': False}


def main() -> int:
    parser = argparse.ArgumentParser(description='GC18 read-only recovered native proof gate')
    parser.add_argument('--a1-archive', type=Path, required=True)
    parser.add_argument('--a2-archive', type=Path, required=True)
    parser.add_argument('--native-plan', type=Path, required=True)
    args = parser.parse_args()
    try:
        summary = check_all(args.a1_archive, args.a2_archive, args.native_plan)
    except (GateBlocked, OSError, KeyError, TypeError) as exc:
        print('GC18_NATIVE_SOURCE_PROOF_GATE=BLOCKED')
        print('ERROR_CODE=' + (str(exc) if isinstance(exc, GateBlocked) else type(exc).__name__))
        print('CLIENT_PATHS_PRINTED=false')
        return 2
    print('GC18_NATIVE_SOURCE_PROOF_GATE=PASS_RECOVERED_SOURCES_REVIEW_ONLY')
    for k in ('a1_archive_sha256', 'a1_jsx_sha256', 'a2_archive_sha256', 'a2_jsx_sha256',
              'source_sha256', 'source_job_count', 'source_asset_count'):
        print(k.upper() + '=' + str(summary[k]))
    print('NATIVE_ADAPTER_IMPLEMENTED=false')
    print('WINDOWS_WORKER_ADMITTED=false')
    print('WINDOWS_DISPATCH=false')
    print('PDF_BUILDER_INVOKED=false')
    print('CLIENT_WORKSPACE_MUTATED=false')
    print('PRIVATE_SOURCE_EMBEDDED_IN_GIT=false')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

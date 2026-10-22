#!/usr/bin/env python3
"""GDL W2.7-C1 synthetic execution-profile candidate review; no execution.

Validate a reproducible, hash-pinned JSX profile and a W2.7-A package containing
its exact bytes. The result explicitly denies launch/dispatch/acceptance. An
executable-looking JSX is *not* a security clearance or a COM runtime proof.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import sys
import zipfile

from gdl_w27_illustrator_task_package_v0_1 import (
    MAX_ARCHIVE, PackageBlocked, check_static, inspect_zip, read_regular,
    repo_tmp_path,
)

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / 'coordination/graphic_design_lab/worker_runtime/gdl_w27c_native_candidate_contract_v0_1.json'
FIXTURE = ROOT / 'tests/fixtures/graphic_design_lab/gdl_w27c/synthetic_native_roundtrip.jsx'
REQUEST = ROOT / 'tests/fixtures/graphic_design_lab/gdl_w27c/synthetic_native_request.json'
SCHEMA = 'gdl_w27c_native_candidate_contract_v0_1'
STATE = 'SYNTHETIC_NATIVE_CANDIDATE_VERIFIED_NOT_EXECUTABLE_BY_WORKER'
TASK = 'gdl-w27c-native-001'
ATTEMPT = 'a0001'
EXPECTED = [
    {'kind': 'native_ai', 'path': 'export/native_result.ai', 'required': True},
    {'kind': 'machine_result', 'path': 'export/worker_result.json', 'required': True},
]
MARKERS = (
    '#target illustrator', 'NO_DIALOGS_OR_ALERTS', 'app.documents.add',
    'TextType.AREATEXT', 'saveAs', 'app.open', 'DONOTSAVECHANGES',
    'FORPRINT_W27C_SYNTHETIC_NATIVE_REOPENED',
)
SHA = re.compile('^[0-9a-f]{64}$')


class CandidateBlocked(RuntimeError):
    pass


def source_check() -> tuple[dict, bytes]:
    try:
        check_static()
        if any(not p.is_file() or p.is_symlink() for p in (CONTRACT, FIXTURE, REQUEST)):
            raise CandidateBlocked('profile contract or fixtures missing/symlinked')
        config = json.loads(CONTRACT.read_text('utf-8'))
        request = json.loads(REQUEST.read_text('utf-8'))
        script = FIXTURE.read_bytes()
    except (ValueError, OSError, PackageBlocked, UnicodeError, ImportError) as exc:
        raise CandidateBlocked('GDL W2.7-A authority/profile unavailable') from exc
    required = {'schema_version','status','task_id','attempt_id','adapter_id',
                'jsx_sha256','jsx_bytes','jsx_entry','required_outputs',
                'runner_implementation','launch_authorized','blueprint_review_pending',
                'customer_data_allowed','automatic_accept','production_publish',
                'cleanup_allowed'}
    if not isinstance(config, dict) or set(config) != required:
        raise CandidateBlocked('profile contract keys changed')
    if (config['schema_version'] != SCHEMA or
            config['status'] != 'LOCAL_SYNTHETIC_CANDIDATE_PENDING_EXECUTION_AUTHORIZATION' or
            config['task_id'] != TASK or config['attempt_id'] != ATTEMPT or
            config['adapter_id'] != 'illustrator' or
            config['jsx_entry'] != 'input/main.jsx' or
            config['required_outputs'] != [x['path'] for x in EXPECTED] or
            config['runner_implementation'] != 'NOT_IMPLEMENTED' or
            config['blueprint_review_pending'] is not True or
            any(config[k] is not False for k in ('launch_authorized','customer_data_allowed',
                                               'automatic_accept','production_publish','cleanup_allowed'))):
        raise CandidateBlocked('profile execution authority/identity changed')
    if (type(config['jsx_bytes']) is not int or not 128 <= len(script) <= 8192 or
            config['jsx_bytes'] != len(script) or not isinstance(config['jsx_sha256'],str) or
            not SHA.fullmatch(config['jsx_sha256']) or
            sha256(script).hexdigest() != config['jsx_sha256']):
        raise CandidateBlocked('JSX profile digest or size changed')
    # These are documentary/profile markers, NOT a static safe-JSX proof.
    try:
        source = script.decode('ascii')
    except UnicodeDecodeError as exc:
        raise CandidateBlocked('JSX profile is not ASCII') from exc
    if any(m not in source for m in MARKERS):
        raise CandidateBlocked('synthetic proof source missing reviewed markers')
    for bad in ('alert(', 'confirm(', 'prompt(', 'app.quit(', 'Folder.myDocuments',
                'File.openDialog', 'executeMenuCommand(', 'system.callSystem('):
        if bad in source:
            raise CandidateBlocked('profile contains forbidden interactive/system API')
    if (not isinstance(request,dict) or request.get('schema_version') != 'gdl_illustrator_task_request_v0_1' or
            request.get('task_id') != TASK or request.get('attempt_id') != ATTEMPT or
            request.get('adapter_id') != 'illustrator' or request.get('data_class') != 'SYNTHETIC_ONLY' or
            request.get('script') != {'path':'input/main.jsx','bytes':len(script), 'sha256': config['jsx_sha256']} or
            request.get('inputs') != [] or request.get('expected_outputs') != EXPECTED or
            request.get('authority') != {'worker_launch':False,'production_publish':False,'automatic_accept':False}):
        raise CandidateBlocked('synthetic W2.7-A request does not match pinned profile')
    return config, script


def inspect_candidate(raw: bytes, expected: str, config: dict, script: bytes) -> dict:
    if not isinstance(expected, str) or not SHA.fullmatch(expected):
        raise CandidateBlocked('expected package digest invalid')
    try:
        manifest, digest = inspect_zip(raw)
        with zipfile.ZipFile(io.BytesIO(raw), 'r') as z:
            payload = z.read('input/main.jsx')
    except (PackageBlocked, zipfile.BadZipFile, OSError, KeyError) as exc:
        raise CandidateBlocked('W2.7-A package not structurally verified') from exc
    if digest != expected:
        raise CandidateBlocked('independent package digest mismatch')
    if (manifest.get('task_id') != TASK or manifest.get('attempt_id') != ATTEMPT or
            manifest.get('script_path') != 'input/main.jsx' or
            manifest.get('data_class') != 'SYNTHETIC_ONLY' or
            manifest.get('authority') != {'worker_launch':False,'production_publish':False,
                                          'automatic_accept':False,'dispatch_authorized':False} or
            manifest.get('expected_outputs') != sorted(EXPECTED, key=lambda x:x['path']) or
            manifest.get('governance') != 'BLUEPRINT_REVIEW_PENDING'):
        raise CandidateBlocked('candidate identity/scope/authority mismatch')
    if payload != script or sha256(payload).hexdigest() != config['jsx_sha256']:
        raise CandidateBlocked('candidate JSX differs from profile source')
    return {
        'schema_version':'gdl_w27c_native_candidate_review_v0_1',
        'state':STATE,
        'task_id':TASK,'attempt_id':ATTEMPT,
        'archive_sha256':digest,'archive_bytes':len(raw),
        'jsx_sha256':config['jsx_sha256'],'jsx_bytes':len(payload),
        'profile_exact_bytes_verified':True,'package_structurally_verified':True,
        'synthetic_only':True,'staging_status':'NOT_EVALUATED',
        'windows_mutation':False,'illustrator_execution':False,
        'worker_launch_authorized':False,'dispatch_authorized':False,
        'blueprint_review_pending':True,'production_ready':False,'accepted':False,
        'automatic_cleanup':False,'runtime_verified':False,
        'next_boundary':'EXPLICIT_OPERATOR_BLUEPRINT_EXECUTION_AUTHORITY_AND_RUNNER_REVIEW',
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', choices=('source-check','review-package'), required=True)
    p.add_argument('--archive', type=Path)
    p.add_argument('--expected-archive-sha256')
    args = p.parse_args(argv)
    try:
        config, source = source_check()
        if args.mode == 'source-check':
            if args.archive or args.expected_archive_sha256:
                raise CandidateBlocked('source-check accepts no package')
            print('GDL_W27C_NATIVE_CANDIDATE=SOURCE_CHECK_PASS')
            print('WINDOWS_WRITE=false ILLUSTRATOR_EXECUTION=false DISPATCH_ALLOWED=false')
            return 0
        if not args.archive or not args.expected_archive_sha256:
            raise CandidateBlocked('explicit package and independent digest required')
        try:
            pth = repo_tmp_path(args.archive, must_exist=True)
            if pth.suffix != '.zip':
                raise CandidateBlocked('package must be zip')
            raw = read_regular(pth, MAX_ARCHIVE)
        except (PackageBlocked,OSError) as exc:
            raise CandidateBlocked('unsafe package location or size') from exc
        doc = inspect_candidate(raw,args.expected_archive_sha256,config,source)
        print(json.dumps(doc,sort_keys=True,ensure_ascii=False,indent=2))
        print('GDL_W27C_NATIVE_CANDIDATE='+doc['state'])
        return 0
    except CandidateBlocked as exc:
        print('GDL_W27C_NATIVE_CANDIDATE=BLOCKED reason='+str(exc),file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

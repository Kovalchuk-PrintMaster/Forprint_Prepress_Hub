#!/usr/bin/env python3
"""GDL W2.7-A: deterministic local Illustrator task package, NEVER dispatches.

Prepares a synthetic-only, immutable task/attempt-bound ZIP under repo tmp/.
No SSH, Windows, Illustrator, Makefile, Git, cleanup or production side effects.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / 'coordination/graphic_design_lab/worker_runtime/gdl_w27_task_package_contract_v0_1.json'
W1 = ROOT / 'coordination/graphic_design_lab/worker_runtime/windows_worker_w1_pilot_contract_v0_1.yaml'
SCHEMA = 'gdl_illustrator_task_package_v0_1'
REQUEST = 'gdl_illustrator_task_request_v0_1'
STATUS = 'PREPARED_NOT_DISPATCH_AUTHORIZED'
REVIEW = 'PACKAGE_STRUCTURALLY_VERIFIED_NOT_DISPATCHED'
NAME_RE = re.compile(r'^[a-z][a-z0-9-]{3,63}$')
ATTEMPT_RE = re.compile(r'^a[0-9]{4}$')
SHA_RE = re.compile(r'^[0-9a-f]{64}$')
SEG_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}$')
MAX_MEMBER = 8 * 1024 * 1024
MAX_TOTAL = 16 * 1024 * 1024
MAX_ARCHIVE = 18 * 1024 * 1024
ZIP_DATE = (2020, 1, 1, 0, 0, 0)
ALLOWED_INPUT_SUFFIXES = {'.jsx', '.svg', '.png', '.jpg', '.jpeg', '.pdf', '.txt', '.json', '.ai', '.eps'}
ALLOWED_OUTPUT_SUFFIXES = {'.ai', '.pdf', '.svg', '.png', '.json'}

class PackageBlocked(ValueError):
    pass


def fail(msg: str) -> None:
    raise PackageBlocked(msg)


def sha(blob: bytes) -> str:
    return sha256(blob).hexdigest()


def json_bytes(doc: dict) -> bytes:
    return (json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')


def exact_keys(doc: object, keys: set[str], title: str) -> dict:
    if not isinstance(doc, dict) or set(doc) != keys:
        fail(title + ' keys/schema invalid')
    return doc


def safe_rel(raw: object, *, prefix: str | None = None, suffixes: set[str] | None = None) -> str:
    if not isinstance(raw, str) or not 1 <= len(raw) <= 240 or '\\' in raw or '\x00' in raw:
        fail('unsafe relative path')
    p = PurePosixPath(raw)
    if p.is_absolute() or str(p) != raw or any(not SEG_RE.fullmatch(s) or s in ('.', '..') or s.startswith('.') for s in raw.split('/')):
        fail('unsafe path segments')
    if prefix is not None and (not raw.startswith(prefix + '/') or len(raw.split('/')) < 2):
        fail('path outside required namespace')
    if suffixes is not None and p.suffix.lower() not in suffixes:
        fail('file suffix not allowed')
    return raw


def positive_int(value: object, maxval: int) -> int:
    if type(value) is not int or not 0 < value <= maxval:
        fail('file size invalid')
    return value


def hash_string(value: object) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        fail('invalid SHA256')
    return value


def check_static() -> dict:
    if not CONTRACT.is_file() or CONTRACT.is_symlink() or not W1.is_file() or W1.is_symlink():
        fail('contract source missing or symlink')
    try:
        c = json.loads(CONTRACT.read_text('utf-8'))
        import yaml
        w1 = yaml.safe_load(W1.read_text('utf-8'))
    except (OSError, ValueError, ImportError) as exc:
        raise PackageBlocked('contract source unreadable') from exc
    exact_keys(c, {'schema_version', 'state', 'schema', 'scope', 'allowed_adapter',
                   'requires_blueprint_review', 'launch_allowed', 'production_publish_allowed',
                   'automatic_accept_allowed', 'source_root', 'archive_root', 'max_payload_bytes'}, 'W2.7 contract')
    if (c['schema_version'] != 'gdl_w27_task_package_contract_v0_1'
            or c['state'] != 'LOCAL_DRAFT_PENDING_BLUEPRINT_REVIEW'
            or c['schema'] != SCHEMA or c['scope'] != 'SYNTHETIC_ONLY'
            or c['allowed_adapter'] != 'illustrator'
            or c['requires_blueprint_review'] is not True
            or any(c[k] is not False for k in ('launch_allowed', 'production_publish_allowed', 'automatic_accept_allowed'))
            or c['source_root'] != 'tmp' or c['archive_root'] != 'tmp'
            or type(c['max_payload_bytes']) is not int or c['max_payload_bytes'] != MAX_TOTAL):
        fail('W2.7 scope or authority mismatch')
    if (w1.get('windows', {}).get('access_control', {}).get('policy_id') != 'gdl_windows_operator_full_control_dev_v0_3'
            or w1.get('authority', {}).get('worker_launch') is not False
            or w1.get('authority', {}).get('production_publish') is not False
            or w1.get('authority', {}).get('automatic_acceptance') is not False
            or w1.get('cleanup', {}).get('no_automatic_deletion') is not True):
        fail('W1 authority changed')
    return c


def read_request(source_root: Path, request_path: Path) -> tuple[dict, dict[str, bytes]]:
    if not source_root.is_dir() or source_root.is_symlink():
        fail('source root invalid')
    if not request_path.is_file() or request_path.is_symlink():
        fail('request missing/symlink')
    try:
        raw = request_path.read_bytes()
        if len(raw) > 65536:
            fail('request too large')
        r = json.loads(raw.decode('utf-8'))
    except (ValueError, UnicodeError, OSError) as exc:
        raise PackageBlocked('request invalid JSON') from exc
    exact_keys(r, {'schema_version', 'task_id', 'attempt_id', 'adapter_id', 'data_class',
                   'script', 'inputs', 'expected_outputs', 'authority'}, 'task request')
    if (r['schema_version'] != REQUEST or not isinstance(r['task_id'], str)
            or not NAME_RE.fullmatch(r['task_id']) or not isinstance(r['attempt_id'], str)
            or not ATTEMPT_RE.fullmatch(r['attempt_id']) or r['adapter_id'] != 'illustrator'
            or r['data_class'] != 'SYNTHETIC_ONLY'):
        fail('task identity/adapter/scope mismatch')
    authority = exact_keys(r['authority'], {'worker_launch', 'production_publish', 'automatic_accept'}, 'authority')
    if any(authority[k] is not False for k in authority):
        fail('task tries to grant execution authority')
    if (not isinstance(r['inputs'], list) or len(r['inputs']) > 24
            or not isinstance(r['expected_outputs'], list) or not 1 <= len(r['expected_outputs']) <= 16):
        fail('input/output inventory invalid')
    script = exact_keys(r['script'], {'path', 'bytes', 'sha256'}, 'script')
    script_path = safe_rel(script['path'], prefix='input', suffixes={'.jsx'})
    if script_path != 'input/main.jsx':
        fail('script path must be input/main.jsx')
    positive_int(script['bytes'], MAX_MEMBER)
    hash_string(script['sha256'])
    all_sources = [script] + r['inputs']
    seen: set[str] = set()
    blobs: dict[str, bytes] = {}
    total = 0
    for i, entry in enumerate(all_sources):
        exact_keys(entry, {'path', 'bytes', 'sha256'}, 'input entry')
        member = safe_rel(entry['path'], prefix='input', suffixes=ALLOWED_INPUT_SUFFIXES)
        if i > 0 and not member.startswith('input/assets/'):
            fail('asset path must use input/assets/')
        if member.casefold() in seen:
            fail('duplicate or case-colliding payload path')
        seen.add(member.casefold())
        length = positive_int(entry['bytes'], MAX_MEMBER)
        digest = hash_string(entry['sha256'])
        total += length
        if total > MAX_TOTAL:
            fail('payload byte budget exceeded')
        rel = member.removeprefix('input/')
        candidate = source_root / rel
        # Reject symlink components and non-regular files, including surprising hard links.
        current = source_root
        for comp in PurePosixPath(rel).parts:
            current = current / comp
            if current.is_symlink():
                fail('symlink payload path')
        try:
            mode = candidate.stat(follow_symlinks=False).st_mode
            if not stat.S_ISREG(mode) or candidate.stat(follow_symlinks=False).st_nlink != 1:
                fail('payload not a single regular file')
            if candidate.stat(follow_symlinks=False).st_size != length:
                fail('payload length changed')
            blob = candidate.read_bytes()
        except OSError as exc:
            raise PackageBlocked('payload inaccessible') from exc
        if len(blob) != length or sha(blob) != digest:
            fail('payload SHA256 does not match request')
        blobs[member] = blob
    outputs = []
    for item in r['expected_outputs']:
        exact_keys(item, {'path', 'kind', 'required'}, 'expected output')
        name = safe_rel(item['path'], prefix='export', suffixes=ALLOWED_OUTPUT_SUFFIXES)
        if item['required'] is not True or item['kind'] not in ('native_ai', 'pdf', 'svg', 'png', 'machine_result'):
            fail('output kind/required invalid')
        if (item['kind'] == 'native_ai' and not name.endswith('.ai')
                or item['kind'] == 'pdf' and not name.endswith('.pdf')
                or item['kind'] == 'svg' and not name.endswith('.svg')
                or item['kind'] == 'png' and not name.endswith('.png')
                or item['kind'] == 'machine_result' and not name.endswith('.json')):
            fail('output suffix-kind mismatch')
        if name.casefold() in seen:
            fail('duplicated output name')
        seen.add(name.casefold())
        outputs.append(item)
    if not any(item['kind'] == 'native_ai' for item in outputs):
        fail('native editable Illustrator output required')
    if not any(item['kind'] == 'machine_result' for item in outputs):
        fail('machine-readable result required')
    return r, blobs


def manifest_for(request: dict, blobs: dict[str, bytes]) -> dict:
    return {
        'schema_version': SCHEMA,
        'state': STATUS,
        'task_id': request['task_id'], 'attempt_id': request['attempt_id'],
        'adapter_id': 'illustrator', 'data_class': 'SYNTHETIC_ONLY',
        'source_schema': REQUEST,
        'script_path': 'input/main.jsx',
        'inputs': [{'path': name, 'bytes': len(blob), 'sha256': sha(blob)} for name, blob in sorted(blobs.items())],
        'expected_outputs': sorted(request['expected_outputs'], key=lambda e: e['path']),
        'transport': {'target_host': 'PREPRESS', 'target_session': 'INTERACTIVE_REQUIRED',
                      'run_level': 'Limited', 'method': 'COM_DO_JAVASCRIPT',
                      'windows_stage': 'NOT_IMPLEMENTED', 'return_stage': 'NOT_IMPLEMENTED'},
        'authority': {'worker_launch': False, 'production_publish': False,
                      'automatic_accept': False, 'dispatch_authorized': False},
        'acceptance': {'state': 'NOT_ACCEPTED', 'independent_result_required': True,
                       'independent_artifact_sha_required': True},
        'cleanup': {'automatic_deletion': False},
        'governance': 'BLUEPRINT_REVIEW_PENDING',
    }


def zip_member(name: str, blob: bytes) -> tuple[zipfile.ZipInfo, bytes]:
    zi = zipfile.ZipInfo(name, date_time=ZIP_DATE)
    zi.compress_type = zipfile.ZIP_STORED
    zi.create_system = 3
    zi.external_attr = (0o100600 << 16)
    return zi, blob


def archive_bytes(manifest: dict, blobs: dict[str, bytes]) -> bytes:
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, mode='w', allowZip64=False) as z:
        for name, blob in [('task_manifest.json', json_bytes(manifest)), *sorted(blobs.items())]:
            info, payload = zip_member(name, blob)
            z.writestr(info, payload)
    buf = raw.getvalue()
    if len(buf) > MAX_ARCHIVE:
        fail('archive too large')
    return buf


def validate_manifest(doc: object) -> dict:
    exact_keys(doc, {'schema_version', 'state', 'task_id', 'attempt_id', 'adapter_id', 'data_class',
                     'source_schema', 'script_path', 'inputs', 'expected_outputs', 'transport',
                     'authority', 'acceptance', 'cleanup', 'governance'}, 'manifest')
    if doc['schema_version'] != SCHEMA or doc['state'] != STATUS or doc['data_class'] != 'SYNTHETIC_ONLY' or doc['adapter_id'] != 'illustrator':
        fail('archive manifest schema/scope invalid')
    if doc['source_schema'] != REQUEST or doc['script_path'] != 'input/main.jsx' or doc['governance'] != 'BLUEPRINT_REVIEW_PENDING':
        fail('archive manifest bindings invalid')
    if not isinstance(doc['task_id'], str) or not NAME_RE.fullmatch(doc['task_id']) or not isinstance(doc['attempt_id'], str) or not ATTEMPT_RE.fullmatch(doc['attempt_id']):
        fail('archive attempt ID invalid')
    if doc['authority'] != {'worker_launch':False,'production_publish':False,'automatic_accept':False,'dispatch_authorized':False}:
        fail('archive authority changed')
    if doc['acceptance'] != {'state':'NOT_ACCEPTED','independent_result_required':True,'independent_artifact_sha_required':True}:
        fail('archive acceptance changed')
    if doc['cleanup'] != {'automatic_deletion':False}:
        fail('archive cleanup changed')
    if doc['transport'] != {'target_host':'PREPRESS','target_session':'INTERACTIVE_REQUIRED','run_level':'Limited',
                            'method':'COM_DO_JAVASCRIPT','windows_stage':'NOT_IMPLEMENTED','return_stage':'NOT_IMPLEMENTED'}:
        fail('archive transport boundary changed')
    if not isinstance(doc['inputs'],list) or not 1 <= len(doc['inputs']) <= 25 or not isinstance(doc['expected_outputs'],list) or not 2 <= len(doc['expected_outputs']) <= 16:
        fail('archive input/output inventory invalid')
    return doc


def inspect_zip(raw: bytes) -> tuple[dict, str]:
    if len(raw) > MAX_ARCHIVE or len(raw) < 200:
        fail('archive outside size bound')
    try:
        with zipfile.ZipFile(io.BytesIO(raw), mode='r') as z:
            infos = z.infolist()
            if len(infos) > 26 or len(infos) < 2 or infos[0].filename != 'task_manifest.json':
                fail('archive file list invalid')
            names = [v.filename for v in infos]
            if len(names) != len(set(n.casefold() for n in names)):
                fail('archive duplicate or casefold collision')
            for i in infos:
                if (i.date_time != ZIP_DATE or i.compress_type != zipfile.ZIP_STORED or
                        i.create_system != 3 or ((i.external_attr >> 16) & 0o170777) != 0o100600 or
                        i.file_size > MAX_MEMBER or i.flag_bits & 0x1 or i.is_dir()):
                    fail('archive member metadata unsafe')
            manifest_raw = z.read('task_manifest.json')
            if len(manifest_raw) > 32768:
                fail('archive manifest too large')
            doc = validate_manifest(json.loads(manifest_raw.decode('utf-8')))
            if manifest_raw != json_bytes(doc):
                fail('manifest not canonical JSON')
            expected = []
            total = 0
            seen = set()
            for entry in doc['inputs']:
                exact_keys(entry, {'path', 'bytes', 'sha256'}, 'archive input')
                name = safe_rel(entry['path'], prefix='input', suffixes=ALLOWED_INPUT_SUFFIXES)
                if name.casefold() in seen:
                    fail('archive duplicate payload')
                if name != 'input/main.jsx' and not name.startswith('input/assets/'):
                    fail('archive asset namespace invalid')
                seen.add(name.casefold())
                length = positive_int(entry['bytes'], MAX_MEMBER)
                digest = hash_string(entry['sha256'])
                blob = z.read(name)
                if len(blob) != length or sha(blob) != digest:
                    fail('archive file SHA mismatch')
                total += length
                expected.append(name)
            if total > MAX_TOTAL or 'input/main.jsx' not in expected:
                fail('archive payload budget or script absent')
            if names != ['task_manifest.json', *sorted(expected)]:
                fail('unexpected/archive reordered members')
            kinds = set()
            seen = set()
            for entry in doc['expected_outputs']:
                exact_keys(entry, {'path','kind','required'}, 'archive output')
                name = safe_rel(entry['path'], prefix='export', suffixes=ALLOWED_OUTPUT_SUFFIXES)
                if name.casefold() in seen or entry['required'] is not True:
                    fail('bad expected output')
                seen.add(name.casefold())
                if (entry['kind'], PurePosixPath(name).suffix) not in {('native_ai','.ai'),('pdf','.pdf'),('svg','.svg'),('png','.png'),('machine_result','.json')}:
                    fail('bad expected output kind')
                kinds.add(entry['kind'])
            if 'native_ai' not in kinds or 'machine_result' not in kinds:
                fail('required output kind missing')
            if doc['inputs'] != sorted(doc['inputs'], key=lambda e:e['path']) or doc['expected_outputs'] != sorted(doc['expected_outputs'], key=lambda e:e['path']):
                fail('manifest input/output unsorted')
            return doc, sha(raw)
    except (zipfile.BadZipFile, json.JSONDecodeError, UnicodeError, KeyError, RuntimeError, OSError, OverflowError) as exc:
        raise PackageBlocked('archive structurally invalid') from exc


def read_regular(path: Path, bound: int) -> bytes:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > bound:
        fail('archive source invalid/symlink/oversized')
    return path.read_bytes()


def repo_tmp_path(path: Path, *, must_exist: bool) -> Path:
    # Lexical AND resolved bounds avoid traversal, symlink parents and accidental client roots.
    tmp = ROOT / 'tmp'
    if not tmp.is_dir() or tmp.is_symlink():
        fail('repository tmp missing/unsafe')
    resolved_tmp = tmp.resolve(strict=True)
    path = path.absolute()
    if not path.is_relative_to(tmp.absolute()) or path == tmp.absolute():
        fail('path must stay inside repository tmp')
    parent = path.parent
    if not parent.is_dir() or parent.is_symlink() or parent.resolve(strict=True) != resolved_tmp:
        # W2.7-A intentionally permits only a DIRECT child of tmp for source/output.
        fail('path must be an immediate tmp child, without symlink parent')
    if must_exist and (not path.is_file() or path.is_symlink()):
        fail('expected file absent/unsafe')
    if not must_exist and (path.exists() or path.is_symlink()):
        fail('destination already present; do not overwrite')
    return path


def run_prepare(request_file: Path, source: Path, output: Path) -> dict:
    request_file = repo_tmp_path(request_file, must_exist=True)
    # source is a unique non-symlink immediate child directory of repo tmp.
    source = source.absolute()
    tmp = (ROOT / 'tmp').absolute()
    if source.parent != tmp or not source.is_dir() or source.is_symlink() or source.resolve(strict=True).parent != tmp.resolve(strict=True):
        fail('source must be immediate tmp child directory')
    output = repo_tmp_path(output, must_exist=False)
    if output.suffix != '.zip':
        fail('destination must have .zip extension')
    request, blobs = read_request(source, request_file)
    manifest = manifest_for(request, blobs)
    raw = archive_bytes(manifest, blobs)
    verified, digest = inspect_zip(raw)
    if verified != manifest:
        fail('self-verification contradiction')
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os,'O_NOFOLLOW',0)
    try:
        fd = os.open(output, flags, 0o600)
        with os.fdopen(fd, 'wb') as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
    except OSError as exc:
        raise PackageBlocked('new-only package write failed; inspect before retry') from exc
    return receipt(STATUS, manifest, digest, len(raw), output.name)


def receipt(state: str, doc: dict, digest: str, length: int, basename: str) -> dict:
    return {'schema_version':'gdl_w27_task_package_receipt_v0_1',
            'state':state, 'task_id':doc['task_id'], 'attempt_id':doc['attempt_id'],
            'archive_filename':basename, 'archive_bytes':length, 'archive_sha256':digest,
            'payload_count':len(doc['inputs']), 'expected_output_count':len(doc['expected_outputs']),
            'synthetic_only':True,'windows_mutation':False,'illustrator_execution':False,
            'worker_launch_authorized':False,'production_ready':False,'accepted':False,
            'automatic_cleanup':False,'blueprint_review_pending':True}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('source-check','prepare','verify'), required=True)
    parser.add_argument('--request', type=Path)
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--expected-archive-sha256')
    parser.add_argument('--confirm-synthetic-package', action='store_true')
    args = parser.parse_args(argv)
    try:
        check_static()
        if args.mode == 'source-check':
            if any([args.request,args.source_root,args.output,args.archive,args.expected_archive_sha256,args.confirm_synthetic_package]):
                fail('source-check accepts no operation arguments')
            print('GDL_W2_7_TASK_PACKAGE=SOURCE_CHECK_PASS')
            print('WINDOWS_WRITE=false ILLUSTRATOR_EXECUTION=false DISPATCH_ALLOWED=false')
            return 0
        if args.mode == 'prepare':
            if (not args.confirm_synthetic_package or not all([args.request,args.source_root,args.output])
                    or args.archive or args.expected_archive_sha256):
                fail('prepare arguments or explicit confirmation missing')
            result = run_prepare(args.request, args.source_root, args.output)
        else:
            if (args.confirm_synthetic_package or not args.archive or args.request or args.source_root or args.output):
                fail('verify arguments invalid')
            path = repo_tmp_path(args.archive, must_exist=True)
            if path.suffix != '.zip':
                fail('verify requires .zip')
            raw = read_regular(path, MAX_ARCHIVE)
            doc, digest = inspect_zip(raw)
            if args.expected_archive_sha256 and hash_string(args.expected_archive_sha256) != digest:
                fail('independent expected archive SHA256 mismatched')
            result = receipt(REVIEW, doc, digest, len(raw), path.name)
        print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))
        print('GDL_W2_7_TASK_PACKAGE=' + result['state'])
        return 0
    except (PackageBlocked, OSError) as exc:
        print('GDL_W2_7_TASK_PACKAGE=BLOCKED reason=' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

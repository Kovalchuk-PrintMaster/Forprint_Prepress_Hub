#!/usr/bin/env python3
"""C3J: verify candidate signed Ed25519 evidence but NEVER issue execution authority.

No private key, trust anchor, Dispatcher, Windows/SSH/COM, launch or mutation.
A self-chosen public key can prove only signature consistency, not owner authority.
Owner/trust root and actual single-use consumption remain external blocked gates.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

from gdl_w27c3i_closeout_readiness_v0_1 import (
    source_check as c3i_source_check, ReadinessBlocked,
)

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / 'coordination/graphic_design_lab/worker_runtime/gdl_w27c3j_authority_proof_review_contract_v0_1.json'
SCHEMA = 'gdl_w27c3j_authority_proof_review_contract_v0_1'
PROOF_SCHEMA = 'gdl_w27c3j_signed_execution_intent_v0_1'
REPORT = 'gdl_w27c3j_authority_evidence_review_v0_1'
TASK = 'gdl-w27c-native-001'
ATTEMPT = 'a0001'
PACKAGE = 'd1949844b3ab2d68936facf8012e6b8fba1ecd1134597f2e6f4139ef1449b3e7'
JSX = '98780bcd7939df58f16aa0e123ced5efc4956ed43cc6438d0516b43d4d819902'
RUNNER = '8ef7a0298646295c24d2d091ce433ac0cfcdbb4831b05469c493ff6d3ce8b934'
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
HEX32 = re.compile(r'[0-9a-f]{32}\Z')
DATE = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z')
ED25519_DER_PREFIX = bytes.fromhex('302a300506032b6570032100')


class AuthorityBlocked(RuntimeError):
    pass


def require(value: bool, reason: str) -> None:
    if not value:
        raise AuthorityBlocked(reason)


def unique(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for k, v in pairs:
        require(k not in result, 'duplicate JSON key')
        result[k] = v
    return result


def exact_json(blob: bytes) -> dict:
    try:
        text = blob.decode('utf-8', 'strict')
        obj = json.loads(text, object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(AuthorityBlocked('invalid JSON constant')))
    except (UnicodeError, ValueError, TypeError) as exc:
        raise AuthorityBlocked('malformed JSON') from exc
    require(type(obj) is dict, 'expected JSON object')
    return obj


def source_check() -> dict:
    try:
        c3i_source_check()
        require(CONTRACT.is_file() and not CONTRACT.is_symlink(), 'missing/unsafe C3J contract')
        c = exact_json(CONTRACT.read_bytes())
    except (ReadinessBlocked, OSError, UnicodeError, ValueError) as exc:
        raise AuthorityBlocked('missing/invalid C3I provenance or C3J contract') from exc
    expected = {
        'schema_version': SCHEMA, 'state': 'SIGNED_ONE_USE_AUTHORITY_EVIDENCE_REVIEW_ONLY',
        'task_id': TASK, 'attempt_id': ATTEMPT, 'package_sha256': PACKAGE,
        'jsx_sha256': JSX, 'runner_sha256': RUNNER, 'host': 'PREPRESS',
        'windows_account': 'PREPRESS\\Work', 'signature_algorithm': 'Ed25519',
        'review_max_validity_seconds': 900,
        'approved_issuer_public_key_sha256': None,
        'approved_dispatcher_owner_id': None,
        'external_owner_approval_recorded': False,
        'windows_execution_entrypoint_enabled': False,
        'windows_write': False, 'ssh_used': False,
        'dispatch_authorized': False, 'execution_authorized': False,
        'retry_authorized': False, 'production_ready': False,
        'automatic_acceptance': False, 'cleanup_allowed': False,
        'blueprint_review_deferred_not_waived': True,
    }
    require(type(c) is dict and set(c) == set(expected), 'C3J contract fields changed')
    for k, val in expected.items():
        require(type(c[k]) is type(val) and c[k] == val, 'unsafe source contract: ' + k)
    return c


def read_tmp_file(path: Path, limit: int, suffix: str) -> bytes:
    """Bounded, no-follow file reading under project tmp/<one-folder>/<file>."""
    raw = path if path.is_absolute() else ROOT/path
    path = Path(os.path.normpath(str(raw)))
    try:
        bits = path.relative_to(ROOT / 'tmp').parts
        require(len(bits) == 2 and all(b not in ('', '.', '..') for b in bits) and
                bits[1].endswith(suffix), 'evidence must reside in tmp/<dir>/<file>' + suffix)
        for parent in (ROOT/'tmp', ROOT/'tmp'/bits[0]):
            require(stat.S_ISDIR(parent.lstat().st_mode), 'unsafe evidence directory')
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        with os.fdopen(fd, 'rb') as f:
            st = os.fstat(f.fileno())
            require(stat.S_ISREG(st.st_mode) and 1 <= st.st_size <= limit, 'unsafe evidence size/type')
            blob = f.read(limit + 1)
        require(len(blob) == st.st_size, 'evidence changed during read')
        return blob
    except (OSError, ValueError) as exc:
        raise AuthorityBlocked('missing/unsafe evidence path') from exc


def parse_utc(value: str) -> datetime:
    require(type(value) is str and DATE.fullmatch(value) is not None, 'UTC second timestamp required')
    try:
        return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise AuthorityBlocked('invalid timestamp') from exc


def validate_intent(raw: bytes, now: datetime) -> dict:
    require(1 <= len(raw) <= 8192, 'intent size invalid')
    obj = exact_json(raw)
    wanted = {
        'schema_version': PROOF_SCHEMA, 'intent': 'ONE_TIME_SYNTHETIC_NATIVE_EXECUTION',
        'task_id': TASK, 'attempt_id': ATTEMPT, 'package_sha256': PACKAGE,
        'jsx_sha256': JSX, 'runner_sha256': RUNNER, 'host': 'PREPRESS',
        'windows_account': 'PREPRESS\\Work', 'decision': 'ALLOW_SINGLE_ATTEMPT',
        'issuer_key_id': None, 'dispatcher_owner_id': None,
        'nonce': None, 'issued_at': None, 'not_before': None, 'expires_at': None,
    }
    require(set(obj) == set(wanted), 'signed intent unexpected/missing fields')
    for key, val in wanted.items():
        if val is not None:
            require(type(obj[key]) is type(val) and obj[key] == val,
                    'signed intent binding mismatch: ' + key)
    for field in ('issuer_key_id', 'dispatcher_owner_id'):
        require(type(obj[field]) is str and re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.:-]{3,79}', obj[field]) is not None,
                'invalid issuer/owner label')
    require(type(obj['nonce']) is str and HEX32.fullmatch(obj['nonce']) is not None, 'invalid nonce')
    issued, start, end = (parse_utc(obj[k]) for k in ('issued_at','not_before','expires_at'))
    require(issued <= start < end and end - start <= timedelta(seconds=900), 'invalid validity window')
    require(issued >= start - timedelta(minutes=5), 'issued time too early')
    require(now.tzinfo is not None, 'UTC reference required')
    current = now.astimezone(timezone.utc)
    require(start <= current < end, 'intent not current or expired')
    require(issued <= current + timedelta(seconds=30), 'issued in the future')
    canonical = (json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)+'\n').encode('utf-8')
    require(raw == canonical, 'signed intent is not canonical JSON bytes')
    return obj


def verify_ed25519(manifest_bytes: bytes, signature_bytes: bytes, public_key_bytes: bytes) -> None:
    """Verify frozen read-only inputs, never a mutable original evidence path."""
    try:
        # Runtime scratch (not tracked evidence); source evidence is never edited.
        with tempfile.TemporaryDirectory(prefix='gdl_c3j_verify_', dir=ROOT/'tmp') as directory:
            paths = [Path(directory)/n for n in ('proof.json', 'signature.sig', 'issuer.pem')]
            for path, data in zip(paths, (manifest_bytes, signature_bytes, public_key_bytes)):
                path.write_bytes(data)
                path.chmod(0o600)
            def openssl(*args: str) -> subprocess.CompletedProcess:
                return subprocess.run(['openssl', *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      check=False, timeout=10)
            pub = openssl('pkey', '-pubin', '-in', str(paths[2]), '-outform', 'DER')
            require(pub.returncode == 0 and len(pub.stdout) == 44 and
                    pub.stdout.startswith(ED25519_DER_PREFIX), 'not an Ed25519 public key')
            r = openssl('pkeyutl', '-verify', '-pubin', '-inkey', str(paths[2]),
                        '-rawin', '-in', str(paths[0]), '-sigfile', str(paths[1]))
            require(r.returncode == 0, 'Ed25519 signature invalid')
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AuthorityBlocked('OpenSSL signature verifier unavailable') from exc


def review(manifest: Path | None = None, signature: Path | None = None,
           public_key: Path | None = None, now: datetime | None = None) -> dict:
    source_check()
    supplied = (manifest, signature, public_key)
    require(all(x is None for x in supplied) or all(x is not None for x in supplied),
            'signed proof requires manifest, signature and public key together')
    result = {
        'schema_version': REPORT, 'task_id': TASK, 'attempt_id': ATTEMPT,
        'package_sha256': PACKAGE, 'jsx_sha256': JSX, 'runner_sha256': RUNNER,
        'state': 'NO_INDEPENDENT_AUTHORIZATION_PROOF_EXECUTION_BLOCKED',
        'cryptographic_signature_consistent_with_supplied_key': False,
        'trusted_issuer_pinned': False, 'owner_authority_independently_proven': False,
        'dispatcher_owner_approved': False, 'one_use_claim_consumed': False,
        'native_execution_authorized': False, 'dispatch_authorized': False,
        'retry_authorized': False, 'accepted': False, 'production_ready': False,
        'windows_write': False, 'ssh_used': False, 'cleanup_executed': False,
        'next_boundary': 'INDEPENDENT_OWNER_TRUST_ROOT_AND_DISPATCHER_AUTHORITY_REVIEW',
        'proof_sha256': None, 'supplied_untrusted_public_key_sha256': None,
    }
    if manifest is not None:
        blob = read_tmp_file(manifest, 8192, '.json')
        sig = read_tmp_file(signature, 64, '.sig')
        pub = read_tmp_file(public_key, 2048, '.pem')
        require(len(sig) == 64, 'invalid Ed25519 signature byte count')
        validate_intent(blob, now or datetime.now(timezone.utc))
        verify_ed25519(blob, sig, pub)
        result['state'] = 'SELF_CONSISTENT_SIGNATURE_UNTRUSTED_AUTHORITY_BLOCKED'
        result['cryptographic_signature_consistent_with_supplied_key'] = True
        result['proof_sha256'] = sha256(blob).hexdigest()
        result['supplied_untrusted_public_key_sha256'] = sha256(pub).hexdigest()
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode', required=True, choices=('source-check', 'review-proof'))
    ap.add_argument('--manifest', type=Path)
    ap.add_argument('--signature', type=Path)
    ap.add_argument('--public-key', type=Path)
    args = ap.parse_args(argv)
    try:
        if args.mode == 'source-check':
            require(not any((args.manifest,args.signature,args.public_key)),
                    'source-check does not take evidence')
            source_check()
            print('GDL_W27C3J_AUTHORITY_BOUNDARY=SOURCE_CHECK_PASS')
            print('WINDOWS_WRITE=false DISPATCH=false EXECUTION=false ISSUER_TRUST_CONFIGURED=false')
            return 0
        r = review(args.manifest, args.signature, args.public_key)
        print(json.dumps(r, indent=2, sort_keys=True))
        print('GDL_W27C3J_AUTHORITY_BOUNDARY=' + r['state'])
        return 0
    except (AuthorityBlocked, ReadinessBlocked, OSError, ValueError) as exc:
        print('GDL_W27C3J_AUTHORITY_BOUNDARY=BLOCKED reason=' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

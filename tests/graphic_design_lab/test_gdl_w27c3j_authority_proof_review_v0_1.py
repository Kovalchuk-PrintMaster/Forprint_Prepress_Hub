"""C3J proof candidate tests: cryptographic verification is NOT execution permission."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts/graphic_design_lab/worker_runtime'))
import gdl_w27c3j_authority_proof_review_v0_1 as j

NOW = datetime(2026, 10, 23, 15, 0, tzinfo=timezone.utc)


def stamp(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


def intent():
    return {
        'schema_version': j.PROOF_SCHEMA,
        'intent': 'ONE_TIME_SYNTHETIC_NATIVE_EXECUTION',
        'task_id': j.TASK, 'attempt_id': j.ATTEMPT,
        'package_sha256': j.PACKAGE, 'jsx_sha256': j.JSX,
        'runner_sha256': j.RUNNER, 'host': 'PREPRESS',
        'windows_account': 'PREPRESS\\Work',
        'decision': 'ALLOW_SINGLE_ATTEMPT', 'issuer_key_id': 'external-owner-key-v1',
        'dispatcher_owner_id': 'external-dispatch-owner', 'nonce': 'a'*32,
        'issued_at': stamp(NOW-timedelta(minutes=2)),
        'not_before': stamp(NOW-timedelta(minutes=1)),
        'expires_at': stamp(NOW+timedelta(minutes=3)),
    }


def encode(d):
    return (json.dumps(d, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n').encode()


def run(*cmd):
    return subprocess.run(cmd, check=True, capture_output=True)


@pytest.fixture
def proof_dir():
    base = j.ROOT/'tmp'
    base.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='c3j_test_', dir=base) as td:
        yield Path(td)


@pytest.fixture
def signed(proof_dir):
    key = proof_dir/'private.pem'
    pub = proof_dir/'issuer.pem'
    manifest = proof_dir/'manifest.json'
    sig = proof_dir/'signature.sig'
    manifest.write_bytes(encode(intent()))
    run('openssl','genpkey','-algorithm','ED25519','-out',str(key))
    run('openssl','pkey','-in',str(key),'-pubout','-out',str(pub))
    run('openssl','pkeyutl','-sign','-inkey',str(key),'-rawin','-in',str(manifest),'-out',str(sig))
    assert sig.stat().st_size == 64
    return manifest, sig, pub, key


def test_source_check():
    c = j.source_check()
    assert c['approved_issuer_public_key_sha256'] is None
    assert c['windows_execution_entrypoint_enabled'] is False
    assert c['external_owner_approval_recorded'] is False


def test_review_without_evidence():
    r = j.review()
    assert r['state'] == 'NO_INDEPENDENT_AUTHORIZATION_PROOF_EXECUTION_BLOCKED'
    assert not r['dispatch_authorized'] and not r['native_execution_authorized']


def test_signature_self_consistency_no_authority(signed):
    manifest, sig, pub, _ = signed
    r = j.review(manifest, sig, pub, NOW)
    assert r['state'] == 'SELF_CONSISTENT_SIGNATURE_UNTRUSTED_AUTHORITY_BLOCKED'
    assert r['cryptographic_signature_consistent_with_supplied_key'] is True
    assert r['trusted_issuer_pinned'] is False
    for flag in ('native_execution_authorized', 'dispatch_authorized', 'retry_authorized',
                 'accepted', 'production_ready', 'owner_authority_independently_proven',
                 'one_use_claim_consumed'):
        assert r[flag] is False


@pytest.mark.parametrize('mode', ['source-check','review-proof'])
def test_cli_modes_no_approval(mode, capsys):
    assert j.main(['--mode',mode]) == 0
    assert 'GDL_W27C3J_AUTHORITY_BOUNDARY=' in capsys.readouterr().out


@pytest.mark.parametrize('field,invalid', [
    ('schema_version','unauthorized'), ('intent','PRODUCTION'), ('task_id','other'),
    ('attempt_id','a0002'), ('package_sha256','b'*64), ('jsx_sha256','0'*64),
    ('runner_sha256','9'*64), ('host','OTHER'), ('windows_account','OTHER\\Work'),
    ('decision','ALLOW_RETRY'), ('nonce','xyz'), ('nonce','A'*32),
    ('issuer_key_id','!bad'),('issuer_key_id','x'*90),
    ('dispatcher_owner_id','invalid spaces'),
    ('expires_at','2026-10-23T14:00:00Z'),
    ('not_before','2026-10-23T16:00:00Z'),
    ('issued_at','2026-10-23T16:00:00Z'),
    ('issued_at','2026-10-23T14:00:00Z'),
])
def test_invalid_signed_intent_fields(field,invalid):
    data = intent()
    data[field] = invalid
    with pytest.raises(j.AuthorityBlocked):
        j.validate_intent(encode(data), NOW)


@pytest.mark.parametrize('field', list(intent().keys()))
def test_missing_field_fails(field):
    data = intent()
    data.pop(field)
    with pytest.raises(j.AuthorityBlocked):
        j.validate_intent(encode(data), NOW)


@pytest.mark.parametrize('raw',[
    b'', b'[]', b'null', b'{"x":1,"x":2}', b'{"x":NaN}',
    b'{"x":Infinity}', b'\xff', b'notjson', b'\xef\xbb\xbf{}',
])
def test_invalid_json_rejected(raw):
    with pytest.raises(j.AuthorityBlocked):
        j.validate_intent(raw, NOW)


def test_noncanonical_order_rejected():
    with pytest.raises(j.AuthorityBlocked, match='canonical'):
        j.validate_intent(json.dumps(intent()).encode(), NOW)


def test_trailing_extra_field_rejected():
    d=intent(); d['dispatch_authorized']=True
    with pytest.raises(j.AuthorityBlocked):
        j.validate_intent(encode(d), NOW)


def test_valid_intent():
    assert j.validate_intent(encode(intent()), NOW)['task_id']==j.TASK


def test_expired_fails():
    with pytest.raises(j.AuthorityBlocked):
        j.validate_intent(encode(intent()), NOW + timedelta(hours=2))


def test_yet_to_start_fails():
    with pytest.raises(j.AuthorityBlocked):
        j.validate_intent(encode(intent()), NOW - timedelta(hours=2))


def test_long_ttl_fails():
    d=intent(); d['expires_at']=stamp(NOW+timedelta(minutes=20))
    with pytest.raises(j.AuthorityBlocked):
        j.validate_intent(encode(d), NOW)


def test_UTC_only():
    d=intent(); d['issued_at']='2026-10-23T14:58:00+00:00'
    with pytest.raises(j.AuthorityBlocked):
        j.validate_intent(encode(d), NOW)


def test_malformed_signature_rejected(signed):
    manifest, sig, pub, _ = signed
    sig.write_bytes(b'0'*64)
    with pytest.raises(j.AuthorityBlocked):
        j.review(manifest, sig, pub, NOW)


def test_wrong_public_key_rejected(signed, proof_dir):
    manifest, sig, pub, _ = signed
    other = proof_dir/'other-private.pem'
    run('openssl','genpkey','-algorithm','ED25519','-out',str(other))
    run('openssl','pkey','-in',str(other),'-pubout','-out',str(pub))
    with pytest.raises(j.AuthorityBlocked):
        j.review(manifest,sig,pub,NOW)


def test_modified_manifest_invalid_signature(signed):
    manifest, sig, pub, _ = signed
    obj = intent(); obj['nonce'] = 'b'*32
    manifest.write_bytes(encode(obj))
    with pytest.raises(j.AuthorityBlocked):
        j.review(manifest,sig,pub,NOW)


def test_rsa_public_key_rejected(signed, proof_dir):
    manifest, sig, pub, _ = signed
    key = proof_dir/'rsa.pem'
    run('openssl','genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:2048','-out',str(key))
    run('openssl','pkey','-in',str(key),'-pubout','-out',str(pub))
    with pytest.raises(j.AuthorityBlocked):
        j.review(manifest,sig,pub,NOW)


def test_missing_one_of_triple_fails(signed):
    manifest,sig,pub,_=signed
    for values in [(manifest,None,None),(manifest,sig,None),(None,sig,pub),(None,None,pub)]:
        with pytest.raises(j.AuthorityBlocked):
            j.review(*values,now=NOW)


def test_symbolic_link_rejected(signed, proof_dir):
    manifest,sig,pub,_=signed
    link=proof_dir/'link.json'; link.symlink_to(manifest)
    with pytest.raises(j.AuthorityBlocked):
        j.review(link,sig,pub,NOW)


def test_outside_tmp_rejected(signed, tmp_path):
    manifest,sig,pub,_=signed
    outside=tmp_path/'outside.json'; outside.write_bytes(manifest.read_bytes())
    with pytest.raises(j.AuthorityBlocked):
        j.review(outside,sig,pub,NOW)


def test_empty_or_oversized_signature_rejected(signed):
    manifest,sig,pub,_=signed
    for bad in (b'', b'x'*65, b'x'*63):
        sig.write_bytes(bad)
        with pytest.raises(j.AuthorityBlocked):
            j.review(manifest,sig,pub,NOW)


def test_proof_does_not_mutate_original_files(signed):
    manifest,sig,pub,_=signed
    original={p:p.read_bytes() for p in (manifest,sig,pub)}
    j.review(manifest,sig,pub,NOW)
    assert all(p.read_bytes()==raw for p,raw in original.items())


def test_contract_escalation_detected(monkeypatch, proof_dir):
    data=json.loads(j.CONTRACT.read_text())
    data['windows_execution_entrypoint_enabled']=True
    temp=proof_dir/'contradictory.json'; temp.write_text(json.dumps(data))
    monkeypatch.setattr(j,'CONTRACT',temp)
    with pytest.raises(j.AuthorityBlocked):
        j.source_check()


def test_local_code_still_blocks_execution():
    text=Path(j.__file__).read_text()
    assert 'GetActiveObject' not in text
    assert 'DoJavaScript' not in text
    assert '--mode' in text
    assert "'review-proof'" in text
    assert 'subprocess.run' in text  # OpenSSL public-key verification only.


def test_duplicate_proof_keys_rejected():
    raw=encode(intent()).decode()
    bad=raw[:-2]+',"task_id":"x"}\n'
    with pytest.raises(j.AuthorityBlocked):
        j.validate_intent(bad.encode(),NOW)

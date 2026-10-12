#!/usr/bin/env python3
"""Operator reviewed, original-photo-only pilot from GDL server-transfer ZIP.

Never edits photographs, guesses approval, bypasses original rejected Creator
revision, or produces production authority. Produces a valid final handoff only
from an explicit operator approval bound to exact reviewed content + source ZIP.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.graphic_design_lab.greeting_card_constructor_bundle import build_accepted_constructor_bundle
from app.graphic_design_lab.greeting_card_builder_input import attach_builder_payload_v1
from scripts.graphic_design_lab.greeting_cards.intake_handoff_runner_v0_1 import inspect_zip

CATALOG = REPO / 'coordination/graphic_design_lab/directions/greeting_cards/signature_variant_catalog_v0_1.yaml'
SOURCE_BASIS = 'SOURCE_ASSET_OPERATOR_REVIEW_PASS'
MANIFEST = '99_PACKET_MANIFEST.json'
INVENTORY = 'intake_resume/source_inventory.yaml'
BATCH = 'intake_resume/normalized_batch.yaml'
MAX_MEMBER = 100 * 1024 * 1024
MAX_TOTAL = 850 * 1024 * 1024


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def load_archive(path: Path) -> tuple[dict, dict, dict, dict]:
    if not path.is_file():
        raise ValueError('source_archive_missing')
    if path.stat().st_size > 250 * 1024 * 1024:
        raise ValueError('source_archive_too_large')
    with zipfile.ZipFile(path) as z:
        names, casefold = {}, set()
        total_uncompressed = 0
        for item in z.infolist():
            n = item.filename
            parts = n.split('/')
            if (not n or n.startswith('/') or '\\' in n or ':' in parts[0]
                    or any(x in ('', '.', '..') for x in parts) or item.is_dir()):
                raise ValueError('unsafe_member_path')
            mode = (item.external_attr >> 16) & 0o170000
            if mode not in (0, 0o100000) or item.file_size > MAX_MEMBER:
                raise ValueError('unsafe_member_type_or_size')
            if n.casefold() in casefold:
                raise ValueError('duplicate_member')
            total_uncompressed += item.file_size
            if total_uncompressed > MAX_TOTAL:
                raise ValueError('transfer_archive_uncompressed_limit_exceeded')
            casefold.add(n.casefold()); names[n] = item
        for n in (MANIFEST, INVENTORY, BATCH):
            if n not in names: raise ValueError('required_transfer_member_missing:' + n)
        manifest = json.loads(z.read(MANIFEST))
        entries = manifest['entries']
        if manifest['entry_count'] != len(entries) or len(entries) != len(names) - 1:
            raise ValueError('transfer_manifest_count_mismatch')
        if {e['path'] for e in entries} != set(names) - {MANIFEST}:
            raise ValueError('transfer_manifest_set_mismatch')
        for e in entries:
            b = z.read(e['path'])
            if len(b) != e['bytes'] or sha(b) != e['sha256']:
                raise ValueError('transfer_manifest_hash_mismatch')
        inventory = yaml.safe_load(z.read(INVENTORY))
        batch = yaml.safe_load(z.read(BATCH))
        if not isinstance(batch, dict) or not isinstance(inventory, dict):
            raise ValueError('input_yaml_mapping_required')
        assets = {}
        for a in inventory['asset_registry']:
            ref = a['path']
            n = 'intake_resume/' + ref
            if n not in names: raise ValueError('source_asset_path_missing')
            b = z.read(n)
            if sha(b) != a['sha256']:
                raise ValueError('source_asset_digest_mismatch')
            assets[a['job_id'], a['semantic_role']] = (a, b)
        return batch, inventory, assets, manifest


def selected_jobs(batch: dict, selection: list[str]) -> list[dict]:
    jobs = [x for x in batch['jobs'] if x['job_id'] in selection]
    if len(jobs) != len(selection) or len(set(selection)) != len(selection):
        raise ValueError('unknown_or_duplicate_selected_job')
    for job in jobs:
        if job.get('uncertainties'):
            raise ValueError('job_uncertainties_not_resolved')
        if job['branding_selection']['presence'] != 'ABSENT':
            raise ValueError('recipient_branding_not_supported_in_pilot')
        if job['signature_selection']['variant_id'] not in ('GRIGO', 'HERASYMENKO'):
            raise ValueError('sender_variant_not_supported_in_pilot')
        if job['builder_support']['current_v1_front'] != 'STANDARD':
            raise ValueError('front_family_not_supported_in_pilot')
        for role in ('recipient_entity', 'greeting_text', 'portrait', 'recipient_branding', 'signature', 'sender_variant'):
            b = job['bindings'][role]
            if b['state'] != 'CONFIRMED' or b['human_confirmation_required'] is not False:
                raise ValueError('binding_not_confirmed:' + role)
    return jobs


def select_from_source(raw: str) -> list[str]:
    out = [x.strip() for x in raw.split(',') if x.strip()]
    if not out or len(out) != len(set(out)):
        raise ValueError('selected_jobs_required_and_unique')
    return out


def prepare(source: Path, workspace: Path, select: list[str]) -> dict:
    workspace.mkdir(parents=True, exist_ok=True)
    review_path = workspace / 'operator_review_PRIVATE.md'
    state_path = workspace / 'prepare_state.json'
    if review_path.exists() or state_path.exists():
        raise ValueError('preparation_already_exists_no_overwrite')
    batch, inventory, assets, manifest = load_archive(source)
    jobs = selected_jobs(batch, select)
    lines = ['# ForPrint — перевірка даних перед пробним PDF', '',
             '**ЦЕ ПОГОДЖЕННЯ ДАНИХ ДЛЯ ВНУТРІШНЬОГО ПЕРЕГЛЯДУ, НЕ ДОЗВІЛ НА ДРУК.**',
             '', 'Джерело: `' + source.name + '`', 'SHA256: `' + sha_file(source) + '`',
             '', 'Оригінальні фото без Creator, без змін пікселів. Відхилені Creator-result не використовуються.', '']
    for j in jobs:
        p, b = assets[j['job_id'], 'inside_image.portrait']
        lines += [f"## {j['raw_recipient_name']} / `{j['job_id']}`", '',
                  f"Фотографія: `{p['path']}` · SHA256 `{p['sha256']}` · {p['width_px']}×{p['height_px']} px", '',
                  f"Обкладинка: {j['front_display_text']['exact_text']}", '',
                  '**Текст привітання:**', '', j['greeting_text']['exact_text'], '',
                  '**Блок відправника:**', '']
        lines += [f"{x['id']}: {x['text']}" for x in j['sender_text']['lines']]
        lines += ['', f"Підпис: `{j['signature_selection']['variant_id']}`", '', '---', '']
    review = '\n'.join(lines) + '\n'
    review_path.write_text(review, encoding='utf-8')
    state = {'schema_version':'gdl_original_photo_pilot_prepare_v0_1',
             'source_archive': str(source.resolve()), 'source_sha256':sha_file(source),
             'batch_id':batch['batch_id'], 'job_ids':[j['job_id'] for j in jobs],
             'review_file_sha256': sha(review.encode('utf-8')),
             'transport_manifest_sha256':sha(json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode()),
             'status':'WAITING_FOR_OPERATOR_ACK'}
    state['ack_token'] = 'ACK-REVIEW-' + sha((state['source_sha256'] + state['review_file_sha256'] + ':'.join(state['job_ids'])).encode())[:16].upper()
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return state


def promote(source: Path, workspace: Path, *, ack: str, reviewer: str) -> Path:
    if not reviewer.strip(): raise ValueError('reviewer_required')
    state = json.loads((workspace / 'prepare_state.json').read_text(encoding='utf-8'))
    if state['source_sha256'] != sha_file(source) or state['source_archive'] != str(source.resolve()):
        raise ValueError('source_changed_since_review')
    if sha((workspace / 'operator_review_PRIVATE.md').read_bytes()) != state['review_file_sha256']:
        raise ValueError('operator_review_sheet_changed')
    if ack != state['ack_token']:
        raise ValueError('explicit_operator_ack_required')
    target = workspace / 'output' / 'gdl_intake_handoff.zip'
    if target.exists(): raise ValueError('handoff_already_exists_no_overwrite')
    batch, inventory, assets, manifest = load_archive(source)
    jobs = selected_jobs(batch, state['job_ids'])
    catalog = yaml.safe_load(CATALOG.read_text(encoding='utf-8'))
    review_id = 'gdl-operator-review-' + state['review_file_sha256'][:16]
    catalog_source_assets = [
        {'asset_id':x['source_id'], 'source_id':x['source_id'], 'sha256':x['sha256']}
        for x in inventory['sources']]
    entity_registry = {'entities': [{'entity_id':j['candidate_entity_id'], 'display_name':j['raw_recipient_name']} for j in jobs]}
    normalized_jobs = []
    visuals = {}
    payloads = {}
    artifact_entries = {}
    picture_data = {}
    for j in jobs:
        portrait = j['bindings']['portrait']
        srcid = portrait['source_id']
        p, picture = assets[j['job_id'], 'inside_image.portrait']
        if p['source_id'] != srcid or sha(picture) != portrait['sha256']:
            raise ValueError('portrait_source_identity_mismatch')
        p_sha = sha(picture)
        art_ref = 'pass-through:' + j['job_id'] + ':' + p_sha[:12]
        ext = '.png' if picture[:8] == b'\x89PNG\r\n\x1a\n' else '.jpg'
        rel = 'assets/' + j['job_id'] + ext
        artifact_entries[art_ref] = {'source_asset_id':srcid,'path':rel,'sha256':p_sha}
        picture_data[rel] = picture
        visuals[j['job_id']] = {'job_id':j['job_id'], 'target_object_id':'inside_image.portrait',
                                 'source_asset_id':srcid, 'artifact_ref':art_ref,
                                 'acceptance_basis':SOURCE_BASIS,'review_id':review_id,
                                 'result_id':'original-photo-' + p_sha[:20], 'revision':1,
                                 'provenance_sha256':p_sha}
        bindings = {
            'recipient_entity': {'state':'CONFIRMED','basis':'customer_assignment', 'human_confirmation_required':False,
                                 'entity_id':j['candidate_entity_id']},
            'greeting_text': {'state':'CONFIRMED','basis':'customer_assignment','human_confirmation_required':False,
                              'text':j['greeting_text']['exact_text'],'source_ref':j['greeting_text_source']},
            'portrait': {'state':'CONFIRMED','basis':'customer_assignment','human_confirmation_required':False,'source_id':srcid},
            'recipient_branding': {'state':'CONFIRMED','basis':'customer_assignment','human_confirmation_required':False,
                                   'presence':'ABSENT','source_id':None},
            'signature': {'state':'CONFIRMED','basis':'customer_assignment','human_confirmation_required':False,
                          'source_id':j['signature_selection']['source_id'],
                          'variant_id':j['signature_selection']['variant_id']},
            'sender_variant':{'state':'CONFIRMED','basis':'customer_assignment','human_confirmation_required':False,
                              'value':j['sender_variant']},
        }
        normalized_jobs.append({
            'job_id':j['job_id'], 'raw_recipient_name':j['raw_recipient_name'],
            'candidate_entity_id':j['candidate_entity_id'], 'occasion':j['occasion'],
            'greeting_text_source':j['greeting_text_source'], 'sender_variant':j['sender_variant'],
            'supplied_assets':sorted(set([srcid,j['signature_selection']['source_id']])),
            'special_requests':j.get('special_requests',[]), 'uncertainties':[], 'bindings':bindings,
        })
        payloads[j['job_id']] = {
            'schema_version':'gdl_greeting_card_builder_payload_v0_1','revision':'r001',
            'front':{'family':'STANDARD','occasion':{
                'kind':j['occasion'],'display_text':j['front_display_text']['exact_text']}},
            'inside_image':{'mode':'PORTRAIT','asset_id':srcid, 'asset_sha256':p_sha,
                            'accepted_artifact_ref':art_ref},
            'sender_text':{'signature_variant_id':j['signature_selection']['variant_id'],
                           'lines':j['sender_text']['lines']},
        }
    normalized = {'schema_version':'gdl_greeting_card_normalized_batch_v0_1',
                  'batch_id':batch['batch_id'],
                  'request_id':'review-only-' + batch['batch_id'],
                  'product_playbook_id':'recurring_greeting_card_v0_1',
                  'product_type':'greeting_card', 'jobs':normalized_jobs}
    bundle = build_accepted_constructor_bundle(
        normalized, source_inventory={'assets':catalog_source_assets}, entity_registry=entity_registry,
        accepted_visuals_by_job=visuals, signature_catalog=catalog,
        intake_review={'state':'PASS','review_id':review_id,'reviewer_source':'OPERATOR:' + reviewer,
                       'basis':'OPERATOR_REVIEWED_NORMALIZED_BATCH','source_batch_id':batch['batch_id']},
        bundle_id='review-only-' + batch['batch_id'] + '-' + state['review_file_sha256'][:8],
    )
    bundle = attach_builder_payload_v1(bundle, payload_by_job=payloads, signature_catalog=catalog)
    bundle_raw = yaml.safe_dump(bundle, allow_unicode=True, sort_keys=False).encode('utf-8')
    arts_raw = yaml.safe_dump({'schema_version':'gdl_greeting_card_builder_artifact_manifest_v0_1',
                               'artifacts':artifact_entries}, allow_unicode=True,sort_keys=False).encode('utf-8')
    manifest_raw = json.dumps({'schema_version':'gdl_intake_builder_handoff_v0_1','mode':'REVIEW_ONLY',
                               'accepted_bundle_file_sha256':sha(bundle_raw),
                               'artifact_manifest_file_sha256':sha(arts_raw)},indent=2).encode('utf-8')
    evidence = json.dumps({'schema_version':'gdl_original_photo_operator_ack_v0_1',
                            'approved_for':'REVIEW_ONLY_NOT_PRODUCTION',
                            'source_zip_sha256':state['source_sha256'],
                            'operator_review_sheet_sha256':state['review_file_sha256'],
                            'ack_token':ack, 'review_id':review_id,
                            'reviewer_source': 'OPERATOR:' + reviewer,
                            'job_ids':state['job_ids'], 'image_transform_performed':False,
                            'original_failed_creator_result_used':False},
                          ensure_ascii=False,indent=2).encode('utf-8')
    staging = workspace / 'validation_PRIVATE' / 'gdl_intake_handoff.zip'
    staging.parent.mkdir(exist_ok=True)
    if staging.exists(): raise ValueError('staged_handoff_already_exists')
    with zipfile.ZipFile(staging,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for n,b in sorted({**picture_data, 'accepted_constructor_bundle.yaml':bundle_raw,
                           'artifact_manifest.yaml':arts_raw,
                           'handoff_manifest.json':manifest_raw,
                           'intake_evidence/operator_review.json':evidence}.items()):
            z.writestr(n,b)
    # The project-owned final Intake gate validates exact source bytes and bundle.
    inspect_zip(staging)
    target.parent.mkdir(exist_ok=True)
    if target.exists(): raise ValueError('handoff_already_exists_no_overwrite')
    staging.rename(target)
    return target


def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode',required=True,choices=('prepare','approve'))
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--workspace',type=Path,required=True)
    ap.add_argument('--jobs',default='')
    ap.add_argument('--ack-token',default='')
    ap.add_argument('--reviewer',default='')
    args=ap.parse_args()
    try:
        if args.mode == 'prepare':
            state=prepare(args.source,args.workspace,select_from_source(args.jobs))
            print('GDL_ORIGINAL_PHOTO_PREPARE=PASS')
            print('REVIEW_SHEET=' + str(args.workspace/'operator_review_PRIVATE.md'))
            print('REVIEW_SHEET_SHA256=' + state['review_file_sha256'])
            print('ACK_TOKEN=' + state['ack_token'])
            print('NEXT=REVIEW_SHEET_THEN_EXPLICIT_OPERATOR_ACK')
        else:
            target=promote(args.source,args.workspace,ack=args.ack_token,reviewer=args.reviewer)
            print('GDL_ORIGINAL_PHOTO_HANDOFF=PASS')
            print('OUTPUT=' + str(target))
            print('SHA256=' + sha_file(target))
            print('PRODUCTION_APPROVED=false')
        return 0
    except Exception as exc:
        print('GDL_ORIGINAL_PHOTO_PILOT=BLOCKED')
        print('ERROR_CODE=' + str(exc).split(':')[0])
        return 2

if __name__ == '__main__':
    raise SystemExit(main())

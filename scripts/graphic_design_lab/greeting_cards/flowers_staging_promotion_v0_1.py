#!/usr/bin/env python3
"""GC15-B: exact Intake flowers staging -> human review -> one canonical Handoff.

No Creator; no automatic review/print/customer approval. Original staging bytes
are immutable. A separate real operator ACK bound to review and source is required.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sys
from typing import Any
from zipfile import ZipFile, ZIP_DEFLATED

import yaml

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.graphic_design_lab.greeting_card_constructor_bundle import build_accepted_constructor_bundle
from app.graphic_design_lab.greeting_card_builder_input import attach_builder_payload_v1
from app.graphic_design_lab.greeting_card_private_resources import (
    RESOURCE_DEFAULT_FLOWERS, EXPECTED_RESOURCES,
)
from app.graphic_design_lab.greeting_card_builder_renderer import (
    SUPPORTED_FRONT_FAMILIES, SUPPORTED_IMAGE_MODES,
)
from scripts.graphic_design_lab.greeting_cards.intake_handoff_runner_v0_1 import inspect_zip

SCHEMA = 'gdl_gc15_flowers_staging_promotion_v0_1'
CATALOG = ROOT / 'coordination/graphic_design_lab/directions/greeting_cards/signature_variant_catalog_v0_1.yaml'
CANONICAL_SENDER_REGISTRY = ROOT / 'coordination/graphic_design_lab/directions/greeting_cards/canonical_sender_blocks_v0_1.yaml'
REVIEW_FORMAT_VERSION = 'GC15B_CANONICAL_SENDER_DUAL_VIEW_V0_2'
FLOWERS_ID = 'flowers.default.v1'
FLOWERS_SHA = EXPECTED_RESOURCES[RESOURCE_DEFAULT_FLOWERS]['sha256']
MANDATORY = frozenset({
    'packet_manifest.json', 'SERVER_INGEST_STAGING.yaml', 'BLOCKERS.yaml',
    'normalized_batch.yaml', 'source_inventory.yaml', 'texts/exact_greetings.json',
    'visual_routing.yaml', 'assets/flowers.default.v1.png',
})
SAFE_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,100}$')
HEX = re.compile(r'^[a-f0-9]{64}$')
MAX_ARCHIVE = 250 * 1024 * 1024
MAX_UNPACKED = 500 * 1024 * 1024


class Blocked(ValueError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fp:
        for block in iter(lambda: fp.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()



def _verify_reusable_staged_handoff(staged: Path, pkg_files: dict[str, bytes]) -> None:
    """GC15-B recovery: rebind an interrupted, immutable ZIP to THIS approval.

    All bytes except the archival promotion timestamp must exactly match the
    newly derived accepted bundle, logo and review evidence. Never trust a
    merely well-formed ZIP or a matching filename as authorization to reuse.
    """
    if staged.is_symlink() or not staged.is_file():
        raise Blocked('staged_handoff_missing_or_unsafe')
    with ZipFile(staged) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != set(pkg_files):
            raise Blocked('staged_handoff_inventory_mismatch')
        for name, expected in pkg_files.items():
            actual = archive.read(name)
            if name == 'intake_evidence/operator_review.json':
                current_evidence = json.loads(actual)
                expected_evidence = json.loads(expected)
                timestamp = current_evidence.pop('promoted_at', None)
                expected_evidence.pop('promoted_at', None)
                if (not isinstance(timestamp, str) or not timestamp
                        or current_evidence != expected_evidence):
                    raise Blocked('staged_handoff_ack_evidence_mismatch')
            elif actual != expected:
                raise Blocked('staged_handoff_source_binding_mismatch')


def _publish_staged_handoff(staged: Path, target: Path) -> Path:
    """Cross-filesystem publish: copy -> SHA check -> no-clobber atomic link.

    The temporary name ends with .part (never a GC14 .zip candidate).
    The last operation is an atomic no-overwrite hard-link in the SMB input
    filesystem; no rename() is attempted across the tmp / SMB boundary.
    """
    if staged.is_symlink() or not staged.is_file():
        raise Blocked('staged_handoff_missing_or_unsafe')
    if not target.parent.is_dir() or target.parent.is_symlink():
        raise Blocked('handoff_input_folder_missing_or_unsafe')
    if target.exists() or target.is_symlink():
        raise Blocked('input_final_handoff_already_exists_no_overwrite')
    digest = sha_file(staged)
    scratch_name = '.' + target.name + '.' + secrets.token_hex(12) + '.part'
    temporary = target.parent / scratch_name
    created = False
    try:
        with staged.open('rb') as src, temporary.open('xb') as dst:
            created = True
            shutil.copyfileobj(src, dst, 1024 * 1024)
            dst.flush()
            os.fsync(dst.fileno())
        if sha_file(temporary) != digest or sha_file(staged) != digest:
            raise Blocked('handoff_copy_sha256_mismatch')
        try:
            # Atomic and no-clobber: target and temporary share one filesystem.
            os.link(temporary, target)
        except FileExistsError as exc:
            raise Blocked('input_final_handoff_already_exists_no_overwrite') from exc
        except OSError as exc:
            raise Blocked('handoff_atomic_link_not_supported') from exc
        if sha_file(target) != digest:
            raise Blocked('published_handoff_sha256_mismatch')
        return target
    finally:
        if created and (temporary.exists() or temporary.is_symlink()):
            temporary.unlink()

def load_staging(source: Path) -> dict[str, Any]:
    if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_ARCHIVE:
        raise Blocked('source_not_regular_or_too_large')
    with ZipFile(source) as z:
        infos = z.infolist()
        names = [i.filename for i in infos]
        if len(infos) > 300 or len(names) != len({n.casefold() for n in names}):
            raise Blocked('zip_duplicate_or_too_many_members')
        if not MANDATORY <= set(names):
            raise Blocked('staging_required_members_missing')
        if sum(i.file_size for i in infos) > MAX_UNPACKED:
            raise Blocked('zip_expansion_too_large')
        for item in infos:
            name = item.filename
            mode = (item.external_attr >> 16) & 0o170000
            if (not name or name.startswith('/') or '\\' in name or '\x00' in name
                    or ':' in name.split('/')[0] or any(p in ('', '.', '..') for p in name.split('/'))
                    or item.is_dir() or mode not in (0, 0o100000)):
                raise Blocked('zip_unsafe_member')
        manifest = json.loads(z.read('packet_manifest.json'))
        entries = manifest.get('entries')
        if (manifest.get('schema_version') != 'gdl_intake_staging_packet_manifest_v0_1'
                or not isinstance(entries, list) or len(entries) != len(names) - 1
                or {e.get('path') for e in entries} != set(names) - {'packet_manifest.json'}):
            raise Blocked('staging_manifest_invalid')
        for item in entries:
            name = item['path']
            if (not isinstance(item.get('sha256'), str) or not HEX.fullmatch(item['sha256'])
                    or item['bytes'] != z.getinfo(name).file_size
                    or sha(z.read(name)) != item['sha256']):
                raise Blocked('staging_file_digest_mismatch')
        route = yaml.safe_load(z.read('SERVER_INGEST_STAGING.yaml'))
        blockers = yaml.safe_load(z.read('BLOCKERS.yaml'))
        selection = yaml.safe_load(z.read('visual_routing.yaml'))
        inventory = yaml.safe_load(z.read('source_inventory.yaml'))
        batch = yaml.safe_load(z.read('normalized_batch.yaml'))
        texts = json.loads(z.read('texts/exact_greetings.json'))
        if (route.get('packet_kind') != 'STRUCTURED_INTAKE_STAGING_NOT_ACCEPTED_BUNDLE'
                or blockers.get('final_handoff_allowed') is not False
                or route['batch_id'] != batch['batch_id']
                or selection['batch_id'] != batch['batch_id']
                or inventory['batch_id'] != batch['batch_id']
                or texts['batch_id'] != batch['batch_id']
                or blockers['batch_id'] != batch['batch_id']):
            raise Blocked('staging_authority_or_batch_inconsistent')
        flowers = z.read('assets/flowers.default.v1.png')
        if (sha(flowers) != FLOWERS_SHA
                or selection['image_source']['sha256'] != FLOWERS_SHA
                or selection['image_source']['asset_id'] != FLOWERS_ID
                or selection['image_source']['path'] != 'assets/flowers.default.v1.png'
                or selection['target_builder_mode'] != 'DEFAULT_ASSET'
                or selection.get('creator_dispatch_required') is not False
                or selection.get('creator_jobs') != []
                or selection.get('apply_to_all_jobs') is not True):
            raise Blocked('default_flowers_source_or_selection_invalid')
        jobs = batch.get('jobs')
        if not isinstance(jobs, list) or len(jobs) != 4:
            raise Blocked('staging_job_set_unexpected')
        job_ids = [j.get('job_id') for j in jobs]
        if (len(set(job_ids)) != 4 or any(not isinstance(s, str) or not SAFE_ID.fullmatch(s) for s in job_ids)
                or set(job_ids) != set(route['asset_selection_rule']['all_job_ids'])
                or set(job_ids) != set(selection['apply_to_jobs'])
                or set(job_ids) != {j['job_id'] for j in texts['jobs']}):
            raise Blocked('staging_job_ids_inconsistent')
        if (route['asset_selection_rule']['sha256'] != FLOWERS_SHA
                or route['asset_selection_rule']['inside_image_mode'] != 'DEFAULT_ASSET'):
            raise Blocked('routing_asset_not_canonical')
        entry_by_id = {a['job_id']: a for a in texts['jobs']}
        logo_bytes = {}
        for job in jobs:
            item = entry_by_id[job['job_id']]
            greeting = job['greeting_text']['exact_text']
            if (item['greeting_text_exact'] != greeting
                    or sha(greeting.encode('utf-8')) != item['greeting_text_sha256']
                    or item['greeting_text_sha256'] != job['greeting_text']['exact_text_sha256']
                    or item['greeting_source_id'] != job['greeting_text_source']
                    or item['signature_variant_id'] != job['signature_selection']['variant_id']
                    or item['sender_variant'] != job['sender_variant']
                    or item['sender_lines'] != job['sender_text']['lines']
                    or job['sender_text']['lines'] != job['builder_v1']['sender_text']['lines']
                    or job['builder_v1']['inside_image']['mode'] != 'DEFAULT_ASSET'
                    or job['builder_v1']['inside_image']['asset_sha256'] != FLOWERS_SHA
                    or job['builder_v1']['inside_image']['asset_id'] != FLOWERS_ID):
                raise Blocked('staging_job_exact_content_mismatch')
            for role in ('recipient_entity', 'greeting_text', 'portrait', 'recipient_branding', 'signature', 'sender_variant'):
                b = job['bindings'][role]
                if b.get('state') != 'CONFIRMED' or b.get('human_confirmation_required') is not False:
                    raise Blocked('staging_binding_requires_clarification')
            if (job['bindings']['portrait'].get('sha256') != FLOWERS_SHA
                    or job['bindings']['portrait'].get('source_asset_id') != FLOWERS_ID):
                raise Blocked('portrait_selection_not_default_flowers')
            front = job['front_display_text']
            if (not isinstance(front.get('exact_text'), str) or not front['exact_text']
                    or job['builder_v1']['front']['occasion']['display_text'] != front['exact_text']):
                raise Blocked('front_title_candidate_inconsistent')
            if job['signature_selection']['variant_id'] not in ('GRIGO', 'HERASYMENKO'):
                raise Blocked('unsupported_signature')
            presence = job['branding_selection']['presence']
            family = 'RECIPIENT_BRANDING_OVERLAY' if presence == 'PRESENT' else 'STANDARD'
            if (presence not in ('PRESENT', 'ABSENT')
                    or job['builder_v1']['front']['family'] != family):
                raise Blocked('branding_family_mismatch')
            if presence == 'PRESENT':
                b = job['bindings']['recipient_branding']
                meta = [a for a in inventory['asset_registry'] if a.get('semantic_role') == 'front.recipient_branding'
                        and a.get('job_id') == job['job_id']]
                if (len(meta) != 1 or b.get('source_id') != meta[0]['source_id']
                        or b.get('asset_id') != meta[0]['asset_id']
                        or job['branding_selection']['asset_id'] != meta[0]['asset_id']
                        or meta[0].get('mime_type') != 'image/png'):
                    raise Blocked('recipient_branding_source_mismatch')
                logo_data = z.read(meta[0]['path'])
                if sha(logo_data) != meta[0]['sha256'] or not logo_data.startswith(b'\x89PNG\r\n\x1a\n'):
                    raise Blocked('recipient_logo_invalid')
                logo_bytes[job['job_id']] = (meta[0], logo_data)
            elif job['bindings']['recipient_branding'].get('presence') != 'ABSENT':
                raise Blocked('unexpected_branding_binding')
        return {'batch': batch, 'inventory': inventory, 'text_map': texts,
                'source_sha256': sha_file(source), 'logo_bytes': logo_bytes,
                'job_ids': job_ids, 'flowers_sha256': FLOWERS_SHA}


def workspace_for_source(source: Path) -> Path:
    # Exact location only: _forprint_automation/input/<archive>.zip.
    if source.is_symlink() or source.suffix.lower() != '.zip':
        raise Blocked('source_must_be_input_zip')
    path = source.absolute()
    if (path.parent.name != 'input' or path.parent.parent.name != '_forprint_automation'
            or path.parent.is_symlink() or path.parent.parent.is_symlink()):
        raise Blocked('source_outside_expected_workspace_input')
    workspace = path.parent.parent
    if not (workspace / 'output').is_dir():
        raise Blocked('workspace_output_missing')
    return workspace


def canonical_sender_data() -> tuple[dict[str, list[str]], str]:
    """Actual rendered text from the source-verified project-owned sender registry.

    Never interpret Intake sender slots as PDF rendering authority.
    """
    source = CANONICAL_SENDER_REGISTRY
    if source.is_symlink() or not source.is_file():
        raise Blocked('canonical_sender_registry_missing_or_unsafe')
    registry = yaml.safe_load(source.read_text(encoding='utf-8'))
    if (not isinstance(registry, dict)
            or registry.get('schema_version') != 'gdl_greeting_card_canonical_sender_blocks_v0_1'
            or registry.get('dual_runtime_enabled') is not False):
        raise Blocked('canonical_sender_registry_contract_invalid')
    variants = registry.get('variants')
    if not isinstance(variants, dict):
        raise Blocked('canonical_sender_variants_invalid')
    result: dict[str, list[str]] = {}
    for variant in ('GRIGO', 'HERASYMENKO'):
        row = variants.get(variant)
        if (not isinstance(row, dict) or not isinstance(row.get('texts'), list)
                or not row['texts'] or not all(isinstance(s, str) and s.strip() for s in row['texts'])):
            raise Blocked('canonical_sender_variant_missing_or_invalid')
        result[variant] = list(row['texts'])
    return result, sha_file(source)


def review_paths(source: Path, source_sha: str) -> tuple[Path, Path]:
    workspace = workspace_for_source(source)
    folder = workspace / 'intake' / 'reviews' / ('flowers_' + source_sha[:16] + '_r002')
    return folder / 'operator_review_PRIVATE.md', folder / 'prepare_state.json'


def review_text(source: Path, data: dict[str, Any]) -> str:
    canonical, canonical_sha = canonical_sender_data()
    rows = [
        '# ForPrint GC15-B — погодження чотирьох листівок із квітами', '',
        '**Це виключно операторський review для внутрішнього PDF, не дозвіл на друк.**', '',
        f'Вхідний ZIP: `{source.name}`', f'SHA256 ZIP: `{data["source_sha256"]}`',
        f'Batch ID: `{data["batch"]["batch_id"]}`', '',
        'Квіти `flowers.default.v1` для всіх 4: SHA256 `' + FLOWERS_SHA + '`.',
        '**ВАЖЛИВО:** Builder відображає канонічний блок підписанта зі свого перевіреного реєстру,',
        '**а не рядки sender_text.lines, отримані з Intake.** Обидва блоки показані нижче.',
        f'Канонічний реєстр підписантів SHA256: `{canonical_sha}`.',
        'Creator не запускаємо. Початкові портрети тільки транзитні.',
        'Дати з імен DOCX не використовуються як підтверджені дати.', '',
    ]
    for j in data['batch']['jobs']:
        title = j['front_display_text']['exact_text']
        rows += [
            f'## {j["raw_recipient_name"]} — `{j["job_id"]}`', '',
            '**Заголовок обкладинки (ПОТРЕБУЄ ПІДТВЕРДЖЕННЯ):**', title, '',
            '**Дослівний текст привітання:**', '', j['greeting_text']['exact_text'], '',
            '**Відправник за Intake (дослівне джерело; НЕ фактичні рядки PDF):**', '',
        ]
        intake_lines = [str(line['text']) for line in j['sender_text']['lines']]
        rows += [f'- `{line["id"]}`: {line["text"]}' for line in j['sender_text']['lines']]
        rendered_lines = canonical[j['signature_selection']['variant_id']]
        rows += ['', '**ФАКТИЧНИЙ БЛОК ПІДПИСАНТА В PDF — КАНОНІЧНИЙ (потребує погодження):**', '']
        rows += [f'{i}. {line}' for i, line in enumerate(rendered_lines, start=1)]
        if intake_lines != rendered_lines:
            rows += ['', '**НЕВІДПОВІДНІСТЬ:** рядки Intake та канонічного PDF відрізняються.',
                     'ACK означає погодження саме наведеного КАНОНІЧНОГО блока для внутрішнього PDF;',
                     'за незгоди — зупинити процес і погодити окрему зміну з оператором.', '']
        logo = data['logo_bytes'].get(j['job_id'])
        rows += ['', f'Підпис: `{j["signature_selection"]["variant_id"]}`',
                 'Зображення: `DEFAULT_ASSET flowers.default.v1`',
                 ('Логотип отримувача: ОБОВ’ЯЗКОВИЙ — `' + logo[0]['path'] + '` · SHA256 `' + logo[0]['sha256'] + '`')
                 if logo else 'Логотип отримувача: відсутній (STANDARD)', '', '---', '']
    rows += ['**Перед ACK звірити кожен текст, звернення, заголовок, підпис і наявність логотипа.**',
             'При будь-якій незгоді зупинити процес і повернути на Intake.', '']
    return '\n'.join(rows)


def prepare(source: Path) -> dict[str, Any]:
    data = load_staging(source)
    if 'DEFAULT_ASSET' not in SUPPORTED_IMAGE_MODES or 'RECIPIENT_BRANDING_OVERLAY' not in SUPPORTED_FRONT_FAMILIES:
        raise Blocked('installed_builder_capability_missing')
    review, state = review_paths(source, data['source_sha256'])
    if review.exists() or state.exists():
        raise Blocked('review_previously_prepared_no_overwrite')
    folder = review.parent
    folder.mkdir(parents=True, exist_ok=True)
    content = review_text(source, data)
    _, canonical_sha = canonical_sender_data()
    content_sha = sha(content.encode('utf-8'))
    token = 'ACK-FLOWERS-' + sha((data['source_sha256'] + content_sha + ':'.join(data['job_ids'])).encode())[:20].upper()
    record = {
        'schema_version': SCHEMA, 'source_sha256': data['source_sha256'],
        'source_archive': source.name, 'batch_id': data['batch']['batch_id'],
        'job_ids': data['job_ids'], 'review_file_sha256': content_sha,
        'review_format_version': REVIEW_FORMAT_VERSION,
        'canonical_sender_registry_sha256': canonical_sha,
        'ack_token': token, 'status': 'AWAITING_REAL_OPERATOR_REVIEW',
        'production_approved': False, 'customer_approved': False,
    }
    with review.open('x', encoding='utf-8') as f:
        f.write(content)
    with state.open('x', encoding='utf-8') as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
        f.write('\n')
    return {'review': review, 'state': state, **record}


def promote(source: Path, *, ack_token: str, reviewer: str) -> Path:
    if not reviewer or not reviewer.strip() or len(reviewer) > 128:
        raise Blocked('explicit_reviewer_required')
    data = load_staging(source)
    review, state_path = review_paths(source, data['source_sha256'])
    state = json.loads(state_path.read_text(encoding='utf-8'))
    if (state.get('schema_version') != SCHEMA
            or state.get('source_archive') != source.name
            or state.get('source_sha256') != data['source_sha256']
            or state.get('batch_id') != data['batch']['batch_id']
            or state.get('job_ids') != data['job_ids']
            or state.get('status') != 'AWAITING_REAL_OPERATOR_REVIEW'
            or state.get('review_format_version') != REVIEW_FORMAT_VERSION
            or state.get('canonical_sender_registry_sha256') != canonical_sender_data()[1]
            or sha_file(review) != state.get('review_file_sha256')
            or sha(review_text(source, data).encode('utf-8')) != state.get('review_file_sha256')
            or not ack_token or ack_token != state.get('ack_token')):
        raise Blocked('review_ack_or_source_identity_invalid')
    catalog = yaml.safe_load(CATALOG.read_text(encoding='utf-8'))
    review_id = 'gc15-flowers-operator-' + state['review_file_sha256'][:16]
    batch = data['batch']; inventory = data['inventory']; logo_bytes = data['logo_bytes']
    source_assets = [{'asset_id': s['source_id'], 'source_id': s['source_id'], 'sha256': s['sha256']}
                     for s in inventory['sources']]
    # Canonical default logical ID is an explicitly verified alias of Intake src_014.
    source_assets.append({'asset_id': FLOWERS_ID, 'source_id': FLOWERS_ID, 'sha256': FLOWERS_SHA})
    normalized_jobs, visuals, payloads, archive_assets, entries = [], {}, {}, {}, {}
    for j in batch['jobs']:
        job_id = j['job_id']
        logo_item = logo_bytes.get(job_id)
        logo_binding = None
        if logo_item:
            meta, content = logo_item
            source_id, digest = meta['source_id'], sha(content)
            ref = 'recipient-logo:' + job_id + ':' + digest[:12]
            rel = 'assets/' + job_id + '__recipient_logo.png'
            entries[ref] = {'source_asset_id': source_id, 'path': rel, 'sha256': digest}
            archive_assets[rel] = content
            logo_binding = {'asset_id': source_id, 'asset_sha256': digest, 'accepted_artifact_ref': ref}
        visuals[job_id] = {
            'job_id': job_id, 'target_object_id': 'inside_image.portrait',
            'source_asset_id': FLOWERS_ID,
            # Logical review identity, not a transported artifact: DEFAULT_ASSET skips manifest binding.
            'artifact_ref': 'default-reviewed:' + job_id + ':' + FLOWERS_SHA[:12],
            'acceptance_basis': 'SOURCE_ASSET_OPERATOR_REVIEW_PASS',
            'review_id': review_id, 'result_id': 'flowers-source-' + FLOWERS_SHA[:20],
            'revision': 1, 'provenance_sha256': FLOWERS_SHA,
        }
        old = j['bindings']
        bindings = {
            'recipient_entity': {'state': 'CONFIRMED', 'basis': 'customer_assignment',
                                 'human_confirmation_required': False, 'entity_id': j['candidate_entity_id']},
            'greeting_text': {'state': 'CONFIRMED', 'basis': 'customer_assignment',
                              'human_confirmation_required': False,
                              'text': j['greeting_text']['exact_text'], 'source_ref': j['greeting_text_source']},
            'portrait': {'state': 'CONFIRMED', 'basis': 'operator_assignment',
                         'human_confirmation_required': False, 'source_id': FLOWERS_ID},
            'recipient_branding': {'state': 'CONFIRMED',
                                   'basis': 'customer_assignment' if logo_binding else 'operator_assignment',
                                   'human_confirmation_required': False,
                                   'presence': 'PRESENT' if logo_binding else 'ABSENT',
                                   'source_id': logo_binding['asset_id'] if logo_binding else None},
            'signature': {'state': 'CONFIRMED', 'basis': 'customer_assignment',
                          'human_confirmation_required': False,
                          'source_id': old['signature']['source_id'],
                          'variant_id': j['signature_selection']['variant_id']},
            'sender_variant': {'state': 'CONFIRMED', 'basis': 'customer_assignment',
                               'human_confirmation_required': False, 'value': j['sender_variant']},
        }
        supplied = [FLOWERS_ID, old['signature']['source_id']]
        if logo_binding:
            supplied.append(logo_binding['asset_id'])
        normalized_jobs.append({
            'job_id': job_id, 'raw_recipient_name': j['raw_recipient_name'],
            'candidate_entity_id': j['candidate_entity_id'], 'occasion': j['occasion'],
            'greeting_text_source': j['greeting_text_source'], 'sender_variant': j['sender_variant'],
            'supplied_assets': sorted(set(supplied)),
            'special_requests': deepcopy(j.get('special_requests', [])), 'uncertainties': [],
            'bindings': bindings,
        })
        front = {'family': 'RECIPIENT_BRANDING_OVERLAY' if logo_binding else 'STANDARD',
                 'occasion': {'kind': j['occasion'], 'display_text': j['front_display_text']['exact_text']}}
        if logo_binding:
            front['recipient_branding'] = logo_binding
        payloads[job_id] = {
            'schema_version': 'gdl_greeting_card_builder_payload_v0_1', 'revision': 'r001',
            'front': front, 'inside_image': {'mode': 'DEFAULT_ASSET',
                        'asset_id': FLOWERS_ID, 'asset_sha256': FLOWERS_SHA, 'accepted_artifact_ref': None},
            'sender_text': {'signature_variant_id': j['signature_selection']['variant_id'],
                            'lines': deepcopy(j['sender_text']['lines'])},
        }
    normalized = {
        'schema_version': 'gdl_greeting_card_normalized_batch_v0_1',
        'batch_id': batch['batch_id'], 'request_id': 'gc15-flowers-' + batch['batch_id'],
        'product_playbook_id': 'recurring_greeting_card_v0_1',
        'product_type': 'greeting_card', 'jobs': normalized_jobs,
    }
    bundle = build_accepted_constructor_bundle(
        normalized, source_inventory={'assets': source_assets},
        entity_registry={'entities': [{'entity_id': j['candidate_entity_id'], 'display_name': j['raw_recipient_name']}
                                      for j in batch['jobs']]},
        accepted_visuals_by_job=visuals, signature_catalog=catalog,
        intake_review={'state': 'PASS', 'review_id': review_id,
                       'reviewer_source': 'OPERATOR:' + reviewer.strip(),
                       'basis': 'OPERATOR_REVIEWED_NORMALIZED_BATCH',
                       'source_batch_id': batch['batch_id']},
        bundle_id='gc15-flowers-' + batch['batch_id'] + '-' + state['review_file_sha256'][:8],
    )
    bundle = attach_builder_payload_v1(bundle, payload_by_job=payloads, signature_catalog=catalog)
    bundle_raw = yaml.safe_dump(bundle, allow_unicode=True, sort_keys=False).encode('utf-8')
    art_raw = yaml.safe_dump({'schema_version': 'gdl_greeting_card_builder_artifact_manifest_v0_1',
                              'artifacts': entries}, allow_unicode=True, sort_keys=False).encode('utf-8')
    header_raw = json.dumps({'schema_version': 'gdl_intake_builder_handoff_v0_1', 'mode': 'REVIEW_ONLY',
                             'accepted_bundle_file_sha256': sha(bundle_raw),
                             'artifact_manifest_file_sha256': sha(art_raw)}, indent=2).encode('utf-8')
    evidence_raw = json.dumps({
        'schema_version': 'gdl_gc15_flowers_operator_ack_v0_1',
        'source_staging_sha256': data['source_sha256'],
        'source_batch_id': batch['batch_id'],
        'operator_review_sha256': state['review_file_sha256'],
        'review_format_version': REVIEW_FORMAT_VERSION,
        'canonical_sender_registry_sha256': state['canonical_sender_registry_sha256'],
        'ack_token': ack_token, 'reviewer_source': 'OPERATOR:' + reviewer.strip(),
        'review_id': review_id, 'job_ids': data['job_ids'],
        'flowers_sha256': FLOWERS_SHA, 'creator_dispatched': False,
        'original_portraits_used': False, 'customer_approved': False,
        'production_approved': False,
        'promoted_at': datetime.now(timezone.utc).isoformat(),
    }, ensure_ascii=False, indent=2).encode('utf-8')
    pkg_files = {**archive_assets,
                 'accepted_constructor_bundle.yaml': bundle_raw,
                 'artifact_manifest.yaml': art_raw,
                 'handoff_manifest.json': header_raw,
                 'intake_evidence/operator_review.json': evidence_raw}
    scratch = ROOT / 'tmp/gdl_gc15_flowers_staging_promotion_v0_1' / data['source_sha256'][:16]
    scratch.mkdir(parents=True, exist_ok=True)
    staged = scratch / 'gdl_intake_handoff.zip'
    target = workspace_for_source(source) / 'input' / ('gdl_flowers_reviewed_' + data['source_sha256'][:16] + '.zip')
    if target.exists() or target.is_symlink():
        raise Blocked('input_final_handoff_already_exists_no_overwrite')
    if staged.exists() or staged.is_symlink():
        _verify_reusable_staged_handoff(staged, pkg_files)
    else:
        with ZipFile(staged, 'x', compression=ZIP_DEFLATED) as z:
            for name, contents in sorted(pkg_files.items()):
                z.writestr(name, contents)
    inspected = inspect_zip(staged)
    if inspected['jobs'] != len(data['job_ids']) or inspected['archive_sha256'] != sha_file(staged):
        raise Blocked('final_handoff_preflight_failed')
    if sha_file(source) != data['source_sha256'] or sha_file(review) != state['review_file_sha256']:
        raise Blocked('source_or_review_changed_during_promotion')
    # GC14 accepts the noncanonical published basename and stages its own exact
    # gdl_intake_handoff.zip copy. Preserve validated staging for recovery.
    return _publish_staged_handoff(staged, target)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', required=True, choices=('prepare', 'promote'))
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--ack-token', default='')
    p.add_argument('--reviewer', default='')
    args = p.parse_args()
    try:
        source = args.source.absolute()
        workspace_for_source(source)
        if args.mode == 'prepare':
            result = prepare(source)
            print('GDL_GC15_FLOWERS_PREPARE=PASS')
            print('REVIEW_FILE=' + str(result['review']))
            print('SOURCE_SHA256=' + result['source_sha256'])
            print('ACK_TOKEN=' + result['ack_token'])
            print('NEXT=REVIEW_FOUR_JOBS_THEN_EXPLICIT_OPERATOR_ACK')
        else:
            target = promote(source, ack_token=args.ack_token, reviewer=args.reviewer)
            print('GDL_GC15_FLOWERS_PROMOTE=PASS')
            print('OUTPUT=' + str(target))
            print('HANDOFF_SHA256=' + sha_file(target))
            print('READY_FOR_GC14_QUEUE=true')
            print('PRODUCTION_APPROVED=false')
        return 0
    except Exception as exc:
        code = str(exc).split(':', 1)[0] if isinstance(exc, Blocked) else type(exc).__name__
        print('GDL_GC15_FLOWERS_PROMOTION=BLOCKED')
        print('ERROR_CODE=' + (code if re.fullmatch(r'[A-Za-z0-9_]+', code) else 'UNEXPECTED_ERROR'))
        print('PRODUCTION_APPROVED=false')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

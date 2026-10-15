"""Sanitized GC15-B staging intake -> explicit ACK tests (no customer data)."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import zipfile

import pytest
import yaml
from PIL import Image

from scripts.graphic_design_lab.greeting_cards import flowers_staging_promotion_v0_1 as p


def digest(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@pytest.fixture
def mock_source(tmp_path, monkeypatch):
    root = tmp_path / '_forprint_automation'
    (root / 'input').mkdir(parents=True)
    (root / 'output').mkdir()
    source = root / 'input' / 'intake_staging.zip'
    buf = io.BytesIO()
    Image.new('RGBA', (32, 32), (180, 30, 40, 255)).save(buf, 'PNG')
    flowers = buf.getvalue()
    flower_sha = digest(flowers)
    monkeypatch.setattr(p, 'FLOWERS_SHA', flower_sha)
    # Synthetic canonical sender registry: avoid embedding real sender identities in tests.
    registry_path = tmp_path / 'canonical_sender_registry.yaml'
    registry_path.write_text(yaml.safe_dump({
        'schema_version': 'gdl_greeting_card_canonical_sender_blocks_v0_1',
        'dual_runtime_enabled': False,
        'variants': {
            'GRIGO': {'texts': ['З повагою', 'Умовний відправник А']},
            'HERASYMENKO': {'texts': ['З найкращими побажаннями', 'Умовний відправник Б']},
        },
    }, allow_unicode=True), encoding='utf-8')
    monkeypatch.setattr(p, 'CANONICAL_SENDER_REGISTRY', registry_path)
    texts = []; jobs = []
    asset_registry = [{'asset_id':'flowers.default.v1','source_id':'src_014',
                       'path':'assets/flowers.default.v1.png','sha256':flower_sha,
                       'semantic_role':'inside_image.DEFAULT_ASSET', 'job_id':None}]
    sources = [{'source_id':'src_014','sha256':flower_sha}]
    assets = {'assets/flowers.default.v1.png':flowers}
    for i in range(4):
        job_id = f'synthetic_{i}'
        text = f'Вітаємо зі святом. Тестова листівка {i}!'
        branding = i == 3
        signature = 'GRIGO' if i < 2 else 'HERASYMENKO'
        selected = {'presence':'PRESENT' if branding else 'ABSENT',
                    'asset_id':'synthetic-logo-1' if branding else None}
        role = {'state':'CONFIRMED', 'human_confirmation_required':False}
        portrait = {**role, 'sha256':flower_sha,'source_asset_id':'flowers.default.v1'}
        sent = [{'id':'closing_phrase','text':'З повагою'},
                {'id':'sender_name','text':'Синтетичний відправник'},
                {'id':'sender_role_1','text':'Тестова посада'}]
        bindings = {'recipient_entity':dict(role), 'greeting_text':dict(role), 'portrait':portrait,
                    'recipient_branding':{**role,'presence':selected['presence'],'source_id': 'logo-source' if branding else None,
                                          'asset_id':selected['asset_id']},
                    'signature':{**role,'source_id':f'src_{i+1:03}'},'sender_variant':dict(role)}
        if branding:
            b = io.BytesIO()
            Image.new('RGBA',(64,64),(100,90,80,255)).save(b,'PNG')
            logo = b.getvalue()
            assets['source/logo.png'] = logo
            asset_registry.append({'asset_id':'synthetic-logo-1','source_id':'logo-source',
                                   'path':'source/logo.png','sha256':digest(logo),'job_id':job_id,
                                   'semantic_role':'front.recipient_branding','mime_type':'image/png'})
            sources.append({'source_id':'logo-source','sha256':digest(logo)})
        title = 'Привітання з нагоди Дня Народження!'
        jobs.append({'job_id':job_id,'raw_recipient_name':f'Synthetic_{i}',
                     'candidate_entity_id':f'synthetic-recipient-{i}','occasion':'BIRTHDAY',
                     'greeting_text_source':f'src_{i+1:03}',
                     'front_display_text':{'exact_text':title},
                     'greeting_text':{'exact_text':text,'exact_text_sha256':digest(text.encode())},
                     'sender_variant':'SINGLE_PRIMARY' if i < 2 else 'SINGLE_SECONDARY',
                     'sender_text':{'lines':sent}, 'bindings':bindings,
                     'branding_selection':selected,
                     'signature_selection':{'variant_id':signature,'source_id':f'src_{i+1:03}'},
                     'builder_v1':{'front':{'family':'RECIPIENT_BRANDING_OVERLAY' if branding else 'STANDARD',
                                            'occasion':{'display_text':title}},
                                   'inside_image':{'mode':'DEFAULT_ASSET','asset_sha256':flower_sha,
                                                   'asset_id':'flowers.default.v1'},
                                   'sender_text':{'lines':sent}},
                     'special_requests':[]})
        texts.append({'job_id':job_id,'greeting_source_id':f'src_{i+1:03}',
                      'greeting_text_exact':text,'greeting_text_sha256':digest(text.encode()),
                      'signature_variant_id':signature,'sender_variant':jobs[-1]['sender_variant'],
                      'sender_lines':sent})
        sources.append({'source_id':f'src_{i+1:03}', 'sha256':'a'*64})
    ids = [j['job_id'] for j in jobs]
    batch_id = 'synthetic-flowertest'
    y = lambda o: yaml.safe_dump(o,allow_unicode=True).encode('utf-8')
    assets.update({
        'SERVER_INGEST_STAGING.yaml':y({'packet_kind':'STRUCTURED_INTAKE_STAGING_NOT_ACCEPTED_BUNDLE',
                                        'batch_id':batch_id,'asset_selection_rule':{'all_job_ids':ids,
                                                      'inside_image_mode':'DEFAULT_ASSET','sha256':flower_sha}}),
        'BLOCKERS.yaml':y({'batch_id':batch_id,'final_handoff_allowed':False}),
        'visual_routing.yaml':y({'batch_id':batch_id,'image_source':{'sha256':flower_sha,
                                  'asset_id':'flowers.default.v1','path':'assets/flowers.default.v1.png'},
                                  'target_builder_mode':'DEFAULT_ASSET','creator_dispatch_required':False,
                                  'creator_jobs':[], 'apply_to_all_jobs':True,'apply_to_jobs':ids}),
        'normalized_batch.yaml':y({'batch_id':batch_id,'jobs':jobs}),
        'source_inventory.yaml':y({'batch_id':batch_id,'sources':sources,'asset_registry':asset_registry}),
        'texts/exact_greetings.json':json.dumps({'batch_id':batch_id,'jobs':texts},ensure_ascii=False).encode(),
    })
    def save(source_contents=None):
        content = assets if source_contents is None else source_contents
        entries = [{'path':n,'bytes':len(b),'sha256':digest(b)} for n,b in sorted(content.items())]
        manifest = json.dumps({'schema_version':'gdl_intake_staging_packet_manifest_v0_1',
                               'entries':entries},sort_keys=True).encode()
        with zipfile.ZipFile(source,'w') as z:
            for n,b in sorted(content.items()):z.writestr(n,b)
            z.writestr('packet_manifest.json',manifest)
    save()
    return source, root, assets, save


def test_synthetic_intake_validated_exact_and_unchanged(mock_source):
    source,_,_,_ = mock_source
    before = p.sha_file(source)
    data = p.load_staging(source)
    assert data['job_ids'] == [f'synthetic_{i}' for i in range(4)]
    assert len(data['logo_bytes']) == 1
    assert p.sha_file(source) == before


def test_modified_source_member_fails_digest(mock_source):
    source,_,assets,save = mock_source
    changed = dict(assets)
    text_map = json.loads(changed['texts/exact_greetings.json'])
    text_map['jobs'][0]['greeting_text_exact'] += ' ПОМИЛКА'
    changed['texts/exact_greetings.json'] = json.dumps(text_map, ensure_ascii=False).encode()
    save(changed)
    # Every ZIP member remains hashed by the new manifest, but internal
    # semantic cross-binding must still fail closed.
    with pytest.raises(p.Blocked, match='staging_job_exact_content_mismatch'):
        p.load_staging(source)


def test_missing_canonical_flowers_blocks(mock_source):
    source,_,assets,save = mock_source
    changed = dict(assets)
    changed.pop('assets/flowers.default.v1.png')
    save(changed)
    with pytest.raises(p.Blocked, match='staging_required_members_missing'):
        p.load_staging(source)


def test_no_creator_and_must_bind_logo(mock_source):
    source,_,assets,save = mock_source
    data = p.load_staging(source)
    assert data['job_ids'][-1] in data['logo_bytes']
    changed = dict(assets)
    route = yaml.safe_load(changed['visual_routing.yaml'])
    route['creator_dispatch_required'] = True
    changed['visual_routing.yaml'] = yaml.safe_dump(route).encode()
    save(changed)
    with pytest.raises(p.Blocked, match='default_flowers_source_or_selection_invalid'):
        p.load_staging(source)


def test_prepare_requires_real_review_and_is_immutable(mock_source):
    source, root, _, _ = mock_source
    result = p.prepare(source)
    assert result['status'] == 'AWAITING_REAL_OPERATOR_REVIEW'
    assert result['ack_token'].startswith('ACK-FLOWERS-')
    assert result['review'].is_file()
    assert root / 'intake' / 'reviews' / ('flowers_' + p.sha_file(source)[:16] + '_r002') / 'prepare_state.json'
    with pytest.raises(p.Blocked, match='review_previously_prepared_no_overwrite'):
        p.prepare(source)
    with pytest.raises(p.Blocked, match='explicit_reviewer_required'):
        p.promote(source, ack_token=result['ack_token'], reviewer='')
    with pytest.raises(p.Blocked, match='review_ack_or_source_identity_invalid'):
        p.promote(source, ack_token='WRONG', reviewer='Operator')
    result['review'].write_text(result['review'].read_text() + '\nMODIFIED\n')
    with pytest.raises(p.Blocked, match='review_ack_or_source_identity_invalid'):
        p.promote(source, ack_token=result['ack_token'], reviewer='Operator')
    assert not list((root / 'input').glob('gdl_flowers_reviewed_*'))


def test_bad_workspace_path_is_blocked(tmp_path):
    source = tmp_path / 'staging.zip'
    source.write_bytes(b'x')
    with pytest.raises(p.Blocked, match='source_outside_expected_workspace_input'):
        p.workspace_for_source(source)


def test_explicit_synthetic_ack_builds_only_logo_asset(mock_source, monkeypatch, tmp_path):
    source, root, _, _ = mock_source
    result = p.prepare(source)
    # Stub only canonical downstream Builder/Bundle checks: this test verifies
    # our archive transport and authority state, not the real Builder contract.
    def fake_bundle(batch, **kwargs):
        assert len(batch['jobs']) == 4
        assert all(j['bindings']['portrait']['source_id'] == 'flowers.default.v1'
                   for j in batch['jobs'])
        assert all(v['acceptance_basis'] == 'SOURCE_ASSET_OPERATOR_REVIEW_PASS'
                   for v in kwargs['accepted_visuals_by_job'].values())
        assert kwargs['intake_review']['state'] == 'PASS'
        return {'jobs': batch['jobs']}
    def fake_attach(bundle, *, payload_by_job, signature_catalog):
        for job in bundle['jobs']:
            job['builder_v1'] = payload_by_job[job['job_id']]
        return bundle
    catalog = tmp_path / 'catalog.yaml'
    catalog.write_text('variants: []\n', encoding='utf-8')
    monkeypatch.setattr(p, 'CATALOG', catalog)
    monkeypatch.setattr(p, 'build_accepted_constructor_bundle', fake_bundle)
    monkeypatch.setattr(p, 'attach_builder_payload_v1', fake_attach)
    monkeypatch.setattr(p, 'inspect_zip', lambda path: {'jobs':4,'archive_sha256':p.sha_file(path)})
    # Scratch should remain in isolated project tmp, not customer shared source.
    project_tmp = tmp_path / 'project'
    project_tmp.mkdir()
    monkeypatch.setattr(p, 'ROOT', project_tmp)
    final = p.promote(source, ack_token=result['ack_token'], reviewer='TEST_OPERATOR')
    assert final.parent == root / 'input'
    assert final.name.startswith('gdl_flowers_reviewed_')
    with zipfile.ZipFile(final) as z:
        names = set(z.namelist())
        assert {'accepted_constructor_bundle.yaml', 'artifact_manifest.yaml',
                'handoff_manifest.json', 'intake_evidence/operator_review.json'} <= names
        assert 'assets/flowers.default.v1.png' not in names
        assert len([n for n in names if n.startswith('assets/')]) == 1
        assert z.read('assets/synthetic_3__recipient_logo.png').startswith(b'\x89PNG')
        evidence = json.loads(z.read('intake_evidence/operator_review.json'))
        assert evidence['creator_dispatched'] is False
        assert evidence['production_approved'] is False
    with pytest.raises(p.Blocked, match='temporary_handoff_already_exists_no_overwrite|input_final_handoff_already_exists_no_overwrite'):
        p.promote(source, ack_token=result['ack_token'], reviewer='TEST_OPERATOR')


def test_review_exposes_actual_canonical_sender_not_just_intake(mock_source):
    source, _, _, _ = mock_source
    data = p.load_staging(source)
    sheet = p.review_text(source, data)
    assert '**ФАКТИЧНИЙ БЛОК ПІДПИСАНТА В PDF' in sheet
    assert 'Умовний відправник А' in sheet
    assert 'Умовний відправник Б' in sheet
    assert 'НЕВІДПОВІДНІСТЬ' in sheet
    assert 'НЕ фактичні рядки PDF' in sheet


def test_registry_mutation_invalidates_old_review_ack(mock_source):
    source, root, _, _ = mock_source
    result = p.prepare(source)
    original_doc = result['review'].read_bytes()
    registry = p.CANONICAL_SENDER_REGISTRY
    changed = registry.read_text(encoding='utf-8') + '\n# changed after prepare\n'
    registry.write_text(changed, encoding='utf-8')
    with pytest.raises(p.Blocked, match='review_ack_or_source_identity_invalid'):
        p.promote(source, ack_token=result['ack_token'], reviewer='TEST_OPERATOR')
    assert result['review'].read_bytes() == original_doc
    assert not list((root / 'input').glob('gdl_flowers_reviewed_*'))


def _mock_staged_package(tmp_path):
    """Synthetic interrupted GC15-B handoff (no customer material)."""
    pkg = {
        'accepted_constructor_bundle.yaml': b'jobs: [synthetic]\n',
        'artifact_manifest.yaml': b'artifacts: {}\n',
        'handoff_manifest.json': b'{"mode":"REVIEW_ONLY"}',
        'intake_evidence/operator_review.json': json.dumps({
            'schema_version': 'gdl_gc15_flowers_operator_ack_v0_1',
            'ack_token': 'ACK-SYNTHETIC',
            'operator_review_sha256': 'a' * 64,
            'reviewer_source': 'OPERATOR:TEST',
            'production_approved': False,
            'promoted_at': '2026-10-15T12:00:00+00:00',
        }).encode(),
    }
    stage = tmp_path / 'project_tmp' / 'gdl_intake_handoff.zip'
    stage.parent.mkdir()
    with zipfile.ZipFile(stage, 'x') as z:
        for name, data in pkg.items():
            z.writestr(name, data)
    expected = dict(pkg)
    evidence = json.loads(expected['intake_evidence/operator_review.json'])
    evidence['promoted_at'] = '2026-10-15T13:00:00+00:00'
    expected['intake_evidence/operator_review.json'] = json.dumps(evidence).encode()
    return stage, expected


def test_gc15b_crossfs_recovery_reuses_only_matching_review_evidence(tmp_path):
    stage, expected = _mock_staged_package(tmp_path)
    before = p.sha_file(stage)
    p._verify_reusable_staged_handoff(stage, expected)
    assert p.sha_file(stage) == before


@pytest.mark.parametrize('wrong', ['source', 'ack', 'inventory'])
def test_gc15b_crossfs_recovery_refuses_stale_or_tampered_stage(tmp_path, wrong):
    stage, expected = _mock_staged_package(tmp_path)
    if wrong == 'source':
        expected['accepted_constructor_bundle.yaml'] = b'CHANGED'
    elif wrong == 'ack':
        evidence = json.loads(expected['intake_evidence/operator_review.json'])
        evidence['ack_token'] = 'ACK-CHANGED'
        expected['intake_evidence/operator_review.json'] = json.dumps(evidence).encode()
    else:
        expected['unexpected_asset'] = b'UNEXPECTED'
    with pytest.raises(p.Blocked, match='staged_handoff_'):
        p._verify_reusable_staged_handoff(stage, expected)


def test_gc15b_crossfs_publish_is_atomic_no_clobber_and_digest_bound(tmp_path, monkeypatch):
    stage, expected = _mock_staged_package(tmp_path)
    p._verify_reusable_staged_handoff(stage, expected)
    inp = tmp_path / 'smb_input'
    inp.mkdir()
    target = inp / 'gdl_flowers_reviewed_synthetic.zip'
    before = p.sha_file(stage)
    real_link = p.os.link
    pairs = []

    def checked_link(src, dst):
        assert src.parent == dst.parent == inp
        assert src.suffix == '.part'
        pairs.append((src, dst))
        return real_link(src, dst)

    monkeypatch.setattr(p.os, 'link', checked_link)
    assert p._publish_staged_handoff(stage, target) == target
    assert len(pairs) == 1
    assert p.sha_file(stage) == p.sha_file(target) == before
    assert sorted(f.name for f in inp.iterdir()) == [target.name]
    with pytest.raises(p.Blocked, match='already_exists_no_overwrite'):
        p._publish_staged_handoff(stage, target)
    assert p.sha_file(target) == before


def test_gc15b_crossfs_publish_link_error_never_exposes_partial_zip(tmp_path, monkeypatch):
    stage, _ = _mock_staged_package(tmp_path)
    inp = tmp_path / 'smb_input'
    inp.mkdir()
    target = inp / 'gdl_flowers_reviewed_synthetic.zip'
    original_digest = p.sha_file(stage)

    def unavailable_link(_src, _dst):
        raise OSError('simulated SMB hardlink not supported')

    monkeypatch.setattr(p.os, 'link', unavailable_link)
    with pytest.raises(p.Blocked, match='handoff_atomic_link_not_supported'):
        p._publish_staged_handoff(stage, target)
    assert not target.exists()
    assert list(inp.iterdir()) == []
    assert p.sha_file(stage) == original_digest


def test_gc15b_crossfs_publish_rejects_dangling_destination_symlink(tmp_path):
    stage, _ = _mock_staged_package(tmp_path)
    inp = tmp_path / 'smb_input'
    inp.mkdir()
    target = inp / 'gdl_flowers_reviewed_synthetic.zip'
    target.symlink_to(inp / 'missing.zip')
    with pytest.raises(p.Blocked, match='already_exists_no_overwrite'):
        p._publish_staged_handoff(stage, target)
    assert target.is_symlink()
    assert len(list(inp.iterdir())) == 1

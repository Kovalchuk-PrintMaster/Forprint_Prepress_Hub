from __future__ import annotations

import copy
import hashlib
import json
import zipfile
from pathlib import Path

import pytest
import yaml

from app.graphic_design_lab.greeting_card_constructor_bundle import build_accepted_constructor_bundle
from app.graphic_design_lab.greeting_card_builder_input import attach_builder_payload_v1, validate_builder_ready_bundle_v1
from scripts.graphic_design_lab.greeting_cards.real_intake_pass_through_pilot_v0_1 import (
    load_archive, select_from_source, selected_jobs, source_recipient_logo, prepare, promote,
)

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / 'coordination/graphic_design_lab/directions/greeting_cards/signature_variant_catalog_v0_1.yaml'


def base_bundle():
    cat = yaml.safe_load(CATALOG.read_text(encoding='utf-8'))
    digest = hashlib.sha256(b'jpeg-synthetic').hexdigest()
    normalized = {
      'schema_version':'gdl_greeting_card_normalized_batch_v0_1',
      'batch_id':'synthetic-batch','request_id':'synthetic-request',
      'product_playbook_id':'recurring_greeting_card_v0_1','product_type':'greeting_card',
      'jobs':[{
        'job_id':'synthetic-job','raw_recipient_name':'Synthetic person',
        'candidate_entity_id':'synthetic-entity','occasion':'BIRTHDAY',
        'greeting_text_source':'synthetic-source','sender_variant':'SINGLE_PRIMARY',
        'supplied_assets':['portrait-source','signature-source'],
        'special_requests':[],'uncertainties':[],
        'bindings':{
            'recipient_entity':{'state':'CONFIRMED','basis':'customer_assignment','human_confirmation_required':False,'entity_id':'synthetic-entity'},
            'greeting_text':{'state':'CONFIRMED','basis':'customer_assignment','human_confirmation_required':False,'text':'Вітаємо з днем народження!','source_ref':'synthetic-source'},
            'portrait':{'state':'CONFIRMED','basis':'customer_assignment','human_confirmation_required':False,'source_id':'portrait-source'},
            'recipient_branding':{'state':'CONFIRMED','basis':'customer_assignment','human_confirmation_required':False,'presence':'ABSENT','source_id':None},
            'signature':{'state':'CONFIRMED','basis':'customer_assignment','human_confirmation_required':False,'source_id':'signature-source','variant_id':'GRIGO'},
            'sender_variant':{'state':'CONFIRMED','basis':'customer_assignment','human_confirmation_required':False,'value':'SINGLE_PRIMARY'},
        }
      }]
    }
    visuals = {'synthetic-job':{'job_id':'synthetic-job','target_object_id':'inside_image.portrait',
            'source_asset_id':'portrait-source','artifact_ref':'original-photo-synthetic',
            'acceptance_basis':'SOURCE_ASSET_OPERATOR_REVIEW_PASS',
            'review_id':'explicit-synthetic-operator-review', 'result_id':'original-synthetic',
            'revision':1,'provenance_sha256':digest}}
    bundle=build_accepted_constructor_bundle(normalized,
        source_inventory={'assets':[{'asset_id':'portrait-source'},{'asset_id':'signature-source'}]},
        entity_registry={'entities':[{'entity_id':'synthetic-entity'}]},
        accepted_visuals_by_job=visuals,signature_catalog=cat,
        intake_review={'state':'PASS','review_id':'explicit-synthetic-operator-review',
        'reviewer_source':'SYNTHETIC_TEST_OPERATOR','basis':'OPERATOR_REVIEWED_NORMALIZED_BATCH','source_batch_id':'synthetic-batch'},
        bundle_id='synthetic-bundle')
    payload={'schema_version':'gdl_greeting_card_builder_payload_v0_1','revision':'r001',
      'front':{'family':'STANDARD','occasion':{'kind':'BIRTHDAY','display_text':'Привітання з нагоди Дня Народження!'}},
      'inside_image':{'mode':'PORTRAIT','asset_id':'portrait-source','asset_sha256':digest,'accepted_artifact_ref':'original-photo-synthetic'},
      'sender_text':{'signature_variant_id':'GRIGO','lines':[{'id':'sender_name','text':'Synthetic Sender'}]}}
    return attach_builder_payload_v1(bundle,payload_by_job={'synthetic-job':payload},signature_catalog=cat), cat


def test_reviewed_unmodified_photo_is_valid():
    bundle,cat=base_bundle()
    assert validate_builder_ready_bundle_v1(bundle,signature_catalog=cat)==[]
    assert bundle['provenance_manifest']['accepted_visual_review_ids']==['explicit-synthetic-operator-review']


def test_pass_through_rejects_image_sha_mismatch_even_with_rehashed_bundle():
    bundle,cat=base_bundle()
    from app.graphic_design_lab.greeting_card_constructor_bundle import compute_bundle_sha256
    bundle['jobs'][0]['builder_v1']['inside_image']['asset_sha256']='f'*64
    bundle['provenance_manifest']['bundle_sha256']=compute_bundle_sha256(bundle)
    errors=validate_builder_ready_bundle_v1(bundle,signature_catalog=cat)
    assert any('pass_through_provenance' in x for x in errors)


def test_prepare_requires_explicit_operator_confirmation(tmp_path):
    with pytest.raises(ValueError,match='selected_jobs_required'):
        select_from_source('')
    with pytest.raises(ValueError,match='selected_jobs_required'):
        select_from_source('a,a')


def branded_source_job():
    def confirmed(**fields):
        return {'state': 'CONFIRMED', 'human_confirmation_required': False, **fields}
    return {
        'job_id': 'fixture_branded', 'uncertainties': [],
        'raw_recipient_name': 'Synthetic Recipient',
        'candidate_entity_id': 'synthetic-recipient',
        'occasion': 'BIRTHDAY',
        'front_display_text': {'exact_text': 'Привітання з нагоди Дня Народження!'},
        'greeting_text_source': 'fixture-document',
        'greeting_text': {'exact_text': 'Вітаємо!'},
        'sender_variant': 'SINGLE_SECONDARY',
        'sender_text': {'lines': []},
        'signature_selection': {'variant_id': 'HERASYMENKO', 'source_id': 'signature-source'},
        'branding_selection': {'presence': 'PRESENT', 'asset_id': 'logo-candidate',
                               'target_object_id': 'front.recipient_branding'},
        'builder_support': {'current_v1_front': 'RECIPIENT_BRANDING_OVERLAY_UNSUPPORTED'},
        'bindings': {
            'recipient_entity': confirmed(entity_id='synthetic-recipient'),
            'greeting_text': confirmed(text='Вітаємо!', source_ref='fixture-document'),
            'portrait': confirmed(source_id='portrait-source', sha256='p'*64),
            'recipient_branding': confirmed(presence='PRESENT', source_id='logo-source', asset_id='logo-candidate'),
            'signature': confirmed(source_id='signature-source', variant_id='HERASYMENKO'),
            'sender_variant': confirmed(value='SINGLE_SECONDARY'),
        },
    }


def test_supported_branded_job_keeps_exact_source_family():
    job = branded_source_job()
    assert selected_jobs({'jobs': [job]}, ['fixture_branded']) == [job]
    assert job['builder_support']['current_v1_front'] == 'RECIPIENT_BRANDING_OVERLAY_UNSUPPORTED'
    assert job['branding_selection']['presence'] == 'PRESENT'


def test_branded_source_identity_required():
    job = branded_source_job()
    job['bindings']['recipient_branding']['source_id'] = None
    with pytest.raises(ValueError, match='source_recipient_branding_not_confirmed'):
        selected_jobs({'jobs': [job]}, ['fixture_branded'])


def test_branded_source_does_not_downgrade_if_runtime_unsupported(monkeypatch):
    from scripts.graphic_design_lab.greeting_cards import real_intake_pass_through_pilot_v0_1 as pilot
    monkeypatch.setattr(pilot, 'SUPPORTED_FRONT_FAMILIES', ('STANDARD',))
    with pytest.raises(ValueError, match='source_front_family_not_supported_by_current_builder'):
        pilot.selected_jobs({'jobs': [branded_source_job()]}, ['fixture_branded'])


def test_branded_logo_sha_and_role_are_source_bound():
    from PIL import Image
    import io
    job = branded_source_job()
    f = io.BytesIO()
    Image.new('RGBA', (128, 96), (10, 20, 30, 255)).save(f, format='PNG')
    data = f.getvalue()
    item = {'semantic_role':'front.recipient_branding', 'job_id':job['job_id'],
            'asset_id':'logo-candidate', 'source_id':'logo-source',
            'mime_type':'image/png', 'sha256':hashlib.sha256(data).hexdigest(),
            'width_px':128, 'height_px':96, 'path':'source/logo.png'}
    assets = {(job['job_id'], 'front.recipient_branding'): (item, data)}
    assert source_recipient_logo(job, assets) == (item, data)
    with pytest.raises(ValueError, match='recipient_logo_source_not_authenticated'):
        source_recipient_logo(job, {(job['job_id'], 'front.recipient_branding'): (item, data+b'x')})
    item2 = {**item, 'source_id':'other-source'}
    with pytest.raises(ValueError, match='recipient_logo_source_not_authenticated'):
        source_recipient_logo(job, {(job['job_id'], 'front.recipient_branding'): (item2, data)})
    with pytest.raises(ValueError, match='recipient_logo_source_missing'):
        source_recipient_logo(job, {})


def test_prepare_branded_is_review_only_and_requires_real_ack(monkeypatch, tmp_path):
    import hashlib
    from scripts.graphic_design_lab.greeting_cards import real_intake_pass_through_pilot_v0_1 as pilot
    from PIL import Image
    import io
    job = branded_source_job()
    job['sender_text']['lines'] = [{'id':'source-sender', 'text':'Synthetic Sender'}]
    photo = b'fixture-photo-source'
    logo_buf = io.BytesIO()
    Image.new('RGBA', (128, 96)).save(logo_buf, format='PNG')
    logo = logo_buf.getvalue()
    assets = {
        ('fixture_branded','inside_image.portrait'):
            ({'source_id':'portrait-source', 'path':'source/photo.jpg',
              'sha256':hashlib.sha256(photo).hexdigest(), 'width_px':100,'height_px':100}, photo),
        ('fixture_branded','front.recipient_branding'):
            ({'source_id':'logo-source', 'asset_id':'logo-candidate','job_id':'fixture_branded',
              'semantic_role':'front.recipient_branding', 'mime_type':'image/png',
              'sha256':hashlib.sha256(logo).hexdigest(),'width_px':128,'height_px':96,
              'path':'source/logo.png'}, logo),
    }
    monkeypatch.setattr(pilot, 'load_archive', lambda source: (
        {'batch_id': 'synthetic-batch', 'jobs':[job]},
        {'sources':[]}, assets, {'entries':[], 'entry_count':0}))
    src = tmp_path/'source.zip';src.write_bytes(b'fixture-transport')
    work = tmp_path/'private'
    state = pilot.prepare(src, work, ['fixture_branded'])
    review = (work/'operator_review_PRIVATE.md').read_text()
    assert 'Логотип отримувача' in review
    assert assets[('fixture_branded','front.recipient_branding')][0]['sha256'] in review
    assert state['status'] == 'WAITING_FOR_OPERATOR_ACK'
    assert not (work/'output'/'gdl_intake_handoff.zip').exists()
    with pytest.raises(ValueError, match='explicit_operator_ack_required'):
        pilot.promote(src, work, ack='NOT_APPROVED', reviewer='fixture-reviewer')
    assert not (work/'output'/'gdl_intake_handoff.zip').exists()


def test_transfer_rejects_modified_bytes_even_with_manifest_present(tmp_path):
    out=tmp_path/'bad.zip'
    b='intake_resume/normalized_batch.yaml'
    m='99_PACKET_MANIFEST.json'
    content={'intake_resume/normalized_batch.yaml':b'jobs: []',
             'intake_resume/source_inventory.yaml':b'asset_registry: []'}
    entries=[{'path':n,'bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()}
             for n,v in content.items()]
    content[m]=json.dumps({'entry_count':len(entries),'entries':entries}).encode()
    with zipfile.ZipFile(out,'w') as z:
        for n,v in content.items():z.writestr(n,v)
    # Replace a member without updating the manifest; do not create duplicate ZIP names.
    with zipfile.ZipFile(out,'w') as z:
        for n,v in content.items(): z.writestr(n, b'tampered' if n == b else v)
    with pytest.raises(ValueError,match='transfer_manifest_hash_mismatch'):
        load_archive(out)


def test_synthetic_branded_explicit_ack_builds_valid_private_handoff(monkeypatch, tmp_path):
    """A true project Constructor/Builder contract check; no real customer approval."""
    import io
    from PIL import Image
    from scripts.graphic_design_lab.greeting_cards import real_intake_pass_through_pilot_v0_1 as pilot
    from app.graphic_design_lab.greeting_card_constructor_bundle import compute_bundle_sha256
    job = branded_source_job()
    job['sender_text']['lines'] = [{'id': 'source-sender', 'text': 'Synthetic'}]
    photo_io = io.BytesIO()
    Image.new('RGB', (778, 838), (12, 15, 17)).save(photo_io, format='JPEG')
    photo = photo_io.getvalue()
    logo_io = io.BytesIO()
    Image.new('RGBA', (1954, 1097), (22, 32, 42, 200)).save(logo_io, format='PNG')
    logo = logo_io.getvalue()
    photo_sha = hashlib.sha256(photo).hexdigest()
    logo_sha = hashlib.sha256(logo).hexdigest()
    job['bindings']['portrait']['sha256'] = photo_sha
    inventory = {'sources': [
        {'source_id':'portrait-source','sha256':photo_sha},
        {'source_id':'logo-source','sha256':logo_sha},
        {'source_id':'signature-source','sha256':'a'*64},
    ]}
    images = {
        ('fixture_branded','inside_image.portrait'): ({
            'source_id':'portrait-source','path':'source/portrait.jpg',
            'sha256':photo_sha,'width_px':778,'height_px':838}, photo),
        ('fixture_branded','front.recipient_branding'): ({
            'semantic_role':'front.recipient_branding', 'job_id':'fixture_branded',
            'asset_id':'logo-candidate','source_id':'logo-source', 'mime_type':'image/png',
            'sha256':logo_sha,'width_px':1954,'height_px':1097,'path':'source/logo.png'}, logo),
    }
    monkeypatch.setattr(pilot, 'load_archive', lambda source: (
        {'batch_id':'synthetic-batch','jobs':[job]}, inventory, images, {'entries':[]}))
    checked = []
    checked_sha256 = []
    def strict_probe(path):
        with zipfile.ZipFile(path) as z:
            bundle = yaml.safe_load(z.read('accepted_constructor_bundle.yaml'))
            artifacts = yaml.safe_load(z.read('artifact_manifest.yaml'))['artifacts']
            cat = yaml.safe_load(CATALOG.read_text(encoding='utf-8'))
            assert validate_builder_ready_bundle_v1(bundle, signature_catalog=cat) == []
            assert compute_bundle_sha256(bundle) == bundle['provenance_manifest']['bundle_sha256']
            bjob = bundle['jobs'][0]
            assert bjob['branding_selection']['presence'] == 'PRESENT'
            front = bjob['builder_v1']['front']
            assert front['family'] == 'RECIPIENT_BRANDING_OVERLAY'
            logo_ref = front['recipient_branding']['accepted_artifact_ref']
            assert artifacts[logo_ref]['sha256'] == logo_sha
            assert hashlib.sha256(z.read(artifacts[logo_ref]['path'])).hexdigest() == logo_sha
            assert len(artifacts) == 2
            evidence = json.loads(z.read('intake_evidence/operator_review.json'))
            assert evidence['approved_for'] == 'REVIEW_ONLY_NOT_PRODUCTION'
            checked.append(path)
        checked_sha256.append(hashlib.sha256(path.read_bytes()).hexdigest())
    monkeypatch.setattr(pilot, 'inspect_zip', strict_probe)
    source = tmp_path/'source.zip'
    source.write_bytes(b'SYNTHETIC-SOURCE-ONLY')
    workspace = tmp_path/'private'
    state = pilot.prepare(source, workspace, ['fixture_branded'])
    handoff = pilot.promote(source, workspace,
                            ack=state['ack_token'], reviewer='SYNTHETIC_TEST_OPERATOR')
    assert handoff.is_file()
    assert checked == [workspace / "validation_PRIVATE" / "gdl_intake_handoff.zip"]
    assert not checked[0].exists()
    assert hashlib.sha256(handoff.read_bytes()).hexdigest() == checked_sha256[0]

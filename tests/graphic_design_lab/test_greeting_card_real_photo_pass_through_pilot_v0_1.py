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
    load_archive, select_from_source, selected_jobs, prepare, promote,
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


def test_branding_job_must_not_be_silently_downgraded():
    job={'job_id':'a','uncertainties':[], 'branding_selection':{'presence':'PRESENT'},
         'signature_selection':{'variant_id':'GRIGO'}, 'builder_support':{'current_v1_front':'STANDARD'}}
    with pytest.raises(ValueError,match='recipient_branding_not_supported'):
        selected_jobs({'jobs':[job]},['a'])


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

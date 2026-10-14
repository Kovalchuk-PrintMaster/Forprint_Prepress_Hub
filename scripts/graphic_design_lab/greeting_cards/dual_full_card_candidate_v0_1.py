#!/usr/bin/env python3
"""Explicit private DUAL Builder candidate: accepted DUAL jobs only.

Never modifies a customer's accepted bundle, runs ordinary Builder dispatch,
client publish, or promotes the signature registry. See --mode preflight.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml
from app.graphic_design_lab.greeting_card_builder_input import validate_builder_ready_bundle_v1
from app.graphic_design_lab.greeting_card_builder_renderer import build_bundle
from scripts.graphic_design_lab.greeting_cards.full_review_runner_v0_1 import verify_one

CATALOG = ROOT / 'coordination/graphic_design_lab/directions/greeting_cards/signature_variant_catalog_v0_1.yaml'
DUAL = 'DUAL_GRIGO_HERASYMENKO'
SCHEMA = 'gdl_gc09_dual_full_card_candidate_v0_1'


def digest(path: Path) -> str:
    hash_ = sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            hash_.update(chunk)
    return hash_.hexdigest()


def project_tmp(path: Path) -> Path:
    path = path.expanduser().resolve()
    top = (ROOT / 'tmp').resolve()
    if path == top or top not in path.parents:
        raise ValueError('dual_full_candidate_output_outside_project_tmp')
    return path


def checked_page4_proof(path: Path) -> dict:
    r = json.loads(path.read_text(encoding='utf-8'))
    if r.get('status') != 'DUAL_PAGE4_SOURCE_COMPOSITION_CANDIDATE_REQUIRES_VISUAL_REVIEW':
        raise ValueError('page4_proof_status_invalid')
    if r.get('output',{}).get('status') != 'PASS' or r['output'].get('output_vector_count') != 7:
        raise ValueError('page4_proof_vector_validation_missing')
    if r.get('text_evidence',{}).get('sender_line_count') != 6:
        raise ValueError('page4_proof_canonical_sender_missing')
    if r.get('output_overlap',{}).get('status') != 'TRANSPARENT_REGION':
        raise ValueError('page4_proof_visible_overlap')
    if any(r.get(key) is not False for key in (
        'dual_runtime_enabled','production_ready','customer_approved',
        'client_published','full_card_rendered','accepted_job_rendered')):
        raise ValueError('page4_proof_authority_invalid')
    for name,key in (
        ('DUAL_PAGE4_ONLY_NOT_FULL_CARD.pdf','pdf_sha256'),
        ('DUAL_PAGE4_ONLY_NOT_FULL_CARD.png','png_sha256')):
        file = path.parent / name
        if not file.is_file() or digest(file) != r.get(key):
            raise ValueError('page4_proof_artifact_digest_mismatch')
    return r


def read_inputs(path: Path):
    config=json.loads(path.read_text('utf-8'))
    keys={'bundle','resource_manifest','artifact_manifest'}
    if set(config) != keys:
        raise ValueError('private_inputs_keys_invalid')
    inputs={}
    for key in keys:
        item=Path(config[key]).expanduser()
        if not item.is_absolute(): item=ROOT/item
        item=item.resolve()
        if not item.is_file(): raise ValueError('private_'+key+'_not_file')
        inputs[key]=item
    return inputs


def preflight(config: Path, prior: Path, output: Path):
    output=project_tmp(output)
    if output.exists(): raise ValueError('output_exists')
    inputs=read_inputs(config)
    proof=checked_page4_proof(prior)
    bundle=yaml.safe_load(inputs['bundle'].read_text('utf-8'))
    catalog=yaml.safe_load(CATALOG.read_text('utf-8'))
    errors=validate_builder_ready_bundle_v1(bundle,signature_catalog=catalog)
    if errors: raise ValueError('bundle_contract_invalid')
    jobs=bundle.get('jobs')
    if not isinstance(jobs,list) or len(jobs)!=1:
        raise ValueError('dual_private_candidate_requires_exactly_one_job')
    j=jobs[0]
    variant=j.get('signature_selection',{}).get('variant_id')
    builder_variant=j.get('builder_v1',{}).get('sender_text',{}).get('signature_variant_id')
    if variant != DUAL or builder_variant != DUAL:
        raise ValueError('dual_candidate_requires_real_accepted_dual_job')
    if bundle.get('synthetic_fixture_only') is True:
        raise ValueError('synthetic_bundle_not_accepted_as_real_proof')
    if not isinstance(j.get('job_id'),str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',j['job_id']):
        raise ValueError('job_id_unsafe')
    from app.graphic_design_lab.greeting_card_private_resources import (
        RESOURCE_SIGNATURE_DUAL, validate_and_resolve_private_resources,
    )
    manifest=yaml.safe_load(inputs['resource_manifest'].read_text('utf-8'))
    verified=validate_and_resolve_private_resources(manifest,required_ids=[RESOURCE_SIGNATURE_DUAL])
    if verified[RESOURCE_SIGNATURE_DUAL]['sha256'] != proof['source_pdf_sha256']:
        raise ValueError('dual_source_prior_proof_mismatch')
    fingerprints={key:digest(path) for key,path in inputs.items()}
    fingerprints['catalog']=digest(CATALOG)
    fingerprints['page4_proof']=digest(prior)
    return inputs,fingerprints


def run(config: Path, prior: Path, output: Path):
    output=project_tmp(output)
    inputs, before=preflight(config, prior, output)
    result=build_bundle(
        bundle_path=inputs['bundle'],resource_manifest_path=inputs['resource_manifest'],
        artifact_manifest_path=inputs['artifact_manifest'],signature_catalog_path=CATALOG,
        output_dir=output / 'builder_outputs_PRIVATE',dual_candidate=True,
    )
    report=result['bundle_report']
    if report['job_count']!=1 or report['signature_variants'] != [DUAL]:
        raise ValueError('dual_full_card_result_job_mismatch')
    reviewed=[]
    for job in result['jobs']:
        r=job['report']
        if (r.get('signature_variant')!=DUAL or r.get('page4_signature_source_authenticated') is not True
            or r.get('dual_candidate_only') is not True
            or r.get('canonical_sender_line_count')!=6 or r.get('production_ready') is not False):
            raise ValueError('dual_full_card_builder_evidence_invalid')
        exact=verify_one(job['pdf_path'], job['preview_paths'])
        if exact['preview_pixel_replay']!='PASS':
            raise ValueError('dual_full_card_pdf_png_replay_invalid')
        reviewed.append({'job_id':job['job_id'],'revision':job['revision'],
                         'pdf_sha256':exact['pdf_sha256'], 'page_count':4,
                         'png_preview_count':4,'pixel_replay':'PASS'})
    after={key:digest(path) for key,path in inputs.items()}
    after['catalog']=digest(CATALOG)
    after['page4_proof']=digest(prior)
    if before!=after:raise ValueError('source_fingerprints_changed')
    summary={
      'schema_version':SCHEMA,
      'status':'PRIVATE_DUAL_FULL_CARD_CANDIDATE_REQUIRES_VISUAL_REVIEW',
      'source_fingerprints_sha256': before,
      'job_count':1,'pdf_count':1,'png_preview_count':4,
      'jobs':reviewed,'pixel_replay':'PASS',
      'dual_candidate_only':True,'dual_runtime_enabled':False,
      'production_ready':False,'customer_approved':False,
      'client_published':False,'visual_review_required':True,
    }
    (output/'dual_full_card_candidate_report.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',required=True,choices=('preflight','run'))
    p.add_argument('--inputs-config',required=True,type=Path)
    p.add_argument('--prior-page4-report',required=True,type=Path)
    p.add_argument('--output-root',required=True,type=Path)
    args=p.parse_args()
    try:
        if args.mode=='preflight':
            preflight(args.inputs_config,args.prior_page4_report,args.output_root)
            print('GDL_GC09_DUAL_FULL_CARD_PREFLIGHT=PASS')
        else:
            report=run(args.inputs_config,args.prior_page4_report,args.output_root)
            print('GDL_GC09_DUAL_FULL_CARD_CANDIDATE=PASS_REQUIRES_VISUAL_REVIEW')
            print('PDF_COUNT='+str(report['pdf_count']))
            print('PNG_COUNT='+str(report['png_preview_count']))
            print('PIXEL_REPLAY=PASS')
        print('DUAL_DEFAULT_RUNTIME_ENABLED=false')
        print('PRODUCTION_READY=false')
        print('PRIVATE_PATHS_PRINTED=false')
        return 0
    except Exception as exc:
        print('GDL_GC09_DUAL_FULL_CARD_CANDIDATE=BLOCKED')
        print('ERROR_CODE='+type(exc).__name__)
        print('PRIVATE_PATHS_PRINTED=false')
        return 2

if __name__ == '__main__':
    raise SystemExit(main())

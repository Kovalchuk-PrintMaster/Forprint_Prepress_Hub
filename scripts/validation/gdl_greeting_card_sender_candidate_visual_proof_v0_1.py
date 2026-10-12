#!/usr/bin/env python3
"""Synthetic-only HERASYMENKO visual comparison through the existing Builder.

Uses the existing validated private resource set and Builder, temporarily switches
sender drawing *in this process only* for the candidate run; regular Builder
code and customer runtime remain source_locked. Outputs under ignored tmp.
Do NOT upload private PDF/PNG without considering source portrait/signature rights.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pymupdf
import yaml
from PIL import Image, ImageDraw, ImageFont

from app.graphic_design_lab import greeting_card_builder_renderer as renderer
from app.graphic_design_lab.greeting_card_sender_zone_planner_v0_1 import candidate_v03_slots
from scripts.validation import gdl_greeting_card_multi_job_pdf_probe_v0_1 as baseline

ZONES = ROOT / 'coordination/graphic_design_lab/directions/greeting_cards/geometry_zones_v0_1.yaml'
OUT = ROOT / 'tmp/gdl_gc09_sender_candidate_visual_proof_v0_1'
CASES = (baseline.CASES[0], baseline.CASES[1])


def digest(file: Path) -> str:
    h = hashlib.sha256()
    with file.open('rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def candidate_sender(page, lines, *, font_path, start_y_mm):
    """Proof-only adapter; do not mutate Builder source or global runtime settings."""
    if not isinstance(lines, list) or not lines:
        raise ValueError('candidate_sender_lines_missing')
    d = yaml.safe_load(ZONES.read_text(encoding='utf-8'))
    profile = d['pages']['physical_4']['signature_profiles_candidate_v0_3']['HERASYMENKO']
    if profile.get('sender_text_inner_top_inset_mm') != 0.5:
        raise ValueError('candidate_inset_not_installed')
    slots = candidate_v03_slots(
        [str(line['id']) for line in lines], variant='HERASYMENKO', profile=profile
    )
    for line, slot in zip(lines, slots):
        renderer._insert_textbox_exact(
            page,
            renderer._rect_mm(slot.bbox_pdf_mm),
            str(line['text']),
            font_path=font_path,
            fontname='ZapfChanceryC',
            fontsize=renderer._sender_font_size(str(line['id'])),
            align=pymupdf.TEXT_ALIGN_LEFT,
            lineheight=1.0,
        )


def previews(output: Path):
    return {p.name.split('__r001__')[0]: p for p in (output/'preview').glob('*__04.png')}


def run() -> int:
    baseline.guard()
    inputs = baseline.private_inputs(baseline.DEFAULT_CONFIG)
    original_hashes = {k: digest(v) for k,v in inputs.items()}
    source = baseline.load_yaml(inputs['bundle'])
    catalog = baseline.load_yaml(baseline.SIGNATURE_CATALOG)
    if baseline.validate_builder_ready_bundle_v1(source, signature_catalog=catalog):
        raise RuntimeError('SOURCE_BUNDLE_INVALID')
    bundle = baseline.prepare_bundle(source, CASES)
    if baseline.validate_builder_ready_bundle_v1(bundle, signature_catalog=catalog):
        raise RuntimeError('SYNTHETIC_BUNDLE_INVALID')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    work = OUT / 'runs' / stamp
    work.mkdir(parents=True, exist_ok=False)
    private = work / 'synthetic_bundle_PRIVATE.yaml'
    private.write_text(yaml.safe_dump(bundle, allow_unicode=True, sort_keys=False), encoding='utf-8')
    common=dict(bundle_path=private, resource_manifest_path=inputs['resource_manifest'],
                artifact_manifest_path=inputs['artifact_manifest'],
                signature_catalog_path=baseline.SIGNATURE_CATALOG)
    print('GDL_GC09_VISUAL_PROOF=START', flush=True)
    print('SYNTHETIC_JOBS=2', flush=True)
    print('BATCH_SOURCE_LOCKED=START', flush=True)
    normal = work / 'source_locked_PRIVATE'
    renderer.build_bundle(**common, output_dir=normal)
    a = baseline.verify_outputs(normal, bundle)
    print('BATCH_CANDIDATE_ONLY=START', flush=True)
    candidate = work / 'candidate_v03_PRIVATE'
    original_renderer = renderer._render_sender_lines
    try:
        renderer._render_sender_lines = candidate_sender
        renderer.build_bundle(**common, output_dir=candidate)
    finally:
        renderer._render_sender_lines = original_renderer
    b = baseline.verify_outputs(candidate, bundle)
    left, right = previews(normal), previews(candidate)
    if set(left) != set(right) or len(left)!=2:
        raise RuntimeError('PREVIEW_PAIR_SET_INVALID')
    compare_files = []
    all_unchanged_other_pages = True
    for key in sorted(left):
        for n in (1,2,3):
            stem=f'{key}__r001__{n:02d}.png'
            with Image.open(normal/'preview'/stem) as l, Image.open(candidate/'preview'/stem) as r:
                if l.convert('RGB').tobytes()!=r.convert('RGB').tobytes():
                    all_unchanged_other_pages=False
        with Image.open(left[key]) as l, Image.open(right[key]) as r:
            l=l.convert('RGB'); r=r.convert('RGB')
            if l.size!=r.size:
                raise RuntimeError('PAGE4_DIMENSIONS_DIFFER')
            width=850
            h=round(width*l.height/l.width)
            l=l.resize((width,h), Image.Resampling.LANCZOS)
            r=r.resize((width,h), Image.Resampling.LANCZOS)
            margin=18; cap=44
            panel=Image.new('RGB',(width*2+margin*3,h+cap+margin*2),'white')
            panel.paste(l,(margin, cap+margin))
            panel.paste(r,(width+margin*2, cap+margin))
            dr=ImageDraw.Draw(panel)
            dr.text((margin,margin),f'{key} | SOURCE LOCKED',fill='black')
            dr.text((width+margin*2,margin),f'{key} | CANDIDATE v0.3',fill='black')
            output=work/f'{key}__page4_comparison_PRIVATE.png'
            panel.save(output)
            compare_files.append(output.name)
    if not all_unchanged_other_pages:
        raise RuntimeError('FRONT_AND_PORTRAIT_PAGES_CHANGED')
    if {k:digest(v) for k,v in inputs.items()}!=original_hashes:
        raise RuntimeError('PRIVATE_INPUTS_MUTATED')
    baseline.guard()
    result={
      'schema_version':'gdl_gc09_sender_visual_candidate_proof_v0_1',
      'status':'PASS_REQUIRES_OPERATOR_VISUAL_REVIEW',
      'source_locked_pdfs':len(a), 'candidate_pdfs':len(b),
      'source_locked_previews':8,'candidate_previews':8,
      'pdf_text_fidelity':'PASS','pdf_preview_pixel_replay':'PASS',
      'pages_1_2_3_unchanged':True,
      'candidate_inset_mm':0.5, 'source_locked_renderer_modified_on_disk':False,
      'dual_runtime_enabled':False,'production_accepted':False,
      'comparison_files':compare_files,
      'private_artifacts_with_reference_portrait_and_signature':True,
    }
    report = work / 'sanitized_visual_proof_report.json'
    report.write_text(json.dumps(result, indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('RUN=' + str(work.relative_to(ROOT)))
    for file in compare_files:
        print('VISUAL_COMPARE=' + str((work/file).relative_to(ROOT)))
    print('REPORT=' + str(report.relative_to(ROOT)))
    print('GDL_GC09_VISUAL_PROOF=PASS_REQUIRES_OPERATOR_VISUAL_REVIEW')
    return 0


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['preflight','run'], default='preflight')
    args=ap.parse_args()
    try:
        baseline.guard()
        baseline.private_inputs(baseline.DEFAULT_CONFIG)
        d=yaml.safe_load(ZONES.read_text(encoding='utf-8'))
        assert d['pages']['physical_4']['signature_profiles_candidate_v0_3']['HERASYMENKO'].get('sender_text_inner_top_inset_mm')==0.5
        if args.mode=='preflight':
            print('GDL_GC09_VISUAL_PROOF=PREFLIGHT_PASS')
            return 0
        return run()
    except Exception as exc:
        print('GDL_GC09_VISUAL_PROOF=BLOCKED')
        print('ERROR_CLASS='+type(exc).__name__)
        print('ERROR_CODE='+str(exc).split(':',1)[0])
        return 2

if __name__=='__main__':
    raise SystemExit(main())

# ForPrint Graphic Design Lab — roadmap v0.1

Status: **planning baseline**. This is the human-readable view of
`roadmap_v0_1.yaml`. It is not execution, acceptance, release, or production authority.

## Purpose

Graphic Design Lab is an experimental capability inside ForPrint Prepress Hub.
The target is a controlled environment for creating, editing, validating,
versioning and preparing design documents for print.

```text
brief + references + assets
        ↓
Design Specification
        ↓
Product Profile + constraints
        ↓
deterministic compiler
        ↓
specialized / AI tools where useful
        ↓
editable artifact + preview
        ↓
validation / preflight
        ↓
review / print output
        ↓
Prepress Hub
```

## Owner direction preserved

The Human Owner directed that all design approaches discussed so far remain
visible in the roadmap, implementation move from simpler deterministic solutions
toward more complex mixed/AI solutions, storage/template/reference/output
locations remain configurable, and the Abram A5 dated diary be used as the first
practical pilot.

These 2026-09-27 statements are local planning evidence pending normal sync into
the central Blueprint Human Intent ledger; this file does not create a competing
Human Intent authority.

## Reconciliation with recovered Prepress direction

This baseline extends, rather than replaces, recovered Prepress intent:

- capability-first practical experiments before broad integration design;
- product-specific executors where Photoshop, Illustrator, CorelDRAW,
  PDF/Acrobat or similar tools have materially different behavior;
- shared low-level inspection returning stable technical facts;
- several valid processing candidates may coexist and should expose preview plus
  risk/confidence evidence;
- Unix-first deterministic execution where practical, with Windows graphics
  software as a bounded specialist executor;
- Python-first orchestration/rules/reporting;
- future visualization comparing deterministic 2D, scripted/3D, AI-assisted and
  hybrid approaches, with a fresh technology review at implementation time.

## Near-term practical route

1. Planning/configuration/architecture baseline.
2. Design Specification v0.1.
3. Asset/reference/revision/patch contracts.
4. Minimal deterministic editable SVG output.
5. Preview plus structural/geometry validation.
6. Abram Diary Phase 1: October 2026 monthly spread, partial week 15–18 Oct,
   one full week, transition week 26 Oct–1 Nov, A5 geometry, mirrored binding
   margins, bilingual month heading, English weekdays, month colors, editable
   output, review output and validation report.
7. Product profiles/templates/components only as required by the pilot.

The full ~160-page diary remains outside Phase 1 until the first design logic is approved.

## Farther practical horizon

Multipage generation, mixed raster/vector composition, vector artwork/trace,
AI routing and semantic edits, generative assets, review/print PDF, CMYK/ICC,
fonts and image-resolution checks, preflight, Design Package, Wizard/operator
intake, experiment metrics, structural and visual regression.

## Strategic horizon — visible, not activated

Photoshop/Illustrator/CorelDRAW/Acrobat specialized executors; Inkscape/native
SVG/CairoSVG; Pillow/pyvips/OpenCV; PyMuPDF/pikepdf/Ghostscript/veraPDF;
LittleCMS/ImageCms; AI text/image/vectorization providers; ForPrint-owned PDF
Control Layer; deterministic 2D/scripted 3D/AI/hybrid visualization; imposition;
VDP/PDF-VT; responsive print rules; variants/feedback analytics; dependency graph
and incremental rebuild; watched/hot-folder intake; policy-gated managed automation.

## First useful milestone

> structured Abram Phase 1 spec + config-driven paths → deterministic editable
> document → preview → validation report → reproducible revision.

Graphic Design Lab runtime remains `PLANNED_NOT_INITIALIZED` after this planning baseline.

## H1 contract-foundation implementation note

Design Specification v0.1, asset/reference, revision/patch and product-profile contracts plus the dated-diary A5 profile are now locally implemented **pending validation and acceptance**. Renderer/compiler work remains a separate later contour.

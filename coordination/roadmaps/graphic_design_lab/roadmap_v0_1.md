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

On 2026-09-28 the Human Owner refined the practical sequence: get a useful,
repeatable **customer input → guided brief → creator handoff → structured creator
result** workflow before investing further in heavier runtime infrastructure.
Product-specific playbooks should drive wizard questions and asset normalization.
The recurring greeting-card workflow is the first intake/handoff pilot; a
business-card wizard is the next validation scenario. A separate Capability
Catalog should preserve available and future tools/capabilities without turning
every idea into an active roadmap item.

The compressed rationale is preserved separately as local planning evidence at
`coordination/roadmaps/graphic_design_lab/planning_evidence/2026-09-28_guided_intake_creator_handoff_direction.md`.
It is not a competing Human Intent authority.

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
8. Promote the existing `GDL-F07` Wizard/operator intake item into the near-term
   planning horizon as a Product-Playbook-driven Design Brief Builder / Guided
   Design Intake workflow.
9. Promote the existing `GDL-F06` Design Package item into the near-term planning
   horizon and refine it into Creator Handoff + Creator Result packages with
   machine-readable manifests and provenance.

The full ~160-page diary remains outside Phase 1 until the first design logic is approved.
Roadmap promotion does not activate either intake/handoff item.

## Farther practical horizon

Multipage generation, mixed raster/vector composition, vector artwork/trace,
AI routing and semantic edits, generative assets, review/print PDF, CMYK/ICC,
fonts and image-resolution checks, preflight, experiment metrics, structural
and visual regression.

`GDL-F06` Design Package and `GDL-F07` Wizard/operator intake retain their stable
IDs but are promoted to the near-term planning horizon as of 2026-09-28.

## Intake / creator-handoff priority refinement

The first low-programming automation target is deliberately simple:

```text
customer files + references + product playbook
        ↓
guided intake / Design Brief Builder
        ↓
normalized design request + asset mapping
        ↓
Creator Handoff Package
        ↓
specialized creator
        ↓
Creator Result Package
(editable artifact + preview + machine-readable manifest)
```

Ambiguous file-to-role mapping must be surfaced for human confirmation rather
than silently guessed. The first planned pilot is a repeated greeting-card
workflow with a stable template; the second is a business-card guided wizard.

The Capability Catalog is a separate planning/reference surface, cross-linked to
roadmap IDs. It records what ForPrint can already do, can experimentally do, or
may evaluate later without granting runtime/provider/production authority.

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

## H2 deterministic SVG implementation note

The H1 contract foundation is verified and published at `4df34d8`. H2 now implements a deterministic Python-stdlib SVG compiler and structural validation **pending H2 validation and acceptance**.

A required schema refinement accompanies H2: monthly/weekly calendar periods are explicit Design Spec data and are never inferred from stable IDs. The 014 preflight found no confirmed SVG-to-preview renderer, so PNG/PDF preview remains unresolved and no provider is selected.

## H2 published checkpoint

Published commit: `b410860da4ce3d377e095d870f50f188c1f02f56`.

Verified at this checkpoint: deterministic Design Spec → editable SVG compilation,
explicit calendar-period semantics, stable object-ID preservation, semantic
`style_ref`/CMYK metadata preservation, structural SVG validation, temporary
artifact manifest/report, 38 tests, governance and continuity checks.

`GDL-N04` is verified. `GDL-N05` is only partially verified because PNG preview,
review PDF and visual regression remain unresolved. `GDL-N07` is partially
verified for the product-profile contract and dated-diary A5 profile only.
Graphic Design Lab runtime and production write remain disabled.


## Post-H2 visual-baseline reconciliation

After the H2 checkpoint, a bounded `librsvg / rsvg-convert` SVG→PNG review-preview
candidate was experimentally verified. It remains **NOT SELECTED** as the
canonical provider and PNG remains a review artifact, not a production print
artifact.

Monthly and weekly visual-baseline refinements were published at `f0559f5` and
`8103ef6`. The later weekly closeout passed 48 repository tests plus governance,
continuity and structural SVG validation.

`GDL-N06` is now partially implemented/verified for the internal Abram Phase 1
monthly, partial-week, full-week and transition-week visual baselines. This is
not customer approval and does not authorize full diary rollout.

The current practical planning focus has moved to Product-Playbook-driven Guided
Design Intake / Design Brief Builder and structured Creator Handoff/Result
packages.

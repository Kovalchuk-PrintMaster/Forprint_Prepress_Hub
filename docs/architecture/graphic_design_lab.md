# Graphic Design Lab architecture boundary

`Graphic Design Lab` is an `EXPERIMENTAL_CAPABILITY_INSIDE_EXISTING_MODULE`
owned locally by `forprint_prepress_hub`.

It is not a separate ForPrint service and does not own pricing, accounting,
operational order truth, cross-module transport, physical printer configuration,
or System Blueprint architecture.

## Core model

The planned source of truth is a structured Design Specification. SVG, preview
PNG/PDF and production PDF are outputs with different roles.

Planned entities: document, page/spread, stable object IDs, text/vector/raster/
dynamic objects, layers, assets/references with provenance, typography/colors,
design tokens, constraints, product profile, revision/patch, artifact manifest
and validation report.

## Execution model

Use deterministic composition for mechanically provable geometry, text,
calendars, rules, QR/barcodes and similar elements. Specialized vector, raster,
PDF and optional AI providers remain adapters/executors.

This preserves the recovered Prepress direction: product-specific Photoshop,
Illustrator, CorelDRAW and PDF/Acrobat behavior may remain specialized while
shared fact-oriented inspection and orchestration are reused.

Prefer Unix-first execution where practical. A Windows graphics workstation may
later be a bounded specialist quality executor, not the orchestration authority.

## Edit routing

`DIRECT_EDIT`, `LAYOUT_EDIT`, `SEMANTIC_EDIT`, `GENERATIVE_EDIT`,
`FULL_REGENERATION`. Bounded object/revision patches are preferred where possible.

## Configuration

Business logic must resolve paths and providers through
`config/graphic_design_lab.yaml`. No provider is selected by this planning step.

## Pilot

The first practical pilot is Abram Diary Phase 1. Full diary rollout is not
authorized by this document.

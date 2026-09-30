# ForPrint Graphic Design Lab — Capability Catalog v0.1

Status: **planning/reference catalog**. This is not execution, provider-selection,
runtime-initialization, acceptance, release, or production authority.

The roadmap answers **what we decided to develop and in what planning horizon**.
This catalog answers **what design/prepress capabilities exist, are experimentally
proven, are planned, or are strategically worth remembering**.

## Current practical chain

```text
raw customer input
    ↓
Product Playbook
    ↓
Guided Design Intake / Design Brief Builder
    ↓
Creator Handoff Package
    ↓
specialized creator
    ↓
Creator Result Package
    ↓
editable artifact + PNG review preview + machine-readable manifest
```

`librsvg / rsvg-convert` is recorded only as an **experimentally verified**
SVG→PNG review-preview candidate. It is not a selected canonical provider and
PNG is not a production print artifact.

A Product Playbook is the planned bridge between reusable Product Profile rules
and the operator-facing wizard. It can define standard options, expected assets,
question order, mapping hints and creator instructions.

Classical raster→vector trace remains a practical planned capability. Semantic
reconstruction and hybrid raster/vector rebuilding remain farther/strategic
because they aim to recover editable meaning rather than only paths.

First planned intake/handoff pilots:

1. recurring greeting-card workflow;
2. business-card guided wizard.

Catalog presence does not activate either pilot.


## Verified intake/handoff capability slice

The deterministic intake/handoff foundation now has verified partial
implementation:

- Product Playbook — generic contract plus
  `recurring_greeting_card_v0_1`;
- Guided Design Intake — deterministic answer validation, normalized request
  generation and explicit ambiguity handling;
- Creator Handoff Package — deterministic creator brief, machine-readable
  design request and asset/reference mapping.

Implementation evidence: `730134323b814929380d8d6287dbbcb088504116` with hygiene follow-up `e7cf1151a123eb4acc3135a29fe37acd79c9b630`.

`creator_result_package` remains `PLANNED_NEAR_TERM`.
The business-card guided wizard remains deferred and is not activated by this
capability evidence. Provider selection, creator execution, runtime
initialization and production write remain outside this state.

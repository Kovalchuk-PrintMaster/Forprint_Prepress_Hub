# ForPrint Prepress Hub

ForPrint Prepress Hub is the ForPrint module responsible for the prepress and
file-preparation lifecycle.

## Current state

Assistant continuity is `SELF_ONBOARD_VERIFIED`.

The repository has a validated module foundation plus the planning/configuration
baseline for the experimental Graphic Design Lab capability. Graphic Design Lab
runtime remains `PLANNED_NOT_INITIALIZED`.

It does **not** claim production prepress or production design-generation capabilities.

## Safety boundary

This bootstrap does not enable:

- live printer/device control;
- production hot folders or background workers;
- live Integration Gateway writes;
- automatic customer-file mutation;
- production AI generation;
- Graphic Design Lab runtime.

## Operator map

```bash
make help
make test
make bootstrap-check
make governance-check
make status
```

The supported project environment is `.venv_prepress_hub`.

## Assistant continuity

Fresh-worker continuity is module-local and uses the live read-only System
Blueprint as its governance/reference source.

Supported operator commands:

```text
make assistant-handoff-check
make assistant-pack
make assistant-context-pack TOPICS=graphic_design_lab
```

`assistant-pack` produces `MODULE_ONBOARD`; `assistant-context-pack` produces
`MODULE_CONTEXT`. Generated packages live under ignored `tmp/` and carry zero
execution/acceptance/release authority.

The canonical module manifest remains
`coordination/module/manifest.yaml`; no root compatibility manifest is used.

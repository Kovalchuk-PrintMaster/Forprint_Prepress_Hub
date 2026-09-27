# ForPrint Prepress Hub — START HERE

This is the canonical module-local fresh-worker bootstrap entrypoint.

## Reading order

1. `AGENTS.md`
2. `README.md`
3. `coordination/module/manifest.yaml`
4. `coordination/status/current_status.yaml`
5. `coordination/bootstrap/module_bootstrap_manifest.yaml`
6. `coordination/blueprint_source.yaml`
7. `docs/architecture/module_boundary.md`
8. `Makefile`

Then re-read the live System Blueprint sources referenced by the assistant
continuity package before changing canonical module state.

## Continuity commands

```text
make assistant-handoff-check
make assistant-pack
make assistant-context-pack TOPICS=graphic_design_lab
```

Semantics:

```text
assistant-pack         -> MODULE_ONBOARD
assistant-context-pack -> MODULE_CONTEXT
```

These packages are navigation/evidence only. They grant zero execution,
dispatch, acceptance, roadmap mutation, release, production, commit, push,
merge, or cross-repository write authority.

## Owner clean-root directive

The canonical module manifest is:

`coordination/module/manifest.yaml`

Do not create a compatibility copy at repository root. Generic continuity
tooling must resolve the canonical structured path.

## Current boundary

Graphic Design Lab remains `EXPERIMENTAL_CAPABILITY_INSIDE_EXISTING_MODULE`
owned by `forprint_prepress_hub`, but its runtime is not initialized by this
continuity commissioning step.

System Blueprint is read-only from this repository.

## Continuity package authority boundary

`MODULE_ONBOARD` and `MODULE_CONTEXT` are context-transfer artifacts only.

They do not grant execution authority, implementation authorization,
acceptance authority, release authority, or permission to mutate
ForPrint System Blueprint.

Allowed work must be derived from current module state, local policy,
explicit human authorization, and applicable System Blueprint governance.

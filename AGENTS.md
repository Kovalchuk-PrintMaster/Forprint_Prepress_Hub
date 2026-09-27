# ForPrint Prepress Hub — assistant/operator entrypoint

A fresh worker must reconstruct the current module state from canonical
repository surfaces, not from chat history.

## Reading order

1. `README.md`
2. `coordination/module/manifest.yaml`
3. `coordination/status/current_status.yaml`
4. `coordination/README.md`
5. `config/README.md`
6. `docs/architecture/module_boundary.md`
7. `Makefile`

## Authority

- ForPrint System Blueprint remains the cross-module architecture and governance
  authority.
- This repository owns local Prepress Hub implementation and evidence.
- If architecture, ownership, governance, or cross-module policy is ambiguous,
  stop the conflicting part and prepare a precise technical handoff to System
  Blueprint through the human operator.
- Do not edit System Blueprint from this repository.

## Working rules

- Keep governed work on a clean Git tree.
- Treat `tmp/` and root `tmp.py` as local operator workspace, never canonical
  project knowledge.
- Add tests from the first implementation step.
- Keep supported operator workflows visible in the Makefile.
- Use exact-path staging; never broad `git add .` or `git add -A`.
- Do not erase or normalize foreign work.
- Keep physical storage paths out of business logic; later storage capabilities
  must use configuration/logical roles.
- Graphic Design Lab is planned but not initialized by foundation bootstrap.

## Fresh-worker continuity

Canonical bootstrap entrypoint: `coordination/bootstrap/START_HERE.md`.

Before canonical work, use `make assistant-handoff-check`. For replacement
assistant onboarding use `make assistant-pack` (`MODULE_ONBOARD`). For bounded
topic continuation use `make assistant-context-pack TOPICS=<topic>`
(`MODULE_CONTEXT`).

These packages are evidence/navigation only and grant zero execution,
acceptance, release, production, Git mutation, or Blueprint-write authority.

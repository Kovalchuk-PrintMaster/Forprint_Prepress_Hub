# ForPrint Prepress Hub

ForPrint Prepress Hub is the ForPrint module responsible for the prepress and
file-preparation lifecycle.

## Current state

`BOOTSTRAP_FOUNDATION`

The repository currently provides only the module foundation: canonical
identity, operator map, configuration boundary, coordination/status surfaces,
architecture boundary, validation, and tests.

It does **not** claim production prepress capabilities.

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

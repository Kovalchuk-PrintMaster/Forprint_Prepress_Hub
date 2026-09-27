# Configuration

Environment-dependent settings belong under `config/`.

When storage is implemented, business logic must address logical storage roles
rather than hard-coded physical server paths. Physical filesystem, NAS, object
storage, or other backends are later implementation choices.

No production storage backend is configured by foundation bootstrap.

## Graphic Design Lab planning configuration

`graphic_design_lab.yaml` defines planning-time logical path roles and unresolved provider candidates. It does not enable a storage backend, graphics provider, AI provider, or production runtime.

Business logic must resolve these logical roles through configuration rather than embedding physical server/NAS/workstation paths.

# Configuration

Environment-dependent settings belong under `config/`.

When storage is implemented, business logic must address logical storage roles
rather than hard-coded physical server paths. Physical filesystem, NAS, object
storage, or other backends are later implementation choices.

No production storage backend is configured by foundation bootstrap.

# External artifact reference guideline — draft

Keep heavy design/source files outside this working knowledge package.

Prefer references such as:

```yaml
external_artifact_ref:
  storage_role: customer_job_storage
  customer_ref: customer_XXXX
  order_ref: order_YYYY
  artifact_ref: result_r001
```

Avoid customer PII in Git-oriented research metadata unless strictly necessary.

The empirical case should preserve enough information to find the source/result through the proper operational system, not become the customer registry.

## Governed validation boundary

- Git empirical records must set `repository_contains_heavy_artifact: false`.
- Git empirical records must set `pii_allowed_in_git: false`.
- Design/source/result binaries remain outside this evidence surface.
- The case records a stable external locator/reference, not the heavy artifact itself.
- Customer/order identifiers are non-PII references, not customer registry data.

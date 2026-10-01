# ForPrint GDL Empirical Case — MENU-001 / Run 1

Status: **DRAFT / EMPIRICAL / NON-CANONICAL**

Case:
- customer ref: Vitaliy
- venue: `Рибацький стан`
- product: simple restaurant menu
- chain: `GDL Intake Analyst -> Creator Assistant`
- experiment state: first real two-assistant run observed

This package captures:
- what worked;
- what failed;
- which failures belong to Intake;
- which belong to Creator;
- which belong to the handoff/output contract itself;
- candidate changes for the next loader versions.

This is learning evidence, not yet canonical GDL policy.

`SYSTEM_BLUEPRINT_ACCESS_FROM_PREPRESS=READ_ONLY_STRICT`

## Customer feedback delta — review-readiness failure

After the first visual result, the customer accepted the **visual direction** but rejected
the **content fidelity** because the returned menu did not contain the customer's real menu data.

This creates a separate empirical failure class:

```text
visually plausible
!= factually compliant
!= customer-review-ready
```

Future Creator outputs must explicitly declare review-readiness and whether they may be
forwarded to the customer. Style-only or placeholder-based visuals must be visibly marked
as non-customer content and must not be forwarded as a customer menu.

## Creator iteration 002 â€” content correction became CONTENT_PARTIAL

The second Creator iteration materially improved content fidelity and used substantially
more real customer menu data. It still failed customer-review readiness because the visible
scope was incomplete, page numbering implied false completeness, stray template/layout
artifacts remained, and the visual direction drifted from the earlier style the customer liked.

Iteration 002 is preserved as evidence and classified `CONTENT_PARTIAL`.
The case now waits for `CREATOR-ITERATION-003`; Intake is not restarted.

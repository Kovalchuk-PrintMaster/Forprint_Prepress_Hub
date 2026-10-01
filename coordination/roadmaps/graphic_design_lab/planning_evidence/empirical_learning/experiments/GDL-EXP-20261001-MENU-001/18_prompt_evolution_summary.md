# MENU-001 prompt evolution â€” primary empirical finding

## Current strongest finding

Across the MENU-001 correction chain, the clearest observed improvement appeared when
Creator instructions moved from human-style descriptive prose to explicit machine-readable
execution patches.

This is not yet universal causal proof. The case also accumulated cleaner source data and
more specific constraints over time. But the association is strong enough to treat
**structured prompt representation as the primary empirical finding of this case**.

## Observed sequence

### Descriptive correction prose

Broad human-readable review explained what was wrong and what should improve.

Observed problem: Creator repeatedly reintroduced demo/generic restaurant content, changed
already-correct values, or solved layout pressure by dropping confirmed rows.

### `CREATOR_EXECUTION_PATCH_v0_8`

The instruction became an execution contract with explicit mode, visual freeze, source
authority, exact remove/correct/add sets and final failure gates.

Outcome: demo contamination fell sharply and visible factual accuracy improved.

### `CREATOR_EXECUTION_PATCH_v0_9`

The prompt narrowed to completeness reconciliation: preserve existing verified rows, restore
named missing confirmed rows, enumerate allowed space-management actions, and prohibit
removing confirmed content.

Outcome: the remaining defect surface narrowed to a small known omission set.

### `CREATOR_FINAL_RECONCILIATION_PATCH_v1_0`

The patch became minimal and surgical: modify only explicitly listed items, restore the
remaining confirmed rows, remove unsourced copy, keep verified data locked, and output only
after the final gate.

Outcome: the working confirmed set passed review and the result became a customer-review candidate.

## Working interpretation

The useful unit is not merely "YAML instead of prose".

The apparent gain comes from making the instruction structurally explicit and machine-oriented:

```text
MODE
â†’ LOCKS
â†’ DATA_AUTHORITY
â†’ PRESERVE / REMOVE / CORRECT / ADD
â†’ SPACE_MANAGEMENT
â†’ UNRESOLVED_POLICY
â†’ FINAL_GATE
â†’ OUTPUT_STATUS
```

For high-risk corrections, prose should provide brief human context, while the executable
constraint set should be represented in a structured form.

## Status

`PRIMARY_EMPIRICAL_FINDING / STRONG_HYPOTHESIS`

Do not promote to universal GDL policy until reproduced on additional real cases.

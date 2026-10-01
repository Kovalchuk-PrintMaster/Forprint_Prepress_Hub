# GDL prompt evidence

All materially used prompts should be preserved or referenced so we can learn which
prompt forms actually work.

This includes:

- Intake loaders;
- Creator requests;
- correction patches;
- final reconciliation prompts;
- important customer-facing request/approval messages when their form is part of an experiment.

Do not store customer PII or heavy customer assets in Git.

## Effectiveness principle

A prompt is not "good" merely because it is structured.

Evaluation should link:

```text
prompt
→ context
→ creator/intake result
→ operator assessment
→ customer outcome
→ revision count / failure modes
```

The current machine-readable prompt-format finding remains an empirical hypothesis until
supported by broader cases.

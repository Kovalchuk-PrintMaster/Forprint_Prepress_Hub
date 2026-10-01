# GDL Empirical Learning Methodology v0.1

## Strategic purpose

ForPrint Graphic Design Lab should learn from real production work before broad automation is frozen.

The target is not “write many scripts” and not “make one AI do everything”.

The target is to determine, from evidence, the shortest stable path from a real customer request to an acceptable design result, and then decide which tasks should belong to:

- GDL Intake Analyst;
- Creator Assistant;
- local deterministic/specialized tools;
- human operator/customer confirmation.

## Two-assistant experimental chain

### Role 1 — GDL Intake Analyst

Owns:
- raw dialogue analysis;
- source-material analysis;
- extraction of facts;
- uncertainty preservation;
- minimal customer clarification;
- copy-ready customer messages;
- normalized brief;
- Creator Handoff preparation.

Does not own:
- final visual design;
- production approval;
- invented customer facts.

### Role 2 — Creator Assistant

Owns:
- visual implementation from a prepared Creator Handoff;
- first reviewable concept;
- later revisions when requested.

Does not own:
- silently inventing factual content;
- replacing customer/operator confirmation;
- declaring production readiness unless a later governed contour explicitly authorizes it.

## Experiment rule

Expectations must be written before each assistant run.

After a run, do not rewrite the expectation to match the result.

Instead record:
- expected behavior;
- actual behavior;
- delta;
- whether the assistant or the original expectation was more correct;
- lessons for the next loader/pattern version.

## Evidence rule

Successful and failed prompts are both valuable.

A failed result must not be deleted merely because it is bad. It should become evidence with a reason.

One case may create a hypothesis.
One case must not silently become a global policy.

## Minimal customer-contact principle

Use existing information first.

Ask the customer only for information that materially blocks a useful first result.

If a first reviewable concept can be produced safely, prefer:
first concept → concrete feedback
over:
long abstract questionnaire → delayed first concept.

## Versioning rule

Loader changes create a new version.

Example:
- GDL-INTAKE-MENU-v001
- GDL-INTAKE-MENU-v002

Do not overwrite prior behavior history.

## Output-quality distinctions

Keep separate:
- technically valid;
- reviewable;
- operator accepted;
- customer accepted;
- customer explicitly satisfied;
- production ready.

These states are not synonyms.

## Empirical amendment â€” structured prompt representation

Current primary empirical finding from `GDL-EXP-20261001-MENU-001`:

> For high-constraint Creator corrections, machine-readable structured execution patches
> currently produce materially better convergence than human-style descriptive prose.

Treat this as a **strong hypothesis**, not universal policy yet.

Recommended experimental default:

```text
short human context
+
machine-readable execution patch
```

The structured patch should separate immutable and mutable surfaces and explicitly carry:
`MODE`, `LOCKS`, `DATA_AUTHORITY`, `PRESERVE`, `REMOVE`, `CORRECT`, `ADD`,
`SPACE_MANAGEMENT`, `UNRESOLVED_POLICY`, `FINAL_GATE`, and `OUTPUT_STATUS`.

Do not infer that YAML syntax itself is the cause. The observed benefit may come from the
combination of structure, specificity, explicit state and bounded mutation rules.

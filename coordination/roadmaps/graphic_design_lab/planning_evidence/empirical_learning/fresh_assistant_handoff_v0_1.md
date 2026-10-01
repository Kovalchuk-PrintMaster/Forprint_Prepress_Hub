# Fresh assistant handoff â€” GDL empirical lane

A fresh assistant must be able to resume this work without prior chat history.

## Current methodology

The active manual empirical chain is:

```text
real customer case
â†’ fixed case context
â†’ versioned loader
â†’ expectations frozen BEFORE run
â†’ GDL Intake Analyst
â†’ raw response preserved
â†’ expectation-vs-actual evaluation
â†’ Creator Handoff
â†’ Creator Assistant
â†’ raw creator result preserved
â†’ operator/customer outcome
â†’ case lessons
â†’ next loader/pattern version
```

Roles:
- **GDL Intake Analyst** analyzes dialogue/source materials, preserves uncertainty,
  minimizes customer friction, and prepares Creator Handoff.
- **Creator Assistant** is the visual execution role. It must create the requested
  visual result rather than generate another brief.

## Latest baseline

`GDL-EXP-20261001-MENU-001 / RUN-001`, venue `Ð Ð¸Ð±Ð°Ñ†ÑŒÐºÐ¸Ð¹ ÑÑ‚Ð°Ð½`.

The same run is not repeated. It is preserved as baseline evidence.

Strong hypotheses learned:
- unintended mixed-language customer-facing content must be detected before Creator handoff;
- Creator role must be explicitly executable, not merely descriptive;
- FIRST_REVIEWABLE_CONCEPT needs an artifact contract;
- mandatory identity/content elements need a pre-return compliance check.

Open hypotheses:
- two meaningfully different first-review variants may be preferable for open visual tasks;
- SVG may be a useful primary editable source for menu-like layouts.

Before acting, read:
1. `current_learning_state.yaml`
2. `methodology_v0_1.md`
3. `chain_registry_v0_1.yaml`
4. `assistant_role_contracts_v0_1.yaml`
5. latest experiment `README.md` and `03_cross_run_lessons.yaml`

System Blueprint remains strictly read-only from Prepress:
`SYSTEM_BLUEPRINT_ACCESS_FROM_PREPRESS=READ_ONLY_STRICT`.

## New review-readiness lesson from MENU-001

The first menu case exposed a critical distinction:

- the customer may approve the visual direction;
- the same output may still fail content fidelity;
- a visually plausible output is not automatically customer-review-ready.

Every Creator result must therefore declare an explicit output classification and
`customer_forwarding_allowed`. A style-only visual using placeholder/non-customer content
must be marked `STYLE_ONLY_REFERENCE`, visibly labeled as not being the customer's menu,
and blocked from customer forwarding.

Next Creator loader candidate: `GDL-CREATOR-v002`.

## MENU-001 current stage â€” awaiting Creator iteration 003

Creator iteration 002 improved factual content but is still `CONTENT_PARTIAL` and must not
be treated as customer-review-ready.

Known remaining defects:
- visible template/layout debris;
- incomplete confirmed menu scope;
- pagination implying false completeness;
- excess unused layout area;
- drift from the earlier preferred visual direction.

The next case-local instruction is
`experiments/GDL-EXP-20261001-MENU-001/15_creator_correction_instruction_v0_3.md`.

Do not restart Intake. Wait for Creator iteration 003 and evaluate it against:
content fidelity, scope completeness, artifact cleanliness, language, visual-direction
continuity, and explicit `customer_forwarding_allowed`.

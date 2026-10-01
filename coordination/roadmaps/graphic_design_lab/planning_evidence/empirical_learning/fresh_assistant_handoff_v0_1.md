# Fresh assistant handoff — GDL empirical lane

A fresh assistant must be able to resume this work without prior chat history.

## Current methodology

The active manual empirical chain is:

```text
real customer case
→ fixed case context
→ versioned loader
→ expectations frozen BEFORE run
→ GDL Intake Analyst
→ raw response preserved
→ expectation-vs-actual evaluation
→ Creator Handoff
→ Creator Assistant
→ raw creator result preserved
→ operator/customer outcome
→ case lessons
→ next loader/pattern version
```

Roles:
- **GDL Intake Analyst** analyzes dialogue/source materials, preserves uncertainty,
  minimizes customer friction, and prepares Creator Handoff.
- **Creator Assistant** is the visual execution role. It must create the requested
  visual result rather than generate another brief.

## Latest baseline

`GDL-EXP-20261001-MENU-001 / RUN-001`, venue `Рибацький стан`.

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

## MENU-001 current stage — awaiting Creator iteration 003

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

## Primary empirical finding — prompt representation

The strongest current learning from MENU-001 is that structured, machine-readable Creator
execution patches produced markedly better convergence than descriptive human-style correction
text.

Status: `STRONG_HYPOTHESIS`, not yet universal policy.

For the next relevant real cases:
- keep prose short and contextual;
- carry high-risk execution constraints in structured fields;
- explicitly define locks, data authority, allowed mutations, forbidden mutations and final gates;
- collect comparable evidence before promoting this to canonical GDL policy.

Evidence:
`experiments/GDL-EXP-20261001-MENU-001/17_prompt_format_effect_observation.yaml`

## Active bounded empirical prompt

- Prompt: `prepress_gdl_creator_empirical_learning_foundation_v0_1`
- State: active module-owned prompt with local implementation complete and evidence ready for Blueprint review.
- Operator validation: `make gdl-empirical-check`.
- Discovery: `make gdl-empirical-index`.
- Human-readable summary: `make gdl-empirical-summary`.
- Local completion evidence: `coordination/reports/completion/prepress_gdl_creator_empirical_learning_foundation_v0_1_completion.md`.
- Verified implementation/evidence commit: `0f83e6ab581e2cba92f1f0bb4c95b6b2c9ab099d`.
- Next contour activated: `false`.
- System Blueprint remains `READ_ONLY_STRICT` from Prepress.
- Provider execution, runtime initialization, production write and next-contour activation remain false.

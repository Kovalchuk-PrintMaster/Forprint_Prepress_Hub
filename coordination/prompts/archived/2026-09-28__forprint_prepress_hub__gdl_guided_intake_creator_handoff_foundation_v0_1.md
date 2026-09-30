# ForPrint Prepress Hub — GDL Guided Intake / Creator Handoff Foundation v0.1

## Prompt identity

- Prompt ID: `prepress_gdl_guided_intake_creator_handoff_foundation_v0_1`
- Target module: `forprint_prepress_hub`
- Capability: `graphic_design_lab`
- Blueprint request ID: `PREPRESS-BLUEPRINT-REQUEST-GDL-INTAKE-HANDOFF-PROMPT-PUBLICATION-20260928-v0_1`
- Source module baseline at publication request: `4acdd4b548604a2d51b1d128a6cf2da4f75aebdd`
- Execution scope: `BOUNDED_GDL_GUIDED_INTAKE_CREATOR_HANDOFF_FOUNDATION`
- Primary pilot: `recurring_greeting_card_v0_1`
- Queue state: `ready_for_module_pull`

## Authority

This is an executable bounded Blueprint prompt.

Publication makes the prompt available for module pull. It does not itself activate
Prepress Hub implementation.

Before implementation, Prepress Hub must synchronize this prompt through its own
formal module-owned prompt intake workflow and establish exactly one relevant active
prompt.

System Blueprint access from Prepress remains:

`SYSTEM_BLUEPRINT_ACCESS_FROM_PREPRESS=READ_ONLY_STRICT`

Prepress Hub must not create, edit, stage, commit, push, apply, release, or otherwise
mutate System Blueprint files or Git state.

## Goal

Prove the smallest practical deterministic foundation:

```text
product-specific playbook
        ↓
raw/sanitized customer inputs
        ↓
normalized guided-intake request
        ↓
explicit asset/reference mapping
        ↓
Creator Handoff Package
```

The first product-specific pilot is the recurring greeting-card workflow.

The business-card wizard remains a later validation scenario and is not part of this
execution contour.

## Mandatory disposition before implementation

Use:

`REUSE / EXTEND / ADAPT / REPLACE / NEW`

Approved disposition:

### ADAPT

Adapt existing Product Profile semantics into a separate Product Playbook layer.

Product Profile remains reusable physical/layout product semantics.

Product Playbook is a separate reusable operator/intake layer.

### EXTEND

Extend:

- `GDL-F07` with `guided_intake_v0_1`;
- `GDL-F06` with `creator_handoff_v0_1`.

### REUSE

Reuse:

- `asset_reference_v0_1` identity semantics;
- `asset_reference_v0_1` provenance semantics;
- existing validation patterns;
- existing test patterns;
- existing Makefile/operator patterns.

### NEW

`NEW` is authorized only after absence evidence for:

- generic `product_playbook_v0_1` if no equivalent current contract exists;
- `recurring_greeting_card_v0_1`;
- sanitized recurring greeting-card fixture;
- minimal deterministic builder/validator support not already available.

### REPLACE

No replacement is authorized by default in this contour.

If materially equivalent current implementation exists, reuse or adapt it rather than
creating a competing surface.

## Authorized work

Only the following work is authorized:

1. `product_playbook_v0_1`;
2. reusable `recurring_greeting_card_v0_1` playbook;
3. `guided_intake_v0_1`;
4. `creator_handoff_v0_1`;
5. sanitized recurring greeting-card regression fixture;
6. minimal deterministic builder/validator support under the existing
   `app/graphic_design_lab/` package;
7. focused tests from the first implementation step;
8. supported Makefile operator validation workflow;
9. verified local implementation evidence after implementation is actually proven.

Do not broaden this list implicitly.

## Product Profile vs Product Playbook

Product Profile owns reusable physical/layout product semantics.

Do not place customer-instance content, unresolved intake state, questionnaire state,
or customer-specific asset mapping into Product Profile.

Product Playbook may define reusable product-specific intake/operator semantics:

- standard questions;
- deterministic answer choices;
- required and optional information;
- expected asset/reference roles;
- required and optional roles;
- mapping hints;
- creator instructions;
- final-open-question behavior.

The playbook must remain reusable across customer instances.

## Guided Intake vs Design Specification

Guided Intake is explicitly pre-Design-Spec.

`guided_intake_v0_1` may contain:

- normalized request data;
- answered questions;
- unresolved questions;
- asset/reference assignments;
- mapping state;
- mapping source;
- optional mapping note;
- explicit human-confirmation requirement for ambiguous mappings.

Do not overload `design_spec_v0_1` with intake-state, unresolved-question, or ambiguity
semantics.

## Asset/reference mapping

`asset_reference_v0_1` remains the owner of asset/reference identity and provenance.

Guided Intake / Creator Handoff must extend mapping semantics by reference only.

Do not create a competing asset identity or provenance model.

Allowed deterministic mapping states:

```text
CONFIRMED
PROPOSED
UNRESOLVED
```

Ambiguous mapping must follow:

```text
ambiguity detected
        ↓
PROPOSED or UNRESOLVED
        ↓
human_confirmation_required = true
```

Do not silently resolve ambiguity.

Do not invent numeric confidence scores.

`CONFIRMED` requires an explicit deterministic basis such as direct
operator/customer assignment or a previously confirmed mapping represented by the
input contract.

## Creator Handoff

`creator_handoff_v0_1` is the deterministic boundary delivered to a creator.

It may reference:

- normalized design request;
- Guided Intake identity/version where useful;
- asset/reference IDs;
- provenance references;
- resolved and unresolved mapping state;
- creator brief;
- required output expectations.

Creator execution is not authorized by this prompt.

## Recurring greeting-card pilot fixture

The sanitized regression fixture must prove:

- customer notes;
- greeting text or greeting-document reference;
- logo reference;
- multiple photo references;
- at least one intentionally ambiguous mapping;
- ambiguous mapping remains `PROPOSED` or `UNRESOLVED`;
- human confirmation is required for ambiguity;
- normalized guided-intake output;
- deterministic Creator Handoff Package generation;
- deterministic handoff validation.

The fixture must contain no live customer-sensitive content.

## Deterministic implementation behavior

Add only the smallest support required to:

1. validate Product Playbook;
2. normalize sanitized pilot input according to the playbook;
3. construct explicit mapping state;
4. preserve unresolved ambiguity rather than guessing;
5. require human confirmation where required;
6. build a deterministic Creator Handoff Package;
7. validate the resulting handoff.

Do not initialize Graphic Design Lab runtime.

Do not invoke provider execution.

Do not introduce background execution.

## Focused tests

Tests must begin with the implementation.

At minimum prove:

- generic Product Playbook validation;
- recurring greeting-card playbook validation;
- normalized Guided Intake generation;
- answered versus unresolved question preservation;
- reuse of asset/reference identity rather than recreation;
- deterministic validation of `CONFIRMED`, `PROPOSED`, and `UNRESOLVED`;
- ambiguous mapping requires human confirmation;
- ambiguity is never silently resolved via heuristic confidence;
- deterministic Creator Handoff generation;
- deterministic handoff validation;
- same valid input yields semantically stable output;
- no provider execution is required;
- GDL runtime remains uninitialized;
- production write remains disabled.

Existing GDL tests must remain green.

## Makefile operator surface

Expose one supported operator-facing workflow for the intake/handoff validation
contour.

Reuse the repository's current Makefile naming and implementation pattern.

If no existing equivalent target determines the name, preferred naming is:

`gdl-intake-handoff-check`

Do not duplicate an existing equivalent operator workflow.

## Explicit deferrals

Not authorized in this contour:

- Creator Result Package runtime/contract except a strictly necessary minimal reference;
- creator AI/provider execution;
- image generation provider execution;
- vectorization provider execution;
- provider selection;
- canonical provider selection;
- actual customer-file ingestion;
- Word/DOCX parsing;
- production hot folders;
- background workers;
- review PDF generation;
- print PDF generation;
- production writes;
- Graphic Design Lab runtime initialization;
- full business-card wizard;
- cross-module API/integration;
- new queue/orchestration infrastructure;
- broad redesign/refactor;
- System Blueprint mutation from Prepress Hub.

Adjacent discoveries must be recorded separately and must not expand execution
authority.

## Required pre-execution gate in Prepress Hub

Before modifying implementation files:

1. synchronize this prompt through normal module prompt intake;
2. confirm exactly one relevant active prompt;
3. inspect current Product Profile, GDL-F07, GDL-F06, `asset_reference_v0_1`,
   validators/builders/tests/Makefile surfaces;
4. record REUSE/EXTEND/ADAPT/REPLACE/NEW reconciliation;
5. confirm repository/worktree conditions required by module governance;
6. preserve all explicit deferrals above.

If a conflicting active prompt or ownership conflict exists, stop and return the exact
blocker.

## Local implementation acceptance

The contour is accepted locally only when:

- formal prompt intake is synchronized;
- exactly one relevant execution prompt is active;
- REUSE/EXTEND/ADAPT/REPLACE/NEW reconciliation is recorded;
- focused tests pass;
- sanitized recurring greeting-card regression passes;
- existing GDL tests remain green;
- deterministic ambiguity/human-confirmation behavior is proven;
- `git diff --check` passes;
- governance check passes;
- assistant continuity check passes;
- supported Makefile workflow exists;
- no provider is selected;
- no provider is executed;
- GDL runtime remains `PLANNED_NOT_INITIALIZED`;
- production write remains disabled;
- no live customer-file ingestion occurs;
- no System Blueprint mutation occurs from Prepress Hub;
- local status/roadmap evidence reflects only verified implementation;
- exact implementation evidence is committed and pushed;
- post-push module worktree is clean;
- local module HEAD equals upstream.

Completion does not automatically activate the next GDL contour.

## Required completion report

Return at minimum:

- branch and pre/post HEAD;
- active prompt identity;
- exact changed paths;
- REUSE/EXTEND/ADAPT/REPLACE/NEW disposition;
- contracts added/extended;
- playbook instance;
- fixture;
- deterministic builder/validator behavior;
- focused tests;
- existing GDL regression result;
- Makefile target added/reused;
- governance result;
- assistant-continuity result;
- `git diff --check` result;
- provider-selection state;
- GDL runtime state;
- production-write state;
- Blueprint-mutation state;
- commit hash(es);
- push result;
- clean post-push proof;
- unresolved follow-up candidates outside this contour.

## Stop conditions

Stop instead of broadening if:

- an equivalent current Product Playbook / Guided Intake / Creator Handoff contract
  already exists and requires reconciliation;
- Product Profile ownership would need to change;
- `asset_reference_v0_1` identity/provenance ownership would need to change;
- provider selection or execution becomes required;
- GDL runtime initialization becomes required;
- production writes become required;
- cross-module API/integration becomes required;
- Blueprint mutation from Prepress becomes required;
- another active module prompt conflicts;
- repository baseline materially invalidates the reconciled assumptions;
- governance/continuity rules reject the intended write-set.

Report exact evidence. Do not substitute a broader redesign.

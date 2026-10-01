# ForPrint Prepress Hub — GDL Creator Empirical Learning Foundation v0.1

## Prompt identity

- Prompt ID: `prepress_gdl_creator_empirical_learning_foundation_v0_1`
- Target module: `forprint_prepress_hub`
- Capability: `graphic_design_lab`
- Source package: `prepress_gdl_empirical_learning_and_future_horizon_20261001_v0_1`
- Blueprint horizon registry: `coordination/internal_work/blueprint/roadmap_enrichment/prepress_gdl/2026-10-01__gdl_empirical_learning_horizon_v0_1/reconciliation_and_horizon_registry_v0_1.yaml`
- Blueprint preparation baseline: `c90d1c82305f482540d1b25872e37d5fcc5ea5ee`
- Prepress baseline observed during reconciliation: `2039f482eaabe5b50f8fb55c44152906dee55c58`
- Queue state: `ready_for_module_pull`
- Execution scope: `BOUNDED_GDL_CREATOR_EMPIRICAL_LEARNING_FOUNDATION`

## Authority

This is one bounded executable Blueprint prompt.

Blueprint publication makes the prompt available for module pull. It does **not**
activate Prepress implementation by itself.

Prepress Hub must consume/synchronize the prompt through its own formal module-owned prompt
lifecycle before implementation.

`SYSTEM_BLUEPRINT_ACCESS_FROM_PREPRESS=READ_ONLY_STRICT`

Prepress must not create, edit, stage, commit, push, release, or otherwise mutate System
Blueprint files or Git state.

Completion of this contour does not activate sequence 2.

## Source intent

Purpose:

Establish the smallest governed foundation for capturing, comparing and learning from real Creator-facing design cases before broader GDL automation is implemented.

Why first:

Current development can already define contracts and deterministic mechanics, but the next architectural decisions should be driven by real evidence about customer request patterns, operator usability, prompt effectiveness, Creator strengths/weaknesses, revision behavior, and customer acceptance.

Primary outcome:

A lightweight, operator-usable empirical case system plus a manual experimentation protocol that lets the Human Owner and assistant collect real cases immediately while worker-built mechanics mature around them.

## Blueprint reconciliation

The prior Guided Intake / Creator Handoff foundation is accepted and must be **reused**.

Observed live states:

- `GDL-N07`: `PARTIAL_IMPLEMENTED_VERIFIED`
- `GDL-F07`: `PARTIAL_IMPLEMENTED_VERIFIED`
- `GDL-F06`: `PARTIAL_IMPLEMENTED_VERIFIED`
- `creator_result_package`: `PLANNED_NEAR_TERM`
- GDL runtime initialized: `false`
- production write enabled: `false`
- previous prompt accepted/completed: `true`
- active local Prepress prompt before publication: `null`

- existing empirical-learning planning/evidence baseline: `PRESENT`
- empirical-learning baseline commit: `2039f482eaabe5b50f8fb55c44152906dee55c58`
- empirical-learning planning/evidence file count observed: `34`
- empirical-learning authority: `PLANNING_EVIDENCE_NOT_GDL_RUNTIME_AUTHORITY`

The existing `coordination/roadmaps/graphic_design_lab/planning_evidence/empirical_learning/`
surface is a known reusable baseline, not a surprise blocker. It already includes an
empirical case template, experiment lifecycle, methodology/index surfaces,
menu/business-card/flyer loaders, failure-mode evidence and
`GDL-EXP-20261001-MENU-001`.

### REUSE

- existing empirical-learning planning/evidence surface from Prepress commit `2039f48`;
- existing empirical case template and experiment lifecycle;
- existing menu/business-card/flyer empirical loaders;
- existing `GDL-EXP-20261001-MENU-001` evidence and lessons;
- existing Product Playbook contract and recurring greeting-card playbook;
- existing Guided Intake contract and deterministic normalization;
- existing `CONFIRMED / PROPOSED / UNRESOLVED` ambiguity handling;
- existing Creator Handoff contract/builder and asset mapping;
- existing asset-reference identity/provenance;
- existing GDL planning/governance/prompt lifecycle;
- Makefile as operator-facing functional map.

### EXTEND

Reconcile and extend the existing empirical-learning planning/evidence layer into the
smallest governed supported surface required by this contour. Do not rebuild already
committed evidence mechanics merely because the source package contains candidate versions.

### ADAPT

The source package's candidate schemas and examples must be adapted to current Prepress
conventions where equivalent owners already exist.

Menu, business card and flyer are **sanitized experiment examples**. They are not authorization
for the previously deferred full business-card wizard or a production intake runtime.

## Stage 0 - live module reconciliation before mutation

Before implementation:

1. verify current branch, HEAD, upstream and worktree;
2. synchronize/activate this prompt through the canonical module prompt lifecycle;
3. inspect current GDL roadmap, Capability Catalog, status and current prompt state;
4. inventory relevant contracts, builders, validators, indexes, docs, tests and Makefile targets;
5. inspect the committed `planning_evidence/empirical_learning/` surface from `2039f48`
   before proposing any new empirical schema, loader, lifecycle, methodology, index or fixture;
6. classify each existing and proposed surface as `REUSE / EXTEND / ADAPT / REPLACE / NEW`;
7. preserve current ownership instead of creating duplicate semantics;
8. treat the known empirical planning/evidence surface as the normal REUSE/EXTEND baseline,
   not as a blocker merely because an equivalent concept already exists;
9. stop only on a material ownership/authority conflict, an irreconcilable duplicate owner,
   or authority widening.

Do not blindly copy the candidate schema into production if current module semantics already
have a canonical owner. Do not recreate the existing empirical case template, loaders,
experiment lifecycle, methodology/index surfaces or menu experiment unless reconciliation
proves a replacement is necessary.

## Authorized source scope

The source package authorizes:

- `define_creator_interaction_case_schema`
- `define_case_identity_and_external_artifact_reference_semantics`
- `define_product_task_and_variant_metadata`
- `define_prompt_version_and_prompt_text_reference_semantics`
- `define_creator_result_observation_metadata`
- `define_operator_assessment_fields`
- `define_customer_acceptance_and_optional_satisfaction_fields`
- `define_accepted_attempt_and_revision_count_metrics`
- `define_strengths_weaknesses_failure_modes_and_lessons_fields`
- `define_candidate_local_automation_observation_fields`
- `define_manual_operator_intake_experiment_protocol`
- `define_lightweight_product_intake_loader_instruction_pattern`
- `provide_sanitized_examples_for_menu_business_card_and_flyer`
- `add_validation_and_indexing_support`
- `add_human_readable_case_summary_view`
- `add_Makefile_operator_workflow`
- `add_focused_tests`
- `add_verified_local_evidence_after_implementation`

## Required semantic distinctions

The implemented model must preserve:

- `operator_accepted_is_not_customer_accepted`
- `customer_accepted_is_not_customer_explicitly_satisfied`
- `technically_valid_is_not_design_approved`
- `design_approved_is_not_production_ready`
- `failed_prompt_is_learning_evidence_not_discardable_noise`

In practical terms:

- operator accepted ≠ customer accepted;
- customer accepted ≠ customer explicitly satisfied;
- technically valid ≠ design approved;
- design approved ≠ production ready;
- failed prompt/result is learning evidence, not disposable noise.

One case may generate a hypothesis. One case must not silently become global policy.

## Empirical case foundation

Use `coordination/internal_work/blueprint/roadmap_enrichment/prepress_gdl/2026-10-01__gdl_empirical_learning_horizon_v0_1/source_package/04_empirical_case_schema.yaml` as candidate semantic
input, not a frozen implementation file.

The current implementation must support/reconcile at least:

- case identity and observation time;
- non-PII customer/order/job references;
- product family/subtype/format/attributes;
- task category/objective/stage;
- source/input observations and unresolved questions;
- explicit customer permissions/discretion;
- intake method/playbook/dialogue observations;
- Creator prompt ID/version/text reference;
- Creator class plus optional provider/model metadata;
- result revision and external artifact reference;
- operator outcome;
- customer outcome;
- explicit customer satisfaction only when observed;
- `first_attempt_accepted`;
- `accepted_attempt`;
- `revision_count`;
- manual intervention;
- strengths;
- weaknesses;
- failure modes;
- ambiguities;
- preprocessing/postprocessing/local tools/human interventions;
- reusable prompt-pattern hypotheses;
- prompt anti-pattern hypotheses;
- candidate local automation;
- future questions.

## Artifact and privacy boundary

Repository may contain:

- sanitized case metadata;
- sanitized prompt text or prompt reference;
- structured observations/outcomes;
- external artifact locator metadata.

Repository must not require:

- heavy design files;
- customer source assets;
- generated high-resolution design files;
- customer PII.

Prefer stable references such as `customer_ref`, `order_ref`, `case_ref`,
`external_storage_locator`.

## Manual operator intake experiment

Use `coordination/internal_work/blueprint/roadmap_enrichment/prepress_gdl/2026-10-01__gdl_empirical_learning_horizon_v0_1/source_package/05_operator_intake_experiment_protocol.yaml` as the
candidate protocol and reconcile it to current module conventions.

The resulting experiment must be usable by a normal manager/operator in a fresh AI chat without
requiring design, programming, prompt-engineering or GDL-architecture knowledge.

Required behavior:

1. manager starts from all information already known;
2. assistant normalizes known information;
3. unknowns and ambiguity stay explicit;
4. assistant asks only material missing questions;
5. customer reply updates known / unknown / authorized-discretion state;
6. if the customer delegates creative discretion, stop repeatedly asking aesthetic-choice
   questions unless a technical/business constraint still requires clarification;
7. when minimum information is sufficient, build a Creator-ready prompt;
8. later attach Creator result/outcome observations to the empirical case.

This is `manual_experimental`; production runtime is not required.

## Initial sanitized examples

Prepress already contains empirical intake loaders for:

- menu;
- business card;
- flyer.

REUSE/validate/adapt those existing loaders first. Add a new example only when a concrete
acceptance gap remains after reconciliation.

The source package also contains a menu example:

`coordination/internal_work/blueprint/roadmap_enrichment/prepress_gdl/2026-10-01__gdl_empirical_learning_horizon_v0_1/source_package/06_menu_intake_example.yaml`

Reuse/adapt its semantics.

Business-card and flyer examples should remain sanitized learning fixtures, not full
production wizards.

## Deterministic mechanics

Add/reconcile only what is necessary for this contour:

- schema/record validation;
- empirical case validation;
- lightweight indexing/discovery;
- human-readable case summary/view;
- deterministic case ↔ prompt ↔ external-artifact references;
- focused fixtures/tests.

Avoid premature opaque scoring/ranking.

## Makefile operator surface

For every stable supported workflow introduced by this contour, update the Makefile functional
map.

At minimum expose discoverable supported actions for:

- empirical-case validation;
- case/index/summary inspection;
- focused empirical-learning validation/tests.

Do not add placeholder/dead targets.

## Human-readable documentation

Document:

- why the empirical layer exists;
- case semantics;
- privacy/artifact boundaries;
- manual experiment flow;
- outcome distinctions;
- evidence-promotion rule;
- how later Creator Result / evaluation / prompt-composer contours consume the evidence.

Machine-readable planning must not make the system opaque to the Human Owner.

## Explicit deferrals

Source-package deferrals:

- `autonomous_creator_execution`
- `provider_selection`
- `provider_orchestration`
- `production_write`
- `GDL_runtime_initialization`
- `automatic_customer_messaging`
- `automatic_order_creation`
- `automatic_design_approval`
- `heavy_artifact_storage_in_git`
- `broad_cross_module_API`
- `automatic_model_scoring_or_ranking`
- `large_scale_analytics_before_sufficient_cases_exist`

Additionally defer:

- full business-card wizard;
- Creator Result Package implementation beyond minimal references required by the empirical case model;
- automatic release of any later GDL contour.

## Acceptance

Source-package acceptance requirements:

- `case_schema_validated`
- `manual_case_can_be_recorded_without_real_customer_PII`
- `external_artifact_reference_supported_without_copying_artifact_into_repo`
- `accepted_attempt_and_revision_count_are_explicit`
- `operator_and_customer_outcomes_are_separate`
- `strengths_weaknesses_failure_modes_and_lessons_are_recordable`
- `manual_menu_intake_experiment_can_be_run_from_a_fresh_chat`
- `ambiguity_and_missing_information_are_preserved_not_silently_invented`
- `deterministic_validation_passes`
- `focused_tests_pass`
- `governance_passes`
- `assistant_handoff_passes`
- `Makefile_operator_surface_exists`
- `System_Blueprint_remains_read_only_from_Prepress`
- `no_next_contour_auto_activated`

Also prove:

- the existing `2039f48` empirical planning/evidence surface was reconciled and not duplicated by a parallel owner;
- existing menu/business-card/flyer loaders were reused or explicitly adapted with evidence;
- a sanitized/manual case can be recorded without real customer PII;
- external artifact references work without copying heavy design files into Git;
- fresh-chat menu experiment is actually usable;
- ambiguity/missing information is preserved rather than invented;
- existing GDL regression remains green;
- Makefile coverage matches new stable operator functionality;
- module-owned completion evidence is produced;
- provider execution remains false;
- runtime initialization remains false;
- production write remains false;
- Blueprint mutation from Prepress remains false.

## Required completion report

Return at minimum:

- branch and pre/post HEAD;
- prompt identity and local lifecycle state;
- exact changed paths;
- `REUSE / EXTEND / ADAPT / REPLACE / NEW` disposition;
- existing capabilities reused;
- contracts/schemas added or extended;
- sanitized fixtures/examples;
- case index/summary behavior;
- Makefile targets added/reused;
- focused tests;
- existing GDL regression;
- governance result;
- assistant-handoff/continuity result;
- `git diff --check`;
- artifact/privacy boundary proof;
- provider/runtime/production-write states;
- Blueprint mutation state;
- implementation commit(s);
- push result;
- post-push HEAD/upstream/worktree evidence;
- unresolved findings;
- proposed amendments to later contours, if real evidence supports them.

## Stop conditions

Stop and return exact evidence instead of broadening if:

- the existing empirical-learning surface reveals an ownership or authority conflict that
  cannot be resolved through bounded `REUSE / EXTEND / ADAPT` inside this contour;
- a second competing empirical-learning owner would otherwise be created;
- ownership would move to CRM, Operational Registry or another module;
- customer PII would be required in Git;
- provider selection/execution becomes necessary;
- GDL runtime/production write becomes necessary;
- a broad cross-module API/contract is required without Blueprint resolution;
- another active prompt conflicts;
- current GDL state materially invalidates this contour;
- governance/continuity rejects the intended write-set;
- Prepress would need to mutate Blueprint.

Do not substitute a broader GDL redesign.

## Follow-up boundary

Successful completion returns module-owned evidence to Blueprint review.

It does not activate the next planned contour:

`prepress_gdl_creator_result_package_foundation_v0_1`

Sequence 2 remains `PLANNED_REQUIRES_RECONCILIATION` until Blueprint separately reviews:

- new empirical evidence;
- current module state;
- current Human Intent;
- completed prior contours;
- pending contour amendments.

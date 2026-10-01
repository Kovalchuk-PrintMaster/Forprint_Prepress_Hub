# Immediate action plan

## Phase 0 — historical pre-Blueprint preparation

1. Keep all empirical materials explicitly non-canonical.
2. Use one case record for every real design experiment.
3. Start with simple common products.
4. Run: customer request → intake → questions → Creator prompt → result → outcome.
5. Preserve successful and failed prompts.
6. Keep heavy design files outside the project; store references only.
7. Avoid customer PII in the knowledge base.
8. When Blueprint returns the first executable prompt, reconcile these drafts into the authorized contour.

## First metrics

- first_attempt_accepted
- accepted_attempt
- revision_count
- operator_acceptance
- customer_acceptance
- customer_explicit_satisfaction
- manual_intervention_required
- question_round_count
- customer_confusion_observed
- creator_failure_modes

## First research questions

- Which questions are truly needed before Creator can work?
- Which questions confuse or annoy customers?
- When can explicit creative discretion replace missing data?
- Which prompt sections improve first-pass quality?
- Which requirements make Creator less reliable?
- Which work belongs to Creator, local tools, or human confirmation?

## Phase 1 — active bounded empirical foundation

1. Reuse the existing empirical case, loader and MENU-001 evidence owners.
2. Record sanitized case metadata using external artifact references only.
3. Validate case semantics and privacy boundaries with `make gdl-empirical-check`.
4. Use `make gdl-empirical-index` and `make gdl-empirical-summary` for operator discovery.
5. Preserve successful and failed attempts as append-only evidence.
6. Keep provider execution, GDL runtime initialization and production write disabled.
7. Return completion evidence to Blueprint review without activating the next contour.

# ForPrint Graphic Design Lab — module-local primary knowledge surface

Status: **ACTIVE LONG-RUNNING HUMAN + ASSISTANT KNOWLEDGE SURFACE**

This is the main module-local home for reusable Graphic Design Lab operating knowledge.

It is intentionally separate from:

- application runtime code in `app/graphic_design_lab/`;
- contracts in `contracts/graphic_design_lab/`;
- runtime/configuration surfaces;
- historical roadmap evidence in `coordination/roadmaps/graphic_design_lab/planning_evidence/`.

The old empirical-learning tree remains historical evidence and continuity material.
New reusable rules, communication patterns, prompt evidence conventions and specialized
directions should be maintained here.

## Layer model

```text
GLOBAL GDL RULES
        ↓
DIRECTION-SPECIFIC RULES
        ↓
CASE CONTEXT
        ↓
INTAKE / CREATOR / CORRECTION PROMPT
        ↓
RESULT + HUMAN/CUSTOMER OUTCOME
        ↓
PROMPT EFFECTIVENESS EVIDENCE
        ↓
REUSABLE FINDINGS / WORKER CANDIDATES
```

## Main sections

- `policies/` — rules that apply across GDL work;
- `customer_communication/` — Telegram-friendly information collection,
  clarification and approval forms;
- `prompt_evidence/` — storage/indexing rules for prompts and their outcomes;
- `directions/` — specialized product families such as vehicle branding;
- `loaders/` — reusable assistant loaders;
- `cases/` — sanitized case registry.

## Human/customer communication rule

Machine-readable structures are for assistants and internal project evidence.

Customer-facing messages must be easy to paste into ordinary Telegram/chat:
short, structured, visually readable, no YAML, no database-like tables, and with
clear fill-in places so the customer can answer with minimal effort.

Example:

```text
📞 Телефон для макета:
____________________

🔗 Посилання для QR-коду:
____________________

📐 Розмір:
____________________
```

Ask only for missing information. Do not ask the customer to repeat data that is
already known and reliable.

## Prompt evidence rule

Every materially used Intake, Creator, correction or reconciliation prompt should
be preserved or referenced with its case and observed result so prompt effectiveness
can be compared over time.

Customer PII and heavy/raw customer artifacts remain outside Git.

## Authority boundary

This surface records knowledge and empirical operating rules. It does not itself
authorize provider execution, runtime initialization, production write, automatic
customer communication, or a new engineering contour.

`SYSTEM_BLUEPRINT_ACCESS_FROM_PREPRESS=READ_ONLY_STRICT`

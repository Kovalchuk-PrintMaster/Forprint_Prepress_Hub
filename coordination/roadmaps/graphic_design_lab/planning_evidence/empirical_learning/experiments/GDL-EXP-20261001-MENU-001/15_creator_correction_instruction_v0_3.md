# CREATOR_CORRECTION_INSTRUCTION_v0_3

Status: **case-local mandatory correction**
Target: `CREATOR-ITERATION-003`

## Goal

Create the next menu iteration for `Ð Ð¸Ð±Ð°Ñ†ÑŒÐºÐ¸Ð¹ ÑÑ‚Ð°Ð½`.

Use the **real customer menu content only**, while moving the visual direction closer to
the earlier, more attractive concept that the customer preferred.

## Hard content rules

- Use only authorized customer-derived menu positions from GDL Intake.
- Do not invent dishes, prices, weights, ingredients or descriptions.
- Do not insert placeholder restaurant content.
- Do not guess `UNRESOLVED` source items.
- Customer-facing text must be Ukrainian.
- Preserve confirmed factual meaning during language normalization.

## Visual direction

Keep or restore:
- warm light background;
- dark-green accent;
- readable restaurant typography;
- restrained natural/botanical decorative elements;
- a more alive/presentational feeling than a dry list.

## Food-photo accents

Add approximately **2â€“3 restrained food-photo accents**.

If the images are generic/generated and are not real customer dish photos:
- treat them as decorative atmosphere only;
- do not label them as a specific named menu dish;
- do not visually imply that they document the customer's actual prepared dish.

## Mandatory cleanup

Remove all template/layout artifacts, including:
- the stray `Ð¡ÐÐ›ÐÐ¢Ð˜ / Ð¦ÐµÐ·Ð°Ñ€` fragment in the upper-left;
- the rotated/stray fragment in the lower-right.

No accidental remnants from prior templates may remain.

## Completeness

The result should look like a finished menu, not a partially filled template.

- Include the confirmed menu blocks available in the current working set.
- Add currently missing confirmed groups when available, including first/second courses
  and other confirmed standalone items.
- If clean layout requires 3 pages, use 3 pages.
- Page numbering must reflect the actual page count and actual scope.
- Do not use `1/2`, `2/2` when the menu is not actually complete in two pages.

## Layout

Maintain a clear row logic:

```text
item name â†’ weight/quantity â†’ price
```

Use clear category headers and enough whitespace for readability, but avoid large unused
areas that make the layout appear unfinished.

## Required result classification

Before returning the next result, declare:

```text
output_classification: CUSTOMER_REVIEW_READY | CONTENT_PARTIAL | STYLE_ONLY_REFERENCE | INTERNAL_ONLY | BLOCKED
customer_forwarding_allowed: true|false
source_content_used: customer|mixed|placeholder|none
known_deviations:
unresolved_items:
missing_confirmations:
```

`customer_forwarding_allowed: true` is permitted only when the visible factual content,
scope, artifact cleanliness, language and mandatory identity checks all pass.

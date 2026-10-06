# GDL Creator Portrait Loader - Recurring Greeting Cards v001

## Role

Execute one bounded greeting-card portrait transformation task only.

## Input authority

Use the supplied `creator_task` as the complete machine-readable authority for this run.
Do not infer additional document, layout, branding, greeting-text, signature, or production work.

## Required behavior

1. Work only on `source_asset`.
2. Apply only `requested_operations`.
3. Preserve the recipient's likeness and realistic appearance.
4. Do not change recipient identity.
5. Do not perform any item listed in `forbidden_changes`.
6. Directed appearance edits are forbidden unless `explicit_appearance_request_ref` is present.
7. Return only the requested portrait asset type.
8. Preserve task, job, assessment, and source-asset traceability in the result metadata.
9. Do not claim full-card composition, production export, customer approval, or provider/runtime activation.

## Result boundary

The returned asset is external to Git and must be attached through
`forprint_creator_result_package_v0_1`.

A result is not accepted merely because an artifact exists. It must pass the existing
Creator Result Package validation and subsequent internal review.

## Human bridge

This prompt is compatible with the current `HUMAN_COPY_PASTE_BRIDGE`.
Compiling this prompt or a dispatch manifest does not mean Creator execution occurred.

# ForPrint GDL W2.7-C3A — Execution Boundary Handoff (DRAFT)

Status: **REQUEST FOR BLUEPRINT REVIEW — NOT AN APPROVAL**.
Scope: synthetic-only `gdl-w27c-native-001/a0001`. No customers/SMB/production.
Base commit: `c88633a` (Prepress Hub main); preceding C1/C2 checks passed on s01.

## Confirmed technical evidence

- W2.5.3: Limited Token COM → JSX → native editable `.ai` save/reopen proved independently (different task/attempt).
- W2.6: that earlier `.ai` and machine result returned to s01 and SHA verified.
- W2.7-A: immutable manifest + payload archive `sha256=d1949844b3ab2d68936facf8012e6b8fba1ecd1134597f2e6f4139ef1449b3e7`.
- W2.7-B: new C1 native package staged on PREPRESS, receipt SHA `0c025e0132795c7f0e7011fbe52fdf17c44f9f19fc01dcd34f77684e4b11e827`.
- W2.7-C2: interactive Work session 2 with preexisting Illustrator PID 1012 at observation time; this is not a persistent PID or authorization.
- W2.7-C3A: **source draft only**, no executable COM Runner and no Windows action.

## Authority questions for System Blueprint owner

1. Who may authorize the **single synthetic execution** of this exact task/attempt/archive/JSX digest? What independently verifiable, expiring authorization artifact is required? The Worker must not issue its own authorization.
2. Who is the dispatch owner and what prior Task Readiness / double-review gates apply? A successful check/RC=0 must never imply dispatch authorization.
3. How is an attempt claim fenced before Task Scheduler activation? What is the recovery choice if it starts, times out, reboots, partially saves `.ai`, or emits RC=0 without a valid result?
4. Should staging `a0001` itself be used for execution after review, or is a fresh attempt identifier required once an executable adapter exists? Preserve current staged files and previous evidence either way.
5. Exact acceptance boundary for `worker_result.json`: pinned task and attempt, input manifest SHA, source JSX and runner digests, Limited Token proof, preexisting Illustrator PID + session, phase/error code, no/customer/cleanup flags, AI bytes/digest, independent s01 verification and human acceptance separate from technical verification.
6. Which authority owns the executable Illustrator adapter and its durable ledger (Prepress Hub vs System Blueprint control plane)? Avoid duplicate dispatcher and worker ownership.

## Proposed fail-closed execution order (NOT AUTHORIZED)

- operator/Blueprint approval → explicit execution receipt bound to task/attempt/sha and short-lived review
- server-side strict readiness verify → one-use claim → Limited interactive Task Scheduler assignment
- Windows runner reads approved staged inputs and verifies exact digest before any COM call
- existing Illustrator-only COM attach → bounded synthetic JSX → `.ai` save/reopen
- create-new Worker Result (including blocked state if failure) → independent verify
- return source artifact/result to s01 → verify SHA + attempt + evidence; no automatic acceptance
- no automatic deletion, restart, production publish, SMB/customer access or auto Git actions

## Current boundary

`C3A = SOURCE_DRAFT_ONLY`.
`C3B = EXECUTABLE_ADAPTER_SPEC_AND_TESTS_PENDING`.
`EXPLICIT_OWNER_EXECUTION_AUTHORITY = NOT_GRANTED`.

Neither this handoff nor the source draft grants dispatch/execution/acceptance authority.

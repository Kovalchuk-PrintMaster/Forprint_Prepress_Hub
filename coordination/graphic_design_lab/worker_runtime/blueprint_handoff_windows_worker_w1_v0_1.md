# ForPrint W1 — Portfolio Windows Worker / Blueprint review request

Status: **GDL PILOT CANDIDATE; BLUEPRINT AUTHORITY PENDING**. This is a review request, **not** a change to System Blueprint, CF-10, Integration Gateway, or the global dispatcher.

## What user agreed on 2026-10-20

- s01/server remains authoritative task origin and verifier; Windows machines are bounded executors with reusable **one worker infrastructure, multiple program adapters** (Illustrator first; later Acrobat, CorelDRAW and others).
- Workspace for each client is a **small operator interface**, not a program runtime or historical warehouse; current `input/` and `output/` remain untouched. Candidate hidden service root `.forprint/` is **not created**.
- Isolated local Windows D: task/attempt staging, one active task at a time (first pilot). Local execution can survive a brief SMB outage and retry upload after recovery.
- On crash mid-work: retry the **whole unfinished attempt** only after ensuring the old attempt can no longer publish. If finished locally with validated evidence but not transmitted, re-upload without rerender. If independently VERIFIED/ACCEPTED, do not run again.
- Full crash recovery and automatic cleanup **deferred**. Initial cleanup is report-only; do not delete terminal evidence, incomplete output, canonical resources, or unuploaded results.
- Interactive desktop applications must run in a proven interactive Windows user session. Task Scheduler launch at user logon is a candidate, not evidence of robustness after reboot, sign-out or RDP disconnect.

## Authority boundary (required Blueprint response)

1. Who owns the *portfolio-wide* Windows worker runtime and worker registry? GDL must not claim authority over an all-ForPrint queue. Existing CF-10 dispatcher or Integration Gateway transports should be reused/adapted only after review.
2. What is the authoritative Task/Attempt/Worker Result schema and fencing/lease owner? Reuse validated CF-10/Handoff/Worker Result semantics; do not construct a parallel authoritative framework inside GDL.
3. What is the approved independent terminal result ledger location? Current GC14 dedup relies on `output/*/source_info.json` and `report.json`; these cannot be deleted or moved before migration and replay tests.
4. Where should private SMB service data live, and which Windows/Samba identities may read/write it? User observed Linux mode `2777` for `_forprint_automation` and `test`, so copying a private JSX there is unsafe until effective Samba permissions are confirmed and a protected area is approved.
5. Is `D:\ForPrint_Automation\GraficsDesignLab\Automation` acceptable as a cross-program local layout? It is a local implementation candidate, not a portfolio-wide enforced policy.

## 2026-10-20 operator-selected pilot root

- Windows local workspace for **this GDL pilot only**: `D:\ForPrint_Automation\GraficsDesignLab\Automation`. The spelling `GraficsDesignLab` is operator-selected and must not be silently normalized.
- `D:\ForPrint_Automation` is reserved as a possible umbrella for multiple independent module workspaces; it is not itself an active portfolio Worker or an approved shared global authority.
- The path replacement supersedes the original W1 pilot candidate `D:\ForPrint\Automation`. Neither root is created by this documentation change.
- Illustrator, Acrobat and CorelDRAW adapters may share GDL pilot runtime rules, but global runtime ownership, deployment and queue authority remain deferred pending Blueprint review.

## Scope of W1 artifacts

- `windows_worker_w1_pilot_contract_v0_1.yaml`: descriptive pilot constraints and fail-closed limits.
- `windows_worker_w1_pilot_v0_1.py`: read-only schema check, recovery-decision checks and **temporary synthetic smoke only under repository `tmp/`**. No worker daemon, queue promotion, Windows launch, SMB write, private source material or cleanup.
- Tests: exhaustive negative decision checks and client-workspace no-write guards.

## Minimal acceptance for W1

1. Contract checks all expected invariants, markers, paths and authorities; no accidental `dispatch_authorized` or false production PASS.
2. Synthetic restart path after crash and no double-publish; incomplete/ambiguous owner remains blocked pending fencing; finished-local report chooses re-upload.
3. Synthetic result cannot claim VERIFIED on RC=0 alone; source/task/attempt SHA bindings and file digest must independently match.
4. Entire existing Prepress Hub `make governance-check` passes, Git exact-path staging, no mutation to customer SMB.

## Deferred W2 / W3

W2: read-only Windows host capability and session preflight, safe private transfer, manually authorized **GC18 P04_BODY_ONLY** Illustrator AI creation and independent AI reopen proof. W3: queue integration, lifecycle manager, worker supervision, eventual `output` publication and report-only housekeeping. Neither is implemented by W1.

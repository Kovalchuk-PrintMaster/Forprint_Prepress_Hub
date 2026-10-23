# ForPrint GDL W2.7-C3B — Authority & Native Runner Handoff

**State:** `EXECUTION_ADAPTER_SOURCE_REVIEW_ONLY_AUTHORITY_PENDING`.
**Owner review:** System Blueprint / single dispatch owner decision **not received**.
**Base Prepress Hub commit:** `e278332`. **No new launch authority.**

## Confirmed provenance

- W2.7-C1: native synthetic C1 ZIP `d1949844b3ab2d68936facf8012e6b8fba1ecd1134597f2e6f4139ef1449b3e7`, JSX `98780bcd7939df58f16aa0e123ced5efc4956ed43cc6438d0516b43d4d819902`.
- W2.7-B Windows staged `gdl-w27c-native-001/a0001`, independent staging receipt digest `0c025e0132795c7f0e7011fbe52fdf17c44f9f19fc01dcd34f77684e4b11e827`.
- W2.7-C2 GUI-ready at observation: `PREPRESS\\Work`, session `2`, Illustrator PID `1012`. Do **not** treat historical PID/session as persistent after reboot.
- W2.7-C3A inert draft/contract committed at `e278332`; authority remains pending.
- W2.7-C3B contains a candidate PowerShell private function and an independent *file/hash/report* verifier. Only `-Mode review` is exposed; **no Windows call/dispatch/COM execution occurred**.

## Authority issues blocking real execution

1. Blueprint must define an **independently issued, bounded, expiring execution authorization** bound to task, attempt, archive, JSX, runner digest, actor, review and TTL. Do not accept a forged JSON flag or locally writable boolean as approval.
2. Define the single dispatcher/owner, exact Task Scheduler creation and validation (`LogonType Interactive`, `RunLevel Limited`, no triggers, unique task name, exact action path and arguments) and independent review of executable PowerShell on Windows.
3. Define **attempt fencing**: one pre-dispatch start claim, an additional `CreateNew` execution marker in the limited runner, no automatic rerun after crash/timeout/partial outputs; manual reconciliation for ambiguous outcomes.
4. Decide whether staged `gdl-w27c-native-001/a0001` may be used for first authorized execution or requires **a fresh attempt**. Preserve this attempt and existing evidence until explicitly decided.
5. Independently verify returned `native_result.ai` (format and editability, not only hash), `worker_result.json`, task/attempt/source/runner hash binding, scheduler outcome, token evidence and signed authority. `RC=0` and machine report alone **do not grant acceptance**.
6. Confirm remote worker ACL/owner policy before customer data. Current PREPRESS Work FullControl is a **temporary DEV permission**, not production clearance. Keep customer/SMB mutation disabled.

## Current C3B source limitations

- The public candidate PowerShell is **review-only**. Private `Invoke-NativeCandidate` contains source for later review but immediately fails on `BLUEPRINT_EXECUTION_GATE_NOT_IMPLEMENTED` and is **never called** by public entrypoint. It has **not been syntax-parsed or executed on Windows** in this package.
- No authority document reader/verifier or Task Scheduler controller has been implemented. Existing W2.5.3 controlled proof is not transferable as authority to this C1 task.
- The Python verifier checks exact JSON schema, SHA-256 of returned bytes, declared identity and evidence flags. It **cannot independently establish COM happened, the AI is editable, or a run was authorized**. Its output explicitly reports both independent proofs as false and `accepted=false`.
- Unit tests include synthetic mock evidence bytes, including mock non-AI bytes, **not an actual Illustrator proof**.
- Do not deploy/run the PowerShell candidate or treat `review-package`/`SOURCE_CHECK_PASS` as a dispatch gate. No ZIP extraction or Windows file mutation in C3B.

## Suggested next boundary after review

`C3C = AUTHORITY_AND_PRECLAIM_ADAPTER_SPECIFICATION / EXPLICIT OWNER REVIEW` → independently validated `C3D = AUTHORIZED SINGLE-USE SYNTHETIC EXECUTION` → return results to s01 → independent technical verify → separate human acceptance. No automatic cleanup, Git actions or production publication.

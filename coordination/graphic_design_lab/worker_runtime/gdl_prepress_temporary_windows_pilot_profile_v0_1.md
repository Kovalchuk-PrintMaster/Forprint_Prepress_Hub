# ForPrint GDL — PREPRESS Temporary Windows Pilot Profile v0.1

**Status:** `PILOT_TEMPORARY_APPLIED_NOT_PRODUCTION_APPROVED`
**Recorded:** 2026-10-23, Europe/Kyiv
**Scope:** `ForPrint Prepress Hub / Graphic Design Lab / PREPRESS`
**Host:** `PREPRESS`, Windows 10 Enterprise, build 19045
**Role:** Accessible test computer for synthetic Illustrator automation chains. This is *not* an approved permanent production host.

## Verified pilot configuration

| Item | Baseline evidence | Applied state / evidence |
|---|---|---|
| Power scheme | High performance (`8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c`) | Preserved (same GUID) |
| Sleep after — AC | `0x00000000` | `0x00000000` — Never |
| Hibernate after — AC | `0x00000e10` = 3600 seconds | `0x00000000` |
| Hybrid sleep — AC | `0x00000001` | `0x00000000` |
| Hibernate availability | Available | Disabled by `powercfg /hibernate off` |
| Fast Startup | `HiberbootEnabled=1` / available | Unavailable while hibernation is disabled |
| Windows Update policy | WindowsUpdate and AU policy keys not configured | `HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU\AUOptions` `REG_DWORD=3` |
| Windows Update pending reboot | WU: false; CBS: false at baseline audit | Not independently rechecked after policy application |

Applied power result: `PREPRESS_POWER_PROFILE_APPLIED=PASS` and `FORPRINT_PREPRESS_POWER_CHANGE=PASS`.
Applied update-policy result: `PREPRESS_UPDATE_POLICY_APPLIED=PASS` and `FORPRINT_PREPRESS_UPDATE_POLICY=PASS`.

**Meaning of `AUOptions=3`:** notify for installation with automatic download according to the configured Windows Update policy. This is not an absolute guarantee against every form of servicing-initiated restart or external forced action. Do not disable Windows Update services or security mechanisms.

**Caution — baseline exception:** Windows records include Kernel-Power 41 / EventLog 6008 (unclean shutdown), sleep event 42 with `System Idle`, and a planned TrustedInstaller reboot on 2026-10-22. Power loss may still interrupt the host. `powercfg` does not protect against supply loss, user-commanded shutdown, firmware actions, or all servicing restart paths. Maintain fail-closed Worker attempt recovery.

## Evidence kept on s01 (not committed to Git)

- `tmp/gdl_prepress_power_audit_20261023_v0_1/power.txt`
- `tmp/gdl_prepress_power_audit_20261023_v0_1/events.txt`
- `tmp/gdl_prepress_power_apply_20261023_v0_1/power_before.txt`
- `tmp/gdl_prepress_power_apply_20261023_v0_1/events_before.txt`
- `tmp/gdl_prepress_power_apply_20261023_v0_1/apply_log.txt`
- `tmp/gdl_prepress_update_audit_20261023_v0_1/update_policy.txt`
- `tmp/gdl_prepress_update_apply_20261023_v0_1/before.txt`
- `tmp/gdl_prepress_update_apply_20261023_v0_1/apply.txt`

These are operator-side evidence locations, not Git sources of authority. Preserve when needed for audit or rollback. Validate their actual presence before making claims about long-term retention.

## Operational boundaries

1. This profile applies only to the temporary PREPRESS pilot. Do not clone it blindly to a final host.
2. This record confers **no** Dispatcher, Worker launch, COM/JSX, client publication, or retry authority.
3. Existing native task `gdl-w27c-native-001/a0001` and synthetic fence `gdl-w27g-synthetic-fence-001/a0001` remain untouched; never repeat a one-use probe.
4. Power loss and reboot require fresh live inspection and reconciliation before a new Worker attempt.
5. Work on underlying Windows lifecycle, ESU, permanent OS/hardware choice, UPS policy, and production security hardening is deliberately deferred until the base design-automation pipelines are established.
6. Parallel Graphic Design Lab greeting-card work (GC16–GC18) and the shared Makefile must not be modified for this checkpoint.

## Future rollback / handoff (not an execution instruction)

Before rollback, capture current `powercfg /query SCHEME_CURRENT SUB_SLEEP`, `powercfg /a`, and Windows Update policy keys. To restore the observed baseline, an authorized operator would need to re-enable hibernation, restore the one-hour AC hibernate idle and hybrid-sleep AC values, and remove **only** the locally created `AUOptions` policy value after ensuring no other operator or Group Policy now owns it. The original snapshot did not include a complete exported `.pow` scheme and therefore this document is **not** a complete machine-restoration image.

**Next project boundary:** Resume GDL controlled synthetic automation experiments. Do not treat `PREPRESS` as permanent production infrastructure.

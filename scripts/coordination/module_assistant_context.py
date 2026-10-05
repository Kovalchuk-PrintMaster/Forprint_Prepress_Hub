#!/usr/bin/env python3
"""
ForPrint module assistant continuity helper v0.1.

This is a module-owned, standard-library-only reference implementation for:
- assistant-handoff-check
- assistant-pack          -> MODULE_ONBOARD
- assistant-context-pack  -> MODULE_CONTEXT

It reads the current module and the local read-only Blueprint checkout.
It NEVER writes to Blueprint, stages Git, commits, pushes, merges, or grants
execution/acceptance/release authority.

Generated packages are navigation/evidence under tmp/assistant_context/.
Canonical project instructions must still be re-read from live Blueprint.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

SCRIPT_ID = "forprint_module_assistant_context_v0_1"
DEFAULT_MAX_FILE_BYTES = 256 * 1024
DEFAULT_MAX_TOTAL_BYTES = 4 * 1024 * 1024

SYSTEM_BLUEPRINT_ACCESS_FROM_PREPRESS = "READ_ONLY_STRICT"
SYSTEM_BLUEPRINT_POLICY_MARKER = (
    "SYSTEM_BLUEPRINT_ACCESS_FROM_PREPRESS="
    + SYSTEM_BLUEPRINT_ACCESS_FROM_PREPRESS
)

ALWAYS_LOCAL = [
    "AGENTS.md",
    "README.md",
    "coordination/module/manifest.yaml",
    "Makefile",
    "pyproject.toml",
    "coordination/bootstrap/START_HERE.md",
    "coordination/bootstrap/module_bootstrap_manifest.yaml",
    "coordination/blueprint_source.yaml",
    "coordination/status/current_status.yaml",
    "coordination/status/current_status.md",
    "coordination/status/next_questions_for_blueprint.md",
    "coordination/prompts/index.yaml",
    "coordination/reports/index.yaml",
    "coordination/graphic_design_lab/continuity/project_first_working_rule_v0_1.yaml",
]

OPTIONAL_LOCAL_GLOBS = [
    "docs/architecture/**/*.md",
    "docs/operations/**/*.md",
    "docs/development/**/*.md",
    "config/**/*.md",
    "config/**/*.yaml",
    "config/**/*.yml",
    "contracts/**/*.md",
    "contracts/**/*.yaml",
    "contracts/**/*.yml",
    "contracts/**/*.json",
    "coordination/roadmaps/**/*.yaml",
    "coordination/roadmaps/**/*.md",
]

BLUEPRINT_SOURCE_REFS = [
    "coordination/instruction_intake/assistant_reading_order.md",
    "coordination/instruction_intake/instruction_sources.yaml",
    "coordination/global_policy/forprint_project_doctrine.md",
    "coordination/global_policy/clean_tree_first_working_policy_v0_1.md",
    "coordination/standards/index.yaml",
    "coordination/standards/module_assistant_start_protocol.md",
    "coordination/standards/project_structure_standard.md",
    "coordination/standards/repository_structure_baseline.md",
    "coordination/standards/make_command_standard.md",
    "coordination/standards/module_make_target_contract.md",
    "coordination/standards/governance/folder_architecture_policy.md",
    "coordination/standards/governance/documentation_and_recovery_gate.md",
    "coordination/standards/governance/module_workflow_automation_and_external_input_policy.md",
    "coordination/standards/governance/module_workflow_command_architecture_v0_1.md",
    "coordination/standards/modular_topology_and_resilience/module_global_context_policy.md",
    "coordination/standards/modular_topology_and_resilience/data_ownership_and_storage_policy.md",
]

DENY_PARTS = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", "node_modules", "tmp", ".idea", ".vscode",
}

SECRET_NAMES = {
    ".env", ".env.local", ".env.production", "id_rsa", "id_ed25519",
}

SECRET_SUFFIXES = {
    ".pem", ".key", ".p12", ".pfx",
}


class ContextError(RuntimeError):
    pass


def run(cmd: list[str], cwd: Path, allow_fail: bool = False) -> tuple[int, str]:
    cp = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if cp.returncode and not allow_fail:
        raise ContextError(f"COMMAND_FAILED={' '.join(cmd)}\n{cp.stdout}")
    return cp.returncode, cp.stdout.rstrip("\n")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_candidate(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    if any(part in DENY_PARTS for part in rel.parts):
        return False
    if path.name in SECRET_NAMES or path.suffix.lower() in SECRET_SUFFIXES:
        return False
    lowered = path.name.lower()
    if any(token in lowered for token in ("secret", "password", "token", "credential")):
        return False
    return path.is_file()


def git_state(root: Path) -> dict:
    if not (root / ".git").exists():
        raise ContextError("MODULE_GIT_ROOT_NOT_FOUND")
    return {
        "branch": run(["git", "branch", "--show-current"], root)[1],
        "head": run(["git", "rev-parse", "HEAD"], root)[1],
        "status_short": run(
            ["git", "status", "--short", "--untracked-files=all"], root
        )[1].splitlines(),
        "last_commit": run(["git", "log", "-1", "--oneline"], root)[1],
    }


def blueprint_state(root: Path) -> dict:
    if not (root / ".git").exists():
        raise ContextError("BLUEPRINT_GIT_ROOT_NOT_FOUND")
    return {
        "branch": run(["git", "branch", "--show-current"], root)[1],
        "head": run(["git", "rev-parse", "HEAD"], root)[1],
        "status_short": run(
            ["git", "status", "--short", "--untracked-files=no"], root
        )[1].splitlines(),
    }


def required_local_paths(module_root: Path) -> list[Path]:
    return [module_root / item for item in ALWAYS_LOCAL]


def verify(
    module_root: Path,
    blueprint_root: Path,
    module_id: str,
    registration_state: str,
) -> dict:
    module_state = git_state(module_root)
    bp_state = blueprint_state(blueprint_root)

    required = required_local_paths(module_root)
    missing_local = [
        p.relative_to(module_root).as_posix() for p in required if not p.exists()
    ]

    missing_blueprint = [
        path
        for path in BLUEPRINT_SOURCE_REFS
        if not (blueprint_root / path).is_file()
    ]

    module_policy = (
        blueprint_root
        / "coordination"
        / "module_policy"
        / module_id
        / "module_policy.md"
    )
    module_policy_present = module_policy.is_file()

    errors: list[str] = []
    warnings: list[str] = []

    if missing_local:
        errors.append("MISSING_LOCAL_BOOTSTRAP_SURFACE")
    if missing_blueprint:
        errors.append("MISSING_BLUEPRINT_SOURCE_REFS")
    if registration_state == "registered" and not module_policy_present:
        errors.append("REGISTERED_MODULE_POLICY_MISSING")
    if registration_state == "bootstrap_unregistered" and module_policy_present:
        warnings.append("MODULE_POLICY_EXISTS_WHILE_BOOTSTRAP_UNREGISTERED")

    return {
        "script_id": SCRIPT_ID,
        "module_id": module_id,
        "registration_state": registration_state,
        "module": module_state,
        "blueprint": bp_state,
        "module_policy": {
            "path": (
                module_policy.relative_to(blueprint_root).as_posix()
                if module_policy_present
                else None
            ),
            "present": module_policy_present,
        },
        "missing_local": missing_local,
        "missing_blueprint": missing_blueprint,
        "errors": errors,
        "warnings": warnings,
        "status": "PASS" if not errors else "FAIL",
        "policy_markers": {
            "system_blueprint_access_from_prepress":
                SYSTEM_BLUEPRINT_ACCESS_FROM_PREPRESS,
        },
        "authority": {
            "execution": False,
            "acceptance": False,
            "release": False,
            "blueprint_write": False,
        },
    }


def topics_list(raw: str) -> list[str]:
    return [
        x.strip().lower()
        for x in raw.split(",")
        if x.strip()
    ]


def match_topics(path: Path, root: Path, topics: list[str]) -> bool:
    if not topics:
        return True
    rel = path.relative_to(root).as_posix().lower()
    if any(topic in rel for topic in topics):
        return True
    if path.stat().st_size > DEFAULT_MAX_FILE_BYTES:
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
    except Exception:
        return False
    return any(topic in text for topic in topics)


SCOPE_CONTEXT_CONTRACTS: dict[str, str] = {
    "graphic_design_lab": (
        "coordination/graphic_design_lab/continuity/"
        "assistant_context_contract_v0_1.yaml"
    ),
}


def context_pack_priority_paths(module_root: Path, scope: str) -> list[str]:
    # Read bounded scope-priority paths without adding a YAML dependency.
    contract_rel = SCOPE_CONTEXT_CONTRACTS.get(scope)
    if contract_rel is None:
        return []

    contract_path = module_root / contract_rel
    if not contract_path.is_file():
        return []

    try:
        contract_path.resolve().relative_to(module_root.resolve())
    except ValueError:
        return []

    priority_paths: list[str] = []
    active = False
    for raw_line in contract_path.read_text(
        encoding="utf-8", errors="ignore"
    ).splitlines():
        stripped = raw_line.strip()

        if stripped == "context_pack_priority_paths:":
            active = True
            continue

        if not active:
            continue

        if not stripped:
            continue

        if stripped.startswith("- "):
            value = stripped[2:].strip().strip("'").strip('"')
            if value:
                priority_paths.append(value)
            continue

        break

    return priority_paths


def add_priority_candidate(
    selected: dict[str, Path],
    module_root: Path,
    raw: str,
) -> None:
    path = module_root / raw

    try:
        path.resolve().relative_to(module_root.resolve())
    except ValueError:
        return

    if path.is_file():
        if safe_candidate(path, module_root):
            selected[path.relative_to(module_root).as_posix()] = path
        return

    if not path.is_dir():
        return

    for candidate in path.rglob("*"):
        if safe_candidate(candidate, module_root):
            selected[candidate.relative_to(module_root).as_posix()] = candidate


def effective_scope_for_topics(
    scope: str,
    topics: list[str],
) -> str:
    if scope == "bootstrap" and "graphic_design_lab" in topics:
        return "graphic_design_lab"
    return scope


def scope_priority_candidates(
    module_root: Path,
    scope: str,
) -> list[Path]:
    selected: dict[str, Path] = {}
    for raw in context_pack_priority_paths(module_root, scope):
        add_priority_candidate(selected, module_root, raw)
    return [selected[key] for key in sorted(selected)]


def local_candidates(
    module_root: Path,
    package_type: str,
    topics: list[str],
) -> list[Path]:
    selected: dict[str, Path] = {}

    for raw in ALWAYS_LOCAL:
        path = module_root / raw
        if safe_candidate(path, module_root):
            selected[path.relative_to(module_root).as_posix()] = path

    for pattern in OPTIONAL_LOCAL_GLOBS:
        for path in module_root.glob(pattern):
            if not safe_candidate(path, module_root):
                continue
            if package_type == "MODULE_CONTEXT" and not match_topics(
                path, module_root, topics
            ):
                continue
            selected[path.relative_to(module_root).as_posix()] = path

    # Root-level navigation docs, but never arbitrary large data/assets.
    for pattern in ("*.md", "*.yaml", "*.yml", "*.toml"):
        for path in module_root.glob(pattern):
            if safe_candidate(path, module_root):
                selected[path.relative_to(module_root).as_posix()] = path

    return [selected[key] for key in sorted(selected)]


def blueprint_ref_catalog(blueprint_root: Path) -> list[dict]:
    rows = []
    for raw in BLUEPRINT_SOURCE_REFS:
        path = blueprint_root / raw
        if not path.is_file():
            continue
        rows.append(
            {
                "path": raw,
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
                "copied_into_package": False,
                "role": "LIVE_BLUEPRINT_SOURCE_READ_AT_SESSION_START",
            }
        )
    return rows


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_pack(
    module_root: Path,
    blueprint_root: Path,
    module_id: str,
    registration_state: str,
    package_type: str,
    scope: str,
    topics: list[str],
    max_file_bytes: int,
    max_total_bytes: int,
) -> dict:
    check = verify(
        module_root=module_root,
        blueprint_root=blueprint_root,
        module_id=module_id,
        registration_state=registration_state,
    )
    if check["status"] != "PASS":
        raise ContextError(
            "ASSISTANT_HANDOFF_CHECK_FAILED="
            + ",".join(check["errors"])
        )

    head = check["module"]["head"]
    short_head = head[:12]
    slug = package_type.lower()
    base = (
        module_root
        / "tmp"
        / "assistant_context"
        / module_id
        / f"{slug}_{short_head}"
    )

    if base.exists():
        shutil.rmtree(base)
    package_dir = base / "package"
    files_dir = package_dir / "module_files"
    files_dir.mkdir(parents=True, exist_ok=True)

    effective_scope = effective_scope_for_topics(scope, topics)

    candidates = local_candidates(
        module_root,
        package_type,
        topics,
    )
    if package_type == "MODULE_CONTEXT":
        merged = {
            path.relative_to(module_root).as_posix(): path
            for path in candidates
        }
        for path in scope_priority_candidates(
            module_root, effective_scope
        ):
            merged[path.relative_to(module_root).as_posix()] = path
        candidates = [merged[key] for key in sorted(merged)]
    copied: list[dict] = []
    skipped: list[dict] = []
    total = 0

    for src in candidates:
        rel = src.relative_to(module_root)
        size = src.stat().st_size
        if size > max_file_bytes:
            skipped.append(
                {
                    "path": rel.as_posix(),
                    "reason": "FILE_TOO_LARGE",
                    "size_bytes": size,
                }
            )
            continue
        if total + size > max_total_bytes:
            skipped.append(
                {
                    "path": rel.as_posix(),
                    "reason": "PACKAGE_TOTAL_LIMIT",
                    "size_bytes": size,
                }
            )
            continue

        dst = files_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(
            {
                "path": rel.as_posix(),
                "size_bytes": size,
                "sha256": sha256_file(src),
            }
        )
        total += size

    repo_state_path = package_dir / "repository_state.json"
    blueprint_refs_path = package_dir / "blueprint_source_refs.json"

    write_json(repo_state_path, check)
    bp_refs = blueprint_ref_catalog(blueprint_root)
    write_json(blueprint_refs_path, bp_refs)

    manifest = {
        "schema_version": "forprint_module_assistant_package_v0_1",
        "script_id": SCRIPT_ID,
        "package_type": package_type,
        "target_module_or_portfolio_scope": module_id,
        "scope": effective_scope,
        "requested_scope": scope,
        "topics": topics,
        "purpose": (
            "Fresh-assistant module onboarding"
            if package_type == "MODULE_ONBOARD"
            else "Bounded module context transfer"
        ),
        "intended_use": (
            "Navigation and recovery context only; re-read live Blueprint sources before action."
        ),
        "source": {
            "module_head": head,
            "module_branch": check["module"]["branch"],
            "blueprint_head": check["blueprint"]["head"],
            "blueprint_branch": check["blueprint"]["branch"],
            "registration_state": registration_state,
        },
        "authority": {
            "execution": False,
            "dispatch": False,
            "acceptance": False,
            "roadmap_mutation": False,
            "release": False,
            "cross_repository_write": False,
        },
        "policy_markers": {
            "system_blueprint_access_from_prepress":
                SYSTEM_BLUEPRINT_ACCESS_FROM_PREPRESS,
        },
        "selection": {
            "file_count": len(copied),
            "total_bytes": total,
            "max_file_bytes": max_file_bytes,
            "max_total_bytes": max_total_bytes,
            "skipped_count": len(skipped),
        },
        "module_files": copied,
        "skipped": skipped,
        "blueprint_sources": bp_refs,
    }
    manifest_path = package_dir / "manifest.json"
    write_json(manifest_path, manifest)

    readme = f"""# ForPrint Assistant Package

Package type: `{package_type}`
Target module: `{module_id}`
Module HEAD: `{head}`
Blueprint HEAD observed: `{check['blueprint']['head']}`
Scope: `{effective_scope}`
Requested scope: `{scope}`
Topics: `{', '.join(topics) if topics else 'none'}`

## System Blueprint access boundary

`{SYSTEM_BLUEPRINT_POLICY_MARKER}`

From ForPrint Prepress Hub, System Blueprint is strictly read-only.
A Prepress assistant may read Blueprint state, directives and context, but must
not create, edit, stage, commit, push, apply, release or otherwise mutate the
System Blueprint repository.

If a Blueprint-owned change is needed, create a Prepress-owned request or
completion package and hand it to Blueprint for Blueprint-side processing and
confirmation.

## Authority boundary

This archive is navigation/evidence only.

It does **not** grant execution, dispatch, acceptance, roadmap mutation, release,
production access, cross-repository write, commit, push or merge authority.

Before changing code, a fresh assistant must re-read the live Blueprint sources
listed in `blueprint_source_refs.json`, inspect current Git state, then follow
`module_files/coordination/bootstrap/START_HERE.md`.

Module-local copies and this archive are not permanent project-wide sources of truth.
"""
    (package_dir / "README.md").write_text(readme, encoding="utf-8")

    archive = base.with_suffix(".tar.gz")
    if archive.exists():
        archive.unlink()
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(package_dir, arcname=f"{module_id}_{slug}")

    result = {
        "package_type": package_type,
        "module_id": module_id,
        "module_head": head,
        "package_dir": str(package_dir.relative_to(module_root)),
        "archive": str(archive.relative_to(module_root)),
        "archive_sha256": sha256_file(archive),
        "file_count": len(copied),
        "total_bytes": total,
        "skipped_count": len(skipped),
        "status": "PASS",
    }
    write_json(base / "result.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--module-root", default=".")
    parser.add_argument("--module", required=True)
    parser.add_argument("--blueprint-root", required=True)
    parser.add_argument(
        "--registration-state",
        choices=("registered", "bootstrap_unregistered"),
        default="registered",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check")

    pack = sub.add_parser("pack")
    pack.add_argument(
        "--package-type",
        choices=("MODULE_ONBOARD", "MODULE_CONTEXT"),
        required=True,
    )
    pack.add_argument("--scope", default="bootstrap")
    pack.add_argument("--topics", default="")
    pack.add_argument("--max-file-bytes", type=int, default=DEFAULT_MAX_FILE_BYTES)
    pack.add_argument("--max-total-bytes", type=int, default=DEFAULT_MAX_TOTAL_BYTES)

    args = parser.parse_args()
    module_root = Path(args.module_root).resolve()
    blueprint_root = Path(args.blueprint_root).resolve()

    print(f"SCRIPT_ID={SCRIPT_ID}")

    try:
        if args.command == "check":
            result = verify(
                module_root=module_root,
                blueprint_root=blueprint_root,
                module_id=args.module,
                registration_state=args.registration_state,
            )
            print(
                "MODULE_ASSISTANT_HANDOFF_CHECK="
                + result["status"]
            )
            print(f"MODULE_ID={args.module}")
            print(
                f"REGISTRATION_STATE={args.registration_state}"
            )
            print(
                "MODULE_POLICY_PRESENT="
                + str(result["module_policy"]["present"]).lower()
            )
            print(
                f"MISSING_LOCAL_COUNT={len(result['missing_local'])}"
            )
            print(
                f"MISSING_BLUEPRINT_COUNT={len(result['missing_blueprint'])}"
            )
            print(f"WARNING_COUNT={len(result['warnings'])}")
            print(f"{SYSTEM_BLUEPRINT_POLICY_MARKER}")
            print("BLUEPRINT_MUTATED=false")
            print("GIT_MUTATED=false")
            return 0 if result["status"] == "PASS" else 2

        result = build_pack(
            module_root=module_root,
            blueprint_root=blueprint_root,
            module_id=args.module,
            registration_state=args.registration_state,
            package_type=args.package_type,
            scope=args.scope,
            topics=topics_list(args.topics),
            max_file_bytes=args.max_file_bytes,
            max_total_bytes=args.max_total_bytes,
        )
        print("MODULE_ASSISTANT_CONTEXT=PASS")
        print(f"PACKAGE_TYPE={result['package_type']}")
        print(f"MODULE_ID={result['module_id']}")
        print(f"MODULE_HEAD={result['module_head']}")
        print(f"FILE_COUNT={result['file_count']}")
        print(f"TOTAL_BYTES={result['total_bytes']}")
        print(f"SKIPPED_COUNT={result['skipped_count']}")
        print(f"ARCHIVE={result['archive']}")
        print(f"ARCHIVE_SHA256={result['archive_sha256']}")
        print("GRANTS_EXECUTION_AUTHORITY=false")
        print(f"{SYSTEM_BLUEPRINT_POLICY_MARKER}")
        print("BLUEPRINT_MUTATED=false")
        print("GIT_MUTATED=false")
        return 0
    except ContextError as exc:
        print("MODULE_ASSISTANT_CONTEXT=FAIL")
        print(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

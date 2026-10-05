#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

REPORT_DIR = (
    ROOT
    / "tmp"
    / "operator_reports"
    / "project_closeout"
)


class Fail(RuntimeError):
    pass


def run(cmd):
    cp = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    if cp.stdout:
        print(
            cp.stdout,
            end=""
            if cp.stdout.endswith("\n")
            else "\n",
        )

    if cp.returncode:
        raise Fail(
            "COMMAND_FAILED="
            + " ".join(cmd)
            + f" rc={cp.returncode}"
        )

    return cp.stdout.rstrip("\n")


def git(*args):
    return run(
        ["git", *args]
    )


def status():
    result = []

    raw = git(
        "status",
        "--short",
        "--untracked-files=all",
    )

    for line in raw.splitlines():
        if len(line) >= 4:
            result.append(
                line[3:]
            )

    return sorted(result)


def load(path):
    data = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    required = (
        "workstream_id",
        "expected_head",
        "commit_message",
        "write_set",
    )

    for key in required:
        if key not in data:
            raise Fail(
                f"MANIFEST_MISSING={key}"
            )

    return data


def baseline(manifest):
    head = git(
        "rev-parse",
        "HEAD",
    )

    upstream = git(
        "rev-parse",
        "@{upstream}",
    )

    if head != manifest["expected_head"]:
        raise Fail(
            "HEAD_MISMATCH="
            f"{head}!="
            f"{manifest['expected_head']}"
        )

    if upstream != head:
        raise Fail(
            "UPSTREAM_MISMATCH="
            f"{upstream}!={head}"
        )

    staged = git(
        "diff",
        "--cached",
        "--name-only",
    )

    if staged:
        raise Fail(
            "STAGING_NOT_EMPTY"
        )

    expected = sorted(
        manifest["write_set"]
    )

    actual = status()

    if actual != expected:
        raise Fail(
            "WRITE_SET_MISMATCH "
            "actual="
            + json.dumps(actual)
            + " expected="
            + json.dumps(expected)
        )


def fingerprint(paths):
    digest = hashlib.sha256()

    for rel in sorted(paths):
        path = ROOT / rel

        if not path.is_file():
            raise Fail(
                f"WRITE_SET_PATH_MISSING={rel}"
            )

        digest.update(
            rel.encode("utf-8")
        )
        digest.update(b"\0")
        digest.update(
            path.read_bytes()
        )
        digest.update(b"\0")

    return digest.hexdigest()


def privacy_scan(paths):
    blocked_names = {
        ".env",
        ".env.local",
        ".env.production",
        "id_rsa",
        "id_ed25519",
    }

    blocked_suffixes = {
        ".pem",
        ".key",
        ".p12",
        ".pfx",
    }

    private_markers = (
        b"-----BEGIN " + b"PRIVATE KEY-----",
        b"-----BEGIN " + b"OPENSSH PRIVATE KEY-----",
    )

    for rel in paths:
        path = ROOT / rel

        if path.name in blocked_names:
            raise Fail(
                f"FORBIDDEN_SECRET_FILE={rel}"
            )

        if (
            path.suffix.lower()
            in blocked_suffixes
        ):
            raise Fail(
                f"FORBIDDEN_SECRET_FILE={rel}"
            )

        raw = path.read_bytes()

        for marker in private_markers:
            if marker in raw:
                raise Fail(
                    f"PRIVATE_KEY_MATERIAL={rel}"
                )

    jsx = (
        ROOT
        / "scripts"
        / "graphic_design_lab"
        / "greeting_cards"
        / "illustrator_operator_companion_v0_1.jsx"
    )

    if jsx.is_file():
        text = jsx.read_text(
            encoding="utf-8"
        )

        for char in text:
            if (
                "\u0400"
                <= char
                <= "\u04ff"
            ):
                raise Fail(
                    "CLIENT_LITERAL_SCAN_FAIL="
                    "CYRILLIC_IN_GENERIC_JSX"
                )


def report_path(workstream):
    return (
        REPORT_DIR
        / f"{workstream}.json"
    )


def review(manifest):
    baseline(manifest)

    privacy_scan(
        manifest["write_set"]
    )

    for cmd in manifest.get(
        "review_commands",
        [],
    ):
        run(cmd)

    run(
        [
            "git",
            "diff",
            "--check",
            "--",
            *manifest["write_set"],
        ]
    )

    fp = fingerprint(
        manifest["write_set"]
    )

    token = hashlib.sha256(
        (
            manifest["workstream_id"]
            + "\0"
            + manifest["expected_head"]
            + "\0"
            + fp
        ).encode("utf-8")
    ).hexdigest()

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    dirty = {}

    raw_status = git(
        "status",
        "--short",
        "--untracked-files=all",
    )

    for line in raw_status.splitlines():
        if len(line) >= 4:
            dirty[line[3:]] = line[:2]

    rows = []

    for rel in sorted(
        manifest["write_set"]
    ):
        path = ROOT / rel

        rows.append(
            {
                "path": rel,
                "git_status": dirty.get(
                    rel,
                    "??",
                ),
                "size": path.stat().st_size,
                "sha256": hashlib.sha256(
                    path.read_bytes()
                ).hexdigest(),
            }
        )

    record = {
        "status":
            "REVIEWED_NOT_APPLIED",
        "workstream_id":
            manifest["workstream_id"],
        "expected_head":
            manifest["expected_head"],
        "content_fingerprint":
            fp,
        "approval_token":
            token,
        "write_set":
            rows,
    }

    report = report_path(
        manifest["workstream_id"]
    )

    report.write_text(
        json.dumps(
            record,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "PROJECT_CLOSEOUT_REVIEW=PASS"
    )

    print(
        "WRITE_SET_COUNT="
        f"{len(rows)}"
    )

    print(
        "APPROVAL_TOKEN="
        f"{token}"
    )

    print(
        "REPORT="
        f"{report.relative_to(ROOT)}"
    )

    print(
        "STAGING_PERFORMED=false"
    )

    print(
        "COMMIT_PERFORMED=false"
    )

    print(
        "PUSH_PERFORMED=false"
    )


def unstage_exact(paths):
    cp = subprocess.run(
        ["git", "restore", "--staged", "--", *paths],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    if cp.returncode:
        raise Fail(
            "EXACT_UNSTAGE_FAILED="
            + cp.stdout.strip()
        )


def apply(manifest, confirm):
    if confirm != "YES":
        raise Fail(
            "EXPLICIT_CONFIRMATION_REQUIRED"
        )

    report = report_path(
        manifest["workstream_id"]
    )

    if not report.is_file():
        raise Fail(
            "REVIEW_REQUIRED"
        )

    saved = json.loads(
        report.read_text(
            encoding="utf-8"
        )
    )

    baseline(manifest)

    privacy_scan(
        manifest["write_set"]
    )

    fp = fingerprint(
        manifest["write_set"]
    )

    if (
        fp
        != saved.get(
            "content_fingerprint"
        )
    ):
        raise Fail(
            "REVIEW_STALE_CONTENT_CHANGED"
        )

    token = hashlib.sha256(
        (
            manifest["workstream_id"]
            + "\0"
            + manifest["expected_head"]
            + "\0"
            + fp
        ).encode("utf-8")
    ).hexdigest()

    if (
        token
        != saved.get(
            "approval_token"
        )
    ):
        raise Fail(
            "REVIEW_TOKEN_MISMATCH"
        )

    try:
        for rel in manifest["write_set"]:
            run(
                [
                    "git",
                    "add",
                    "--",
                    rel,
                ]
            )

        staged = sorted(
            item
            for item in git(
                "diff",
                "--cached",
                "--name-only",
            ).splitlines()
            if item
        )

        expected = sorted(
            manifest["write_set"]
        )

        if staged != expected:
            raise Fail(
                "STAGED_SET_MISMATCH="
                + json.dumps(staged)
            )

        run(
            [
                "git",
                "diff",
                "--cached",
                "--check",
            ]
        )

    except Exception:
        unstage_exact(
            manifest["write_set"]
        )
        raise

    run(
        [
            "git",
            "commit",
            "-m",
            manifest[
                "commit_message"
            ],
        ]
    )

    run(
        [
            "git",
            "push",
        ]
    )

    head = git(
        "rev-parse",
        "HEAD",
    )

    upstream = git(
        "rev-parse",
        "@{upstream}",
    )

    if head != upstream:
        raise Fail(
            "POST_PUSH_SYNC_FAIL="
            f"{head}!={upstream}"
        )

    final = status()

    if final:
        raise Fail(
            "FINAL_TREE_NOT_CLEAN="
            + json.dumps(final)
        )

    print(
        "PROJECT_CLOSEOUT_APPLY=PASS"
    )

    print(
        f"COMMIT={head}"
    )

    print(
        "HEAD_EQUALS_UPSTREAM=true"
    )

    print(
        "FINAL_TREE_CLEAN=true"
    )

    print(
        "PUSH_PERFORMED=true"
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "mode",
        choices=(
            "review",
            "apply",
        ),
    )

    parser.add_argument(
        "--manifest",
        required=True,
    )

    parser.add_argument(
        "--confirm",
        default="NO",
    )

    args = parser.parse_args()

    manifest_path = (
        ROOT
        / args.manifest
    ).resolve()

    try:
        manifest_path.relative_to(
            ROOT
        )
    except ValueError:
        raise Fail(
            "MANIFEST_OUTSIDE_REPOSITORY"
        )

    manifest = load(
        manifest_path
    )

    if args.mode == "review":
        review(manifest)
    else:
        apply(
            manifest,
            args.confirm,
        )


if __name__ == "__main__":
    try:
        main()

    except Fail as exc:
        print(
            "PROJECT_CLOSEOUT=FAIL"
        )

        print(
            f"ERROR={exc}"
        )

        raise SystemExit(2)

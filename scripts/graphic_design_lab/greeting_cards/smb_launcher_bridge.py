#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import subprocess
from pathlib import Path, PurePosixPath
from typing import Mapping

REPO = Path(__file__).resolve().parents[3]
CONSTRUCTOR_MAKE_TARGET = "gdl-greeting-card-constructor-ingest"

SMB_SHARE_ROOTS: dict[str, Path] = {
    "In_Progress": Path("/srv/smb/In_Progress/data"),
}

ALLOWED_BUNDLE_NAMES = {
    "accepted_constructor_bundle.yaml",
    "accepted_constructor_bundle.yml",
    "accepted_constructor_bundle.json",
}


def decode_relative_path(token: str) -> PurePosixPath:
    if not token:
        raise RuntimeError("relative_path_token_missing")

    padding = "=" * (-len(token) % 4)
    try:
        raw = base64.urlsafe_b64decode(token + padding)
        value = raw.decode("utf-8")
    except Exception as exc:
        raise RuntimeError("relative_path_token_invalid") from exc

    if not value or "\x00" in value:
        raise RuntimeError("relative_path_invalid")

    value = value.replace("\\", "/")
    relative = PurePosixPath(value)

    if relative.is_absolute():
        raise RuntimeError("relative_path_must_not_be_absolute")
    if any(part in {"", ".", ".."} for part in relative.parts):
        raise RuntimeError("relative_path_contains_forbidden_segment")

    return relative


def resolve_bundle_path(
    share: str,
    relative_path_b64: str,
    *,
    share_roots: Mapping[str, Path] | None = None,
) -> Path:
    roots = SMB_SHARE_ROOTS if share_roots is None else share_roots
    if share not in roots:
        raise RuntimeError(f"unsupported_smb_share:{share}")

    root = Path(roots[share]).resolve()
    relative = decode_relative_path(relative_path_b64)
    candidate = (root / Path(*relative.parts)).resolve(strict=False)

    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise RuntimeError("resolved_path_escapes_share_root") from exc

    if candidate.name.lower() not in ALLOWED_BUNDLE_NAMES:
        raise RuntimeError(f"unsupported_bundle_filename:{candidate.name}")
    if not candidate.is_file():
        raise RuntimeError(f"accepted_constructor_bundle_missing:{candidate}")

    return candidate


def constructor_entrypoint_command(bundle_path: Path) -> list[str]:
    return [
        "make",
        CONSTRUCTOR_MAKE_TARGET,
        f"BUNDLE={bundle_path}",
    ]


def launch_bundle(share: str, relative_path_b64: str) -> int:
    bundle_path = resolve_bundle_path(share, relative_path_b64)
    makefile = REPO / "Makefile"
    if not makefile.is_file():
        raise RuntimeError(f"constructor_makefile_missing:{makefile}")

    print("GDL_GREETING_CARD_SMB_LAUNCH=START")
    print(f"SMB_SHARE={share}")
    print(f"BUNDLE_NAME={bundle_path.name}")
    print("PATH_WITHIN_ALLOWED_SHARE=true")
    print("CONSTRUCTOR_ENTRYPOINT=gdl-greeting-card-constructor-ingest")

    cp = subprocess.run(
        constructor_entrypoint_command(bundle_path),
        cwd=REPO,
        check=False,
    )
    if cp.returncode:
        raise RuntimeError(
            f"constructor_ingest_failed:return_code={cp.returncode}"
        )

    print("GDL_GREETING_CARD_SMB_LAUNCH=PASS")
    print("MANUAL_LINUX_PATH_ENTRY=false")
    print("EXACT_BUNDLE_PATH_PASSED=true")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--share", required=True)
    parser.add_argument("--relative-path-b64", required=True)
    args = parser.parse_args()
    launch_bundle(args.share, args.relative_path_b64)


if __name__ == "__main__":
    main()

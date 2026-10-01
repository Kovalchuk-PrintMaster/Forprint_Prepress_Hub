#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
EMP = ROOT / "coordination/roadmaps/graphic_design_lab/planning_evidence/empirical_learning"
SCHEMA_PATH = EMP / "schemas/empirical_case_template_v0_1.yaml"
INDEX_PATH = EMP / "index.yaml"
LOADER_INDEX_PATH = EMP / "loaders/index.yaml"
PROTOCOL_PATH = EMP / "operator_intake_experiment_protocol_v0_1.yaml"
DEFAULT_FIXTURE = ROOT / "tests/fixtures/graphic_design_lab/gdl_empirical_case_menu_sanitized_v0_1.yaml"

ALLOWED_OPERATOR = {"accepted", "accepted_with_reservations", "rejected", "unknown"}
ALLOWED_CUSTOMER = {"accepted", "revision_requested", "rejected", "unknown"}
ALLOWED_SATISFACTION = {"positive", "neutral", "negative", "not_observed"}

EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)")


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected_mapping:{path}")
    return data


def has_pii(value: Any) -> bool:
    if isinstance(value, dict):
        return any(has_pii(v) for v in value.values())
    if isinstance(value, list):
        return any(has_pii(v) for v in value)
    if not isinstance(value, str):
        return False
    if EMAIL_RE.search(value):
        return True
    phone_match = PHONE_RE.search(value)
    if phone_match and sum(ch.isdigit() for ch in phone_match.group(0)) >= 9:
        return True
    return False


def validate_schema_surface(schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = (
        "case_identity",
        "product",
        "task",
        "input_context",
        "intake",
        "creator_prompt",
        "creator_context",
        "result",
        "outcome",
        "quality_observations",
        "workflow_observations",
        "lessons",
        "artifact_policy",
        "authority",
    )
    for key in required:
        if key not in schema:
            errors.append(f"schema_missing:{key}")

    policy = schema.get("artifact_policy", {})
    if policy.get("repository_contains_heavy_artifact") is not False:
        errors.append("schema_heavy_artifact_boundary_invalid")
    if policy.get("external_reference_preferred") is not True:
        errors.append("schema_external_reference_boundary_invalid")
    if policy.get("pii_allowed_in_git") is not False:
        errors.append("schema_pii_boundary_invalid")

    authority = schema.get("authority", {})
    if authority.get("case_is_evidence_not_policy") is not True:
        errors.append("schema_case_evidence_boundary_invalid")
    if authority.get("one_case_must_not_auto_create_global_rule") is not True:
        errors.append("schema_single_case_promotion_boundary_invalid")
    return errors


def validate_case(case: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    required_values = {
        "case_identity.case_id": case.get("case_identity", {}).get("case_id"),
        "case_identity.observed_at": case.get("case_identity", {}).get("observed_at"),
        "product.family": case.get("product", {}).get("family"),
        "task.category": case.get("task", {}).get("category"),
        "task.objective": case.get("task", {}).get("objective"),
        "creator_prompt.prompt_id": case.get("creator_prompt", {}).get("prompt_id"),
        "creator_prompt.prompt_version": case.get("creator_prompt", {}).get("prompt_version"),
        "creator_prompt.prompt_text_ref": case.get("creator_prompt", {}).get("prompt_text_ref"),
        "creator_context.creator_class": case.get("creator_context", {}).get("creator_class"),
        "result.result_revision": case.get("result", {}).get("result_revision"),
        "result.external_artifact_ref": case.get("result", {}).get("external_artifact_ref"),
    }
    for key, value in required_values.items():
        if value in (None, "", []):
            errors.append(f"case_required:{key}")

    outcome = case.get("outcome", {})
    if outcome.get("operator_acceptance") not in ALLOWED_OPERATOR:
        errors.append("case_operator_acceptance_invalid")
    if outcome.get("customer_acceptance") not in ALLOWED_CUSTOMER:
        errors.append("case_customer_acceptance_invalid")
    if outcome.get("customer_explicit_satisfaction") not in ALLOWED_SATISFACTION:
        errors.append("case_customer_satisfaction_invalid")

    first = outcome.get("first_attempt_accepted")
    accepted = outcome.get("accepted_attempt")
    revisions = outcome.get("revision_count")
    if first is not None and not isinstance(first, bool):
        errors.append("case_first_attempt_accepted_not_boolean")
    if accepted is not None and (
        not isinstance(accepted, int) or isinstance(accepted, bool) or accepted < 1
    ):
        errors.append("case_accepted_attempt_invalid")
    if revisions is not None and (
        not isinstance(revisions, int) or isinstance(revisions, bool) or revisions < 0
    ):
        errors.append("case_revision_count_invalid")
    if first is True and accepted not in (None, 1):
        errors.append("case_first_attempt_metric_conflict")
    if accepted is not None and revisions is not None and revisions < accepted - 1:
        errors.append("case_revision_count_below_accepted_attempt")

    policy = case.get("artifact_policy", {})
    if policy.get("repository_contains_heavy_artifact") is not False:
        errors.append("case_heavy_artifact_boundary_invalid")
    if policy.get("external_reference_preferred") is not True:
        errors.append("case_external_reference_boundary_invalid")
    if policy.get("pii_allowed_in_git") is not False:
        errors.append("case_pii_policy_invalid")

    pii_surface = {
        "case_identity": case.get("case_identity", {}),
        "input_context": case.get("input_context", {}),
        "creator_prompt": case.get("creator_prompt", {}),
        "result": case.get("result", {}),
    }
    if has_pii(pii_surface):
        errors.append("case_possible_customer_pii_detected")

    for key in ("strengths", "weaknesses", "failure_modes", "ambiguities"):
        if not isinstance(case.get("quality_observations", {}).get(key), list):
            errors.append(f"case_quality_list_invalid:{key}")
    return errors


def build_index() -> dict[str, Any]:
    empirical_index = load_yaml(INDEX_PATH)
    loader_index = load_yaml(LOADER_INDEX_PATH)

    experiments = []
    experiment_root = EMP / "experiments"
    for directory in sorted(p for p in experiment_root.iterdir() if p.is_dir()):
        files = sorted(p.name for p in directory.iterdir() if p.is_file())
        numbered_evidence = [
            name for name in files if re.match(r"^[0-9]{2}_", name)
        ]
        experiments.append(
            {
                "experiment_id": directory.name,
                "file_count": len(files),
                "numbered_evidence_file_count": len(numbered_evidence),
                "files": files,
            }
        )

    return {
        "schema_version": "gdl_empirical_discovery_index_v0_1",
        "authority": "LOCAL_EMPIRICAL_EVIDENCE_NOT_EXECUTION_AUTHORITY",
        "canonical_index": str(INDEX_PATH.relative_to(ROOT)),
        "loader_index": str(LOADER_INDEX_PATH.relative_to(ROOT)),
        "schema": str(SCHEMA_PATH.relative_to(ROOT)),
        "operator_protocol": str(PROTOCOL_PATH.relative_to(ROOT)),
        "registered_loaders": loader_index.get("roles", {}),
        "experiments": experiments,
        "blueprint_access": empirical_index.get("blueprint_sync", {}).get(
            "access_from_prepress"
        ),
    }


def render_summary(index: dict[str, Any]) -> str:
    experiments = index["experiments"]
    lines = [
        "GDL Empirical Learning Summary",
        "authority: LOCAL_EMPIRICAL_EVIDENCE_NOT_EXECUTION_AUTHORITY",
        f"experiment_count: {len(experiments)}",
    ]
    for experiment in experiments:
        lines.append(
            f"- {experiment['experiment_id']}: "
            f"{experiment['file_count']} directory files / "
            f"{experiment['numbered_evidence_file_count']} numbered evidence files"
        )
    creator = index.get("registered_loaders", {}).get("Creator Assistant", {})
    lines.append(f"creator_loader_versions: {','.join(sorted(creator)) or 'none'}")
    lines.append(f"blueprint_access: {index.get('blueprint_access')}")
    return "\n".join(lines)


def run_validate(case_path: Path) -> int:
    errors = []
    errors.extend(validate_schema_surface(load_yaml(SCHEMA_PATH)))
    errors.extend(validate_case(load_yaml(case_path)))

    protocol = load_yaml(PROTOCOL_PATH)
    if protocol.get("mode") != "MANUAL_EXPERIMENTAL":
        errors.append("operator_protocol_mode_invalid")
    if protocol.get("authority", {}).get("activates_runtime") is not False:
        errors.append("operator_protocol_runtime_authority_invalid")
    if protocol.get("authority", {}).get("allows_production_write") is not False:
        errors.append("operator_protocol_production_authority_invalid")
    if protocol.get("authority", {}).get("mutates_blueprint") is not False:
        errors.append("operator_protocol_blueprint_authority_invalid")

    if errors:
        print("GDL_EMPIRICAL_VALIDATE=FAIL")
        for error in errors:
            print(f"ERROR={error}")
        return 1

    print("GDL_EMPIRICAL_VALIDATE=PASS")
    print(f"CASE={case_path.relative_to(ROOT)}")
    print("PII_IN_GIT=false")
    print("HEAVY_ARTIFACT_IN_GIT=false")
    print("EXTERNAL_ARTIFACT_REFERENCE=true")
    print("RUNTIME_INITIALIZED=false")
    print("PRODUCTION_WRITE=false")
    print("BLUEPRINT_MUTATED=false")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate")
    validate.add_argument("--case", type=Path, default=DEFAULT_FIXTURE)

    sub.add_parser("index")
    sub.add_parser("summary")

    args = parser.parse_args()
    if args.command == "validate":
        case_path = args.case
        if not case_path.is_absolute():
            case_path = ROOT / case_path
        return run_validate(case_path)

    index = build_index()
    if args.command == "index":
        print(json.dumps(index, indent=2, ensure_ascii=False, sort_keys=True))
        return 0

    print(render_summary(index))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

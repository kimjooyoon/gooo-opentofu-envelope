#!/usr/bin/env python3
"""Build a small, read-only Gooo/OpenTofu evidence envelope."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


STATE_VALUES = {"CLOSED", "UNKNOWN", "REFUTED"}
EXECUTION_VALUES = {"EXECUTED", "REUSED", "SKIPPED", "NOT_APPLICABLE"}
CACHE_VALUES = {"HIT", "MISS", "DISABLED", "UNKNOWN"}
REUSE_VALUES = {"REUSED", "NOT_REUSED", "INELIGIBLE", "UNKNOWN"}
PERSISTENCE_VALUES = {"EPHEMERAL", "PERSISTENT", "UNKNOWN"}
UNKNOWN_FIELDS = {"stage", "step", "reason", "unknown_class", "next_operation", "blocked_by"}
PLAN_ACTIONS = {"noop", "create", "read", "update", "replace", "delete", "move"}
REUSE_KEY_FIELDS = [
    "source_digest",
    "toolchain_digest",
    "command_digest",
    "config_digest",
    "dependency_digest",
    "provider_lock_digest",
    "test_inventory_digest",
    "policy_digest",
]
ACTIVITIES = [
    "DeclareGoooInfrastructureIntent",
    "BindGoooIntentToOpenTofu",
    "ConsumePinnedOpenTofuJSONSpec",
    "GenerateOpenTofuCompatibleArtifact",
    "GenerateHumanDossier",
    "VerifyGeneratedOutputs",
    "GenerateOpenTofuPlanReceipt",
    "MatchGoooIntentToOpenTofuPlan",
    "PreserveUnknownCase",
    "RefuteContradictionCase",
    "VerifyDeterministicReplay",
    "PreserveReadOnlyBoundary",
]


def die(message: str) -> None:
    raise SystemExit(message)


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        die(f"cannot read JSON {path}: {exc}")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        die(f"cannot hash {path}: {exc}")
    return digest.hexdigest()


def sha256_value(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        die(f"{name} must be a non-negative integer")
    return value


def contract(path: Path) -> dict[str, Any]:
    value = read_json(path)
    cells = value.get("cells")
    if value.get("schema") != "gooo/opentofu-envelope/denominator/v1" or value.get("target_cells") != 12 or not isinstance(cells, list) or len(cells) != 12:
        die("denominator must contain exactly 12 cells")
    if {cell.get("activity") for cell in cells} != set(ACTIVITIES):
        die("denominator activity set is not exactly the released 12 activities")
    for family in ("FOUNDATION", "COHERENCE", "REGRESSION"):
        if sum(cell.get("proof_family") == family for cell in cells) != 4:
            die(f"proof family denominator is not 4 for {family}")
    for indicator in ("DRIVER", "OUTCOME", "GUARDRAIL"):
        if sum(cell.get("indicator") == indicator for cell in cells) != 4:
            die(f"indicator denominator is not 4 for {indicator}")
    if sum(len(cell.get("depends_on", [])) for cell in cells) != 14:
        die("binding edge denominator is not 14")
    return value


def release_lock(path: Path) -> dict[str, Any]:
    value = read_json(path)
    if value.get("schema") != "gooo/opentofu-envelope/release-lock/v1":
        die("unsupported release lock")
    tofu = value.get("opentofu", {})
    if tofu.get("iac_engine") != "OPENTOFU" or tofu.get("iac_engine_version") != "1.12.6":
        die("release lock does not explicitly identify OpenTofu")
    if value.get("toolchain", {}).get("go") != "1.27.x":
        die("release lock does not explicitly identify Go 1.27")
    authority = value.get("authority", {})
    required_zero = [
        "repository_writes", "local_test_executions", "local_build_executions", "local_formatter_executions",
        "local_vet_executions", "opentofu_source_checkouts", "opentofu_build_executions", "opentofu_init_executions",
        "opentofu_apply_executions", "opentofu_destroy_executions", "opentofu_import_executions", "opentofu_state_mutations",
        "opentofu_test_executions", "opentofu_provider_accesses", "opentofu_cloud_accesses",
    ]
    if any(authority.get(key) != 0 for key in required_zero) or authority.get("opentofu_validate_executions") != 1 or authority.get("opentofu_plan_executions") != 1 or authority.get("opentofu_show_executions") != 1:
        die("release lock authority is not read-only")
    cache = value.get("cache_contract", {})
    if cache.get("installation_binary_cache_state") not in CACHE_VALUES or cache.get("go_build_cache_state") not in CACHE_VALUES:
        die("binary and Go build cache states are invalid")
    if cache.get("prior_test_evidence_reuse_state") not in REUSE_VALUES or cache.get("runner_persistence") not in PERSISTENCE_VALUES:
        die("prior evidence reuse or runner persistence state is invalid")
    if cache.get("reuse_key_fields") != REUSE_KEY_FIELDS:
        die("reuse key field set is not minimal and exact")
    return value


def inventory(root: Path, output: Path) -> None:
    root = root.resolve()
    directories: list[str] = []
    files: list[dict[str, Any]] = []
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name != ".git")
        current_path = Path(current)
        if current_path != root:
            directories.append(current_path.relative_to(root).as_posix())
        for filename in sorted(filenames):
            path = current_path / filename
            relative = path.relative_to(root).as_posix()
            if relative == "README.md" or not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                die(f"cannot read inventory file {path}: {exc}")
            line_count = len(text.splitlines())
            files.append({"path": relative, "bytes": path.stat().st_size, "lines": line_count})
    files.sort(key=lambda item: item["path"])
    result = {
        "schema": "gooo/opentofu-envelope/inventory/v1",
        "root_readme_excluded": True,
        "descendant_directories": directories,
        "regular_files": files,
        "descendant_directory_count": len(directories),
        "regular_file_count": len(files),
        "physical_line_count": sum(item["lines"] for item in files),
        "go_physical_files": sum(item["path"].endswith(".go") for item in files),
        "go_physical_lines": sum(item["lines"] for item in files if item["path"].endswith(".go")),
        "gooo_physical_files": sum(item["path"].endswith(".gooo") for item in files),
        "gooo_physical_lines": sum(item["lines"] for item in files if item["path"].endswith(".gooo")),
    }
    write_json(output, result)


def graph_activities(graph: dict[str, Any]) -> dict[str, str]:
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        die("released graph nodes are missing")
    result = {node.get("name"): node.get("id") for node in nodes if node.get("kind") == "Activity"}
    if set(result) != set(ACTIVITIES) or any(not isinstance(value, str) for value in result.values()):
        die("released graph does not expose exactly the 12 activities")
    return result


def bind(source_path: Path, graph_path: Path, denominator_path: Path, output: Path) -> None:
    denominator = contract(denominator_path)
    source_sha = sha256_file(source_path)
    graph = read_json(graph_path)
    activity_ids = graph_activities(graph)
    cells = denominator["cells"]
    bindings = []
    for cell in cells:
        bindings.append({
            "ordinal": cell["ordinal"],
            "cell_id": cell["id"],
            "activity": cell["activity"],
            "activity_id": activity_ids[cell["activity"]],
            "stage": cell["stage"],
            "step": cell["step"],
            "proof_family": cell["proof_family"],
            "indicator": cell["indicator"],
            "depends_on": cell["depends_on"],
            "producer": {"source": str(source_path), "ir": str(graph_path), "generated_artifact": "bindings.json", "evaluator": "scripts/envelope.py:bind"},
        })
    write_json(output, {
        "schema": "gooo/opentofu-envelope/bindings/v1",
        "state": "CLOSED",
        "source_sha256": source_sha,
        "graph_sha256": sha256_file(graph_path),
        "activity_count": len(bindings),
        "binding_edges": sum(len(item["depends_on"]) for item in bindings),
        "bindings": bindings,
    })


def generated_artifact() -> dict[str, Any]:
    return {
        "//": "Generated from the Gooo intent; OpenTofu is the pinned configuration authority.",
        "output": {"hello_id": {"value": "${terraform_data.hello.id}"}},
        "resource": {"terraform_data": {"hello": {"input": "hello-from-gooo"}}},
    }


def generate(source_path: Path, graph_path: Path, lock_path: Path, spec_path: Path, bindings_path: Path, denominator_path: Path, inventory_path: Path, output_dir: Path) -> None:
    lock = release_lock(lock_path)
    denominator = contract(denominator_path)
    bindings = read_json(bindings_path)
    if bindings.get("state") != "CLOSED" or bindings.get("activity_count") != 12:
        die("bindings are not closed")
    if not spec_path.is_file():
        die("pinned OpenTofu JSON specification is missing")
    inventory_doc = read_json(inventory_path)
    artifact = generated_artifact()
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "intent.tf.json", artifact)
    lines = [
        "# Gooo OpenTofu Envelope",
        "",
        "This dossier is a deterministic, read-only observation envelope.",
        "",
        "## Authority",
        "",
        f"- Gooo source SHA-256: `{sha256_file(source_path)}`",
        f"- released graph SHA-256: `{sha256_file(graph_path)}`",
        f"- pinned OpenTofu: `{lock['opentofu']['iac_engine']} {lock['opentofu']['iac_engine_version']}`",
        f"- pinned JSON specification SHA-256: `{sha256_file(spec_path)}`",
        "- mutation profile: `READ_ONLY`",
        "- CLI observation boundary: pinned `version -json`, `validate -json`, plan exit code, and `show -json` only",
        "",
        "## Repository inventory",
        "",
        f"- descendant directories (root README excluded): `{inventory_doc['descendant_directory_count']}`",
        f"- regular files (root README excluded): `{inventory_doc['regular_file_count']}`",
        f"- physical lines including blank/comment lines: `{inventory_doc['physical_line_count']}`",
        f"- Go files / lines: `{inventory_doc['go_physical_files']} / {inventory_doc['go_physical_lines']}`",
        f"- Gooo files / lines: `{inventory_doc['gooo_physical_files']} / {inventory_doc['gooo_physical_lines']}`",
        "",
        "## Cells",
        "",
        f"- fixed denominator: `{denominator['target_cells']}` cells",
        "- proof family denominator: `FOUNDATION 4 / COHERENCE 4 / REGRESSION 4`",
        "- indicator denominator: `DRIVER 4 / OUTCOME 4 / GUARDRAIL 4`",
        "",
        "## Artifact",
        "",
        "- `intent.tf.json` contains one built-in `terraform_data.hello` resource and one output.",
        "- No provider installation, cloud access, source checkout, state mutation, apply, destroy, import, or test execution is part of this envelope.",
        "- Exact before/after observations are absent, so improvement is `UNKNOWN`; a cache hit never counts as test-evidence reuse.",
    ]
    for item in inventory_doc["regular_files"]:
        lines.append(f"- `{item['path']}`: {item['lines']} physical lines, {item['bytes']} bytes")
    (output_dir / "dossier.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def unknown_claim(stage: str, step: str, reason: str, unknown_class: str, next_operation: str, blocked_by: list[str] | None = None) -> dict[str, Any]:
    if unknown_class not in {"DIRECT_MISSING", "OBSERVATION_UNAVAILABLE"}:
        die("unsupported unknown class")
    return {
        "state": "UNKNOWN",
        "stage": stage,
        "step": step,
        "reason": reason,
        "unknown_class": unknown_class,
        "next_operation": next_operation,
        "blocked_by": blocked_by or [],
    }


def refuted_claim(stage: str, step: str, reason: str) -> dict[str, Any]:
    return {"state": "REFUTED", "stage": stage, "step": step, "reason": reason, "unknown_class": None, "next_operation": None, "blocked_by": []}


def closed_claim(stage: str, step: str, reason: str) -> dict[str, Any]:
    return {"state": "CLOSED", "stage": stage, "step": step, "reason": reason, "unknown_class": None, "next_operation": None, "blocked_by": []}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    messages = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            die(f"plan JSONL line {number} is malformed: {exc}")
        if not isinstance(value, dict):
            die(f"plan JSONL line {number} is not an object")
        messages.append(value)
    if not messages:
        die("plan JSONL is empty")
    return messages


def load_oracle(path: Path) -> dict[str, Any]:
    oracle = read_json(path)
    expected_summary = {"add": 1, "change": 0, "forget": 0, "import": 0, "operation": "plan", "remove": 0}
    expected_effects = {"apply": 0, "cloud": 0, "network": 0, "provider": 0, "source_write": 0, "state_mutation": 0}
    if oracle.get("schema") != "gooo/opentofu-envelope/plan-oracle/v1" or oracle.get("change_summary") != expected_summary or oracle.get("side_effects") != expected_effects:
        die("plan oracle is not fixed")
    actions = oracle.get("resource_actions")
    if actions != [{"address": "terraform_data.hello", "action": "create"}]:
        die("plan oracle action set is not fixed")
    return oracle


def show_actions(show: dict[str, Any]) -> tuple[list[dict[str, str]], dict[str, int], int]:
    changes = show.get("resource_changes")
    if not isinstance(changes, list):
        die("OpenTofu show JSON resource_changes is missing")
    actions: list[dict[str, str]] = []
    summary = {"add": 0, "change": 0, "forget": 0, "import": 0, "operation": "plan", "remove": 0}
    for item in changes:
        if not isinstance(item, dict) or not isinstance(item.get("address"), str):
            die("OpenTofu show JSON resource change address is missing")
        change = item.get("change")
        raw_actions = change.get("actions") if isinstance(change, dict) else None
        if not isinstance(raw_actions, list) or not all(isinstance(action, str) for action in raw_actions):
            die("OpenTofu show JSON resource change actions are missing")
        action_set = tuple(raw_actions)
        if action_set == ("no-op",):
            action = "noop"
        elif action_set == ("create",):
            action = "create"
        elif action_set == ("update",):
            action = "update"
        elif action_set in (("delete",), ("delete", "create"), ("create", "delete")):
            action = "delete" if action_set == ("delete",) else "replace"
        elif action_set == ("read",):
            action = "read"
        else:
            die("OpenTofu show JSON resource change action set is unsupported")
        actions.append({"address": item["address"], "action": action})
        if action == "create":
            summary["add"] += 1
        elif action == "delete":
            summary["remove"] += 1
        elif action != "noop":
            summary["change"] += 1
    drift = show.get("resource_drift")
    if drift is None:
        drift = []
    if not isinstance(drift, list):
        die("OpenTofu show JSON resource_drift is malformed")
    return sorted(actions, key=lambda item: (item["address"], item["action"])), summary, len(drift)


def plan_receipt(plan_show: Path, version_json: Path, binary: Path, artifact: Path, oracle_path: Path, lock_path: Path, exit_code: int, output: Path) -> None:
    lock = release_lock(lock_path)
    oracle = load_oracle(oracle_path)
    show = read_json(plan_show)
    version = read_json(version_json)
    receipt: dict[str, Any] = {
        "schema": "gooo/opentofu-envelope/plan-receipt/v1",
        "state": "UNKNOWN",
        "iac_engine": lock["opentofu"]["iac_engine"],
        "engine_version": lock["opentofu"]["iac_engine_version"],
        "engine_identity_source": "PINNED_RELEASE_LOCK",
        "binary_sha256": sha256_file(binary),
        "version_json_sha256": sha256_file(version_json),
        "version_json": version,
        "show_json_sha256": sha256_file(plan_show),
        "show_format_version": show.get("format_version"),
        "exit_code": exit_code,
        "input_artifact_sha256": sha256_file(artifact),
        "oracle_sha256": sha256_file(oracle_path),
        "release_lock_sha256": sha256_file(lock_path),
        "command_sha256": sha256_value({"plan": lock["opentofu"]["plan_command"], "show": lock["opentofu"]["show_command"], "validate": lock["opentofu"]["validate_command"]}),
        "resource_actions": [],
        "change_summary": None,
        "drift_count": 0,
        "side_effects": oracle["side_effects"],
        "checksum_verification": {
            "release_asset_sha256": lock["opentofu"]["asset"]["sha256"],
            "release_checksums_sha256": lock["opentofu"]["checksums"]["sha256"],
            "binary_matches_lock": sha256_file(binary) == lock["opentofu"]["binary_sha256"],
        },
        "unknown": None,
    }
    if receipt["binary_sha256"] != lock["opentofu"]["binary_sha256"]:
        receipt["unknown"] = unknown_claim("ENGINE", "VERIFY_BINARY_DIGEST", "BINARY_DIGEST_DOES_NOT_MATCH_RELEASE_LOCK", "OBSERVATION_UNAVAILABLE", "REACQUIRE_PINNED_OPENTOFU_ASSET")
    elif version.get("terraform_version") != lock["opentofu"]["iac_engine_version"]:
        receipt["unknown"] = unknown_claim("ENGINE", "READ_VERSION_JSON", "VERSION_JSON_DOES_NOT_MATCH_RELEASE_LOCK", "OBSERVATION_UNAVAILABLE", "CAPTURE_PINNED_VERSION_JSON")
    elif not isinstance(show.get("format_version"), str) or not show["format_version"].startswith("1."):
        receipt["unknown"] = unknown_claim("PLAN", "READ_PLAN_SHOW_JSON", "UNSUPPORTED_SHOW_JSON_FORMAT_MAJOR", "OBSERVATION_UNAVAILABLE", "PIN_SUPPORTED_SHOW_JSON_FORMAT")
    elif exit_code not in (0, 2):
        receipt["unknown"] = unknown_claim("PLAN", "READ_PLAN_EXIT_CODE", "PLAN_EXIT_CODE_NOT_0_OR_2", "OBSERVATION_UNAVAILABLE", "CAPTURE_SUCCESSFUL_READ_ONLY_PLAN")
    else:
        try:
            actions, summary, drift_count = show_actions(show)
        except SystemExit:
            receipt["unknown"] = unknown_claim("PLAN", "READ_PLAN_SHOW_JSON", "UNSUPPORTED_PLAN_SHOW_JSON_SHAPE", "OBSERVATION_UNAVAILABLE", "PIN_SUPPORTED_PLAN_SHOW_JSON")
        else:
            receipt["state"] = "CLOSED"
            receipt["resource_actions"] = actions
            receipt["change_summary"] = summary
            receipt["drift_count"] = drift_count
    write_json(output, receipt)


def match_plan(artifact: Path, receipt_path: Path, oracle_path: Path, output: Path) -> None:
    receipt = read_json(receipt_path)
    oracle = load_oracle(oracle_path)
    expected = oracle["resource_actions"]
    actual = receipt.get("resource_actions", [])
    if receipt.get("state") != "CLOSED":
        claim = receipt.get("unknown")
        if not isinstance(claim, dict) or not UNKNOWN_FIELDS.issubset(claim) or not isinstance(claim.get("blocked_by"), list):
            claim = unknown_claim("PLAN", "MATCH_PLAN", "PLAN_RECEIPT_NOT_CLOSED", "OBSERVATION_UNAVAILABLE", "CAPTURE_CLOSED_PLAN_RECEIPT")
    elif receipt.get("input_artifact_sha256") != sha256_file(artifact):
        claim = unknown_claim("PLAN", "MATCH_CURRENT_PLAN_INPUT", "STALE_PLAN_INPUT_DIGEST", "DIRECT_MISSING", "REGENERATE_PLAN_FOR_CURRENT_ARTIFACT")
    elif receipt.get("iac_engine") != "OPENTOFU" or receipt.get("engine_identity_source") != "PINNED_RELEASE_LOCK":
        claim = unknown_claim("ENGINE", "BIND_PLAN_ENGINE", "ENGINE_INFERRED_FROM_COMPATIBILITY_FIELD", "DIRECT_MISSING", "CAPTURE_EXPLICIT_OPENTOFU_RELEASE_RECEIPT")
    elif receipt.get("drift_count") != 0:
        claim = refuted_claim("PLAN", "REJECT_IGNORED_DRIFT", "PLAN_DRIFT_WAS_NOT_INCLUDED_IN_MATCH")
    elif actual != expected or receipt.get("change_summary") != oracle["change_summary"]:
        claim = refuted_claim("PLAN", "MATCH_RESOURCE_ACTION_SET", "GOOO_INTENT_PLAN_RESOURCE_ACTION_CONTRADICTION")
    else:
        claim = closed_claim("PLAN", "MATCH_RESOURCE_ACTION_SET", "GOOO_INTENT_MATCHES_OPENTOFU_PLAN")
    write_json(output, {
        "schema": "gooo/opentofu-envelope/plan-match/v1",
        "state": claim["state"],
        "claim": claim,
        "artifact_sha256": sha256_file(artifact),
        "plan_receipt_sha256": sha256_file(receipt_path),
        "oracle_sha256": sha256_file(oracle_path),
        "expected_resource_actions": expected,
        "observed_resource_actions": actual,
        "resource_action_count": len(actual),
    })


def attach_activity(claim: dict[str, Any], activity: str, activity_ids: dict[str, str]) -> dict[str, Any]:
    return {"activity": activity, "activity_id": activity_ids[activity], **claim}


def evaluate_cases(plan_match_path: Path, bindings_path: Path, output: Path) -> None:
    bindings = read_json(bindings_path)
    activity_ids = {item["activity"]: item["activity_id"] for item in bindings["bindings"]}
    plan_match = read_json(plan_match_path)
    if plan_match.get("state") != "CLOSED":
        die("normal canonical cases require a closed plan match")
    normal_base = closed_claim("PLAN", "MATCH_RESOURCE_ACTION_SET", "GOOO_INTENT_MATCHES_OPENTOFU_PLAN")
    unknowns = [
        ("unknown-stale-plan", unknown_claim("PLAN", "MATCH_CURRENT_PLAN_INPUT", "STALE_PLAN_INPUT_DIGEST", "DIRECT_MISSING", "REGENERATE_PLAN_FOR_CURRENT_ARTIFACT")),
        ("unknown-inferred-engine", unknown_claim("ENGINE", "BIND_PLAN_ENGINE", "ENGINE_INFERRED_FROM_COMPATIBILITY_FIELD", "DIRECT_MISSING", "CAPTURE_EXPLICIT_OPENTOFU_RELEASE_RECEIPT")),
        ("unknown-unsupported-show-json", unknown_claim("PLAN", "READ_PLAN_SHOW_JSON", "UNSUPPORTED_SHOW_JSON_FORMAT_MAJOR", "OBSERVATION_UNAVAILABLE", "PIN_SUPPORTED_SHOW_JSON_FORMAT")),
    ]
    refuted = [
        ("refuted-ignored-drift", refuted_claim("PLAN", "REJECT_IGNORED_DRIFT", "PLAN_DRIFT_WAS_NOT_INCLUDED_IN_MATCH")),
        ("refuted-resource-action", refuted_claim("PLAN", "MATCH_RESOURCE_ACTION_SET", "GOOO_INTENT_PLAN_RESOURCE_ACTION_CONTRADICTION")),
        ("refuted-summary", refuted_claim("PLAN", "MATCH_CHANGE_SUMMARY", "GOOO_INTENT_PLAN_SUMMARY_CONTRADICTION")),
    ]
    cases = []
    for case_id in ("normal-exact-resource-action", "normal-explicit-engine", "normal-zero-drift"):
        cases.append({"case_id": case_id, "class": "normal", "decision": "CLOSED", "claims": [attach_activity(normal_base, "MatchGoooIntentToOpenTofuPlan", activity_ids)], "resolution": "EXACT"})
    for case_id, claim in unknowns:
        full = attach_activity(claim, "MatchGoooIntentToOpenTofuPlan", activity_ids)
        if set(full) < UNKNOWN_FIELDS or not isinstance(full["blocked_by"], list):
            die("unknown canonical case lost coordinates")
        cases.append({"case_id": case_id, "class": "unknown", "decision": "FAIL_CLOSED", "claims": [full], "resolution": "LOWER_RESOLUTION"})
    for case_id, claim in refuted:
        full = attach_activity(claim, "MatchGoooIntentToOpenTofuPlan", activity_ids)
        cases.append({"case_id": case_id, "class": "refuted", "decision": "FAIL_CLOSED", "claims": [full], "precedence": "REFUTED_OVER_UNKNOWN", "resolution": "EXACT"})
    if sum(case["class"] == "normal" for case in cases) != 3 or sum(case["class"] == "unknown" for case in cases) != 3 or sum(case["class"] == "refuted" for case in cases) != 3:
        die("canonical case denominator is not 3/3/3")
    write_json(output, {
        "schema": "gooo/opentofu-envelope/cases/v1",
        "state": "CLOSED",
        "state_precedence": ["REFUTED", "UNKNOWN", "CLOSED"],
        "precedence_rule": "REFUTED > UNKNOWN > CLOSED",
        "outcome_counts": {"CLOSED": 3, "UNKNOWN": 3, "REFUTED": 3},
        "case_count": len(cases),
        "cases": cases,
    })


def replay(publish_dir: Path, source: Path, graph: Path, lock: Path, spec: Path, bindings: Path, denominator: Path, inventory_path: Path, output: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="envelope-replay-") as directory:
        replay_dir = Path(directory)
        generate(source, graph, lock, spec, bindings, denominator, inventory_path, replay_dir)
        comparisons = []
        for name in ("intent.tf.json", "dossier.md"):
            first = publish_dir / name
            second = replay_dir / name
            equal = first.read_bytes() == second.read_bytes()
            comparisons.append({"file": name, "byte_equal": equal, "first_sha256": sha256_file(first), "second_sha256": sha256_file(second)})
    write_json(output, {"schema": "gooo/opentofu-envelope/replay/v1", "state": "CLOSED" if all(item["byte_equal"] for item in comparisons) else "REFUTED", "comparison_count": len(comparisons), "comparisons": comparisons})


def producer(source: Path, graph: Path, artifact: str, evaluator: str) -> dict[str, str]:
    return {"source": str(source), "ir": str(graph), "generated_artifact": artifact, "evaluator": evaluator}


def record(publish_dir: Path, source: Path, graph: Path, lock: Path, spec: Path, bindings_path: Path, denominator_path: Path, inventory_path: Path, validation_path: Path, receipt_path: Path, match_path: Path, oracle_path: Path, cases_path: Path, replay_path: Path, measurements_path: Path, go_version_path: Path, output: Path) -> None:
    lock_doc = release_lock(lock)
    denominator = contract(denominator_path)
    bindings = read_json(bindings_path)
    activity_ids = {item["activity"]: item["activity_id"] for item in bindings["bindings"]}
    cell_ids = {cell["activity"]: cell["id"] for cell in denominator["cells"]}
    inventory_doc = read_json(inventory_path)
    validation = read_json(validation_path)
    receipt = read_json(receipt_path)
    match = read_json(match_path)
    oracle = load_oracle(oracle_path)
    cases = read_json(cases_path)
    replay_doc = read_json(replay_path)
    measurements = read_json(measurements_path)
    if receipt.get("state") != "CLOSED" or match.get("state") != "CLOSED" or validation.get("state") != "CLOSED" or replay_doc.get("state") != "CLOSED":
        die("record requires closed validation, plan match, and replay")
    if cases.get("case_count") != 9 or len(cases.get("cases", [])) != 9 or cases.get("state_precedence") != ["REFUTED", "UNKNOWN", "CLOSED"] or cases.get("precedence_rule") != "REFUTED > UNKNOWN > CLOSED":
        die("record requires exactly 9 canonical cases")
    if cases.get("outcome_counts") != {"CLOSED": 3, "UNKNOWN": 3, "REFUTED": 3}:
        die("canonical case outcome counts are not 3/3/3")
    for stage in measurements:
        if stage.get("execution_state") not in EXECUTION_VALUES or stage.get("cache_state") not in CACHE_VALUES or stage.get("runner_persistence") not in PERSISTENCE_VALUES or stage.get("prior_test_evidence_reuse_state") not in REUSE_VALUES:
            die("measurement enum value is invalid")
        for field in ("wall_ms", "count", "executed_test_count", "reused_test_evidence_count", "skipped_test_count", "not_observed_test_count", "peak_rss_kib"):
            integer(stage.get(field), field)
    by_stage = {stage["stage"]: stage for stage in measurements}
    for required in ("build", "test", "conformance"):
        if required not in by_stage:
            die(f"missing {required} measurement")
    try:
        go_version = go_version_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        die(f"cannot read Go version evidence {go_version_path}: {exc}")
    if not go_version.startswith("go version go1.27"):
        die("Go version evidence is not Go 1.27")
    reuse_key = {
        "source_digest": sha256_file(source),
        "toolchain_digest": sha256_value({"gooo_release": lock_doc["gooo"]["asset"]["sha256"], "opentofu_binary": lock_doc["opentofu"]["binary_sha256"]}),
        "command_digest": sha256_value({"plan": lock_doc["opentofu"]["plan_command"], "show": lock_doc["opentofu"]["show_command"], "validate": lock_doc["opentofu"]["validate_command"]}),
        "config_digest": sha256_file(lock),
        "dependency_digest": sha256_value({"json_spec": sha256_file(spec), "python": sys.version.split()[0]}),
        "provider_lock_digest": sha256_value({"provider_lock": "ABSENT_FOR_BUILTIN_TERRAFORM_DATA"}),
        "test_inventory_digest": sha256_file(cases_path),
        "policy_digest": sha256_value({"profile": "READ_ONLY", "apply": 0, "test": 0, "cloud": 0, "network": 0, "source_write": 0}),
    }
    for key in REUSE_KEY_FIELDS:
        if not isinstance(reuse_key.get(key), str) or len(reuse_key[key]) != 64:
            die(f"reuse key field is missing: {key}")

    def metric(name: str, value: int, unit: str, activity: str, artifact: str) -> dict[str, Any]:
        integer(value, name)
        return {"name": name, "value": value, "unit": unit, "activity": activity, "activity_id": activity_ids[activity], "cell_id": cell_ids[activity], "producer": producer(source, graph, artifact, "scripts/envelope.py:record")}

    artifact_files = sorted(path.name for path in publish_dir.iterdir() if path.is_file())
    artifact_bytes = sum((publish_dir / name).stat().st_size for name in artifact_files)
    metrics = [
        metric("user_path_steps", denominator["expected_user_path_steps"], "steps", "PreserveReadOnlyBoundary", "observation.json"),
        metric("generated_file_count", len(artifact_files), "files", "GenerateHumanDossier", "observation.json"),
        metric("executed_verification_stages", sum(stage["count"] for stage in measurements if stage["execution_state"] == "EXECUTED"), "stage-executions", "PreserveReadOnlyBoundary", "observation.json"),
        metric("reused_verification_stages", sum(stage["count"] for stage in measurements if stage["execution_state"] == "REUSED"), "stage-reuses", "PreserveReadOnlyBoundary", "observation.json"),
        metric("resource_action_count", match["resource_action_count"], "resource-actions", "MatchGoooIntentToOpenTofuPlan", "plan-match.json"),
        metric("build_wall_ms", by_stage["build"]["wall_ms"], "ms", "GenerateOpenTofuCompatibleArtifact", "observation.json"),
        metric("test_wall_ms", by_stage["test"]["wall_ms"], "ms", "PreserveReadOnlyBoundary", "observation.json"),
        metric("conformance_wall_ms", by_stage["conformance"]["wall_ms"], "ms", "MatchGoooIntentToOpenTofuPlan", "observation.json"),
        metric("peak_rss_kib", max(stage["peak_rss_kib"] for stage in measurements), "KiB", "PreserveReadOnlyBoundary", "observation.json"),
        metric("executed_test_count", by_stage["test"]["executed_test_count"], "tests", "PreserveReadOnlyBoundary", "observation.json"),
        metric("reused_test_evidence_count", by_stage["test"]["reused_test_evidence_count"], "tests", "VerifyDeterministicReplay", "observation.json"),
        metric("skipped_test_count", by_stage["test"]["skipped_test_count"], "tests", "PreserveReadOnlyBoundary", "observation.json"),
        metric("not_observed_test_count", by_stage["test"]["not_observed_test_count"], "tests", "PreserveReadOnlyBoundary", "observation.json"),
        metric("artifact_files", len(artifact_files), "files", "GenerateOpenTofuCompatibleArtifact", "observation.json"),
        metric("artifact_bytes", artifact_bytes, "bytes", "GenerateOpenTofuCompatibleArtifact", "observation.json"),
        metric("repository_writes", lock_doc["authority"]["repository_writes"], "writes", "PreserveReadOnlyBoundary", "observation.json"),
        metric("descendant_directories", inventory_doc["descendant_directory_count"], "directories", "PreserveReadOnlyBoundary", "dossier.md"),
        metric("regular_files_excluding_root_readme", inventory_doc["regular_file_count"], "files", "VerifyGeneratedOutputs", "dossier.md"),
        metric("repository_physical_lines", inventory_doc["physical_line_count"], "lines", "VerifyGeneratedOutputs", "dossier.md"),
        metric("go_physical_files", inventory_doc["go_physical_files"], "files", "GenerateOpenTofuCompatibleArtifact", "dossier.md"),
        metric("go_physical_lines", inventory_doc["go_physical_lines"], "lines", "GenerateOpenTofuCompatibleArtifact", "dossier.md"),
        metric("gooo_physical_files", inventory_doc["gooo_physical_files"], "files", "DeclareGoooInfrastructureIntent", "main.gooo"),
        metric("gooo_physical_lines", inventory_doc["gooo_physical_lines"], "lines", "DeclareGoooInfrastructureIntent", "main.gooo"),
    ]
    improvement_claim = unknown_claim(
        "IMPROVEMENT",
        "COMPARE_EXACT_BEFORE_AFTER",
        "EXACT_BEFORE_AFTER_PAIR_MISSING",
        "DIRECT_MISSING",
        "CAPTURE_EXACT_BEFORE_AFTER_PAIR",
        ["BEFORE_EXACT_OBSERVATION", "AFTER_EXACT_OBSERVATION"],
    )
    primary = []
    for cell in denominator["cells"]:
        primary.append({"metric_id": f"cell-metric-{cell['ordinal']:02d}", "cell_id": cell["id"], "activity": cell["activity"], "activity_id": activity_ids[cell["activity"]], "value": "CLOSED", "unit": "cell-state", "producer": producer(source, graph, "observation.json", "scripts/envelope.py:record")})
    output_doc = {
        "schema": "gooo/opentofu-envelope/observation/v1",
        "state": "CLOSED",
        "state_precedence": ["REFUTED", "UNKNOWN", "CLOSED"],
        "precedence_rule": "REFUTED > UNKNOWN > CLOSED",
        "subject": {"source_sha256": sha256_file(source), "graph_sha256": sha256_file(graph), "release_lock_sha256": sha256_file(lock)},
        "toolchain": {"go_requirement": "1.27.x", "go_version_evidence": go_version},
        "user_path": {
            "step_count": denominator["expected_user_path_steps"],
            "activities": [
                "DeclareGoooInfrastructureIntent",
                "BindGoooIntentToOpenTofu",
                "GenerateOpenTofuCompatibleArtifact",
                "VerifyGeneratedOutputs",
                "MatchGoooIntentToOpenTofuPlan",
            ],
        },
        "generated_outputs": {"file_count": len(artifact_files), "files": artifact_files, "bytes": artifact_bytes, "digests": {name: sha256_file(publish_dir / name) for name in artifact_files}},
        "metrics": metrics,
        "primary_metrics": primary,
        "verification_stages": measurements,
        "improvement": {
            "state": "UNKNOWN",
            "claim": improvement_claim,
            "before": None,
            "after": None,
            "cache_hit_is_not_reuse": True,
        },
        "cases": cases,
        "validation": validation,
        "plan_receipt": receipt,
        "plan_match": match,
        "plan_oracle": {"sha256": sha256_file(oracle_path), "resource_actions": oracle["resource_actions"], "side_effects": oracle["side_effects"]},
        "identity": {"source_sha256": sha256_file(source), "graph_sha256": sha256_file(graph), "artifact_sha256": sha256_file(publish_dir / "intent.tf.json"), "dossier_sha256": sha256_file(publish_dir / "dossier.md"), "plan_receipt_sha256": sha256_file(receipt_path), "plan_match_sha256": sha256_file(match_path), "oracle_sha256": sha256_file(oracle_path), "binary_sha256": receipt["binary_sha256"], "version_json_sha256": receipt["version_json_sha256"], "show_json_sha256": receipt["show_json_sha256"]},
        "reuse_contract": {"installation_binary_cache_state": lock_doc["cache_contract"]["installation_binary_cache_state"], "go_build_cache_state": lock_doc["cache_contract"]["go_build_cache_state"], "prior_test_evidence_reuse_state": lock_doc["cache_contract"]["prior_test_evidence_reuse_state"], "runner_persistence": lock_doc["cache_contract"]["runner_persistence"], "reuse_key": reuse_key},
        "authority": lock_doc["authority"],
        "official_inputs": {"gooo_release": lock_doc["gooo"], "opentofu_release": lock_doc["opentofu"], "json_spec_sha256": sha256_file(spec), "go_version_evidence": go_version},
        "replay": replay_doc,
    }
    write_json(output, output_doc)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    sub = root.add_subparsers(dest="command", required=True)

    command = sub.add_parser("inventory")
    command.add_argument("--root", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)

    command = sub.add_parser("bind")
    for name in ("source", "graph", "denominator", "output"):
        command.add_argument(f"--{name}", type=Path, required=True)

    command = sub.add_parser("generate")
    for name in ("source", "graph", "lock", "spec", "bindings", "denominator", "inventory", "output-dir"):
        command.add_argument(f"--{name}", type=Path, required=True)

    command = sub.add_parser("plan-receipt")
    for name in ("plan-show", "version-json", "binary", "artifact", "oracle", "lock", "output"):
        command.add_argument(f"--{name}", type=Path, required=True)
    command.add_argument("--exit-code", type=int, required=True)

    command = sub.add_parser("match-plan")
    for name in ("artifact", "receipt", "oracle", "output"):
        command.add_argument(f"--{name}", type=Path, required=True)

    command = sub.add_parser("cases")
    for name in ("plan-match", "bindings", "output"):
        command.add_argument(f"--{name}", type=Path, required=True)

    command = sub.add_parser("replay")
    for name in ("publish-dir", "source", "graph", "lock", "spec", "bindings", "denominator", "inventory", "output"):
        command.add_argument(f"--{name}", type=Path, required=True)

    command = sub.add_parser("validate")
    command.add_argument("--tofu-json", type=Path, required=True)
    command.add_argument("--artifact", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)

    command = sub.add_parser("record")
    for name in ("publish-dir", "source", "graph", "lock", "spec", "bindings", "denominator", "inventory", "validation", "receipt", "match", "oracle", "cases", "replay", "measurements", "go-version", "output"):
        command.add_argument(f"--{name}", type=Path, required=True)
    return root


def main() -> None:
    args = parser().parse_args()
    if args.command == "inventory":
        inventory(args.root, args.output)
    elif args.command == "bind":
        bind(args.source, args.graph, args.denominator, args.output)
    elif args.command == "generate":
        generate(args.source, args.graph, args.lock, args.spec, args.bindings, args.denominator, args.inventory, args.output_dir)
    elif args.command == "plan-receipt":
        plan_receipt(args.plan_show, args.version_json, args.binary, args.artifact, args.oracle, args.lock, args.exit_code, args.output)
    elif args.command == "match-plan":
        match_plan(args.artifact, args.receipt, args.oracle, args.output)
    elif args.command == "cases":
        evaluate_cases(args.plan_match, args.bindings, args.output)
    elif args.command == "replay":
        replay(args.publish_dir, args.source, args.graph, args.lock, args.spec, args.bindings, args.denominator, args.inventory, args.output)
    elif args.command == "validate":
        tofu = read_json(args.tofu_json)
        valid = tofu.get("valid") is True and (tofu.get("error_count") in (None, 0))
        write_json(args.output, {"schema": "gooo/opentofu-envelope/validation/v1", "state": "CLOSED" if valid else "REFUTED", "artifact_sha256": sha256_file(args.artifact), "official_opentofu": tofu, "structural_checks": {"output_file_count": 2}})
    elif args.command == "record":
        record(args.publish_dir, args.source, args.graph, args.lock, args.spec, args.bindings, args.denominator, args.inventory, args.validation, args.receipt, args.match, args.oracle, args.cases, args.replay, args.measurements, args.go_version, args.output)


if __name__ == "__main__":
    main()

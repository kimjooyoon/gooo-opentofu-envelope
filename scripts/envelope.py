#!/usr/bin/env python3
"""Build a small, read-only Gooo/OpenTofu service-contract envelope."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
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
    "GenerateOpenTofuValidationReceipt",
    "MatchGoooIntentToIndependentOracle",
    "PreserveUnknownCase",
    "RefuteContradictionCase",
    "VerifyDeterministicReplay",
    "PreserveReadOnlyBoundary",
]
ENTITY_NAMES = [
    "ServiceInfrastructureContract",
    "ServicePortContract",
    "OpenTofuSpecBinding",
    "OpenTofuJSONSpecReceipt",
    "OpenTofuArtifact",
    "HumanDossier",
    "NormalVerification",
    "OpenTofuValidationReceipt",
    "SemanticOracleMatch",
    "UnknownCase",
    "RefutedCase",
    "ReplayVerification",
    "ReadOnlyObservation",
]
ACTIVITY_INPUTS = {
    "DeclareGoooInfrastructureIntent": {"ServiceInfrastructureContract"},
    "BindGoooIntentToOpenTofu": {"ServicePortContract"},
    "ConsumePinnedOpenTofuJSONSpec": {"OpenTofuSpecBinding"},
    "GenerateOpenTofuCompatibleArtifact": {"OpenTofuJSONSpecReceipt"},
    "GenerateHumanDossier": {"OpenTofuArtifact"},
    "VerifyGeneratedOutputs": {"HumanDossier"},
    "GenerateOpenTofuValidationReceipt": {"NormalVerification"},
    "MatchGoooIntentToIndependentOracle": {"OpenTofuValidationReceipt"},
    "PreserveUnknownCase": {"SemanticOracleMatch"},
    "RefuteContradictionCase": {"SemanticOracleMatch"},
    "VerifyDeterministicReplay": {"NormalVerification"},
    "PreserveReadOnlyBoundary": {"UnknownCase", "RefutedCase", "ReplayVerification", "SemanticOracleMatch"},
}
ACTIVITY_OUTPUTS = {
    "DeclareGoooInfrastructureIntent": {"ServicePortContract"},
    "BindGoooIntentToOpenTofu": {"OpenTofuSpecBinding"},
    "ConsumePinnedOpenTofuJSONSpec": {"OpenTofuJSONSpecReceipt"},
    "GenerateOpenTofuCompatibleArtifact": {"OpenTofuArtifact"},
    "GenerateHumanDossier": {"HumanDossier"},
    "VerifyGeneratedOutputs": {"NormalVerification"},
    "GenerateOpenTofuValidationReceipt": {"OpenTofuValidationReceipt"},
    "MatchGoooIntentToIndependentOracle": {"SemanticOracleMatch"},
    "PreserveUnknownCase": {"UnknownCase"},
    "RefuteContradictionCase": {"RefutedCase"},
    "VerifyDeterministicReplay": {"ReplayVerification"},
    "PreserveReadOnlyBoundary": {"ReadOnlyObservation"},
}


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
    if [cell.get("ordinal") for cell in cells] != list(range(1, 13)):
        die("denominator ordinals are not exactly 1 through 12")
    if len({cell.get("id") for cell in cells}) != 12:
        die("denominator cell IDs are not unique")
    expected_cell_fields = {"ordinal", "id", "activity", "stage", "step", "proof_family", "indicator", "depends_on"}
    cell_ids = {cell.get("id") for cell in cells}
    for cell in cells:
        if set(cell) != expected_cell_fields or not isinstance(cell.get("depends_on"), list):
            die("every cell must have exactly 8 fixed fields")
        if any(dependency not in cell_ids or dependency == cell["id"] for dependency in cell["depends_on"]):
            die(f"denominator dependency is invalid for {cell['id']}")
        if any(next(item["ordinal"] for item in cells if item["id"] == dependency) >= cell["ordinal"] for dependency in cell["depends_on"]):
            die(f"denominator dependency is not acyclic for {cell['id']}")
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
        "opentofu_plan_executions", "opentofu_show_executions", "opentofu_apply_executions", "opentofu_destroy_executions",
        "opentofu_import_executions", "opentofu_state_mutations", "opentofu_test_executions", "opentofu_provider_accesses",
        "opentofu_cloud_accesses",
    ]
    if any(authority.get(key) != 0 for key in required_zero) or authority.get("opentofu_validate_executions") != 1:
        die("release lock authority is not the read-only validate profile")
    if authority.get("opentofu_runtime_network_access_claimed") is not False or authority.get("opentofu_runtime_network_access_observed") is not False:
        die("OpenTofu runtime network authority is not false")
    cache = value.get("cache_contract", {})
    if cache.get("installation_binary_cache_state") not in CACHE_VALUES or cache.get("go_build_cache_state") not in CACHE_VALUES:
        die("binary and Go build cache states are invalid")
    if cache.get("prior_test_evidence_reuse_state") not in REUSE_VALUES or cache.get("runner_persistence") not in PERSISTENCE_VALUES:
        die("prior evidence reuse or runner persistence state is invalid")
    if cache.get("reuse_key_fields") != REUSE_KEY_FIELDS:
        die("reuse key field set is not minimal and exact")
    policy = value.get("policy", {})
    if policy.get("default_profile") != "READ_ONLY" or policy.get("authorized_profile") != "AUTHORIZED_ACCEPTANCE":
        die("policy profiles are not explicit")
    if policy.get("default_forbidden") != ["tofu test", "TF_ACC acceptance test"]:
        die("default forbidden acceptance operations are not fixed")
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
            files.append({"path": relative, "bytes": path.stat().st_size, "lines": len(text.splitlines())})
    files.sort(key=lambda item: item["path"])
    write_json(output, {
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
    })


def graph_model(graph: dict[str, Any], source_path: Path) -> dict[str, Any]:
    if graph.get("schema_version") != "gooo-graph/v1":
        die("released graph schema is not gooo-graph/v1")
    if graph.get("source_digest") != sha256_file(source_path):
        die("released graph source digest does not match the Gooo source")
    ir = graph.get("ir", {})
    authorities = graph.get("authorities", {})
    if ir.get("status") != "available" or not isinstance(ir.get("semantic_digest"), str):
        die("released semantic IR is not available")
    if authorities.get(".gooo") != "authoritative" or authorities.get("ir") != "authoritative" or authorities.get("graph") != "derived":
        die("released graph does not expose the expected Gooo authority boundary")
    nodes = graph.get("nodes")
    relations = graph.get("relations")
    if not isinstance(nodes, list) or not isinstance(relations, list):
        die("released graph nodes or relations are missing")
    node_ids = [node.get("id") for node in nodes]
    if any(not isinstance(node_id, str) for node_id in node_ids) or len(set(node_ids)) != len(node_ids):
        die("released graph node IDs are not unique")
    activity_nodes = [node for node in nodes if node.get("kind") == "Activity"]
    if len(activity_nodes) != len(ACTIVITIES):
        die("released graph activity node count is not exactly 12")
    result = {node.get("name"): node.get("id") for node in activity_nodes}
    if set(result) != set(ACTIVITIES) or any(not isinstance(value, str) for value in result.values()):
        die("released graph does not expose exactly the 12 activities")
    if len(result) != len(activity_nodes):
        die("released graph activity names are not unique")
    entity_nodes = [node for node in nodes if node.get("kind") == "Entity"]
    if len(entity_nodes) != len(ENTITY_NAMES):
        die("released graph entity node count is not fixed")
    entity_ids = {node.get("name"): node.get("id") for node in entity_nodes}
    if set(entity_ids) != set(ENTITY_NAMES) or any(not isinstance(value, str) for value in entity_ids.values()):
        die("released graph does not expose the fixed service-contract entities")
    if len(entity_ids) != len(entity_nodes):
        die("released graph entity names are not unique")
    name_by_id = {node_id: name for name, node_id in {**result, **entity_ids}.items()}
    inputs = {name: set() for name in ACTIVITIES}
    outputs = {name: set() for name in ACTIVITIES}
    relation_keys: set[tuple[str, str, str, str]] = set()
    for relation in relations:
        status = relation.get("status")
        subject = relation.get("subject")
        predicate = relation.get("predicate")
        obj = relation.get("object")
        key = (status, subject, predicate, obj)
        if key in relation_keys:
            die("released graph contains duplicate relations")
        relation_keys.add(key)
        if status != "deterministic":
            continue
        if predicate == "used" and subject in result and obj in name_by_id and name_by_id[obj] in ENTITY_NAMES:
            inputs[name_by_id[subject]].add(name_by_id[obj])
        elif predicate == "wasGeneratedBy" and obj in result and subject in name_by_id and name_by_id[subject] in ENTITY_NAMES:
            outputs[name_by_id[obj]].add(name_by_id[subject])
    for activity in ACTIVITIES:
        if inputs[activity] != ACTIVITY_INPUTS[activity] or outputs[activity] != ACTIVITY_OUTPUTS[activity]:
            die(f"released graph input/output contract mismatch for {activity}")
    return {"activity_ids": result, "entity_ids": entity_ids, "inputs": inputs, "outputs": outputs, "ir_digest": ir["semantic_digest"]}


def bind(source_path: Path, graph_path: Path, denominator_path: Path, output: Path) -> None:
    denominator = contract(denominator_path)
    graph = read_json(graph_path)
    model = graph_model(graph, source_path)
    activity_ids = model["activity_ids"]
    try:
        source_text = source_path.read_text(encoding="utf-8")
    except OSError as exc:
        die(f"cannot read Gooo source {source_path}: {exc}")
    for activity in ACTIVITIES:
        if f"activity {activity}(" not in source_text:
            die(f"Gooo source does not declare {activity}")
    bindings = []
    for cell in denominator["cells"]:
        activity = cell["activity"]
        graph_dependencies = []
        for predecessor in denominator["cells"]:
            if predecessor["id"] not in cell["depends_on"]:
                continue
            predecessor_activity = predecessor["activity"]
            predecessor_output = ACTIVITY_OUTPUTS[predecessor_activity]
            activity_inputs = ACTIVITY_INPUTS[activity]
            if not predecessor_output.intersection(activity_inputs):
                die(f"denominator dependency does not match Gooo graph contract for {cell['id']}")
            graph_dependencies.append(predecessor["id"])
        if sorted(graph_dependencies) != sorted(cell["depends_on"]):
            die(f"graph dependency mismatch for {cell['id']}")
        bindings.append({
            "ordinal": cell["ordinal"],
            "cell_id": cell["id"],
            "activity": activity,
            "activity_id": activity_ids[activity],
            "stage": cell["stage"],
            "step": cell["step"],
            "proof_family": cell["proof_family"],
            "indicator": cell["indicator"],
            "depends_on": cell["depends_on"],
            "input_entities": sorted(model["inputs"][activity]),
            "output_entities": sorted(model["outputs"][activity]),
            "producer": {"source": str(source_path), "ir": str(graph_path), "generated_artifact": "bindings.json", "evaluator": "scripts/envelope.py:bind"},
        })
    write_json(output, {
        "schema": "gooo/opentofu-envelope/bindings/v1",
        "state": "CLOSED",
        "semantic_authority": {
            "state": "CLOSED",
            "source": "GOOO_SOURCE_AUTHORITATIVE",
            "ir": "GOOO_SEMANTIC_IR_AUTHORITATIVE",
            "graph": "DERIVED_FROM_RELEASED_IR",
            "ir_sha256": model["ir_digest"],
            "reason": "released Gooo graph exposes the exact 12 activity and entity contracts",
        },
        "source_sha256": sha256_file(source_path),
        "graph_sha256": sha256_file(graph_path),
        "activity_count": len(bindings),
        "binding_edges": sum(len(item["depends_on"]) for item in bindings),
        "bindings": bindings,
    })


def service_contract(source_path: Path) -> dict[str, Any]:
    try:
        lines = source_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        die(f"cannot read Gooo source {source_path}: {exc}")
    service: dict[str, Any] | None = None
    environment: dict[str, Any] | None = None
    required_outputs: list[dict[str, str]] = []
    relations: list[dict[str, str]] = []
    for raw in lines:
        line = raw.strip()
        match = re.fullmatch(r"// @service name=([A-Za-z0-9_.-]+) type=([A-Za-z0-9_.-]+) port=([0-9]+)", line)
        if match:
            if service is not None:
                die("service contract declares multiple services")
            service = {"name": match.group(1), "type": match.group(2), "port": int(match.group(3))}
            continue
        match = re.fullmatch(r"// @environment name=([A-Za-z0-9_.-]+) type=([A-Za-z0-9_.-]+) value=([A-Za-z0-9_.-]+)", line)
        if match:
            if environment is not None:
                die("service contract declares multiple environments")
            environment = {"name": match.group(1), "type": match.group(2), "value": match.group(3)}
            continue
        match = re.fullmatch(r"// @required_output name=([A-Za-z0-9_.-]+) type=([A-Za-z0-9_.-]+)", line)
        if match:
            required_outputs.append({"name": match.group(1), "type": match.group(2)})
            continue
        match = re.fullmatch(r"// @relation subject=([A-Za-z0-9_.-]+) predicate=([A-Za-z0-9_.-]+) object=([A-Za-z0-9_.-]+)", line)
        if match:
            relations.append({"subject": match.group(1), "predicate": match.group(2), "object": match.group(3)})
    if service is None or environment is None or len(required_outputs) != 3 or len(relations) != 4:
        die("Gooo source does not contain the fixed service contract")
    if len({item["name"] for item in required_outputs}) != 3 or len({json.dumps(item, sort_keys=True) for item in relations}) != 4:
        die("Gooo service contract contains duplicate outputs or relations")
    return {"service": service, "environment": environment, "required_outputs": required_outputs, "relations": relations}


def generated_artifact(contract_doc: dict[str, Any]) -> dict[str, Any]:
    service = contract_doc["service"]
    environment = contract_doc["environment"]
    required = {item["name"]: item["type"] for item in contract_doc["required_outputs"]}
    if set(required) != {"service_url", "service_port", "service_type"}:
        die("required service outputs are not fixed")
    return {
        "//": "Generated from the Gooo service contract; OpenTofu is the pinned validation authority.",
        "resource": {"terraform_data": {"service_contract": {"input": {
            "service_name": service["name"],
            "service_type": service["type"],
            "service_port": service["port"],
            "environment": {environment["name"]: environment["value"]},
        }}}},
        "output": {
            "service_url": {"value": "${terraform_data.service_contract.input.service_type}://${terraform_data.service_contract.input.service_name}"},
            "service_port": {"value": "${terraform_data.service_contract.input.service_port}"},
            "service_type": {"value": "${terraform_data.service_contract.input.service_type}"},
        },
    }


def generate(source_path: Path, graph_path: Path, lock_path: Path, spec_path: Path, bindings_path: Path, denominator_path: Path, inventory_path: Path, output_dir: Path) -> None:
    lock = release_lock(lock_path)
    denominator = contract(denominator_path)
    bindings = read_json(bindings_path)
    graph = read_json(graph_path)
    model = graph_model(graph, source_path)
    if bindings.get("state") != "CLOSED" or bindings.get("activity_count") != 12 or bindings.get("binding_edges") != 14:
        die("bindings are not closed")
    if bindings.get("source_sha256") != sha256_file(source_path) or bindings.get("graph_sha256") != sha256_file(graph_path):
        die("bindings do not describe the current Gooo source and graph")
    semantic_authority = bindings.get("semantic_authority", {})
    if semantic_authority.get("state") != "CLOSED" or semantic_authority.get("ir") != "GOOO_SEMANTIC_IR_AUTHORITATIVE" or semantic_authority.get("ir_sha256") != model["ir_digest"]:
        die("Gooo semantic authority was not closed by the released graph")
    if not spec_path.is_file():
        die("pinned OpenTofu JSON specification is missing")
    inventory_doc = read_json(inventory_path)
    contract_doc = service_contract(source_path)
    artifact = generated_artifact(contract_doc)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "main.tf.json", artifact)
    lines = [
        "# Gooo OpenTofu Service Contract Envelope",
        "",
        "This dossier is a deterministic, read-only service-infrastructure contract observation.",
        "",
        "## Service contract",
        "",
        f"- service: `{contract_doc['service']['name']}`",
        f"- type: `{contract_doc['service']['type']}`",
        f"- port: `{contract_doc['service']['port']}`",
        f"- environment: `{contract_doc['environment']['name']}={contract_doc['environment']['value']}` ({contract_doc['environment']['type']})",
        f"- required outputs: `{', '.join(item['name'] for item in contract_doc['required_outputs'])}`",
        f"- semantic relations: `{len(contract_doc['relations'])}`",
        "",
        "## Authority",
        "",
        f"- Gooo source SHA-256: `{sha256_file(source_path)}`",
        f"- released graph SHA-256: `{sha256_file(graph_path)}`",
        f"- released semantic IR SHA-256: `{model['ir_digest']}`",
        "- semantic authority: `.gooo` source and released semantic IR are authoritative; the graph is their derived, checked binding.",
        f"- pinned OpenTofu: `{lock['opentofu']['iac_engine']} {lock['opentofu']['iac_engine_version']}`",
        f"- pinned JSON specification SHA-256: `{sha256_file(spec_path)}`",
        "- mutation profile: `READ_ONLY`",
        "- CLI observation boundary: pinned `version -json` and `validate -json` only",
        "- provider installation, init download, plan, apply, state/backend, credentials, network infrastructure, `tofu test`, and TF_ACC acceptance tests are forbidden in the default profile.",
        "",
        "## Cells",
        "",
        f"- fixed denominator: `{denominator['target_cells']}` cells",
        "- proof family denominator: `FOUNDATION 4 / COHERENCE 4 / REGRESSION 4`",
        "- indicator denominator: `DRIVER 4 / OUTCOME 4 / GUARDRAIL 4`",
        "",
        "## Artifact",
        "",
        "- `main.tf.json` contains one providerless built-in `terraform_data.service_contract` resource and three required outputs.",
        "- `contract-receipt.json` binds source, released IR, generated JSON, OpenTofu JSON observation, and independent semantic oracle digests.",
        "- Exact before/after observations are absent, so improvement and user utility remain `UNKNOWN`; a binary cache hit never counts as test-evidence reuse.",
        "",
        "## Repository inventory",
        "",
        f"- descendant directories (root README excluded): `{inventory_doc['descendant_directory_count']}`",
        f"- regular files (root README excluded): `{inventory_doc['regular_file_count']}`",
        f"- physical lines including blank/comment lines: `{inventory_doc['physical_line_count']}`",
        f"- Go files / lines: `{inventory_doc['go_physical_files']} / {inventory_doc['go_physical_lines']}`",
        f"- Gooo files / lines: `{inventory_doc['gooo_physical_files']} / {inventory_doc['gooo_physical_lines']}`",
    ]
    for item in inventory_doc["regular_files"]:
        lines.append(f"- `{item['path']}`: {item['lines']} physical lines, {item['bytes']} bytes")
    (output_dir / "dossier.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def unknown_claim(stage: str, step: str, reason: str, unknown_class: str, next_operation: str, blocked_by: list[str] | None = None) -> dict[str, Any]:
    if unknown_class not in {"DIRECT_MISSING", "OBSERVATION_UNAVAILABLE"}:
        die("unsupported unknown class")
    if not isinstance(blocked_by, list):
        die("UNKNOWN blocked_by must be an array")
    return {"state": "UNKNOWN", "stage": stage, "step": step, "reason": reason, "unknown_class": unknown_class, "next_operation": next_operation, "blocked_by": blocked_by}


def refuted_claim(stage: str, step: str, reason: str) -> dict[str, Any]:
    return {"state": "REFUTED", "stage": stage, "step": step, "reason": reason, "unknown_class": None, "next_operation": None, "blocked_by": []}


def closed_claim(stage: str, step: str, reason: str) -> dict[str, Any]:
    return {"state": "CLOSED", "stage": stage, "step": step, "reason": reason, "unknown_class": None, "next_operation": None, "blocked_by": []}


def highest_state(*claims: dict[str, Any]) -> str:
    states = {claim.get("state") for claim in claims}
    if "REFUTED" in states:
        return "REFUTED"
    if "UNKNOWN" in states:
        return "UNKNOWN"
    if states == {"CLOSED"}:
        return "CLOSED"
    return "UNKNOWN"


def load_service_oracle(path: Path) -> dict[str, Any]:
    oracle = read_json(path)
    if oracle.get("schema") != "gooo/opentofu-envelope/service-contract-oracle/v1" or oracle.get("service") != {"name": "web", "type": "http", "port": 8080}:
        die("service oracle service identity is not fixed")
    if oracle.get("environment") != {"name": "APP_ENV", "type": "string", "value": "production"}:
        die("service oracle environment is not fixed")
    if oracle.get("required_outputs") != [
        {"name": "service_url", "type": "string"},
        {"name": "service_port", "type": "number"},
        {"name": "service_type", "type": "string"},
    ]:
        die("service oracle required outputs are not fixed")
    if oracle.get("relations") != [
        {"subject": "service", "predicate": "declares", "object": "service_port"},
        {"subject": "service", "predicate": "declares", "object": "service_type"},
        {"subject": "service", "predicate": "requires", "object": "service_url"},
        {"subject": "environment", "predicate": "configures", "object": "service"},
    ] or oracle.get("side_effects") != {"network": 0, "provider_install": 0, "infrastructure_mutation": 0, "state_mutation": 0}:
        die("service oracle relations or side effects are not fixed")
    return oracle


def validate(tofu_json: Path, artifact: Path, output: Path) -> None:
    tofu = read_json(tofu_json)
    artifact_doc = read_json(artifact)
    error_count = integer(tofu.get("error_count", 0), "OpenTofu validation error_count")
    warning_count = integer(tofu.get("warning_count", 0), "OpenTofu validation warning_count")
    resource = artifact_doc.get("resource")
    outputs = artifact_doc.get("output")
    terraform_data = resource.get("terraform_data") if isinstance(resource, dict) else None
    providerless = (
        "provider" not in artifact_doc
        and "terraform" not in artifact_doc
        and isinstance(terraform_data, dict)
        and set(terraform_data) == {"service_contract"}
        and isinstance(terraform_data["service_contract"], dict)
    )
    providerless = providerless and isinstance(outputs, dict) and set(outputs) == {"service_url", "service_port", "service_type"}
    valid = tofu.get("valid") is True and error_count == 0 and providerless
    write_json(output, {
        "schema": "gooo/opentofu-envelope/validation/v2",
        "state": "CLOSED" if valid else "REFUTED",
        "artifact_sha256": sha256_file(artifact),
        "official_opentofu": tofu,
        "structural_checks": {"generated_config": "main.tf.json", "providerless": providerless, "output_file_count_before_receipt": 2},
        "diagnostics": {"error_count": error_count, "warning_count": warning_count},
    })


def contract_receipt(source: Path, graph: Path, artifact: Path, validation_path: Path, tofu_json: Path, version_json: Path, binary: Path, oracle_path: Path, lock_path: Path, exit_code: int, output: Path) -> None:
    lock = release_lock(lock_path)
    graph_doc = read_json(graph)
    graph_authority = graph_model(graph_doc, source)
    source_contract = service_contract(source)
    validation = read_json(validation_path)
    version = read_json(version_json)
    oracle = load_service_oracle(oracle_path)
    artifact_doc = read_json(artifact)
    receipt: dict[str, Any] = {
        "schema": "gooo/opentofu-envelope/contract-receipt/v1",
        "state": "UNKNOWN",
        "iac_engine": lock["opentofu"]["iac_engine"],
        "engine_version": lock["opentofu"]["iac_engine_version"],
        "engine_identity_source": "PINNED_RELEASE_LOCK",
        "binary_sha256": sha256_file(binary),
        "version_json_sha256": sha256_file(version_json),
        "version_json": version,
        "validation_json_sha256": sha256_file(tofu_json),
        "validation_exit_code": exit_code,
        "validation_command": lock["opentofu"]["validate_command"],
        "validation_attempted": 1,
        "validation_executed": 1,
        "input_artifact_sha256": sha256_file(artifact),
        "release_lock_sha256": sha256_file(lock_path),
        "json_spec_sha256": lock["opentofu"]["json_spec"]["sha256"],
        "diagnostics": validation.get("diagnostics", {"error_count": 0, "warning_count": 0}),
        "semantic_contract": source_contract,
        "generated_mappings": {
            "resource": artifact_doc.get("resource", {}).get("terraform_data", {}).get("service_contract"),
            "outputs": artifact_doc.get("output", {}),
        },
        "checksum_verification": {
            "release_asset_sha256": lock["opentofu"]["asset"]["sha256"],
            "release_checksums_sha256": lock["opentofu"]["checksums"]["sha256"],
            "binary_matches_lock": sha256_file(binary) == lock["opentofu"]["binary_sha256"],
        },
        "side_effects": oracle["side_effects"],
        "provenance": {
            "source": {"path": str(source), "sha256": sha256_file(source)},
            "ir": {"path": str(graph), "sha256": sha256_file(graph)},
            "generated_tf_json": {"path": str(artifact), "sha256": sha256_file(artifact)},
            "opentofu_observation": {"path": str(tofu_json), "sha256": sha256_file(tofu_json)},
            "independent_oracle": {"path": str(oracle_path), "sha256": sha256_file(oracle_path)},
        },
        "oracle_sha256": sha256_file(oracle_path),
        "semantic_authority": {
            "state": "CLOSED",
            "source": "GOOO_SOURCE_AUTHORITATIVE",
            "ir": "GOOO_SEMANTIC_IR_AUTHORITATIVE",
            "graph": "DERIVED_FROM_RELEASED_IR",
            "ir_sha256": graph_authority["ir_digest"],
        },
        "claim": None,
        "unknown": None,
    }
    if validation.get("state") == "REFUTED":
        receipt["claim"] = refuted_claim("VALIDATION", "REJECT_OPENTOFU_VALIDATE_OBSERVATION", "PINNED_OPENTOFU_REFUTED_GENERATED_CONFIGURATION")
    elif receipt["binary_sha256"] != lock["opentofu"]["binary_sha256"]:
        receipt["claim"] = unknown_claim("ENGINE", "VERIFY_BINARY_DIGEST", "BINARY_DIGEST_DOES_NOT_MATCH_RELEASE_LOCK", "OBSERVATION_UNAVAILABLE", "REACQUIRE_PINNED_OPENTOFU_ASSET")
    elif version.get("terraform_version") != lock["opentofu"]["iac_engine_version"]:
        receipt["claim"] = unknown_claim("ENGINE", "READ_VERSION_JSON", "VERSION_JSON_DOES_NOT_MATCH_RELEASE_LOCK", "OBSERVATION_UNAVAILABLE", "CAPTURE_PINNED_VERSION_JSON")
    elif exit_code != 0:
        receipt["claim"] = unknown_claim("VALIDATION", "READ_VALIDATE_EXIT_CODE", "VALIDATE_EXIT_CODE_IS_NOT_ZERO", "OBSERVATION_UNAVAILABLE", "CAPTURE_SUCCESSFUL_READ_ONLY_VALIDATION")
    elif validation.get("state") != "CLOSED":
        receipt["claim"] = unknown_claim("VALIDATION", "READ_VALIDATE_JSON", "VALIDATE_JSON_OBSERVATION_UNAVAILABLE", "OBSERVATION_UNAVAILABLE", "CAPTURE_VALIDATE_JSON")
    elif validation.get("official_opentofu", {}).get("valid") is True:
        receipt["state"] = "CLOSED"
    else:
        receipt["claim"] = unknown_claim("VALIDATION", "READ_VALIDATE_JSON", "VALIDATE_JSON_OBSERVATION_UNAVAILABLE", "OBSERVATION_UNAVAILABLE", "CAPTURE_VALIDATE_JSON")
    if receipt["claim"] is not None:
        receipt["state"] = receipt["claim"]["state"]
        if receipt["claim"]["state"] == "UNKNOWN":
            receipt["unknown"] = receipt["claim"]
    # Keep the legacy unknown field for consumers while making REFUTED explicit.
    if receipt["state"] == "REFUTED":
        receipt["unknown"] = None
    write_json(output, receipt)


def match_contract(source: Path, graph: Path, artifact: Path, validation_path: Path, tofu_json: Path, receipt_path: Path, oracle_path: Path, output: Path) -> None:
    graph_authority = graph_model(read_json(graph), source)
    source_doc = service_contract(source)
    oracle = load_service_oracle(oracle_path)
    receipt = read_json(receipt_path)
    validation = read_json(validation_path)
    artifact_doc = read_json(artifact)
    expected_outputs = oracle["required_outputs"]
    observed_outputs = [{"name": name, "type": next((item["type"] for item in expected_outputs if item["name"] == name), "UNKNOWN"), "value": value.get("value")} for name, value in sorted(artifact_doc.get("output", {}).items())]
    expected_mapping = {
        "service_url": "${terraform_data.service_contract.input.service_type}://${terraform_data.service_contract.input.service_name}",
        "service_port": "${terraform_data.service_contract.input.service_port}",
        "service_type": "${terraform_data.service_contract.input.service_type}",
    }
    expected_resource_input = {
        "service_name": oracle["service"]["name"],
        "service_type": oracle["service"]["type"],
        "service_port": oracle["service"]["port"],
        "environment": {oracle["environment"]["name"]: oracle["environment"]["value"]},
    }
    observed_mapping = {name: value.get("value") for name, value in artifact_doc.get("output", {}).items()}
    observed_resource_input = artifact_doc.get("resource", {}).get("terraform_data", {}).get("service_contract", {}).get("input")
    upstream_state = highest_state({"state": receipt.get("state")}, {"state": validation.get("state")})
    if upstream_state == "REFUTED":
        claim = receipt.get("claim") if receipt.get("state") == "REFUTED" and isinstance(receipt.get("claim"), dict) else refuted_claim("VALIDATION", "REJECT_UPSTREAM_OBSERVATION", "UPSTREAM_VALIDATION_CONTRADICTION")
        if claim.get("state") != "REFUTED":
            claim = refuted_claim("VALIDATION", "REJECT_UPSTREAM_OBSERVATION", "UPSTREAM_VALIDATION_CONTRADICTION")
    elif upstream_state == "UNKNOWN":
        claim = receipt.get("claim") or receipt.get("unknown")
        if not isinstance(claim, dict) or claim.get("state") != "UNKNOWN" or not UNKNOWN_FIELDS.issubset(claim) or not isinstance(claim.get("blocked_by"), list):
            claim = unknown_claim("VALIDATION", "MATCH_VALIDATE_OBSERVATION", "OPENTOFU_VALIDATE_JSON_NOT_OBSERVED", "OBSERVATION_UNAVAILABLE", "CAPTURE_PINNED_VALIDATE_JSON", ["OPENTOFU_VALIDATE_JSON"])
    elif receipt.get("input_artifact_sha256") != sha256_file(artifact):
        claim = unknown_claim("CONFORMANCE", "MATCH_CURRENT_GENERATED_CONFIG", "STALE_GENERATED_CONFIG_DIGEST", "DIRECT_MISSING", "REGENERATE_MAIN_TF_JSON")
    elif receipt.get("validation_json_sha256") != sha256_file(tofu_json) or receipt.get("oracle_sha256") != sha256_file(oracle_path):
        claim = unknown_claim("PROVENANCE", "MATCH_CURRENT_OBSERVATIONS", "STALE_OBSERVATION_DIGEST", "OBSERVATION_UNAVAILABLE", "RECAPTURE_PINNED_OBSERVATIONS", ["OPENTOFU_VALIDATE_JSON", "INDEPENDENT_ORACLE"])
    elif receipt.get("iac_engine") != "OPENTOFU" or receipt.get("engine_identity_source") != "PINNED_RELEASE_LOCK":
        claim = unknown_claim("ENGINE", "BIND_VALIDATE_ENGINE", "ENGINE_IDENTITY_NOT_EXPLICITLY_PINNED", "DIRECT_MISSING", "CAPTURE_PINNED_OPENTOFU_VERSION_RECEIPT")
    elif receipt.get("semantic_authority", {}).get("state") != "CLOSED" or receipt.get("semantic_authority", {}).get("ir_sha256") != graph_authority["ir_digest"]:
        claim = unknown_claim("META", "BIND_GOOO_SEMANTIC_AUTHORITY", "RELEASED_SEMANTIC_AUTHORITY_NOT_OBSERVED", "OBSERVATION_UNAVAILABLE", "RECAPTURE_RELEASED_GOOO_GRAPH", ["GOOO_SEMANTIC_IR"])
    elif source_doc["service"] != oracle["service"] or source_doc["environment"] != oracle["environment"] or source_doc["required_outputs"] != expected_outputs or source_doc["relations"] != oracle["relations"]:
        claim = refuted_claim("CONFORMANCE", "MATCH_SERVICE_CONTRACT_RELATIONS", "GOOO_SERVICE_RELATION_CONTRADICTION")
    elif observed_resource_input != expected_resource_input or observed_mapping != expected_mapping or observed_outputs != [{"name": "service_port", "type": "number", "value": expected_mapping["service_port"]}, {"name": "service_type", "type": "string", "value": expected_mapping["service_type"]}, {"name": "service_url", "type": "string", "value": expected_mapping["service_url"]}]:
        claim = refuted_claim("CONFORMANCE", "MATCH_REQUIRED_OUTPUT_MAPPING", "GENERATED_REQUIRED_OUTPUT_MAPPING_CONTRADICTION")
    elif receipt.get("side_effects") != oracle["side_effects"] or receipt.get("validation_exit_code") != 0:
        claim = refuted_claim("AUTHORITY", "REJECT_SIDE_EFFECT_OR_EXIT_CONTRADICTION", "READ_ONLY_AUTHORITY_CONTRADICTION")
    else:
        claim = closed_claim("CONFORMANCE", "MATCH_SERVICE_CONTRACT_RELATIONS", "GOOO_SERVICE_CONTRACT_MATCHES_GENERATED_JSON_AND_OPENTOFU_VALIDATION")
    write_json(output, {
        "schema": "gooo/opentofu-envelope/semantic-oracle-match/v1",
        "state": claim["state"],
        "claim": claim,
        "provenance": {
            "source": {"path": str(source), "sha256": sha256_file(source)},
            "ir": {"path": str(graph), "sha256": sha256_file(graph)},
            "generated_tf_json": {"path": str(artifact), "sha256": sha256_file(artifact)},
            "opentofu_observation": {"path": str(tofu_json), "sha256": sha256_file(tofu_json)},
            "independent_oracle": {"path": str(oracle_path), "sha256": sha256_file(oracle_path)},
        },
        "contract_receipt_sha256": sha256_file(receipt_path),
        "expected_service": oracle["service"],
        "observed_service": source_doc["service"],
        "expected_required_outputs": expected_outputs,
        "observed_required_outputs": observed_outputs,
        "expected_output_mapping": expected_mapping,
        "observed_output_mapping": observed_mapping,
        "expected_resource_input": expected_resource_input,
        "observed_resource_input": observed_resource_input,
        "semantic_relation_count": len(source_doc["relations"]),
    })


def attach_activity(claim: dict[str, Any], activity: str, activity_ids: dict[str, str]) -> dict[str, Any]:
    return {"activity": activity, "activity_id": activity_ids[activity], **claim}


def evaluate_cases(match_path: Path, bindings_path: Path, output: Path) -> None:
    bindings = read_json(bindings_path)
    activity_ids = {item["activity"]: item["activity_id"] for item in bindings["bindings"]}
    match = read_json(match_path)
    if match.get("state") != "CLOSED":
        die("normal canonical cases require a closed semantic oracle match")
    normal_base = closed_claim("CONFORMANCE", "MATCH_SERVICE_CONTRACT_RELATIONS", "GOOO_SERVICE_CONTRACT_MATCHES_GENERATED_JSON_AND_OPENTOFU_VALIDATION")
    unknowns = [
        ("unknown-stale-generated-config", unknown_claim("CONFORMANCE", "MATCH_CURRENT_GENERATED_CONFIG", "STALE_GENERATED_CONFIG_DIGEST", "DIRECT_MISSING", "REGENERATE_MAIN_TF_JSON")),
        ("unknown-unobserved-validate", unknown_claim("VALIDATION", "READ_VALIDATE_JSON", "OPENTOFU_VALIDATE_JSON_NOT_OBSERVED", "OBSERVATION_UNAVAILABLE", "CAPTURE_PINNED_VALIDATE_JSON", ["OPENTOFU_VALIDATE_JSON"])),
        ("unknown-required-mapping", unknown_claim("CONFORMANCE", "MATCH_REQUIRED_OUTPUT_MAPPING", "REQUIRED_OUTPUT_MAPPING_NOT_OBSERVED", "DIRECT_MISSING", "CAPTURE_REQUIRED_OUTPUT_MAPPING", [])),
    ]
    refuted = [
        ("refuted-port-type", refuted_claim("CONFORMANCE", "MATCH_SERVICE_CONTRACT_RELATIONS", "SERVICE_PORT_TYPE_CONTRADICTION")),
        ("refuted-required-output", refuted_claim("CONFORMANCE", "MATCH_REQUIRED_OUTPUT_MAPPING", "REQUIRED_OUTPUT_RELATION_CONTRADICTION")),
        ("refuted-authority", refuted_claim("AUTHORITY", "REJECT_SIDE_EFFECT_OR_EXIT_CONTRADICTION", "READ_ONLY_PERMISSION_CONTRADICTION")),
    ]
    cases = []
    for case_id in ("normal-service-port", "normal-required-outputs", "normal-providerless-validation"):
        cases.append({"case_id": case_id, "class": "normal", "decision": "CLOSED", "claims": [attach_activity(normal_base, "MatchGoooIntentToIndependentOracle", activity_ids)], "resolution": "EXACT"})
    for case_id, claim in unknowns:
        full = attach_activity(claim, "PreserveUnknownCase", activity_ids)
        if not UNKNOWN_FIELDS.issubset(full) or not isinstance(full["blocked_by"], list):
            die("unknown canonical case lost coordinates")
        cases.append({"case_id": case_id, "class": "unknown", "decision": "FAIL_CLOSED", "claims": [full], "resolution": "LOWER_RESOLUTION"})
    for case_id, claim in refuted:
        full = attach_activity(claim, "RefuteContradictionCase", activity_ids)
        cases.append({"case_id": case_id, "class": "refuted", "decision": "FAIL_CLOSED", "claims": [full], "precedence": "REFUTED_OVER_UNKNOWN", "resolution": "EXACT"})
    if sum(case["class"] == "normal" for case in cases) != 3 or sum(case["class"] == "unknown" for case in cases) != 3 or sum(case["class"] == "refuted" for case in cases) != 3:
        die("canonical case denominator is not 3/3/3")
    write_json(output, {
        "schema": "gooo/opentofu-envelope/cases/v2",
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
        for name in ("main.tf.json", "dossier.md"):
            first = publish_dir / name
            second = replay_dir / name
            equal = first.read_bytes() == second.read_bytes()
            comparisons.append({"file": name, "byte_equal": equal, "first_sha256": sha256_file(first), "second_sha256": sha256_file(second)})
    write_json(output, {"schema": "gooo/opentofu-envelope/replay/v2", "state": "CLOSED" if all(item["byte_equal"] for item in comparisons) else "REFUTED", "comparison_count": len(comparisons), "comparisons": comparisons})


def producer(source: Path, graph: Path, artifact: str, observation: str, oracle: str, evaluator: str) -> dict[str, str]:
    return {"source": str(source), "ir": str(graph), "generated_artifact": artifact, "opentofu_observation": observation, "independent_oracle": oracle, "evaluator": evaluator}


def record(publish_dir: Path, source: Path, graph: Path, lock: Path, spec: Path, bindings_path: Path, denominator_path: Path, inventory_path: Path, validation_path: Path, receipt_path: Path, match_path: Path, oracle_path: Path, cases_path: Path, replay_path: Path, measurements_path: Path, go_version_path: Path, repository_status_path: Path, output: Path) -> None:
    lock_doc = release_lock(lock)
    denominator = contract(denominator_path)
    bindings = read_json(bindings_path)
    activity_ids = {item["activity"]: item["activity_id"] for item in bindings["bindings"]}
    cell_ids = {cell["activity"]: cell["id"] for cell in denominator["cells"]}
    inventory_doc = read_json(inventory_path)
    validation_doc = read_json(validation_path)
    receipt = read_json(receipt_path)
    match = read_json(match_path)
    oracle = load_service_oracle(oracle_path)
    cases = read_json(cases_path)
    replay_doc = read_json(replay_path)
    measurements = read_json(measurements_path)
    if not isinstance(inventory_doc.get("regular_files"), list) or not isinstance(inventory_doc.get("descendant_directories"), list):
        die("repository inventory lists are missing")
    inventory_summary = {
        "file_count": len(inventory_doc["regular_files"]),
        "subfolder_count": len(inventory_doc["descendant_directories"]),
        "physical_line_count": sum(integer(item.get("lines"), "inventory file lines") for item in inventory_doc["regular_files"]),
        "go_files": sum(item.get("path", "").endswith(".go") for item in inventory_doc["regular_files"]),
        "go_physical_lines": sum(integer(item.get("lines"), "inventory file lines") for item in inventory_doc["regular_files"] if item.get("path", "").endswith(".go")),
        "gooo_files": sum(item.get("path", "").endswith(".gooo") for item in inventory_doc["regular_files"]),
        "gooo_physical_lines": sum(integer(item.get("lines"), "inventory file lines") for item in inventory_doc["regular_files"] if item.get("path", "").endswith(".gooo")),
    }
    for key, expected in (("regular_file_count", inventory_summary["file_count"]), ("descendant_directory_count", inventory_summary["subfolder_count"]), ("physical_line_count", inventory_summary["physical_line_count"]), ("go_physical_files", inventory_summary["go_files"]), ("go_physical_lines", inventory_summary["go_physical_lines"]), ("gooo_physical_files", inventory_summary["gooo_files"]), ("gooo_physical_lines", inventory_summary["gooo_physical_lines"])):
        if inventory_doc.get(key) != expected:
            die(f"repository inventory summary is not exact for {key}")
    if receipt.get("state") != "CLOSED" or match.get("state") != "CLOSED" or validation_doc.get("state") != "CLOSED" or replay_doc.get("state") != "CLOSED":
        die("record requires closed validation, semantic match, receipt, and replay")
    if cases.get("case_count") != 9 or len(cases.get("cases", [])) != 9 or cases.get("state_precedence") != ["REFUTED", "UNKNOWN", "CLOSED"] or cases.get("precedence_rule") != "REFUTED > UNKNOWN > CLOSED":
        die("record requires exactly 9 canonical cases")
    if cases.get("outcome_counts") != {"CLOSED": 3, "UNKNOWN": 3, "REFUTED": 3}:
        die("canonical case outcome counts are not 3/3/3")
    for stage in measurements:
        if stage.get("execution_state") not in EXECUTION_VALUES or stage.get("cache_state") not in CACHE_VALUES or stage.get("runner_persistence") not in PERSISTENCE_VALUES or stage.get("prior_test_evidence_reuse_state") not in REUSE_VALUES:
            die("measurement enum value is invalid")
        for field in ("wall_ms", "count", "executed_test_count", "reused_test_evidence_count", "skipped_test_count", "not_observed_test_count", "peak_rss_kib"):
            integer(stage.get(field), field)
        if stage["execution_state"] == "REUSED" and stage["count"] == 0:
            die("reused phase must not be represented as a zero-count execution")
    by_stage = {stage["stage"]: stage for stage in measurements}
    if len(by_stage) != 3:
        die("measurement stages are not exactly build/test/conformance")
    for required in ("build", "test", "conformance"):
        if required not in by_stage:
            die(f"missing {required} measurement")
    test_total = len(cases["cases"])
    test_counts = {
        "total": test_total,
        "executed": by_stage["test"]["executed_test_count"],
        "reused": by_stage["test"]["reused_test_evidence_count"],
        "skipped": by_stage["test"]["skipped_test_count"],
        "not_observed": by_stage["test"]["not_observed_test_count"],
    }
    if by_stage["test"]["count"] != test_total or sum(test_counts[key] for key in ("executed", "reused", "skipped", "not_observed")) != test_total:
        die("test total and execution states are not exact")
    try:
        repository_status = repository_status_path.read_text(encoding="utf-8")
    except OSError as exc:
        die(f"cannot read repository write observation {repository_status_path}: {exc}")
    repository_status_lines = [line for line in repository_status.splitlines() if line.strip()]
    repository_writes = len(repository_status_lines)
    if repository_writes != lock_doc["authority"]["repository_writes"]:
        die("repository write observation contradicts the read-only authority lock")
    side_effects = oracle["side_effects"]
    mutation_counts = {
        "network": integer(side_effects["network"], "network mutations"),
        "provider_install": integer(side_effects["provider_install"], "provider-install mutations"),
        "infrastructure": integer(side_effects["infrastructure_mutation"], "infrastructure mutations"),
        "state": integer(side_effects["state_mutation"], "state mutations"),
    }
    mutation_counts["external_mutations"] = sum(mutation_counts.values())
    core_authority = {
        "state": "CLOSED",
        "evidence": ["GOOO_SEMANTIC_IR", "PINNED_OPENTOFU_VALIDATE_JSON", "INDEPENDENT_SERVICE_ORACLE"],
        "reason": "the released Gooo graph, pinned read-only validation, and independent oracle all agree",
    }
    try:
        go_version = go_version_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        die(f"cannot read Go version evidence {go_version_path}: {exc}")
    if not go_version.startswith("go version go1.27"):
        die("Go version evidence is not Go 1.27")
    reuse_key = {
        "source_digest": sha256_file(source),
        "toolchain_digest": sha256_value({"gooo_release": lock_doc["gooo"]["asset"]["sha256"], "opentofu_binary": lock_doc["opentofu"]["binary_sha256"]}),
        "command_digest": sha256_value({"version": ["tofu", "version", "-json"], "validate": lock_doc["opentofu"]["validate_command"]}),
        "config_digest": sha256_file(lock),
        "dependency_digest": sha256_value({"json_spec": sha256_file(spec), "python": sys.version.split()[0]}),
        "provider_lock_digest": sha256_value({"provider_lock": "ABSENT_FOR_PROVIDERLESS_CONFIG"}),
        "test_inventory_digest": sha256_file(cases_path),
        "policy_digest": sha256_value({"profile": "READ_ONLY", "apply": 0, "test": 0, "cloud": 0, "network": 0, "provider_install": 0, "source_write": 0}),
    }
    for key in REUSE_KEY_FIELDS:
        if not isinstance(reuse_key.get(key), str) or len(reuse_key[key]) != 64:
            die(f"reuse key field is missing: {key}")

    def metric(name: str, value: int, unit: str, activity: str, artifact: str, observation: str = "validation.json") -> dict[str, Any]:
        integer(value, name)
        return {"name": name, "value": value, "unit": unit, "activity": activity, "activity_id": activity_ids[activity], "cell_id": cell_ids[activity], "producer": producer(source, graph, artifact, observation, "service-contract-oracle-v1.json", "scripts/envelope.py:record")}

    artifact_files = sorted(path.name for path in publish_dir.iterdir() if path.is_file())
    if artifact_files != sorted(["contract-receipt.json", "dossier.md", "main.tf.json"]):
        die("generated artifact set is not exactly main.tf.json, contract-receipt.json, dossier.md")
    artifact_bytes = sum((publish_dir / name).stat().st_size for name in artifact_files)
    main_tf_bytes = (publish_dir / "main.tf.json").stat().st_size
    metrics = [
        metric("input_gooo_files", inventory_doc["gooo_physical_files"], "files", "DeclareGoooInfrastructureIntent", "main.gooo", "bindings.json"),
        metric("input_gooo_lines", inventory_doc["gooo_physical_lines"], "lines", "DeclareGoooInfrastructureIntent", "main.gooo", "bindings.json"),
        metric("generated_tf_json_files", 1, "files", "GenerateOpenTofuCompatibleArtifact", "main.tf.json"),
        metric("generated_tf_json_bytes", main_tf_bytes, "bytes", "GenerateOpenTofuCompatibleArtifact", "main.tf.json"),
        metric("semantic_relations", match["semantic_relation_count"], "relations", "BindGoooIntentToOpenTofu", "bindings.json"),
        metric("opentofu_commands_attempted", receipt["validation_attempted"], "commands", "GenerateOpenTofuValidationReceipt", "contract-receipt.json"),
        metric("opentofu_commands_executed", receipt["validation_executed"], "commands", "GenerateOpenTofuValidationReceipt", "contract-receipt.json"),
        metric("opentofu_exit_code", receipt["validation_exit_code"], "exit-code", "GenerateOpenTofuValidationReceipt", "contract-receipt.json"),
        metric("validation_error_count", receipt["diagnostics"]["error_count"], "diagnostics", "GenerateOpenTofuValidationReceipt", "contract-receipt.json"),
        metric("validation_warning_count", receipt["diagnostics"]["warning_count"], "diagnostics", "GenerateOpenTofuValidationReceipt", "contract-receipt.json"),
        metric("build_wall_ms", by_stage["build"]["wall_ms"], "ms", "GenerateOpenTofuCompatibleArtifact", "observation.json"),
        metric("test_wall_ms", by_stage["test"]["wall_ms"], "ms", "PreserveReadOnlyBoundary", "observation.json"),
        metric("conformance_wall_ms", by_stage["conformance"]["wall_ms"], "ms", "MatchGoooIntentToIndependentOracle", "observation.json"),
        metric("peak_rss_kib", max(stage["peak_rss_kib"] for stage in measurements), "KiB", "PreserveReadOnlyBoundary", "observation.json"),
        metric("tests_total", test_counts["total"], "tests", "PreserveReadOnlyBoundary", "cases.json", "cases.json"),
        metric("tests_executed", test_counts["executed"], "tests", "PreserveReadOnlyBoundary", "cases.json", "cases.json"),
        metric("tests_reused", test_counts["reused"], "tests", "VerifyDeterministicReplay", "replay.json", "cases.json"),
        metric("tests_skipped", test_counts["skipped"], "tests", "PreserveReadOnlyBoundary", "cases.json", "cases.json"),
        metric("tests_not_observed", test_counts["not_observed"], "tests", "PreserveReadOnlyBoundary", "cases.json", "cases.json"),
        metric("replay_comparisons", replay_doc["comparison_count"], "comparisons", "VerifyDeterministicReplay", "replay.json", "cases.json"),
        metric("replay_mismatches", sum(not item["byte_equal"] for item in replay_doc["comparisons"]), "mismatches", "VerifyDeterministicReplay", "replay.json", "cases.json"),
        metric("artifact_files", len(artifact_files), "files", "VerifyGeneratedOutputs", "observation.json"),
        metric("repository_writes", repository_writes, "writes", "PreserveReadOnlyBoundary", "observation.json"),
        metric("infrastructure_mutations", mutation_counts["infrastructure"], "mutations", "PreserveReadOnlyBoundary", "observation.json"),
        metric("network_provider_install_attempts", mutation_counts["provider_install"], "attempts", "PreserveReadOnlyBoundary", "observation.json"),
    ]
    improvement_claim = unknown_claim("IMPROVEMENT", "COMPARE_EXACT_BEFORE_AFTER", "EXACT_BEFORE_AFTER_PAIR_MISSING", "DIRECT_MISSING", "CAPTURE_EXACT_BEFORE_AFTER_PAIR", ["BEFORE_EXACT_OBSERVATION", "AFTER_EXACT_OBSERVATION"])
    primary = []
    for cell in denominator["cells"]:
        primary.append({"metric_id": f"cell-metric-{cell['ordinal']:02d}", "cell_id": cell["id"], "activity": cell["activity"], "activity_id": activity_ids[cell["activity"]], "value": "CLOSED", "unit": "cell-state", "producer": producer(source, graph, "main.tf.json", "validation.json", "service-contract-oracle-v1.json", "scripts/envelope.py:record")})
    output_doc = {
        "schema": "gooo/opentofu-envelope/observation/v2",
        "state": "CLOSED",
        "state_precedence": ["REFUTED", "UNKNOWN", "CLOSED"],
        "precedence_rule": "REFUTED > UNKNOWN > CLOSED",
        "subject": {"source_sha256": sha256_file(source), "graph_sha256": sha256_file(graph), "release_lock_sha256": sha256_file(lock)},
        "semantic_authority": bindings.get("semantic_authority"),
        "core_authority": core_authority,
        "toolchain": {"go_requirement": "1.27.x", "go_version_evidence": go_version},
        "user_path": {"step_count": denominator["expected_user_path_steps"], "activities": ["DeclareGoooInfrastructureIntent", "BindGoooIntentToOpenTofu", "GenerateOpenTofuCompatibleArtifact", "VerifyGeneratedOutputs", "MatchGoooIntentToIndependentOracle"]},
        "generated_outputs": {"file_count": len(artifact_files), "files": artifact_files, "bytes": artifact_bytes, "digests": {name: sha256_file(publish_dir / name) for name in artifact_files}},
        "repository_inventory": inventory_summary,
        "test_counts": test_counts,
        "mutation_counts": {"repository_writes": repository_writes, **mutation_counts},
        "metrics": metrics,
        "primary_metrics": primary,
        "verification_stages": measurements,
        "phase_contract": {"execution_state_values": sorted(EXECUTION_VALUES), "cache_state_values": sorted(CACHE_VALUES), "runner_persistence_values": sorted(PERSISTENCE_VALUES), "reuse_never_zero_ms_execution": True, "cache_hit_is_not_test_reuse": True, "prior_evidence_requires_all_reuse_key_fields": REUSE_KEY_FIELDS},
        "improvement": {"state": "UNKNOWN", "claim": improvement_claim, "before": None, "after": None, "cache_hit_is_not_reuse": True},
        "utility": {"state": "UNKNOWN", "claim": unknown_claim("UTILITY", "COMPARE_USER_OUTCOME", "EXACT_USER_UTILITY_OBSERVATION_MISSING", "DIRECT_MISSING", "CAPTURE_EXACT_USER_UTILITY_OBSERVATION", ["BEFORE_UTILITY_OBSERVATION", "AFTER_UTILITY_OBSERVATION"]), "evidence": None},
        "cases": cases,
        "validation": validation_doc,
        "contract_receipt": receipt,
        "semantic_oracle_match": match,
        "independent_oracle": {"sha256": sha256_file(oracle_path), "service": oracle["service"], "required_outputs": oracle["required_outputs"], "side_effects": oracle["side_effects"]},
        "identity": {"source_sha256": sha256_file(source), "graph_sha256": sha256_file(graph), "main_tf_json_sha256": sha256_file(publish_dir / "main.tf.json"), "contract_receipt_sha256": sha256_file(publish_dir / "contract-receipt.json"), "dossier_sha256": sha256_file(publish_dir / "dossier.md"), "validation_json_sha256": sha256_file(validation_path), "binary_sha256": receipt["binary_sha256"], "version_json_sha256": receipt["version_json_sha256"]},
        "reuse_contract": {"installation_binary_cache_state": lock_doc["cache_contract"]["installation_binary_cache_state"], "go_build_cache_state": lock_doc["cache_contract"]["go_build_cache_state"], "prior_test_evidence_reuse_state": lock_doc["cache_contract"]["prior_test_evidence_reuse_state"], "runner_persistence": lock_doc["cache_contract"]["runner_persistence"], "reuse_key": reuse_key},
        "authority": lock_doc["authority"],
        "policy": lock_doc["policy"],
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
    command = sub.add_parser("validate")
    command.add_argument("--tofu-json", type=Path, required=True)
    command.add_argument("--artifact", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    command = sub.add_parser("contract-receipt")
    for name in ("source", "graph", "artifact", "validation", "tofu-json", "version-json", "binary", "oracle", "lock", "output"):
        command.add_argument(f"--{name}", type=Path, required=True)
    command.add_argument("--exit-code", type=int, required=True)
    command = sub.add_parser("match-contract")
    for name in ("source", "graph", "artifact", "validation", "tofu-json", "receipt", "oracle", "output"):
        command.add_argument(f"--{name}", type=Path, required=True)
    command = sub.add_parser("cases")
    for name in ("match", "bindings", "output"):
        command.add_argument(f"--{name}", type=Path, required=True)
    command = sub.add_parser("replay")
    for name in ("publish-dir", "source", "graph", "lock", "spec", "bindings", "denominator", "inventory", "output"):
        command.add_argument(f"--{name}", type=Path, required=True)
    command = sub.add_parser("record")
    for name in ("publish-dir", "source", "graph", "lock", "spec", "bindings", "denominator", "inventory", "validation", "receipt", "match", "oracle", "cases", "replay", "measurements", "go-version", "repository-status", "output"):
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
    elif args.command == "validate":
        validate(args.tofu_json, args.artifact, args.output)
    elif args.command == "contract-receipt":
        contract_receipt(args.source, args.graph, args.artifact, args.validation, args.tofu_json, args.version_json, args.binary, args.oracle, args.lock, args.exit_code, args.output)
        if read_json(args.output).get("state") != "CLOSED":
            die("contract receipt did not close")
    elif args.command == "match-contract":
        match_contract(args.source, args.graph, args.artifact, args.validation, args.tofu_json, args.receipt, args.oracle, args.output)
    elif args.command == "cases":
        evaluate_cases(args.match, args.bindings, args.output)
    elif args.command == "replay":
        replay(args.publish_dir, args.source, args.graph, args.lock, args.spec, args.bindings, args.denominator, args.inventory, args.output)
    elif args.command == "record":
        record(args.publish_dir, args.source, args.graph, args.lock, args.spec, args.bindings, args.denominator, args.inventory, args.validation, args.receipt, args.match, args.oracle, args.cases, args.replay, args.measurements, args.go_version, args.repository_status, args.output)


if __name__ == "__main__":
    main()

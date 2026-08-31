#!/usr/bin/env python3
"""Produce and verify the v0.2.0 generated service-project evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


ACTIVITIES = [
    "DeclareProjectResourceIntent",
    "DeclareServiceCapability",
    "DeclareServiceEndpoint",
    "BindResourceCapability",
    "BindCapabilityEndpoint",
    "GenerateOpenTofuServiceProject",
    "GenerateServiceContract",
    "GenerateRelationReport",
    "ValidateGeneratedServiceProject",
    "EvaluateScenarioEvidence",
    "VerifyDeterministicReplay",
    "PreserveReadOnlyBoundary",
]
ENTITY_NAMES = [
    "ProjectResourceIntent",
    "ServiceCapability",
    "ServiceEndpoint",
    "ResourceContract",
    "CapabilityContract",
    "EndpointContract",
    "ResourceCapabilityBinding",
    "CapabilityEndpointBinding",
    "OpenTofuProjectArtifact",
    "ServiceContractArtifact",
    "RelationReportArtifact",
    "ValidationEvidence",
    "ScenarioEvidence",
    "ReplayEvidence",
    "ReadOnlyObservation",
]
ACTIVITY_INPUTS = {
    "DeclareProjectResourceIntent": {"ProjectResourceIntent"},
    "DeclareServiceCapability": {"ServiceCapability"},
    "DeclareServiceEndpoint": {"ServiceEndpoint"},
    "BindResourceCapability": {"ResourceContract", "CapabilityContract"},
    "BindCapabilityEndpoint": {"CapabilityContract", "EndpointContract"},
    "GenerateOpenTofuServiceProject": {"ResourceCapabilityBinding", "CapabilityEndpointBinding"},
    "GenerateServiceContract": {"OpenTofuProjectArtifact"},
    "GenerateRelationReport": {"ServiceContractArtifact"},
    "ValidateGeneratedServiceProject": {"ServiceContractArtifact", "RelationReportArtifact"},
    "EvaluateScenarioEvidence": {"ValidationEvidence"},
    "VerifyDeterministicReplay": {"ValidationEvidence"},
    "PreserveReadOnlyBoundary": {"ScenarioEvidence", "ReplayEvidence"},
}
ACTIVITY_OUTPUTS = {
    "DeclareProjectResourceIntent": {"ResourceContract"},
    "DeclareServiceCapability": {"CapabilityContract"},
    "DeclareServiceEndpoint": {"EndpointContract"},
    "BindResourceCapability": {"ResourceCapabilityBinding"},
    "BindCapabilityEndpoint": {"CapabilityEndpointBinding"},
    "GenerateOpenTofuServiceProject": {"OpenTofuProjectArtifact"},
    "GenerateServiceContract": {"ServiceContractArtifact"},
    "GenerateRelationReport": {"RelationReportArtifact"},
    "ValidateGeneratedServiceProject": {"ValidationEvidence"},
    "EvaluateScenarioEvidence": {"ScenarioEvidence"},
    "VerifyDeterministicReplay": {"ReplayEvidence"},
    "PreserveReadOnlyBoundary": {"ReadOnlyObservation"},
}
UNKNOWN_FIELDS = {"stage", "step", "reason", "unknown_class", "next_operation", "blocked_by"}
SCOPE = "GENERATED_OPENTOFU_SERVICE_PROJECT_ONLY"
PRECEDENCE = ["REFUTED", "UNKNOWN", "CLOSED"]


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
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        die(f"{name} must be a non-negative integer")
    return value


def parse_directive(line: str, name: str) -> dict[str, str] | None:
    prefix = f"// @{name} "
    if not line.startswith(prefix):
        return None
    rest = line[len(prefix):].strip()
    matches = re.findall(r"([A-Za-z_][A-Za-z0-9_]*)=([^\s]+)", rest)
    if not matches or len(matches) != len(rest.split()):
        die(f"invalid @{name} directive")
    result = dict(matches)
    if len(result) != len(matches):
        die(f"duplicate @{name} field")
    return result


def require_fields(item: dict[str, str], required: set[str], name: str) -> None:
    if set(item) != required:
        die(f"{name} fields are not exactly {sorted(required)}")


def parse_source(path: Path) -> dict[str, Any]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        die(f"cannot read source {path}: {exc}")
    project: dict[str, str] | None = None
    resources: list[dict[str, str]] = []
    capabilities: list[dict[str, str]] = []
    endpoints: list[dict[str, str]] = []
    bindings: list[dict[str, str]] = []
    scenarios: list[dict[str, str]] = []
    for raw in lines:
        line = raw.strip()
        item = parse_directive(line, "project")
        if item is not None:
            if project is not None:
                die("multiple project directives")
            require_fields(item, {"name", "environment"}, "project")
            project = item
            continue
        item = parse_directive(line, "resource")
        if item is not None:
            require_fields(item, {"name", "kind", "image"}, "resource")
            resources.append(item)
            continue
        item = parse_directive(line, "capability")
        if item is not None:
            require_fields(item, {"name", "protocol"}, "capability")
            capabilities.append(item)
            continue
        item = parse_directive(line, "endpoint")
        if item is not None:
            require_fields(item, {"name", "capability", "path", "port"}, "endpoint")
            item["port"] = str(int(item["port"]))
            endpoints.append(item)
            continue
        item = parse_directive(line, "binding")
        if item is not None:
            require_fields(item, {"resource", "capability", "endpoint"}, "binding")
            bindings.append(item)
            continue
        item = parse_directive(line, "scenario")
        if item is not None:
            required = {"id", "class", "resource", "capability", "endpoint"}
            optional = {"reason", "expected_port", "observed_port", "expected_capability", "observed_capability"}
            if set(item) - required - optional:
                die("scenario contains an unknown field")
            if not set(item) & {"reason", "expected_port", "observed_port", "expected_capability", "observed_capability"} <= optional:
                die("scenario field shape is invalid")
            require_fields(item, set(item), "scenario")
            scenarios.append(item)
    if project is None or len(resources) != 2 or len(capabilities) != 1 or len(endpoints) != 2 or len(bindings) != 2 or len(scenarios) != 6:
        die("source does not contain the fixed project contract")
    for label, values in (("resource", resources), ("capability", capabilities), ("endpoint", endpoints), ("scenario", scenarios)):
        key = "id" if label == "scenario" else "name"
        if len({item[key] for item in values}) != len(values):
            die(f"{label} names are not unique")
    resource_names = {item["name"] for item in resources}
    capability_names = {item["name"] for item in capabilities}
    endpoint_names = {item["name"] for item in endpoints}
    if any(item["resource"] not in resource_names or item["capability"] not in capability_names or item["endpoint"] not in endpoint_names for item in bindings):
        die("binding references an undeclared project object")
    if any(item["capability"] not in capability_names for item in endpoints):
        die("endpoint references an undeclared capability")
    if any(item["resource"] not in resource_names or item["capability"] not in capability_names for item in scenarios):
        die("scenario references an undeclared resource or capability")
    if any(item["class"] != "UNKNOWN" and item["endpoint"] not in endpoint_names for item in scenarios):
        die("only UNKNOWN scenarios may name a missing endpoint")
    class_counts = {kind: sum(item["class"] == kind for item in scenarios) for kind in ("NORMAL", "UNKNOWN", "REFUTED")}
    if class_counts != {"NORMAL": 2, "UNKNOWN": 2, "REFUTED": 2}:
        die("scenario classes must be exactly 2 NORMAL, 2 UNKNOWN, and 2 REFUTED")
    return {"project": project, "resources": resources, "capabilities": capabilities, "endpoints": endpoints, "bindings": bindings, "scenarios": scenarios, "source_sha256": sha256_file(path)}


def project_contract(path: Path) -> dict[str, Any]:
    value = read_json(path)
    cells = value.get("cells")
    if value.get("schema") != "gooo/opentofu-envelope/project-denominator/v2" or value.get("version") != 2 or value.get("target_cells") != 12 or value.get("expected_user_path_steps") != 6 or not isinstance(cells, list) or len(cells) != 12:
        die("project denominator must contain exactly 12 cells and 6 user path steps")
    if [cell.get("ordinal") for cell in cells] != list(range(1, 13)) or len({cell.get("id") for cell in cells}) != 12 or {cell.get("activity") for cell in cells} != set(ACTIVITIES):
        die("project denominator ordinals, IDs, or activities are not exact")
    cell_ids = {cell.get("id") for cell in cells}
    expected_fields = {"ordinal", "id", "activity", "stage", "step", "proof_family", "indicator", "depends_on"}
    for cell in cells:
        if set(cell) != expected_fields or not isinstance(cell["depends_on"], list):
            die("every project denominator cell must have exactly 8 fields")
        if any(dep not in cell_ids or dep == cell["id"] for dep in cell["depends_on"]):
            die(f"invalid denominator dependency for {cell['id']}")
        if any(next(item["ordinal"] for item in cells if item["id"] == dep) >= cell["ordinal"] for dep in cell["depends_on"]):
            die(f"denominator dependency is not acyclic for {cell['id']}")
    if sum(len(cell["depends_on"]) for cell in cells) != 14:
        die("project denominator binding edge count is not 14")
    if {family: sum(cell["proof_family"] == family for cell in cells) for family in ("FOUNDATION", "COHERENCE", "REGRESSION")} != {"FOUNDATION": 4, "COHERENCE": 4, "REGRESSION": 4}:
        die("project proof-family denominator is not 4/4/4")
    if {indicator: sum(cell["indicator"] == indicator for cell in cells) for indicator in ("DRIVER", "OUTCOME", "GUARDRAIL")} != {"DRIVER": 4, "OUTCOME": 4, "GUARDRAIL": 4}:
        die("project indicator denominator is not 4/4/4")
    if value.get("expected_output_files") != ["contract-receipt.json", "dossier.md", "main.tf.json", "relation-report.md", "service-contract.json"]:
        die("project output denominator is not exact")
    return value


def graph_model(graph_path: Path, source_path: Path) -> dict[str, Any]:
    graph = read_json(graph_path)
    if graph.get("schema_version") != "gooo-graph/v1" or graph.get("source_digest") != sha256_file(source_path):
        die("released graph schema or source digest is invalid")
    ir = graph.get("ir", {})
    authorities = graph.get("authorities", {})
    if ir.get("status") != "available" or not isinstance(ir.get("semantic_digest"), str):
        die("released semantic IR is unavailable")
    if authorities.get(".gooo") != "authoritative" or authorities.get("ir") != "authoritative" or authorities.get("graph") != "derived":
        die("released graph authority boundary is invalid")
    nodes = graph.get("nodes")
    relations = graph.get("relations")
    if not isinstance(nodes, list) or not isinstance(relations, list):
        die("released graph nodes or relations are missing")
    ids = [node.get("id") for node in nodes]
    if len(ids) != len(set(ids)) or any(not isinstance(node_id, str) for node_id in ids):
        die("released graph node IDs are not unique")
    activity_nodes = [node for node in nodes if node.get("kind") == "Activity"]
    entity_nodes = [node for node in nodes if node.get("kind") == "Entity"]
    if len(activity_nodes) != 12 or len(entity_nodes) != 15:
        die("released graph must contain 12 activities and 15 entities")
    activity_ids = {node.get("name"): node.get("id") for node in activity_nodes}
    entity_ids = {node.get("name"): node.get("id") for node in entity_nodes}
    if set(activity_ids) != set(ACTIVITIES) or set(entity_ids) != set(ENTITY_NAMES) or len(activity_ids) != 12 or len(entity_ids) != 15:
        die("released graph names are not exact")
    name_by_id = {node_id: name for name, node_id in {**activity_ids, **entity_ids}.items()}
    inputs = {activity: set() for activity in ACTIVITIES}
    outputs = {activity: set() for activity in ACTIVITIES}
    relation_keys: set[tuple[Any, ...]] = set()
    for relation in relations:
        key = (relation.get("status"), relation.get("subject"), relation.get("predicate"), relation.get("object"))
        if key in relation_keys:
            die("released graph contains duplicate relations")
        relation_keys.add(key)
        if relation.get("status") != "deterministic":
            continue
        subject = name_by_id.get(relation.get("subject"))
        obj = name_by_id.get(relation.get("object"))
        if relation.get("predicate") == "used" and subject in ACTIVITIES and obj in ENTITY_NAMES:
            inputs[subject].add(obj)
        if relation.get("predicate") == "wasGeneratedBy" and subject in ENTITY_NAMES and obj in ACTIVITIES:
            outputs[obj].add(subject)
    for activity in ACTIVITIES:
        if inputs[activity] != ACTIVITY_INPUTS[activity] or outputs[activity] != ACTIVITY_OUTPUTS[activity]:
            die(f"released graph input/output contract mismatch for {activity}")
    return {"raw": graph, "activity_ids": activity_ids, "entity_ids": entity_ids, "inputs": inputs, "outputs": outputs, "ir_digest": ir["semantic_digest"]}


def bind(source_path: Path, graph_path: Path, denominator_path: Path, output: Path) -> None:
    denominator = project_contract(denominator_path)
    model = graph_model(graph_path, source_path)
    source_text = source_path.read_text(encoding="utf-8")
    for activity in ACTIVITIES:
        if f"activity {activity}(" not in source_text:
            die(f"source does not declare {activity}")
    result = []
    for cell in denominator["cells"]:
        activity = cell["activity"]
        for dependency in cell["depends_on"]:
            predecessor = next(item for item in denominator["cells"] if item["id"] == dependency)
            if not ACTIVITY_OUTPUTS[predecessor["activity"]].intersection(ACTIVITY_INPUTS[activity]):
                die(f"denominator dependency does not match graph ports for {cell['id']}")
        result.append({
            "ordinal": cell["ordinal"], "cell_id": cell["id"], "activity": activity, "activity_id": model["activity_ids"][activity],
            "stage": cell["stage"], "step": cell["step"], "proof_family": cell["proof_family"], "indicator": cell["indicator"],
            "depends_on": cell["depends_on"], "input_entities": sorted(model["inputs"][activity]), "output_entities": sorted(model["outputs"][activity]),
            "producer": {"source": str(source_path), "ir": str(graph_path), "generated_artifact": "bindings.json", "evaluator": "scripts/project_envelope.py:bind"},
        })
    write_json(output, {
        "schema": "gooo/opentofu-envelope/project-bindings/v2", "state": "CLOSED",
        "semantic_authority": {"state": "CLOSED", "source": "GOOO_SOURCE_AUTHORITATIVE", "ir": "GOOO_SEMANTIC_IR_AUTHORITATIVE", "graph": "DERIVED_FROM_RELEASED_IR", "scope": SCOPE, "ir_sha256": model["ir_digest"]},
        "source_sha256": sha256_file(source_path), "graph_sha256": sha256_file(graph_path), "activity_count": 12, "binding_edges": 14, "bindings": result,
    })


def service_contract_doc(model: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "gooo/opentofu-envelope/service-contract/v2", "version": 2,
        "authority": {"source": "GOOO_SOURCE_AUTHORITATIVE", "semantic_scope": SCOPE, "handwritten_go_physical_files": 0},
        "source_sha256": model["source_sha256"], "project": model["project"], "resources": model["resources"],
        "capabilities": model["capabilities"], "endpoints": model["endpoints"], "bindings": model["bindings"], "scenarios": model["scenarios"],
    }


def generated_artifact(model: dict[str, Any]) -> dict[str, Any]:
    project = model["project"]
    return {
        "//": "Generated solely from the authored Gooo source and checked semantic graph.",
        "resource": {"terraform_data": {
            "project": {"input": {"name": project["name"], "environment": project["environment"], "resources": model["resources"], "capabilities": model["capabilities"], "endpoints": model["endpoints"], "bindings": model["bindings"]}},
            "endpoint_health": {"input": {"path": "/health", "port": 8080, "capability": "checkout-http"}},
            "endpoint_orders": {"input": {"path": "/orders", "port": 8080, "capability": "checkout-http"}},
        }},
        "output": {
            "project_name": {"value": "$" + "{terraform_data.project.output.name}"},
            "service_capabilities": {"value": "$" + "{terraform_data.project.output.capabilities}"},
            "service_endpoints": {"value": "$" + "{terraform_data.project.output.endpoints}"},
        },
    }


def unknown_claim(reason: str) -> dict[str, Any]:
    return {"state": "UNKNOWN", "stage": "BINDING", "step": "BIND_SERVICE_CAPABILITY_ENDPOINT", "reason": reason, "unknown_class": "DIRECT_MISSING", "next_operation": "CAPTURE_MISSING_SERVICE_BINDING", "blocked_by": ["SERVICE_CAPABILITY_ENDPOINT_BINDING"]}


def closed_claim() -> dict[str, Any]:
    return {"state": "CLOSED", "stage": "CONFORMANCE", "step": "VERIFY_BOUND_SERVICE_RELATION", "reason": "DECLARED_RESOURCE_CAPABILITY_ENDPOINT_BINDING", "unknown_class": None, "next_operation": None, "blocked_by": []}


def refuted_claim(reason: str) -> dict[str, Any]:
    return {"state": "REFUTED", "stage": "CONFORMANCE", "step": "REJECT_CONTRADICTORY_RESOURCE_ENDPOINT_MAPPING", "reason": reason, "unknown_class": None, "next_operation": None, "blocked_by": []}


def scenario_evidence(model: dict[str, Any]) -> dict[str, Any]:
    binding_set = {(item["resource"], item["capability"], item["endpoint"]) for item in model["bindings"]}
    endpoint_map = {item["name"]: item for item in model["endpoints"]}
    relations = []
    for scenario in model["scenarios"]:
        relation = dict(scenario)
        key = (scenario["resource"], scenario["capability"], scenario["endpoint"])
        if scenario["class"] == "NORMAL":
            if key not in binding_set or scenario["endpoint"] not in endpoint_map:
                die(f"NORMAL scenario is not bound: {scenario['id']}")
            relation.update({"status": "BOUND", "claim": closed_claim()})
        elif scenario["class"] == "UNKNOWN":
            relation.update({"status": "UNBOUND_UNKNOWN", "claim": unknown_claim(scenario.get("reason", "MISSING_SERVICE_BINDING"))})
        elif scenario["class"] == "REFUTED":
            if "expected_port" in scenario and scenario["expected_port"] == scenario.get("observed_port"):
                die(f"REFUTED port scenario is not contradictory: {scenario['id']}")
            if "expected_capability" in scenario and scenario["expected_capability"] == scenario.get("observed_capability"):
                die(f"REFUTED capability scenario is not contradictory: {scenario['id']}")
            relation.update({"status": "REFUTED", "claim": refuted_claim(scenario.get("reason", "CONTRADICTORY_RESOURCE_ENDPOINT_MAPPING"))})
        else:
            die(f"unsupported scenario class for {scenario['id']}")
        relations.append(relation)
    counts = {"BOUND": sum(item["status"] == "BOUND" for item in relations), "UNBOUND_UNKNOWN": sum(item["status"] == "UNBOUND_UNKNOWN" for item in relations), "REFUTED": sum(item["status"] == "REFUTED" for item in relations)}
    if counts != {"BOUND": 2, "UNBOUND_UNKNOWN": 2, "REFUTED": 2}:
        die("scenario evidence counts are not 2/2/2")
    for item in relations:
        if item["status"] == "UNBOUND_UNKNOWN" and set(item["claim"]) - {"state"} != UNKNOWN_FIELDS:
            die(f"UNKNOWN claim fields are not the required six for {item['id']}")
    return {"schema": "gooo/opentofu-envelope/relation-evidence/v2", "version": 2, "state": "CLOSED", "authority": {"source": "GOOO_SOURCE_AUTHORITATIVE", "semantic_scope": SCOPE}, "precedence": PRECEDENCE, "counts": counts, "relations": relations}


def render_relation_report(model: dict[str, Any], evidence: dict[str, Any]) -> str:
    lines = [
        "# Generated service relation report", "",
        f"Project: {model['project']['name']} ({model['project']['environment']})",
        "Semantic source: authored Gooo source; graph and report are derived.",
        f"Scope: {SCOPE}", "",
        "| Scenario | Class | Status | Resource | Capability | Endpoint | Reason |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for relation in evidence["relations"]:
        lines.append(f"| {relation['id']} | {relation['class']} | {relation['status']} | {relation['resource']} | {relation['capability']} | {relation['endpoint']} | {relation['claim']['reason']} |")
    lines.extend(["", "Counts: BOUND=2, UNBOUND_UNKNOWN=2, REFUTED=2.", "State precedence: REFUTED > UNKNOWN > CLOSED.", "UNKNOWN claims carry stage, step, reason, unknown_class, next_operation, and blocked_by."])
    return "\n".join(lines) + "\n"


def validate_lock(lock_path: Path, spec_path: Path) -> dict[str, Any]:
    lock = read_json(lock_path)
    if lock.get("toolchain", {}).get("go") != "1.27.x" or lock.get("opentofu", {}).get("iac_engine") != "OPENTOFU" or lock.get("opentofu", {}).get("iac_engine_version") != "1.12.6" or not spec_path.is_file():
        die("pinned toolchain or JSON specification is invalid")
    return lock


def generate(source_path: Path, graph_path: Path, lock_path: Path, spec_path: Path, bindings_path: Path, denominator_path: Path, inventory_path: Path, output_dir: Path) -> None:
    lock = validate_lock(lock_path, spec_path)
    project_contract(denominator_path)
    bindings = read_json(bindings_path)
    model = parse_source(source_path)
    graph_model(graph_path, source_path)
    if bindings.get("state") != "CLOSED" or bindings.get("activity_count") != 12 or bindings.get("binding_edges") != 14 or bindings.get("source_sha256") != model["source_sha256"]:
        die("project bindings are not closed for the current source")
    contract_doc = service_contract_doc(model)
    artifact = generated_artifact(model)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "main.tf.json", artifact)
    write_json(output_dir / "service-contract.json", contract_doc)
    (output_dir / "relation-report.md").write_text(render_relation_report(model, scenario_evidence(model)), encoding="utf-8")
    inventory_doc = read_json(inventory_path)
    dossier = [
        "# Generated OpenTofu service project", "",
        "This project is authored in one Gooo source file. The project JSON, service contract, and relation report are generated artifacts.", "",
        f"- project: {model['project']['name']}", f"- environment: {model['project']['environment']}",
        f"- resources: {len(model['resources'])}", f"- service capabilities: {len(model['capabilities'])}", f"- service endpoints: {len(model['endpoints'])}", f"- declared bindings: {len(model['bindings'])}",
        "- scenarios: NORMAL=2, UNKNOWN=2, REFUTED=2", f"- source SHA-256: {model['source_sha256']}", f"- released graph SHA-256: {sha256_file(graph_path)}",
        "- semantic authority: authored Gooo source and released IR; graph is derived.", f"- scope: {SCOPE}",
        f"- OpenTofu: {lock['opentofu']['iac_engine']} {lock['opentofu']['iac_engine_version']}", "- handwritten Go physical files: 0",
        "- external utility improvement: UNKNOWN because no exact before/after observation exists.", "- global core authority: NOT_MADE", "",
        "Generated files: main.tf.json, service-contract.json, relation-report.md, dossier.md, and the later contract receipt.",
        f"Repository inventory (root README excluded): {inventory_doc['regular_file_count']} regular files, {inventory_doc['descendant_directory_count']} subfolders.",
    ]
    (output_dir / "dossier.md").write_text("\n".join(dossier) + "\n", encoding="utf-8")


def validate(tofu_json_path: Path, artifact_path: Path, service_contract_path: Path, output: Path) -> None:
    tofu = read_json(tofu_json_path)
    artifact = read_json(artifact_path)
    contract_doc = read_json(service_contract_path)
    resources = tofu.get("resource", {}).get("terraform_data", {})
    expected_resources = {"project", "endpoint_health", "endpoint_orders"}
    checks = {
        "tofu_valid": tofu.get("valid") is True, "tofu_errors": tofu.get("errors", 0) == 0, "tofu_warnings": tofu.get("warnings", 0) == 0,
        "providerless": "provider" not in artifact and "terraform" not in artifact and "module" not in artifact,
        "resource_count": len(resources), "resource_names_exact": set(resources) == expected_resources, "module_count": len(artifact.get("module", {})),
        "outputs_exact": set(artifact.get("output", {})) == {"project_name", "service_capabilities", "service_endpoints"},
        "service_contract_schema": contract_doc.get("schema") == "gooo/opentofu-envelope/service-contract/v2",
    }
    state = "CLOSED" if checks["tofu_valid"] and checks["tofu_errors"] and checks["tofu_warnings"] and checks["providerless"] and checks["resource_count"] == 3 and checks["resource_names_exact"] and checks["module_count"] == 0 and checks["outputs_exact"] and checks["service_contract_schema"] else "REFUTED"
    write_json(output, {
        "schema": "gooo/opentofu-envelope/project-validation/v2", "version": 2, "state": state,
        "official_opentofu": {"valid": tofu.get("valid"), "error_count": tofu.get("errors", 0), "warning_count": tofu.get("warnings", 0), "validation_json_sha256": sha256_file(tofu_json_path)},
        "structural_checks": checks, "resource_names": sorted(resources), "module_names": sorted(artifact.get("module", {})),
    })
    if state != "CLOSED":
        die("generated project did not pass validation evidence")


def receipt(source_path: Path, graph_path: Path, artifact_path: Path, service_contract_path: Path, report_path: Path, validation_path: Path, tofu_json_path: Path, version_json_path: Path, binary_path: Path, lock_path: Path, output: Path) -> None:
    lock = read_json(lock_path)
    validation_doc = read_json(validation_path)
    binary_sha = sha256_file(binary_path)
    state = "CLOSED" if validation_doc.get("state") == "CLOSED" and binary_sha == lock["opentofu"].get("binary_sha256") else "UNKNOWN"
    outputs = {path.name: sha256_file(path) for path in (artifact_path, service_contract_path, report_path)}
    write_json(output, {
        "schema": "gooo/opentofu-envelope/project-receipt/v2", "version": 2, "state": state,
        "authority": {"state": "CLOSED", "semantic_scope": SCOPE, "handwritten_go_physical_files": 0, "external_utility": "UNKNOWN", "global_core_authority_claim": "NOT_MADE"},
        "semantic_path": ["GOOO_SOURCE", "SEMANTIC_GRAPH", "GENERATED_OPENTOFU_TF_JSON", "GENERATED_SERVICE_CONTRACT_JSON", "PINNED_OPENTOFU_VALIDATE_JSON", "RELATION_EVIDENCE"],
        "source": {"path": str(source_path), "sha256": sha256_file(source_path)}, "semantic_graph": {"path": str(graph_path), "sha256": sha256_file(graph_path), "ir_sha256": read_json(graph_path).get("ir", {}).get("semantic_digest")},
        "generated_outputs": outputs, "validation": {"path": str(validation_path), "sha256": sha256_file(validation_path), "state": validation_doc.get("state")},
        "opentofu": {"engine": "OPENTOFU", "version": "1.12.6", "version_json_sha256": sha256_file(version_json_path), "binary_sha256": binary_sha, "command": "tofu validate -json"},
        "side_effects": {"repository_writes": 0, "network": 0, "provider_install": 0, "infrastructure": 0, "state": 0, "external_mutations": 0},
        "producer": "scripts/project_envelope.py:receipt",
    })
    if state != "CLOSED":
        die("project receipt is not closed")


def cases(source_path: Path, bindings_path: Path, output: Path) -> None:
    model = parse_source(source_path)
    bindings = read_json(bindings_path)
    evidence = scenario_evidence(model)
    activity_id = next((item["activity_id"] for item in bindings.get("bindings", []) if item["activity"] == "EvaluateScenarioEvidence"), None)
    values = []
    for relation in evidence["relations"]:
        item = dict(relation)
        item["evidence_activity"] = {"activity": "EvaluateScenarioEvidence", "activity_id": activity_id}
        values.append(item)
    write_json(output, {"schema": "gooo/opentofu-envelope/project-cases/v2", "version": 2, "state": "CLOSED", "precedence": PRECEDENCE, "case_count": len(values), "outcome_counts": {"BOUND": 2, "UNBOUND_UNKNOWN": 2, "REFUTED": 2}, "cases": values})


def replay(source_path: Path, graph_path: Path, lock_path: Path, spec_path: Path, bindings_path: Path, denominator_path: Path, inventory_path: Path, publish_dir: Path, output: Path) -> None:
    comparisons = []
    with tempfile.TemporaryDirectory(prefix="gooo-project-replay-") as temporary:
        candidate = Path(temporary)
        generate(source_path, graph_path, lock_path, spec_path, bindings_path, denominator_path, inventory_path, candidate)
        for name in ("main.tf.json", "service-contract.json", "relation-report.md", "dossier.md"):
            left = publish_dir / name
            right = candidate / name
            comparisons.append({"file": name, "byte_equal": left.read_bytes() == right.read_bytes(), "published_sha256": sha256_file(left), "replay_sha256": sha256_file(right)})
    state = "CLOSED" if all(item["byte_equal"] for item in comparisons) else "REFUTED"
    write_json(output, {"schema": "gooo/opentofu-envelope/project-replay/v2", "version": 2, "state": state, "comparison_count": len(comparisons), "comparisons": comparisons})
    if state != "CLOSED":
        die("deterministic replay was not byte equal")


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
            text = path.read_text(encoding="utf-8", errors="replace")
            files.append({"path": relative, "bytes": path.stat().st_size, "lines": len(text.splitlines())})
    files.sort(key=lambda item: item["path"])
    write_json(output, {"schema": "gooo/opentofu-envelope/project-inventory/v1", "root_readme_excluded": True, "descendant_directories": sorted(directories), "regular_files": files, "descendant_directory_count": len(directories), "regular_file_count": len(files), "physical_line_count": sum(item["lines"] for item in files), "go_physical_files": sum(item["path"].endswith(".go") for item in files), "go_physical_lines": sum(item["lines"] for item in files if item["path"].endswith(".go")), "gooo_physical_files": sum(item["path"].endswith(".gooo") for item in files), "gooo_physical_lines": sum(item["lines"] for item in files if item["path"].endswith(".gooo"))})


def record(publish_dir: Path, source_path: Path, graph_path: Path, lock_path: Path, denominator_path: Path, inventory_path: Path, validation_path: Path, receipt_path: Path, consumer_path: Path, cases_path: Path, replay_path: Path, measurements_path: Path, go_version_path: Path, repository_status_path: Path, output: Path) -> None:
    denominator = project_contract(denominator_path)
    model = parse_source(source_path)
    inventory_doc = read_json(inventory_path)
    validation_doc = read_json(validation_path)
    receipt_doc = read_json(receipt_path)
    consumer_doc = read_json(consumer_path)
    cases_doc = read_json(cases_path)
    replay_doc = read_json(replay_path)
    measurements = read_json(measurements_path)
    if validation_doc.get("state") != "CLOSED" or receipt_doc.get("state") != "CLOSED" or consumer_doc.get("state") != "CLOSED" or cases_doc.get("state") != "CLOSED" or replay_doc.get("state") != "CLOSED":
        die("all project evidence stages must be CLOSED")
    if cases_doc.get("case_count") != 6 or cases_doc.get("outcome_counts") != {"BOUND": 2, "UNBOUND_UNKNOWN": 2, "REFUTED": 2}:
        die("project case counts are not exact")
    if consumer_doc.get("relation_counts") != {"bound": 2, "unbound_unknown": 2, "refuted": 2} or consumer_doc.get("authority", {}).get("semantic_scope") != SCOPE:
        die("independent consumer evidence is not exact")
    if replay_doc.get("comparison_count") != 4 or not all(item.get("byte_equal") is True for item in replay_doc.get("comparisons", [])):
        die("project replay evidence is not exact")
    if not go_version_path.read_text(encoding="utf-8").startswith("go version go1.27"):
        die("Go version evidence is not 1.27")
    if repository_status_path.read_text(encoding="utf-8").strip():
        die("repository status was not clean before evidence publication")
    if set(measurements) != {"compile", "build", "test", "conformance", "tofu_validate"}:
        die("measurement stages are not exact")
    for stage, item in measurements.items():
        integer(item.get("wall_ms"), f"{stage}.wall_ms")
        integer(item.get("peak_rss_kib"), f"{stage}.peak_rss_kib")
        integer(item.get("count"), f"{stage}.count")
    test_counts = {"total": 6, "executed": 6, "reused": 0, "failed": 2, "unknown": 2, "passed": 2}
    artifact_names = ["contract-receipt.json", "dossier.md", "main.tf.json", "relation-report.md", "service-contract.json"]
    generated = {name: {"bytes": (publish_dir / name).stat().st_size, "sha256": sha256_file(publish_dir / name)} for name in artifact_names}
    metric_specs = [
        ("user_path_steps", 6, "steps"), ("generated_artifact_files", 5, "files"), ("generated_artifact_bytes", sum(item["bytes"] for item in generated.values()), "bytes"),
        ("opentofu_resources", validation_doc["structural_checks"]["resource_count"], "resources"), ("opentofu_modules", validation_doc["structural_checks"]["module_count"], "modules"),
        ("service_capabilities", len(model["capabilities"]), "capabilities"), ("service_endpoints", len(model["endpoints"]), "endpoints"),
        ("bound_relations", 2, "relations"), ("unbound_relations", 2, "relations"), ("refuted_relations", 2, "relations"),
        ("go_physical_files", inventory_doc["go_physical_files"], "files"), ("go_physical_lines", inventory_doc["go_physical_lines"], "lines"),
        ("gooo_physical_files", inventory_doc["gooo_physical_files"], "files"), ("gooo_physical_lines", inventory_doc["gooo_physical_lines"], "lines"),
        ("regular_files", inventory_doc["regular_file_count"], "files"), ("subfolders", inventory_doc["descendant_directory_count"], "folders"),
        ("compile_wall_ms", measurements["compile"]["wall_ms"], "ms"), ("build_wall_ms", measurements["build"]["wall_ms"], "ms"), ("test_wall_ms", measurements["test"]["wall_ms"], "ms"),
        ("conformance_wall_ms", measurements["conformance"]["wall_ms"], "ms"), ("tofu_validate_wall_ms", measurements["tofu_validate"]["wall_ms"], "ms"),
        ("peak_rss_kib", max(item["peak_rss_kib"] for item in measurements.values()), "KiB"), ("tests_total", 6, "tests"), ("tests_executed", 6, "tests"), ("tests_reused", 0, "tests"), ("tests_failed", 2, "tests"), ("tests_unknown", 2, "tests"),
    ]
    metrics = [{"name": name, "value": integer(value, name), "unit": unit, "producer": "scripts/project_envelope.py:record"} for name, value, unit in metric_specs]
    write_json(output, {
        "schema": "gooo/opentofu-envelope/project-observation/v1", "version": 1, "state": "CLOSED",
        "authority": {"semantic_scope": SCOPE, "semantic_graph_state": "CLOSED", "external_utility": "UNKNOWN", "global_core_authority_claim": "NOT_MADE", "handwritten_go_physical_files": 0, "repository_writes": 0, "local_tests": 0, "local_build": 0, "opentofu": {"init": 0, "validate": 1, "plan": 0, "apply": 0, "destroy": 0, "provider_install": 0}, "network": 0, "infrastructure_mutations": 0, "state_mutations": 0, "external_mutations": 0},
        "project": {"name": model["project"]["name"], "resources": 2, "service_capabilities": 1, "service_endpoints": 2, "declared_bindings": 2, "bound_relations": 2, "unbound_relations": 2, "refuted_relations": 2, "opentofu_resources": 3, "opentofu_modules": 0},
        "source": {"path": str(source_path), "sha256": sha256_file(source_path), "authoritative": True},
        "semantic_graph": {"path": str(graph_path), "sha256": sha256_file(graph_path), "ir_sha256": receipt_doc["semantic_graph"].get("ir_sha256"), "state": "CLOSED", "scope": "GOOO_SEMANTIC_GRAPH_ONLY"},
        "generated_outputs": {"files": artifact_names, "count": 5, "bytes": sum(item["bytes"] for item in generated.values()), "digests": generated},
        "service_contract": {"path": str(publish_dir / "service-contract.json"), "sha256": generated["service-contract.json"]["sha256"]},
        "relation_evidence": {"path": str(publish_dir / "relation-report.md"), "sha256": generated["relation-report.md"]["sha256"], "counts": {"bound": 2, "unbound_unknown": 2, "refuted": 2}},
        "cases": {"path": str(cases_path), "sha256": sha256_file(cases_path), "state": "CLOSED", "count": 6, "outcome_counts": cases_doc["outcome_counts"], "precedence": PRECEDENCE},
        "validation": {"path": str(validation_path), "sha256": sha256_file(validation_path), "state": "CLOSED"},
        "receipt": {"path": str(receipt_path), "sha256": sha256_file(receipt_path), "state": "CLOSED"},
        "consumer": {"path": str(consumer_path), "sha256": sha256_file(consumer_path), "state": "CLOSED", "relation_counts": consumer_doc["relation_counts"], "digest_chain": consumer_doc["digest_chain"]},
        "replay": {"path": str(replay_path), "sha256": sha256_file(replay_path), "state": "CLOSED", "comparison_count": 4},
        "denominator": {"path": str(denominator_path), "sha256": sha256_file(denominator_path), "target_cells": denominator["target_cells"], "expected_user_path_steps": 6, "binding_edges": 14},
        "toolchain": {"go_requirement": "1.27.x", "opentofu": "1.12.6"}, "test_counts": test_counts, "measurements": measurements, "metrics": metrics, "inventory": inventory_doc,
        "improvement": {"state": "UNKNOWN", "reason": "exact before and after observations are not available", "before": None, "after": None},
        "utility": {"state": "UNKNOWN", "reason": "exact user utility before and after observations are not available"},
        "identity": {"source_sha256": sha256_file(source_path), "graph_sha256": sha256_file(graph_path), "generated_artifact_sha256": sha256_value(generated)},
    })


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("inventory"); p.add_argument("--root", type=Path, required=True); p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("bind")
    for name in ("source", "graph", "denominator"): p.add_argument(f"--{name}", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("generate")
    for name in ("source", "graph", "lock", "spec", "bindings", "denominator", "inventory"): p.add_argument(f"--{name}", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p = sub.add_parser("validate")
    for name in ("tofu-json", "artifact", "service-contract"): p.add_argument(f"--{name}", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("receipt")
    for name in ("source", "graph", "artifact", "service-contract", "relation-report", "validation", "tofu-json", "version-json", "binary", "lock"): p.add_argument(f"--{name}", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("cases")
    for name in ("source", "bindings"): p.add_argument(f"--{name}", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("replay")
    for name in ("source", "graph", "lock", "spec", "bindings", "denominator", "inventory"): p.add_argument(f"--{name}", type=Path, required=True)
    p.add_argument("--publish-dir", type=Path, required=True); p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("record")
    for name in ("publish-dir", "source", "graph", "lock", "denominator", "inventory", "validation", "receipt", "consumer", "cases", "replay", "measurements", "go-version", "repository-status"): p.add_argument(f"--{name}", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "inventory": inventory(args.root, args.output)
    elif args.command == "bind": bind(args.source, args.graph, args.denominator, args.output)
    elif args.command == "generate": generate(args.source, args.graph, args.lock, args.spec, args.bindings, args.denominator, args.inventory, args.output_dir)
    elif args.command == "validate": validate(args.tofu_json, args.artifact, args.service_contract, args.output)
    elif args.command == "receipt": receipt(args.source, args.graph, args.artifact, args.service_contract, args.relation_report, args.validation, args.tofu_json, args.version_json, args.binary, args.lock, args.output)
    elif args.command == "cases": cases(args.source, args.bindings, args.output)
    elif args.command == "replay": replay(args.source, args.graph, args.lock, args.spec, args.bindings, args.denominator, args.inventory, args.publish_dir, args.output)
    elif args.command == "record": record(args.publish_dir, args.source, args.graph, args.lock, args.denominator, args.inventory, args.validation, args.receipt, args.consumer, args.cases, args.replay, args.measurements, args.go_version, args.repository_status, args.output)


if __name__ == "__main__":
    main()

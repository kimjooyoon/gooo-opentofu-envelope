#!/usr/bin/env python3
"""Independently verify the generated v0.2.0 service-project evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SCOPE = "GENERATED_OPENTOFU_SERVICE_PROJECT_ONLY"
PRECEDENCE = ["REFUTED", "UNKNOWN", "CLOSED"]
UNKNOWN_FIELDS = {"stage", "step", "reason", "unknown_class", "next_operation", "blocked_by"}


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
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_value(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def parse_source(path: Path) -> dict[str, Any]:
    project = None
    resources: list[dict[str, str]] = []
    capabilities: list[dict[str, str]] = []
    endpoints: list[dict[str, str]] = []
    bindings: list[dict[str, str]] = []
    scenarios: list[dict[str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        match = re.match(r"// @(project|resource|capability|endpoint|binding|scenario) (.*)$", line)
        if not match:
            continue
        kind, rest = match.groups()
        fields = dict(re.findall(r"([A-Za-z_][A-Za-z0-9_]*)=([^\s]+)", rest))
        if len(fields) != len(rest.split()):
            die(f"malformed source directive: {kind}")
        if kind == "project":
            project = fields
        elif kind == "resource":
            resources.append(fields)
        elif kind == "capability":
            capabilities.append(fields)
        elif kind == "endpoint":
            endpoints.append(fields)
        elif kind == "binding":
            bindings.append(fields)
        else:
            scenarios.append(fields)
    if project != {"name": "checkout-api", "environment": "production"} or len(resources) != 2 or len(capabilities) != 1 or len(endpoints) != 2 or len(bindings) != 2 or len(scenarios) != 6:
        die("independent source parse did not find the fixed project")
    if {item["class"] for item in scenarios} != {"NORMAL", "UNKNOWN", "REFUTED"} or sum(item["class"] == "NORMAL" for item in scenarios) != 2 or sum(item["class"] == "UNKNOWN" for item in scenarios) != 2 or sum(item["class"] == "REFUTED" for item in scenarios) != 2:
        die("independent source parse found incorrect scenario classes")
    return {"project": project, "resources": resources, "capabilities": capabilities, "endpoints": endpoints, "bindings": bindings, "scenarios": scenarios, "source_sha256": sha256_file(path)}


def expected_relations(model: dict[str, Any]) -> list[dict[str, Any]]:
    binding_set = {(item["resource"], item["capability"], item["endpoint"]) for item in model["bindings"]}
    endpoint_names = {item["name"] for item in model["endpoints"]}
    result = []
    for scenario in model["scenarios"]:
        item = dict(scenario)
        key = (scenario["resource"], scenario["capability"], scenario["endpoint"])
        if scenario["class"] == "NORMAL":
            if key not in binding_set or scenario["endpoint"] not in endpoint_names:
                die(f"independent NORMAL relation is unbound: {scenario['id']}")
            item["status"] = "BOUND"
            item["claim"] = {"state": "CLOSED", "stage": "CONFORMANCE", "step": "VERIFY_BOUND_SERVICE_RELATION", "reason": "DECLARED_RESOURCE_CAPABILITY_ENDPOINT_BINDING", "unknown_class": None, "next_operation": None, "blocked_by": []}
        elif scenario["class"] == "UNKNOWN":
            item["status"] = "UNBOUND_UNKNOWN"
            item["claim"] = {"state": "UNKNOWN", "stage": "BINDING", "step": "BIND_SERVICE_CAPABILITY_ENDPOINT", "reason": scenario.get("reason", "MISSING_SERVICE_BINDING"), "unknown_class": "DIRECT_MISSING", "next_operation": "CAPTURE_MISSING_SERVICE_BINDING", "blocked_by": ["SERVICE_CAPABILITY_ENDPOINT_BINDING"]}
        else:
            item["status"] = "REFUTED"
            item["claim"] = {"state": "REFUTED", "stage": "CONFORMANCE", "step": "REJECT_CONTRADICTORY_RESOURCE_ENDPOINT_MAPPING", "reason": scenario.get("reason", "CONTRADICTORY_RESOURCE_ENDPOINT_MAPPING"), "unknown_class": None, "next_operation": None, "blocked_by": []}
        result.append(item)
    return result


def verify(source_path: Path, graph_path: Path, main_tf_path: Path, contract_path: Path, report_path: Path, validation_path: Path, tofu_json_path: Path, output: Path) -> None:
    model = parse_source(source_path)
    graph = read_json(graph_path)
    contract_doc = read_json(contract_path)
    artifact = read_json(main_tf_path)
    validation = read_json(validation_path)
    tofu = read_json(tofu_json_path)
    source_sha = model["source_sha256"]
    if graph.get("schema_version") != "gooo-graph/v1" or graph.get("source_digest") != source_sha:
        die("independent graph source digest check failed")
    if graph.get("ir", {}).get("status") != "available" or graph.get("authorities", {}).get(".gooo") != "authoritative" or graph.get("authorities", {}).get("ir") != "authoritative" or graph.get("authorities", {}).get("graph") != "derived":
        die("independent graph authority check failed")
    if len([node for node in graph.get("nodes", []) if node.get("kind") == "Activity"]) != 12 or len([node for node in graph.get("nodes", []) if node.get("kind") == "Entity"]) != 15:
        die("independent graph cardinality check failed")
    expected_contract = {"schema": "gooo/opentofu-envelope/service-contract/v2", "version": 2, "source_sha256": source_sha, "project": model["project"], "resources": model["resources"], "capabilities": model["capabilities"], "endpoints": model["endpoints"], "bindings": model["bindings"], "scenarios": model["scenarios"]}
    actual_contract = {key: contract_doc.get(key) for key in expected_contract}
    if actual_contract != expected_contract or contract_doc.get("authority", {}).get("semantic_scope") != SCOPE or contract_doc.get("authority", {}).get("handwritten_go_physical_files") != 0:
        die("independent service contract recomputation failed")
    resources = artifact.get("resource", {}).get("terraform_data", {})
    if set(resources) != {"project", "endpoint_health", "endpoint_orders"} or len(resources) != 3 or set(artifact.get("output", {})) != {"project_name", "service_capabilities", "service_endpoints"} or any(key in artifact for key in ("provider", "terraform", "module")):
        die("independent generated OpenTofu shape check failed")
    if validation.get("schema") != "gooo/opentofu-envelope/project-validation/v2" or validation.get("state") != "CLOSED" or validation.get("official_opentofu", {}).get("valid") is not True or validation.get("structural_checks", {}).get("resource_count") != 3 or validation.get("structural_checks", {}).get("module_count") != 0 or validation.get("structural_checks", {}).get("providerless") is not True:
        die("independent OpenTofu validation check failed")
    if tofu.get("valid") is not True or tofu.get("errors", 0) != 0 or tofu.get("warnings", 0) != 0:
        die("independent validate-json check failed")
    relations = expected_relations(model)
    counts = {"bound": sum(item["status"] == "BOUND" for item in relations), "unbound_unknown": sum(item["status"] == "UNBOUND_UNKNOWN" for item in relations), "refuted": sum(item["status"] == "REFUTED" for item in relations)}
    if counts != {"bound": 2, "unbound_unknown": 2, "refuted": 2}:
        die("independent relation counts are not 2/2/2")
    for relation in relations:
        claim = relation["claim"]
        if relation["status"] == "UNBOUND_UNKNOWN" and set(claim) - {"state"} != UNKNOWN_FIELDS:
            die(f"independent UNKNOWN six-field check failed for {relation['id']}")
        marker = f"| {relation['id']} | {relation['class']} | {relation['status']} |"
        if marker not in report_path.read_text(encoding="utf-8"):
            die(f"relation report does not contain {relation['id']}")
    relation_digest = sha256_value(relations)
    output_hashes = {"main.tf.json": sha256_file(main_tf_path), "service-contract.json": sha256_file(contract_path), "relation-report.md": sha256_file(report_path)}
    digest_chain = {
        "source_sha256": source_sha,
        "semantic_graph_sha256": sha256_file(graph_path),
        "ir_sha256": graph["ir"]["semantic_digest"],
        "generated_files": output_hashes,
        "tofu_validation": {"tofu_validate_json_sha256": sha256_file(tofu_json_path), "validation_evidence_sha256": sha256_file(validation_path), "valid": True},
        "relation_evidence": {"report_sha256": output_hashes["relation-report.md"], "relation_evidence_sha256": relation_digest},
        "order": ["SOURCE", "SEMANTIC_GRAPH", "GENERATED_FILES", "PINNED_OPENTOFU_VALIDATE_JSON", "RELATION_EVIDENCE"],
    }
    write_json(output, {
        "schema": "gooo/opentofu-envelope/independent-consumer/v1", "version": 1, "state": "CLOSED",
        "authority": {"semantic_scope": SCOPE, "source": "INDEPENDENT_RECOMPUTATION", "handwritten_go_physical_files": 0, "external_utility": "UNKNOWN", "global_core_authority_claim": "NOT_MADE"},
        "project": {"name": model["project"]["name"], "resources": 2, "service_capabilities": 1, "service_endpoints": 2},
        "relation_counts": counts, "relation_evidence": {"state": "CLOSED", "relations": relations, "precedence": PRECEDENCE},
        "digest_chain": digest_chain, "generated_outputs": output_hashes,
    })


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("source", "graph", "main-tf-json", "service-contract", "relation-report", "validation", "tofu-json"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verify(args.source, args.graph, args.main_tf_json, args.service_contract, args.relation_report, args.validation, args.tofu_json, args.output)


if __name__ == "__main__":
    main()

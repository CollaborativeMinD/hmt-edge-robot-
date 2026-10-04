"""validate: structure interface."""

from __future__ import annotations

import ast
import json

import jsonschema
from contracts_export import contract_models, export
from policy_inventory import fold_measurements
from rdflib import Graph, Namespace
from validate_base import ROOT


def structural_checks() -> dict:
    measurements = fold_measurements(ROOT)
    if any(r["module_status"] != "PASS" or r["function_status"] != "PASS" for r in measurements):
        raise ValueError("PROMOTED_FOLD7_BOUNDS_EXCEEDED")
    lengths = []
    for directory in ("src", "tests", "tools", "notebooks"):
        for path in (ROOT / directory).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    size = (node.end_lineno or node.lineno) - min([node.lineno] + [d.lineno for d in node.decorator_list]) + 1
                    lengths.append(
                        {
                            "path": str(path.relative_to(ROOT)),
                            "function": node.name,
                            "physical_lines": size,
                        }
                    )
                    if size > 60:
                        raise ValueError(f"FUNCTION_LINE_CAP: {path.name}:{node.name}:{size}")
    requirements = json.loads((ROOT / "docs/requirements.json").read_text())["requirements"]
    appliance = json.loads((ROOT / "docs/cd/appliance-requirements.json").read_text())
    requirements += appliance["requirements"]
    if len({r["id"] for r in requirements}) != len(requirements):
        raise ValueError("DUPLICATE_REQUIREMENT")
    for requirement in requirements:
        for source in requirement["source"]:
            if not (ROOT / source).is_file():
                raise ValueError("REQUIREMENT_SOURCE_MISSING")
        for test in requirement["tests"]:
            file, function = test.split("::")
            if f"def {function}(" not in (ROOT / file).read_text():
                raise ValueError("REQUIREMENT_TEST_MISSING")
    ontology_checks()
    trace = json.loads((ROOT / "docs/implementation_traceability.json").read_text())
    trace += appliance["traceability"]
    if {r["req_id"] for r in trace} != {r["id"] for r in requirements}:
        raise ValueError("IMPLEMENTATION_TRACE_INCOMPLETE")
    fields = {
        "req_id",
        "module_id",
        "runtime_partition",
        "source_path",
        "contract_id",
        "safety_constraint_id",
        "test_id",
        "analysis_id",
        "evidence_id",
    }
    if any(set(r) != fields or not all(r.values()) for r in trace):
        raise ValueError("IMPLEMENTATION_TRACE_FIELDS_INVALID")
    handoff = json.loads((ROOT / "docs/machine_handoff.json").read_text())
    schema = json.loads((ROOT / "docs/handoff.schema.json").read_text())
    jsonschema.Draft202012Validator(schema).validate(handoff)
    return {
        "status": "PASS",
        "requirements": len(requirements),
        "functions": lengths,
        "max_physical_lines": max(r["physical_lines"] for r in lengths),
    }

def ontology_checks() -> None:
    export(ROOT)
    bindings = json.loads((ROOT / "docs/field_bindings.json").read_text())
    expected = {
        (name, field) for name, model in contract_models().items() for field in model.model_fields
    }
    actual = {(b["contract"], b["field"]) for b in bindings}
    if expected != actual or len(actual) != len(bindings):
        raise ValueError("FIELD_BINDING_INCOMPLETE")
    baseline = json.loads((ROOT / "docs/source_provenance.json").read_text())
    classes = set(baseline["upstream_subtype_classes"])
    if any(b["subtype"] not in classes for b in bindings):
        raise ValueError("ONTOLOGY_SUBTYPE_UNGOVERNED")
    graph = Graph().parse(ROOT / "docs/field_bindings.ttl", format="turtle")
    forge = Namespace("https://terminal-state.systems/ontology/forge#")
    if len(list(graph.triples((None, forge.hard_binds_to_subtype, None)))) != len(bindings):
        raise ValueError("RDF_BINDING_DIVERGENCE")

"""Export executable contract schemas and explicit domain ontology bindings."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from hmt_edge_robot import api, contracts, geometry
from hmt_edge_robot.assurance import contracts as assurance_contracts
from hmt_edge_robot.assurance import routes as assurance_routes


def contract_models() -> dict:
    models = {}
    for module in (contracts, geometry, api, assurance_contracts, assurance_routes):
        for name, value in inspect.getmembers(module, inspect.isclass):
            if issubclass(value, contracts.Contract) and value is not contracts.Contract:
                models[name] = value
    return models


def semantic_type(model: str, field: str) -> tuple[str, str]:
    if field == "proof":
        return "TrustRootField", "Provisioned identity credential; excluded from evidence payloads"
    if field == "question":
        return "DomainDescriptorField", "Untrusted resident question bounded by its wire contract"
    if field.endswith("hash"):
        return "TelemetryIntegrityField", "Integrity receipt for the declared artifact or payload"
    if field.endswith("_refs") or field == "evidence_id":
        return "EvidenceReferenceField", "References to validated evidence records"
    if field.endswith("_id"):
        return "ArtifactIdentifierField", "Identifier scoped by its declaring domain contract"
    if field in ("state", "pace_lane", "action", "origin"):
        return (
            "RuntimeStateStatusField",
            "Closed runtime state, lane, or advisory action vocabulary",
        )
    if field in ("decision", "admitted", "data_valid", "verdict", "complete", "dry_run"):
        return "ValidationStatusField", "Admission or validity result with declared bounds"
    if field == "rejection_reason" or field == "explanation":
        return "DomainDescriptorField", "Domain-specific reason or advisory explanation"
    if field in ("monotonic_seq", "observed_at", "issued_at", "expires_at"):
        return "TelemetryIntegrityField", "Sequence or clock-domain freshness constraint"
    if model == "Policy" or field == "epochs" or field.endswith("epoch"):
        return "ControlConstraintField", "Named operator-selected supervisory policy constraint"
    if "temp" in field:
        return (
            "ThermalMetricField",
            "Observed or accepted temperature; invalid observations remain gaps",
        )
    if "voltage" in field:
        return "PowerMetricField", "Observed electrical quantity with finite units"
    if field in ("position_mm", "target_mm", "angle_deg", "human_distance_m"):
        return "MechanicalMetricField", "Measured or planned geometric quantity in declared units"
    return "PhysicalBoundField", "Typed domain quantity bounded by the declaring contract"


def export(root: Path) -> None:
    models = contract_models()
    schemas = {name: model.model_json_schema() for name, model in models.items()}
    path = root / "docs"
    path.mkdir(exist_ok=True)
    (path / "contracts.schema.json").write_text(json.dumps(schemas, indent=2) + "\n")
    bindings = []
    for name, model in models.items():
        for field in model.model_fields:
            subtype, basis = semantic_type(name, field)
            bindings.append({"contract": name, "field": field, "subtype": subtype, "basis": basis})
    (path / "field_bindings.json").write_text(json.dumps(bindings, indent=2) + "\n")
    lines = [
        "@prefix edge: <https://collaborativemind.example/hmt-edge#> .",
        "@prefix forge: <https://terminal-state.systems/ontology/forge#> .",
    ]
    for binding in bindings:
        term = binding["contract"] + "_" + binding["field"]
        lines.append(
            f"edge:{term} a forge:CanonicalField ; forge:hard_binds_to_subtype forge:{binding['subtype']} ; "
            f"forge:phase_4_binding_basis {json.dumps(binding['basis'])} ."
        )
    (path / "field_bindings.ttl").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    export(Path(__file__).resolve().parents[1])

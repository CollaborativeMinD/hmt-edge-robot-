"""Scanner, installed-lock, and signed-statement rejection cases."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from artifact_evidence import provenance, scans
from artifact_support import COMMIT, fixture, signature


@pytest.mark.parametrize("fault", ["coverage", "critical", "high", "unknown", "secret", "paid",
    "stop", "replay", "missing_package", "lock", "sbom", "base"])
def test_scan_and_runtime_contradictions_are_rejected(tmp_path: Path, fault: str) -> None:
    directory = fixture(tmp_path)
    sbom = json.loads((directory / "sbom.spdx.json").read_text())
    scan = json.loads((directory / "vulnerabilities.json").read_text())
    probe = json.loads((directory / "container.json").read_text())
    if fault == "coverage":
        scan["Results"] = []
    elif fault in ("critical", "high", "unknown"):
        scan["Results"][0]["Vulnerabilities"] = [{"Severity": fault.upper()}]
    elif fault == "secret":
        scan["Results"][0]["Secrets"] = [{"RuleID": "private-key"}]
    elif fault == "paid":
        probe["paid_calls"] = 1
    elif fault == "stop":
        probe["resident_stopped"] = False
    elif fault == "replay":
        probe["replayed"] = 2
    elif fault == "missing_package":
        probe["packages"] = {}
    elif fault == "lock":
        probe["packages"]["alien"] = "1.0.0"
    elif fault == "sbom":
        sbom["packages"][0]["versionInfo"] = "0.0.0"
    else:
        scan["ArtifactType"] = "repository"
    with pytest.raises(ValueError):
        scans(sbom, scan, probe, (tmp_path / "uv.lock").read_bytes())


def test_low_medium_findings_remain_recorded(tmp_path: Path) -> None:
    directory = fixture(tmp_path)
    scan = json.loads((directory / "vulnerabilities.json").read_text())
    scan["Results"][0]["Vulnerabilities"] = [{"Severity": "LOW"}, {"Severity": "MEDIUM"}]
    scans(json.loads((directory / "sbom.spdx.json").read_text()), scan,
          json.loads((directory / "container.json").read_text()), (tmp_path / "uv.lock").read_bytes())


@pytest.mark.parametrize("fault", ["absent", "subject", "source", "workflow", "predicate"])
def test_provenance_must_bind_exact_subject_source_and_workflow(tmp_path: Path, fault: str) -> None:
    directory = fixture(tmp_path)
    value = signature(directory / "image.oci.tar")
    statement = value[0]["verificationResult"]["statement"]
    archive_hash = statement["subject"][0]["digest"]["sha256"]
    if fault == "absent":
        value = []
    elif fault == "subject":
        statement["subject"] = []
    elif fault == "source":
        statement["predicate"]["buildDefinition"]["resolvedDependencies"] = []
    elif fault == "workflow":
        statement["predicate"]["buildDefinition"]["externalParameters"]["workflow"]["path"] = "invalid"
    else:
        statement["predicateType"] = "invalid"
    with pytest.raises(ValueError):
        provenance(value, archive_hash, COMMIT)

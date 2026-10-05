"""Owner acceptance cannot waive a changed identity, severity, secret or host asset."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from artifact_preflight import assess, main
from artifact_support import COMMIT, fixture
from artifact_waivers import admit, validate

POLICY = Path(__file__).resolve().parents[1] / "policy/artifact_vulnerability_waiver.json"


def policy() -> dict:
    return json.loads(POLICY.read_text())


def scan() -> dict:
    return {"ArtifactType": "container_image", "Metadata": {"OS": {"Family": "debian", "Name": "13.7"},
        "ImageConfig": {"architecture": "arm64", "os": "linux"}}, "Results": [{"Class": "os-pkgs",
        "Vulnerabilities": [{"VulnerabilityID": "TEMP-1147318-639065", "PkgName": "liblzma5",
            "InstalledVersion": "5.8.1-1+deb13u1", "Severity": "UNKNOWN"}]}]}


def test_exact_owner_acceptance_preserves_raw_findings() -> None:
    value = scan()
    before = copy.deepcopy(value)
    accepted = admit(value, policy())
    assert accepted[0]["disposition"] == "OWNER_ACCEPTED_RISK_NOT_FIXED"
    assert accepted[0]["approved_by"] == "repository_owner" and value == before
    with pytest.raises(ValueError, match="NOT_ADMITTED"):
        admit(value)


@pytest.mark.parametrize("field,value", [("VulnerabilityID", "another"), ("PkgName", "another"),
    ("InstalledVersion", "5.8.4-1"), ("Severity", "HIGH"), ("Severity", "CRITICAL"), ("FixedVersion", "5.8.4-1")])
def test_changed_or_fixed_finding_cannot_reuse_acceptance(field: str, value: str) -> None:
    report = scan()
    report["Results"][0]["Vulnerabilities"][0][field] = value
    with pytest.raises(ValueError, match="NOT_ADMITTED"):
        admit(report, policy())


@pytest.mark.parametrize("change", ["host", "architecture", "os", "class", "secret"])
def test_other_assets_and_secrets_still_fail(change: str) -> None:
    report = scan()
    if change == "host":
        report["ArtifactType"] = "filesystem"
    elif change == "architecture":
        report["Metadata"]["ImageConfig"]["architecture"] = "amd64"
    elif change == "os":
        report["Metadata"]["OS"]["Name"] = "14.1"
    elif change == "class":
        report["Results"][0]["Class"] = "lang-pkgs"
    else:
        report["Results"][0]["Secrets"] = [{"RuleID": "private-key"}]
    with pytest.raises(ValueError):
        admit(report, policy())


@pytest.mark.parametrize("change", ["schema", "scope", "owner", "rationale", "identity", "wildcard", "severity"])
def test_waiver_policy_cannot_expand_approval(change: str) -> None:
    value = policy()
    if change == "schema":
        value["schema_version"] = True
    elif change in {"scope", "rationale"}:
        value[change] = ""
    elif change == "owner":
        value["approved_by"] = "unapproved"
    elif change == "identity":
        value["exception"].pop("package")
    else:
        value["exception"]["package" if change == "wildcard" else "severity"] = "*" if change == "wildcard" else "HIGH"
    with pytest.raises(ValueError):
        validate(value)


def test_accepted_finding_and_policy_hash_are_bound_into_prequalification(tmp_path: Path) -> None:
    directory = fixture(tmp_path)
    path = directory / "vulnerabilities.json"
    value = json.loads(path.read_text())
    value["Metadata"].update(scan()["Metadata"])
    value["Results"][0].update(scan()["Results"][0])
    path.write_text(json.dumps(value))
    report = assess(tmp_path, COMMIT)
    assert len(report["vulnerability_exceptions"]) == 1
    assert report["inputs"]["policy/artifact_vulnerability_waiver.json"] == hashlib.sha256(POLICY.read_bytes()).hexdigest()
    assert main(tmp_path, COMMIT) == 0
    value["Results"][0]["Vulnerabilities"].append({"Severity": "HIGH"})
    path.write_text(json.dumps(value))
    assert main(tmp_path, COMMIT) == 1

"""Version-scoped owner risk acceptance; raw findings and host gates stay intact."""
from __future__ import annotations

from datetime import date


def validate(policy: dict) -> dict:
    if not isinstance(policy, dict) or set(policy) != {"schema_version", "scope", "approved_by", "approved_at", "approval_reference", "rationale", "exception"}:
        raise ValueError("RUNTIME_WAIVER_SCHEMA_INVALID")
    if type(policy["schema_version"]) is not int or policy["schema_version"] != 1 or policy["scope"] != "ARM64_RUNTIME_CONTAINER_ONLY":
        raise ValueError("RUNTIME_WAIVER_SCOPE_INVALID")
    if policy["approved_by"] != "repository_owner" or any(not isinstance(policy[k], str) or not policy[k].strip() for k in ("approved_at", "approval_reference", "rationale")):
        raise ValueError("RUNTIME_WAIVER_APPROVAL_MISSING")
    date.fromisoformat(policy["approved_at"])
    exception = policy["exception"]
    fields = {"vulnerability_id", "package", "installed_version", "severity", "os_family", "os_major", "architecture", "fix_available"}
    if not isinstance(exception, dict) or set(exception) != fields:
        raise ValueError("RUNTIME_WAIVER_IDENTITY_INVALID")
    if any(not isinstance(exception[k], str) or not exception[k] or "*" in exception[k] for k in fields - {"os_major", "fix_available"}):
        raise ValueError("RUNTIME_WAIVER_WILDCARD_FORBIDDEN")
    if exception["severity"] != "UNKNOWN" or exception["os_family"] != "debian" or type(exception["os_major"]) is not int or exception["os_major"] != 13 or exception["architecture"] != "arm64" or exception["fix_available"] is not False:
        raise ValueError("RUNTIME_WAIVER_AUTHORITY_WIDENED")
    return exception


def matches(scan: dict, result: dict, vulnerability: dict, exception: dict) -> bool:
    metadata = scan.get("Metadata", {})
    os = metadata.get("OS", {})
    image = metadata.get("ImageConfig", {})
    identity = {"vulnerability_id": vulnerability.get("VulnerabilityID"), "package": vulnerability.get("PkgName"),
        "installed_version": vulnerability.get("InstalledVersion"), "severity": vulnerability.get("Severity"),
        "os_family": os.get("Family"), "os_major": os.get("Name", "").split(".", 1)[0],
        "architecture": image.get("architecture"), "fix_available": bool(vulnerability.get("FixedVersion"))}
    expected = {**exception, "os_major": str(exception["os_major"])}
    return scan.get("ArtifactType") == "container_image" and result.get("Class") == "os-pkgs" and image.get("os") == "linux" and identity == expected


def admit(scan: dict, policy: dict | None = None) -> list[dict]:
    exception = validate(policy) if policy is not None else None
    accepted = []
    for result in scan["Results"]:
        if result.get("Secrets"):
            raise ValueError("IMAGE_SECRET_DETECTED")
        for vulnerability in result.get("Vulnerabilities") or []:
            if vulnerability.get("Severity") in ("LOW", "MEDIUM"):
                continue
            if exception is None or not matches(scan, result, vulnerability, exception):
                raise ValueError("VULNERABILITY_NOT_ADMITTED")
            if not accepted:
                accepted.append({**(policy or {}), "disposition": "OWNER_ACCEPTED_RISK_NOT_FIXED"})
    return accepted

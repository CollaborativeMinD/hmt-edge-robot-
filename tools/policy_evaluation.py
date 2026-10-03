"""Policy assessment gate: full adoption gaps remain explicit HOLD records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ci_admission import ROOT, confined, digest
from policy_inventory import fold_measurements, inventory, load_profile
from policy_pins import source_pins


def evaluate(root: Path) -> dict[str, Any]:
    profile = load_profile(root)
    policies = inventory(root, profile)
    for name, expected in profile.qualification_refs.items():
        if digest(confined(root, name)) != expected:
            raise ValueError("QUALIFICATION_DIGEST_MISMATCH")
    measurements = fold_measurements(root)
    if any(row["function_status"] != "PASS" for row in measurements):
        raise ValueError("HOLD_FUNCTION_CEILING_EXCEEDED")
    support = {"tools/policy_contracts.py", "tools/policy_inventory.py",
               "tools/policy_evaluation.py", "tools/ci_profiles.py", "tools/profile_witnesses.py",
               "tools/policy_pins.py", "tools/tool_qualification.py"}
    if any(row["module_status"] != "PASS" for row in measurements if row["path"] in support):
        raise ValueError("HOLD_SUPPORT_MODULE_CEILING_EXCEEDED")
    holds = [row for row in measurements if row["module_status"] == "HOLD"]
    return {"assessment_status": "PASS", "full_policy_adoption": "HOLD" if holds else "REVIEW_REQUIRED",
            "full_tool_admission": "HOLD", "docker_build": "HOLD", "deployment": "HOLD",
            "policy_profile_hash": digest(root / "policy/ci_support.json"),
            "policies": policies, "historical_source_pins": source_pins(root, profile.policy_sources), "fold_measurements": measurements, "hold_register": holds,
            "reason_codes": ["HOLD_FOLD7_CEILING_EXCEEDED"] if holds else [],
            "notification": "POLICY_ASSESSMENT_RECORDED", "alert": bool(holds)}


def main(root: Path = ROOT) -> int:
    try:
        report = evaluate(root)
    except (ValueError, OSError, TypeError, KeyError) as exc:
        report = {"assessment_status": "FAIL", "reason_codes": [str(exc)], "alert": True}
    destination = root / "evidence/ci/phase2/policy_evaluation.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n")
    temporary.replace(destination)
    print(json.dumps({k: report[k] for k in ("assessment_status", "reason_codes", "alert")}))
    if report["alert"]:
        print("::warning::Policy assessment has unresolved adoption gaps; inspect its HOLD register.")
    return 0 if report["assessment_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

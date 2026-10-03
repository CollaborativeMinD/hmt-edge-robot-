"""Promoted software policy gate; deployment and whole-tool authority remain held."""

from __future__ import annotations

import json
import tokenize
from pathlib import Path
from typing import Any

from ci_admission import ROOT, confined, digest
from policy_inventory import fold_measurements, inventory, load_profile
from policy_pins import source_pins
from policy_promotion import disposition_pins, load_promotion


def evaluate(root: Path) -> dict[str, Any]:
    profile = load_profile(root)
    policies = inventory(root, profile)
    for name, expected in profile.qualification_refs.items():
        if digest(confined(root, name)) != expected:
            raise ValueError("QUALIFICATION_DIGEST_MISMATCH")
    measurements = fold_measurements(root)
    if any(row["function_status"] != "PASS" for row in measurements):
        raise ValueError("HOLD_FUNCTION_CEILING_EXCEEDED")
    promotion = load_promotion(root, profile)
    if any(row["module_status"] != "PASS" for row in measurements):
        raise ValueError("MODULE_CEILING_EXCEEDED")
    pins = disposition_pins(source_pins(root, profile.policy_sources), promotion)
    for policy in policies:
        policy["adoption"] = "PROMOTED_SYSTEM_SOFTWARE_VALIDATION"
    holds = []
    return {"assessment_status": "PASS", "full_policy_adoption": "PROMOTED",
            "full_tool_admission": "HOLD", "docker_build": "HOLD", "deployment": "HOLD",
            "policy_profile_hash": digest(root / "policy/ci_support.json"),
            "policies": policies, "historical_source_pins": pins, "fold_measurements": measurements, "hold_register": holds,
            "promotion_hash": digest(root / "policy/promotion.json"),
            "scope": promotion.scope, "reason_codes": ["HUMAN_PROMOTION_VALIDATED", "FOLD7_BOUNDS_PASS"],
            "notification": "POLICY_ASSESSMENT_RECORDED", "alert": bool(holds)}


def main(root: Path = ROOT) -> int:
    try:
        report = evaluate(root)
    except (ValueError, OSError, TypeError, KeyError, SyntaxError, tokenize.TokenError) as exc:
        report = {"assessment_status": "FAIL", "reason_codes": [str(exc)], "alert": True,
                  "full_policy_adoption": "HOLD", "full_tool_admission": "HOLD",
                  "docker_build": "HOLD", "deployment": "HOLD"}
    destination = root / "evidence/ci/phase2/policy_evaluation.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n")
    temporary.replace(destination)
    print(json.dumps({k: report[k] for k in ("assessment_status", "reason_codes", "alert")}))
    if report["alert"]:
        print("::error::Policy promotion gate rejected input; inspect policy_evaluation.json.")
    return 0 if report["assessment_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

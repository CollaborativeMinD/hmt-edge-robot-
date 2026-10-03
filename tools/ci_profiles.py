"""Software-only CI support profiles with replay hashes and operator alerts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ci_admission import ROOT
from policy_inventory import inventory, load_profile
from profile_witnesses import document_witness, evidence_witness, source_claim

from hmt_edge_robot.contracts import digest


def evaluate(root: Path) -> dict[str, Any]:
    profile = load_profile(root)
    inventory(root, profile)
    claims = [source_claim(root, name) for name in
              ("policy/ci_support.json", "docs/requirements.json", "docs/implementation_traceability.json")]
    witnesses = [document_witness(root, profile), evidence_witness(root, claims)]
    payload = {"profile_id": profile.profile_id, "profile_hash": digest(profile.model_dump(mode="json")),
               "status": "PASS", "witnesses": witnesses, "full_tool_admission": "HOLD",
               "full_policy_adoption": "HOLD", "docker_build": "HOLD", "deployment": "HOLD"}
    return {**payload, "receipt_hash": digest(payload), "notification": "CI_SUPPORT_PROFILES_PASS",
            "alert": False}


def main(root: Path = ROOT) -> int:
    try:
        result = evaluate(root)
    except (ValueError, OSError, TypeError, KeyError) as exc:
        result = {"status": "FAIL", "reason_codes": [str(exc)], "alert": True,
                  "notification": "CI_SUPPORT_PROFILES_FAIL"}
    destination = root / "evidence/ci/phase2/profiles.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, indent=2) + "\n")
    temporary.replace(destination)
    print(json.dumps(result))
    if result["alert"]:
        print("::error::CI support interface rejected input; inspect profiles.json")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Persist success or rejection receipts without stale PASS artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from ci_admission import ROOT
from deployment_admission import evaluate
from deployment_receipts import RejectionReceipt
from pydantic import ValidationError


def main(root: Path = ROOT) -> int:
    try:
        report = evaluate(root).model_dump(mode="json")
    except (ValueError, OSError, TypeError, KeyError) as exc:
        reason = "STAGE3_SCHEMA_REJECTED" if isinstance(exc, ValidationError) else str(exc)
        report = RejectionReceipt(contract_status="FAIL", release_decision="HOLD",
            reason_codes=[reason[:2048]], notification="DEPLOYMENT_DESIGN_REJECTED", alert=True).model_dump(mode="json")
    destination = root / "evidence/cd/stage3/release_receipt.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n")
    temporary.replace(destination)
    print(json.dumps({k: report[k] for k in ("contract_status", "release_decision", "reason_codes", "alert")}))
    if report["alert"]:
        print("::error::Deployment design rejected; execution remains HOLD.")
    return 0 if report["contract_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

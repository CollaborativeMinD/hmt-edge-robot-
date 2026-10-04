"""REQ-CD5-03: replace stale assessment before evaluating three operator captures."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ci_admission import ROOT
from target_admission import evaluate
from target_io import atomic_write, output_path
from target_receipts import Outcome


def assess(root: Path, paths: tuple[Path, ...], output: Path) -> int:
    output = output_path(root, output, paths)
    atomic_write(output, {"inventory_status": "FAIL", "target_qualification": "HOLD", "deployment": "HOLD", "physical_actuation": "HOLD", "reason_codes": ["ASSESSMENT_INCOMPLETE"], "alert": True})
    try:
        result = evaluate(root, paths)
    except (ValueError, OSError, KeyError, TypeError, IndexError, StopIteration):
        result = {"inventory_status": "FAIL", "target_qualification": "HOLD", "deployment": "HOLD", "physical_actuation": "HOLD", "reason_codes": ["TARGET_ASSESSMENT_REJECTED"], "alert": True}
    atomic_write(output, Outcome.validate_json(json.dumps(result)).model_dump(mode="json"))
    print(json.dumps(result))
    return 0 if result["inventory_status"] == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("captures", nargs=3, type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "evidence/cd/stage5/target_receipt.json")
    args = parser.parse_args()
    return assess(ROOT, tuple(args.captures), args.output)


if __name__ == "__main__":
    raise SystemExit(main())

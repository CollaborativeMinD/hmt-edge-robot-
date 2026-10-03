"""Truth Serum command-line contract."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .engine import admit
from .models import AdmissionMode, Decision
from .output import resolve as resolve_output

EXIT = {
    Decision.PASS: 0,
    Decision.FAIL: 1,
    Decision.HOLD: 3,
    Decision.ESCALATE: 4,
}


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description="Deterministic repository admission; never a release seal."
    )
    command.add_argument("--repo", type=Path, default=Path("."))
    command.add_argument("--out", type=Path, required=True)
    command.add_argument(
        "--mode", type=AdmissionMode, choices=tuple(AdmissionMode), default=AdmissionMode.CI
    )
    command.add_argument("--attempt-id")
    return command


def main() -> int:
    command = parser()
    args = command.parse_args()
    if not args.repo.is_dir():
        command.error(f"repository is not a directory: {args.repo}")
    root = args.repo.resolve()
    try:
        out = resolve_output(root, args.out)
    except ValueError as error:
        command.error(str(error))
    attempt_id = args.attempt_id or f"local-{args.mode.value}"
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,79}", attempt_id) is None:
        command.error("--attempt-id must match [A-Za-z0-9][A-Za-z0-9._-]{2,79}")
    report = admit(root, out, args.mode, attempt_id)
    print(
        json.dumps(
            {
                "decision": report.decision.value,
                "report": str(out.relative_to(root) / "admission_report.json"),
            },
            sort_keys=True,
        )
    )
    return EXIT[report.decision]

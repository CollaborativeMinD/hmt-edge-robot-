"""Canonical evidence-claim parsing and byte binding."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from typing import Any

from ..models import Finding
from .claim_model import EvidenceClaim
from .data_parse import loads_json


def load(path: Path) -> list[EvidenceClaim]:
    if path.name.endswith(".jsonl"):
        payload: Any = [
            loads_json(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    else:
        payload = loads_json(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            if set(payload) != {"claims"}:
                raise TypeError("claim envelope must contain only claims")
            payload = payload["claims"]
    if not isinstance(payload, list) or not payload:
        raise TypeError("claims must be a nonempty list")
    return [EvidenceClaim.model_validate(item) for item in payload]


def bind(claim: EvidenceClaim, root: Path, index: int) -> list[Finding]:
    ref = claim.file_path
    digest = claim.sha256
    if _unsafe(root, ref):
        return [_missing(ref, index)]
    target = root / ref
    if not target.is_file():
        return [_missing(ref, index)]
    actual = hashlib.sha256(target.read_bytes()).hexdigest()
    if actual != digest:
        return [
            Finding(
                reason_code="FAIL_EVIDENCE_HASH_MISMATCH",
                message=f"Claim {index} digest mismatch.",
                path=ref,
            )
        ]
    return []


def _unsafe(root: Path, ref: str) -> bool:
    pure = PurePosixPath(ref)
    if pure.is_absolute() or ".." in pure.parts or "\\" in ref:
        return True
    cursor = root
    for part in pure.parts:
        cursor /= part
        if cursor.is_symlink():
            return True
    return not cursor.resolve().is_relative_to(root.resolve())
def _missing(ref: str, index: int) -> Finding:
    return Finding(
        reason_code="FAIL_EVIDENCE_REF_MISSING",
        message=f"Claim {index} references absent or unsafe evidence.",
        path=ref,
    )

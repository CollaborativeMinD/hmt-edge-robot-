"""Reuse the two sovereign validators through read-only bounded interfaces."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ci_admission import confined, digest
from policy_contracts import SupportProfile
from scaffoldctl.models import RepositoryRootDirectory, document_from_text
from scaffoldctl.phase2_models import PolicyDocumentRule
from scaffoldctl.snapshot import WorktreeSnapshot
from scaffoldctl.validation import validate_document
from truth_serum_runtime.gates.claim_contract import bind
from truth_serum_runtime.gates.claim_model import EvidenceClaim


def document_witness(root: Path, profile: SupportProfile) -> dict[str, Any]:
    snapshot = WorktreeSnapshot(root)
    documents = []
    artifacts = []
    for name, headings in profile.documents.items():
        rule = PolicyDocumentRule(canonicalRelativePath=name, maximumLineCountExclusive=100,
                                  requiredHeadings=tuple(headings))
        finding, artifact = validate_document(snapshot, ".", rule, ("__SCAFFOLDCTL_",), 65536)
        if not finding.admitted or artifact is None:
            raise ValueError("SCAFFOLD_DOCUMENT_REJECTED:" + name)
        text = snapshot.read_bytes(name, maximum_bytes=65536).decode()
        documents.append(document_from_text(name, text))
        artifacts.append(artifact.model_dump(mode="json"))
    RepositoryRootDirectory(hasHMTTrifectaDocument=tuple(documents))
    return {"interface": "scaffold-document-validator", "status": "PASS", "artifacts": artifacts}


def evidence_witness(root: Path, claims: list[EvidenceClaim]) -> dict[str, Any]:
    if not 1 <= len(claims) <= 32 or len({c.claim_id for c in claims}) != len(claims):
        raise ValueError("CLAIM_SET_BOUNDS")
    for index, claim in enumerate(claims, start=1):
        confined(root, claim.file_path)
        findings = bind(claim, root, index)
        if findings:
            raise ValueError(findings[0].reason_code)
    return {"interface": "truth-evidence-binding", "status": "PASS",
            "claims": [claim.model_dump(mode="json") for claim in claims],
            "non_claim": "Byte binding alone does not prove a statement semantically true."}


def source_claim(root: Path, name: str) -> EvidenceClaim:
    return EvidenceClaim(claim_id="source." + digest(confined(root, name))[:16],
                         statement="Reviewed input bytes are bound; no runtime promotion is implied.",
                         file_path=name, sha256=digest(root / name))

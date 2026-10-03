"""Existence, forbidden-state and replay tests for the bounded reuse profile."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from ci_admission import ROOT
from ci_profiles import evaluate
from policy_inventory import load_profile
from profile_witnesses import document_witness, evidence_witness, source_claim


def support_copy(tmp_path: Path) -> Path:
    profile = load_profile(ROOT)
    names = ["policy/ci_support.json", "docs/requirements.json", "docs/implementation_traceability.json",
             *profile.documents, *profile.policy_sources, *profile.qualification_refs]
    for name in names:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    return tmp_path


def test_support_reuse_replay_and_no_promotion(tmp_path: Path) -> None:
    root = support_copy(tmp_path)
    first = evaluate(root)
    assert first == evaluate(root)
    assert first["status"] == "PASS"
    assert first["full_tool_admission"] == first["deployment"] == first["docker_build"] == "HOLD"
    assert {w["interface"] for w in first["witnesses"]} == {
        "scaffold-document-validator", "truth-evidence-binding"}


@pytest.mark.parametrize("mutation", ["missing", "overlong", "heading", "link"])
def test_scaffold_support_rejects_document_defects(tmp_path: Path, mutation: str) -> None:
    root = support_copy(tmp_path)
    path = root / "Start_here.md"
    if mutation == "missing":
        path.unlink()
    elif mutation == "overlong":
        path.write_text(path.read_text() + "line\n" * 100)
    elif mutation == "heading":
        path.write_text(path.read_text().replace("## Boundary", "## Other"))
    else:
        path.unlink()
        path.symlink_to(ROOT / "Start_here.md")
    with pytest.raises(ValueError, match="SCAFFOLD_DOCUMENT_REJECTED"):
        document_witness(root, load_profile(root))


@pytest.mark.parametrize("mutation", ["tamper", "missing", "link", "duplicate"])
def test_truth_binding_rejects_changed_or_absent_evidence(tmp_path: Path, mutation: str) -> None:
    root = support_copy(tmp_path)
    path = root / "docs/requirements.json"
    claim = source_claim(root, "docs/requirements.json")
    if mutation == "tamper":
        path.write_text("{}")
    elif mutation == "missing":
        path.unlink()
    elif mutation == "link":
        path.unlink()
        path.symlink_to(ROOT / "docs/requirements.json")
    claims = [claim, claim] if mutation == "duplicate" else [claim]
    with pytest.raises(ValueError):
        evidence_witness(root, claims)


def test_support_profile_denies_authority_widening(tmp_path: Path) -> None:
    root = support_copy(tmp_path)
    path = root / "policy/ci_support.json"
    value = json.loads(path.read_text())
    value["deployment"] = "READY"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        load_profile(root)

"""REQ-CD5-01/03: governed fields and output contracts reject rehashed drift."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import target_bindings
from deployment_receipts import content_hash
from target_admission import evaluate
from target_io import bind
from target_receipts import Outcome
from target_test_support import NOW, captures, make_root
from test_target_io import rebind


@pytest.mark.parametrize("change", ["utc", "hash", "authority", "extra", "boolean"])
def test_receipt_contract(tmp_path: Path, change: str) -> None:
    root = make_root(tmp_path)
    value = evaluate(root, captures(root), NOW)
    if change == "utc":
        value["assessed_at"] = "2026-10-04T18:30:00+01:00"
    elif change == "hash":
        value["receipt_hash"] = "a" * 64
    elif change == "authority":
        value["authority"] = "DEPLOY"
    elif change == "extra":
        value["unexpected"] = "x"
    else:
        value["alert"] = 1
    if change != "hash":
        value["receipt_hash"] = content_hash({k: v for k, v in value.items() if k != "receipt_hash"})
    with pytest.raises(ValueError):
        Outcome.validate_json(json.dumps(value))


@pytest.mark.parametrize("change", ["binding", "subtype", "receipt_schema"])
def test_governed_binding_drift(tmp_path: Path, change: str) -> None:
    root = make_root(tmp_path)
    if change == "binding":
        (root / "docs/cd/target-field-bindings.json").write_text('{"bindings":[]}')
        rebind(root, "docs/cd/target-field-bindings.json")
    elif change == "subtype":
        (root / "docs/source_provenance.json").write_text('{"upstream_subtype_classes":[]}')
    else:
        (root / "docs/cd/target-receipt.schema.json").write_text('{}')
        rebind(root, "docs/cd/target-receipt.schema.json")
    with pytest.raises(ValueError):
        bind(root)


def test_unbound_field_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(target_bindings.GROUPS, "IdentifierField", set())
    with pytest.raises(ValueError):
        target_bindings.bindings()

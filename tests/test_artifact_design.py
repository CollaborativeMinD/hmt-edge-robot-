"""Input integrity binds the separate artifact authority before installation/build."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from artifact_design import evaluate
from ci_admission import digest


def catalog(root: Path) -> Path:
    (root / "policy").mkdir()
    source = root / "recipe"
    source.write_text("declared")
    path = root / "policy/artifact_admission.json"
    path.write_text(json.dumps({"schema_version": 1, "scope": "ARM64_ARTIFACT_QUALIFICATION_ONLY",
                               "files": {"recipe": digest(source)}}))
    return path


def test_artifact_design_admits_only_bound_input(tmp_path: Path) -> None:
    catalog(tmp_path)
    assert evaluate(tmp_path)["status"] == "PASS"
    (tmp_path / "recipe").write_text("changed")
    with pytest.raises(ValueError, match="DRIFT"):
        evaluate(tmp_path)


@pytest.mark.parametrize("field,value", [("schema_version", 2), ("scope", "DEPLOY"), ("unknown", 1)])
def test_artifact_design_rejects_changed_scope_or_schema(tmp_path: Path, field: str, value: object) -> None:
    path = catalog(tmp_path)
    value_dict = json.loads(path.read_text())
    value_dict[field] = value
    path.write_text(json.dumps(value_dict))
    with pytest.raises(ValueError):
        evaluate(tmp_path)

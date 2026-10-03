"""Policy assessment does not conflate measured gaps with qualification."""

from __future__ import annotations

from pathlib import Path

import pytest
from policy_evaluation import evaluate
from policy_inventory import fold_measurements
from test_ci_support import support_copy


def test_policy_inventory_and_full_adoption_hold(tmp_path: Path) -> None:
    root = support_copy(tmp_path)
    source = root / "src/big.py"
    source.parent.mkdir()
    source.write_text("value = 1\n" * 101)
    with pytest.raises(ValueError, match="MODULE_CEILING_EXCEEDED"):
        evaluate(root)


def test_declared_policy_tamper_is_not_admitted(tmp_path: Path) -> None:
    root = support_copy(tmp_path)
    path = root / "policy/hmt/axioms/HMT_Axioms_Policy_v1.0.0.json"
    path.write_text("{}")
    with pytest.raises(ValueError, match="DECLARATIVE_POLICY_DIGEST_MISMATCH"):
        evaluate(root)


def test_policy_loc_metric_counts_docstrings_and_ignores_comments(tmp_path: Path) -> None:
    source = tmp_path / "src/test.py"
    source.parent.mkdir()
    source.write_text('# comment\n\n"""doc\n# doc content\n"""\nvalue = 1 # inline\n')
    rows = fold_measurements(tmp_path)
    assert rows[0]["module_loc"] == 4


def test_new_support_module_cannot_evade_ceiling(tmp_path: Path) -> None:
    root = support_copy(tmp_path)
    source = root / "tools/ci_profiles.py"
    source.parent.mkdir()
    source.write_text("value = 1\n" * 101)
    with pytest.raises(ValueError, match="MODULE_CEILING"):
        evaluate(root)

"""test_assurance_readiness_effects: effects interface."""



import pytest
from test_assurance_readiness_effects_base import HASH, effect_contract, effect_trace

from hmt_edge_robot.assurance.contracts import (
    Effect,
    Epochs,
)
from hmt_edge_robot.assurance.usea import file_manifest, manifest_effects
from hmt_edge_robot.contracts import digest


def test_usea_effect_receipt_distinction(cell):
    result = cell.assurance.usea.attest(effect_contract(), effect_trace())
    assert result.report.verdict == "DECLARED_EFFECT_CONFIRMED"
    result = cell.assurance.usea.attest(effect_contract(), effect_trace(observed=(Effect(kind="network", target="10.0.0.12:443"),)))
    assert result.report.verdict == "SIDE_EFFECT_OUTSIDE_CONTRACT"
    assert "UNDECLARED_NETWORK_ACCESS" in result.report.reason_codes
    assert cell.assurance.kernel.notices()[-1]["requires_ack"]

@pytest.mark.parametrize("changes", [
    {"complete": False}, {"coverage": ("write",)}, {"executable_hash": digest("other")},
    {"epochs": Epochs(policy=2)}, {"started_at": 100.0},
])
def test_usea_incomplete_is_hold(cell, changes):
    result = cell.assurance.usea.attest(effect_contract(), effect_trace(**changes))
    assert result.report.verdict == "ATTESTATION_INCOMPLETE"

@pytest.mark.parametrize("changes", [{"runtime_sec": 3.0}, {"exit_code": 1}])
def test_usea_runtime_and_exit_contract(cell, changes):
    assert cell.assurance.usea.attest(effect_contract(), effect_trace(**changes)).report.verdict == "SIDE_EFFECT_OUTSIDE_CONTRACT"

def test_manifest_actual_writes_and_coverage_limit(tmp_path, cell):
    before = file_manifest(tmp_path)
    (tmp_path/"report.json").write_text("payload")
    after = file_manifest(tmp_path)
    effects = manifest_effects(before, after)
    assert effects == (Effect(kind="write", target="report.json"),)
    result = cell.assurance.usea.attest(effect_contract(), effect_trace(observed=effects, coverage=("write",), complete=False))
    assert result.report.verdict != "DECLARED_EFFECT_CONFIRMED"
    (tmp_path/"link").symlink_to(tmp_path/"report.json")
    with pytest.raises(ValueError, match="MANIFEST_INCOMPLETE"):
        file_manifest(tmp_path)

def test_manifest_resource_bounds(tmp_path):
    (tmp_path/"a").write_bytes(b"1234")
    with pytest.raises(ValueError, match="BYTE_BOUND"):
        file_manifest(tmp_path, max_bytes=3)
    (tmp_path/"b").write_bytes(b"x")
    with pytest.raises(ValueError):
        file_manifest(tmp_path, max_files=1)
    with pytest.raises(ValueError):
        file_manifest(tmp_path, max_files=0)
    with pytest.raises(ValueError):
        manifest_effects({str(i):HASH for i in range(257)}, {})

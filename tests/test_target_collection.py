"""REQ-CD5-02/03: local collection, failed capture replacement and no target writes."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import target_collect
import target_gate
from target_contracts import Capture, Probe, Snapshot
from target_test_support import NOW, captures, make_root, payloads


def mock_host(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    value = payloads(root)[0]
    probes = {p["name"]: Probe.model_validate(p) for p in value["probes"]}
    monkeypatch.setattr(target_collect, "execute", lambda name: probes[name])
    monkeypatch.setattr(target_collect, "snapshot", lambda _: Snapshot.model_validate(value["snapshot"]))
    monkeypatch.setattr(target_collect, "read_host", lambda _: value["boot_id"])


def test_collector_success_and_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_root(tmp_path)
    mock_host(root, monkeypatch)
    destination = root / "evidence/cd/stage5/capture.json"
    assert target_collect.collect(root, destination) == 0
    capture = Capture.model_validate_json(destination.read_text())
    assert capture.deployment == "HOLD" and len(capture.probes) == 11
    monkeypatch.setattr(target_collect, "ROOT", root)
    monkeypatch.setattr("sys.argv", ["target_collect", "--output", str(destination)])
    assert target_collect.main() == 0


@pytest.mark.parametrize("failure", ["probe", "reboot", "snapshot"])
def test_collector_invalidates_prior_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    root = make_root(tmp_path)
    mock_host(root, monkeypatch)
    if failure == "probe":
        monkeypatch.setattr(target_collect, "execute", lambda name: Probe(name=name, status="FAIL", output="", reason_code="COMMAND_UNAVAILABLE"))
    elif failure == "reboot":
        sequence = iter(["12345678-1234-1234-1234-123456789000", "12345678-1234-1234-1234-123456789001"])
        monkeypatch.setattr(target_collect, "read_host", lambda _: next(sequence))
    else:
        def invalid_snapshot(_: object) -> Snapshot:
            raise ValueError("bad snapshot")
        monkeypatch.setattr(target_collect, "snapshot", invalid_snapshot)
    destination = root / "evidence/cd/stage5/capture.json"
    destination.parent.mkdir(parents=True)
    destination.write_text('{"status":"PASS"}')
    assert target_collect.collect(root, destination) == 1
    assert json.loads(destination.read_text())["status"] == "FAIL"


def test_assessment_replaces_stale_pass_and_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_root(tmp_path)
    paths = captures(root)
    destination = root / "evidence/cd/stage5/receipt.json"
    real = target_gate.evaluate
    monkeypatch.setattr(target_gate, "evaluate", lambda r, p: real(r, p, NOW))
    assert target_gate.assess(root, paths, destination) == 0
    monkeypatch.setattr(target_gate, "ROOT", root)
    monkeypatch.setattr("sys.argv", ["target_gate", *map(str, paths), "--output", str(destination)])
    assert target_gate.main() == 0
    paths[0].write_text('{"x":1,"x":2}')
    assert target_gate.assess(root, paths, destination) == 1
    assert json.loads(destination.read_text())["inventory_status"] == "FAIL"

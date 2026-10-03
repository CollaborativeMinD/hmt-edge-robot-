"""Offline software assurance campaign; no actuator, cloud, kernel tracer or hardware probe."""
from __future__ import annotations

import asyncio
import json
import secrets
import tempfile
import time
from pathlib import Path

from hmt_edge_robot.assurance.contracts import (
    Effect,
    EffectContract,
    EffectTrace,
    RecoverySpec,
    StageObservation,
    WarmCandidate,
)
from hmt_edge_robot.assurance.optimization import optimize_warm_set
from hmt_edge_robot.assurance.usea import file_manifest, manifest_effects
from hmt_edge_robot.contracts import digest, utc_now
from hmt_edge_robot.runtime import RobotCell

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "evidence/triad"


async def readiness(cell, token):
    acceptance = {"transaction": "admitted_inspect_and_durable_roundtrip", "schema": "v1"}
    expected = digest(acceptance)
    spec = RecoverySpec(capability_id="software-inspect", capability_hash=digest("cell-inspect-v1"),
        transaction_hash=expected, stages=("policy_loaded", "admission_ready", "first_valid_transaction"),
        recovery_horizon_sec=2.0, reserve_sec=.1, artifact_refs=("recovery-config",))
    session = ""
    async def probe(stage):
        nonlocal session
        if stage == "policy_loaded":
            success = cell.policy.policy_epoch == 1
        elif stage == "admission_ready":
            session = cell.access.login("operator", token, cell.clock())
            success = cell.access.authorize(session, "operator", "inspect", cell.clock())
        else:
            result = cell.resident_tool("inspect", session, "operator")
            if set(result) != {"stopped", "queue_size", "pace_lane", "substrate_ready"}:
                raise ValueError("MISSION_RESULT_SCHEMA_INVALID")
            cell.ledger.append("assurance", "readiness-canary", "mission_acceptance", acceptance)
            last = cell.ledger.recent(1)[0]
            success = last["payload"] == acceptance and cell.ledger.verify() > 0
        return StageObservation(stage=stage, elapsed_sec=0.0, succeeded=success,
                                transaction_hash=expected if stage == "first_valid_transaction" and success else None)
    traces = tuple([await cell.assurance.mcc.collect(spec, probe) for _ in range(8)])
    envelope = cell.assurance.mcc.envelope(spec, traces)
    return spec, envelope, cell.assurance.mcc.assess(spec, traces[-1])


def effects(cell, workspace):
    before = file_manifest(workspace)
    started = cell.clock()
    (workspace/"report.json").write_text('{"validated":true}\n')
    observed = manifest_effects(before, file_manifest(workspace))
    cell.assurance.catalog.put("produced-report", (workspace/"report.json").read_bytes())
    contract = EffectContract(executable_id="software-file-transaction", executable_hash=digest("writer-v1"),
        allowed=(Effect(kind="write", target="report.json"),), required_coverage=("write",), max_runtime_sec=2.0)
    trace = EffectTrace(origin="SOFTWARE_COLLECTED", collector_id="file-manifest", executable_hash=contract.executable_hash,
        epochs=cell.assurance.kernel.epochs(), started_at=started, runtime_sec=cell.clock()-started, exit_code=0,
        coverage=("write",), complete=False, observed=observed, artifact_refs=("produced-report",))
    receipt = cell.assurance.usea.attest(contract, trace)
    return receipt


def scale(cell):
    for i in range(256):
        cell.assurance.catalog.put(f"stale-{i:04}", b"x")
    start = time.monotonic()
    plan = cell.assurance.agc.plan(cell.assurance.catalog.census())
    duration = time.monotonic()-start
    candidates = tuple(WarmCandidate(artifact_id=f"model-{i:02}", cost_units=i+1, saved_sec=float(i+1)) for i in range(64))
    start = time.monotonic()
    result = optimize_warm_set(candidates, 1024)
    optimization_sec = time.monotonic()-start
    return {"artifact_count": len(plan.decisions), "planning_sec": duration,
        "planning_ceiling_sec": 10.0, "optimization_sec": optimization_sec, "optimization_ceiling_sec": 2.0,
        "optimization": result, "pass": duration < 10.0 and optimization_sec < 2.0}


async def campaign(directory):
    token = secrets.token_hex(24)
    cell = RobotCell(directory/"software.db", token)
    try:
        cell.assurance.catalog.put("recovery-config", b"v1-software-policy")
        _, envelope, readiness_receipt = await readiness(cell, token)
        workspace = directory/"workspace"
        workspace.mkdir()
        effect_receipt = effects(cell, workspace)
        session = cell.access.login("operator", token, cell.clock())
        cell.assurance.bind_witness(readiness_receipt, session, "operator")
        cell.assurance.bind_witness(effect_receipt, session, "operator")
        measurements = scale(cell)
        census = cell.assurance.catalog.census()
        plan = cell.assurance.agc.plan(census)
        cell.access.heartbeat(session, "operator", cell.clock())
        grant = cell.assurance.issue_grant(plan, "quarantine", "stale-0000", session, "operator")
        receipt = cell.assurance.mutate(plan, grant)
        fresh = cell.assurance.agc.plan(cell.assurance.catalog.census())
        grant = cell.assurance.issue_grant(fresh, "restore", "stale-0000", session, "operator")
        restored = cell.assurance.mutate(fresh, grant)
        exported = cell.assurance.analytics.export(OUTPUT, cell.assurance.catalog.census())
        return {"classification":"SOFTWARE_VALIDATION_ONLY", "timestamp_utc":utc_now(),
            "status":"PASS" if measurements["pass"] and envelope["failure_count"]==0 else "FAIL",
            "readiness":envelope, "side_effect_verdict":effect_receipt.report.verdict,
            "reclamation":receipt.model_dump(mode="json"), "restoration":restored.model_dump(mode="json"),
            "measurements":measurements, "exports":exported, "verified_events":cell.ledger.verify(),
            "verified_catalog_records":cell.assurance.catalog.verify(), "driver_moves":cell.driver.moves,
            "hardware_verification":"DEFERRED_UNTIL_CONTAINERIZED_DEPLOYMENT"}
    finally:
        cell.close()


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        report = asyncio.run(campaign(Path(directory)))
    (OUTPUT/"campaign.json").write_text(json.dumps(report, indent=2)+"\n")
    if report["status"] != "PASS" or report["driver_moves"]:
        raise SystemExit(1)
    print("G-TRIAD-011 PASS", report["measurements"], flush=True)


if __name__ == "__main__":
    main()

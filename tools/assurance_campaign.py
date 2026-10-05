"""Compatibility facade for the decomposed assurance_campaign interfaces."""

from __future__ import annotations

import asyncio
import json
import secrets
import tempfile
from pathlib import Path

from assurance_campaign_base import OUTPUT as OUTPUT
from assurance_campaign_base import ROOT as ROOT
from assurance_campaign_probes import effects as effects
from assurance_campaign_probes import readiness as readiness
from assurance_campaign_probes import scale as scale

from hmt_edge_robot.contracts import utc_now
from hmt_edge_robot.runtime import RobotCell


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
        session = cell.access.login("operator", token, cell.clock())
        grant = cell.assurance.issue_grant(plan, "quarantine", "stale-0000", session, "operator")
        receipt = cell.assurance.mutate(plan, grant)
        fresh = cell.assurance.agc.plan(cell.assurance.catalog.census())
        session = cell.access.login("operator", token, cell.clock())
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

"""AssuranceAnalytics: queries responsibilities on the owning instance."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import polars as pl

from ..contracts import canonical, digest
from .analytics_exports import atomic_text as atomic_text
from .analytics_exports import reference_graph as reference_graph
from .analytics_exports import summarize as summarize

if TYPE_CHECKING:
    from hmt_edge_robot.assurance.analytics import AssuranceAnalytics

def frame(self: AssuranceAnalytics, limit: int = 1024) -> pl.DataFrame:
    if type(limit) is not int or not 1 <= limit <= 1024:
        raise ValueError("ANALYTICS_WINDOW_INVALID")
    self.kernel.ledger.verify()
    with self.kernel.ledger.lock:
        rows = self.kernel.ledger.db.execute(
            "SELECT seq,payload FROM events WHERE packet_type='assurance_notice' ORDER BY seq DESC LIMIT ?",
            (limit,),
        ).fetchall()
    parsed = []
    for seq, payload in reversed(rows):
        obj = json.loads(payload)
        report = obj.get("report")
        if not report:
            continue
        parsed.append(
            {
                "seq": seq,
                "component": report["component"],
                "verdict": report["verdict"],
                "subject_id": report["scope"]["subject_id"],
                "report_hash": obj["report_hash"],
                "event_payload": canonical(obj),
            }
        )
    return pl.DataFrame(
        parsed,
        schema={
            "seq": pl.Int64,
            "component": pl.String,
            "verdict": pl.String,
            "subject_id": pl.String,
            "report_hash": pl.String,
            "event_payload": pl.String,
        },
    )

def _payloads(self: AssuranceAnalytics, frame, census, limit):
    reports = [json.loads(value) for value in frame["event_payload"]]
    mcc = [r for r in reports if r["report"]["component"] == "MCC"]
    usea = [r for r in reports if r["report"]["component"] == "USEA"]
    agc = [r for r in reports if r["report"]["component"] == "AGC"]
    with self.kernel.ledger.lock:
        row = self.kernel.ledger.db.execute(
            "SELECT payload FROM events WHERE packet_type='reclamation_plan' ORDER BY seq DESC LIMIT 1"
        ).fetchone()
    documents = {
        "cold_start_recovery_margin_report.json": {
            "witnesses": mcc,
            "worst_case_guarantee": False,
        },
        "side_effect_contract_report.json": {"witnesses": usea},
        "safe_reclamation_plan.json": json.loads(row[0]) if row else None,
        "reclaim_receipt.json": {"receipts": [r for r in agc if not r["report"]["dry_run"]]},
        "assurance_summary.json": {
            "window_limit": limit,
            "summary": summarize(frame),
            "census_hash": digest(census.model_dump(mode="json")),
            "complete_history": False,
        },
    }
    return {
        **{name: canonical(payload) + "\n" for name, payload in documents.items()},
        "effect_attestation.jsonl": "".join(canonical(r) + "\n" for r in usea),
        "artifact_reference_graph.graphml": reference_graph(census),
    }

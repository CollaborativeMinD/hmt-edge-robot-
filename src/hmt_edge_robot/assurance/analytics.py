"""Bounded SQLite -> Polars -> DuckDB orchestration and atomic assurance exports."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

import duckdb
import polars as pl

from ..contracts import canonical, digest
from .contracts import Census
from .kernel import AssuranceKernel


class AssuranceAnalytics:
    def __init__(self, kernel: AssuranceKernel):
        self.kernel = kernel

    def frame(self, limit: int = 1024) -> pl.DataFrame:
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

    def summary(self, limit: int = 1024) -> list[dict]:
        return summarize(self.frame(limit))

    def _payloads(self, frame, census, limit):
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

    def export(self, directory: Path, census: Census, limit: int = 1024) -> dict:
        directory.mkdir(parents=True, exist_ok=True)
        frame = self.frame(limit)
        files = []
        for component, name in (
            ("MCC", "capability_readiness_atlas.parquet"),
            ("USEA", "effect_attestation.parquet"),
            ("AGC", "reclamation_verdicts.parquet"),
        ):
            with tempfile.NamedTemporaryFile(
                dir=directory, suffix=".parquet", delete=False
            ) as handle:
                temporary = Path(handle.name)
            try:
                frame.filter(pl.col("component") == component).write_parquet(temporary)
                temporary.replace(directory / name)
            finally:
                temporary.unlink(missing_ok=True)
            files.append(name)
        payloads = self._payloads(frame, census, limit)
        for name, payload in payloads.items():
            atomic_text(directory / name, payload)
            files.append(name)
        manifest = {
            name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in files
        }
        atomic_text(directory / "export_manifest.json", canonical(manifest) + "\n")
        return {"records": frame.height, "files": manifest, "complete_history": False}


def summarize(frame):
    with duckdb.connect(":memory:") as db:
        db.execute("CREATE TABLE reports(component VARCHAR,verdict VARCHAR)")
        rows = frame.select("component", "verdict").rows()
        if rows:
            db.executemany("INSERT INTO reports VALUES(?,?)", rows)
        rows = db.execute(
            "SELECT component,verdict,count(*) FROM reports GROUP BY ALL ORDER BY ALL"
        ).fetchall()
    return [dict(zip(("component", "verdict", "count"), row)) for row in rows]


def atomic_text(path: Path, content: str) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", dir=path.parent, encoding="utf-8", delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def reference_graph(census: Census) -> str:
    namespace = "http://graphml.graphdrawing.org/xmlns"
    root = Element("graphml", xmlns=namespace)
    graph = SubElement(root, "graph", id="artifact_dependencies", edgedefault="directed")
    nodes = {r.identity.artifact_id for r in census.records}
    nodes.update(dep for r in census.records for dep in r.dependencies)
    for artifact in sorted(nodes):
        SubElement(graph, "node", id=artifact)
    for record in census.records:
        for dependency in record.dependencies:
            SubElement(graph, "edge", source=record.identity.artifact_id, target=dependency)
    return tostring(root, encoding="unicode")

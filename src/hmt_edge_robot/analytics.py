"""REQ-DA-01..03: bounded queries, genuine DuckDB/Polars/Parquet integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import polars as pl

from .contracts import canonical
from .ledger import Ledger


class Analytics:
    def __init__(self, ledger: Ledger) -> None:
        self.ledger = ledger

    def frame(self, limit: int = 4096) -> pl.DataFrame:
        self.ledger.verify()
        rows = self.ledger.recent(limit)
        for row in rows:
            row["payload"] = canonical(row["payload"])
        schema = {
            "monotonic_seq": pl.Int64,
            "timestamp_utc": pl.String,
            "producer_id": pl.String,
            "request_id": pl.String,
            "packet_type": pl.String,
            "payload": pl.String,
            "previous_hash": pl.String,
            "determinism_hash": pl.String,
        }
        return pl.DataFrame(rows, schema=schema)

    def summary(self, limit: int = 4096) -> list[dict[str, Any]]:
        frame = self.frame(limit)
        # Register plain records through DuckDB, avoiding extension downloads.
        with duckdb.connect(":memory:") as db:
            db.execute("CREATE TABLE evidence (producer_id VARCHAR, packet_type VARCHAR)")
            records = frame.select("producer_id", "packet_type").rows()
            if records:
                db.executemany("INSERT INTO evidence VALUES (?,?)", records)
            rows = db.execute(
                "SELECT producer_id,packet_type,count(*) AS event_count FROM evidence GROUP BY ALL ORDER BY producer_id,packet_type"
            ).fetchall()
        return [dict(zip(("producer_id", "packet_type", "event_count"), row)) for row in rows]

    def sensor_trends(self, limit: int = 4096) -> dict[str, Any]:
        rows = [
            r["payload"]
            for r in self.ledger.recent(limit)
            if r["packet_type"] == "sensor_assessment"
        ]
        if not rows:
            return {"sample_count": 0, "gap_count": 0, "mean_temp_c": None}
        frame = pl.DataFrame(
            {
                "data_valid": [r["assessment"]["data_valid"] for r in rows],
                "temp_c": [r["assessment"]["accepted_temp_c"] for r in rows],
            },
            schema={"data_valid": pl.Boolean, "temp_c": pl.Float64},
        )
        return {
            "sample_count": len(rows),
            "gap_count": frame.filter(~pl.col("data_valid")).height,
            "mean_temp_c": frame.select(pl.col("temp_c").mean()).item(),
        }

    def export_parquet(self, path: Path, limit: int = 4096) -> int:
        path.parent.mkdir(parents=True, exist_ok=True)
        frame = self.frame(limit)
        temporary = path.with_suffix(".parquet.tmp")
        frame.write_parquet(temporary)
        temporary.replace(path)
        return frame.height

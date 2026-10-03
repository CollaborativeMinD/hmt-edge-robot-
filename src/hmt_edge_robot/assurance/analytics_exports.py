"""analytics: exports interface."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

import duckdb

from .contracts import Census


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

"""Compatibility facade for the decomposed analytics interfaces."""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import polars as pl

from ..contracts import canonical
from .analytics_exports import atomic_text as atomic_text
from .analytics_exports import reference_graph as reference_graph
from .analytics_exports import summarize as summarize
from .analytics_queries import _payloads, frame
from .contracts import Census
from .kernel import AssuranceKernel


class AssuranceAnalytics:
    def __init__(self, kernel: AssuranceKernel):
        self.kernel = kernel

    frame = frame

    def summary(self, limit: int = 1024) -> list[dict]:
        return summarize(self.frame(limit))

    _payloads = _payloads

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

"""Mission readiness traces and empirical recovery envelopes; no hardware readiness claim."""

from __future__ import annotations

import numpy as np

from .contracts import RecoverySpec, RecoveryTrace
from .kernel import AssuranceKernel
from .mcc_collection import _collect_stages, collect
from .mcc_readiness import _verdict, assess


class MissionColdStartCartographer:
    def __init__(self, kernel: AssuranceKernel):
        self.kernel = kernel

    assess = assess

    _verdict = _verdict

    collect = collect

    _collect_stages = _collect_stages

    def envelope(self, spec: RecoverySpec, traces: tuple[RecoveryTrace, ...]) -> dict:
        if not 1 <= len(traces) <= 256:
            raise ValueError("CAMPAIGN_SIZE_INVALID")
        reports = [self.assess(spec, trace) for trace in traces]
        times = np.array([dict(r.report.metrics)["mission_ready_sec"] for r in reports])
        failures = sum(r.report.verdict != "MISSION_READY" for r in reports)
        # Wilson 95% upper confidence endpoint on observed failure proportion.
        n, z = len(times), 1.959963984540054
        p = failures / n
        upper = (p + z * z / (2 * n) + z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (
            1 + z * z / n
        )
        return {
            "classification": "EMPIRICAL_SOFTWARE_CAMPAIGN",
            "sample_count": n,
            "p95_sec": float(np.quantile(times, 0.95, method="higher")),
            "max_sec": float(times.max()),
            "failure_count": failures,
            "failure_probability_upper_95": float(upper),
            "report_hashes": [r.report_hash for r in reports],
            "scenario": spec.scenario,
            "worst_case_guarantee": False,
        }

"""resident: health interface."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import sklearn
from sklearn.ensemble import IsolationForest

from .contracts import digest


class HealthModel:
    """Explicit fit on an operator-selected baseline; no implicit retraining."""

    def __init__(self) -> None:
        self.model: IsolationForest | None = None
        self.artifact_hash = "UNFIT"
        self.bounds: tuple[tuple[float, float], ...] = ()

    def fit(self, baseline: tuple[tuple[float, float], ...]) -> str:
        if not 16 <= len(baseline) <= 4096 or any(
            len(r) != 2 or not all(math.isfinite(x) for x in r) for r in baseline
        ):
            raise ValueError("ML_BASELINE_INVALID")
        values = np.asarray(baseline)
        if np.any(values.std(axis=0) <= 1e-9):
            raise ValueError("ML_BASELINE_DEGENERATE")
        self.model = IsolationForest(
            n_estimators=32,
            max_samples=min(128, len(values)),
            contamination=0.05,
            random_state=7,
            n_jobs=1,
        )
        self.model.fit(values)
        self.bounds = tuple(
            (float(values[:, i].min()), float(values[:, i].max())) for i in range(2)
        )
        self.artifact_hash = digest(
            {
                "baseline": baseline,
                "parameters": self.model.get_params(),
                "sklearn_version": sklearn.__version__,
                "features": ["voltage_v", "temp_c"],
            }
        )
        return self.artifact_hash

    def predict(self, voltage_v: float, temp_c: float) -> dict[str, Any]:
        if not math.isfinite(voltage_v) or not math.isfinite(temp_c):
            raise ValueError("ML_INPUT_NONFINITE")
        if self.model is None:
            return {
                "decision": "HOLD",
                "rejection_reason": "MODEL_NOT_FIT",
                "artifact_hash": self.artifact_hash,
            }
        if any(
            not low <= value <= high for value, (low, high) in zip((voltage_v, temp_c), self.bounds)
        ):
            return {
                "decision": "HOLD",
                "rejection_reason": "OUT_OF_DISTRIBUTION",
                "artifact_hash": self.artifact_hash,
            }
        score = float(self.model.decision_function([[voltage_v, temp_c]])[0])
        return {
            "decision": "HOLD" if score < 0 else "ADMIT",
            "score": score,
            "artifact_hash": self.artifact_hash,
        }

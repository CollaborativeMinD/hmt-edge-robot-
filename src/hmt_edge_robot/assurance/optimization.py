"""Bounded exact resource optimization; recommendations never create authority."""

from __future__ import annotations

from ..contracts import digest
from .contracts import WarmCandidate


def optimize_warm_set(candidates: tuple[WarmCandidate, ...], budget_units: int) -> dict:
    if type(budget_units) is not int or not 0 <= budget_units <= 1024 or len(candidates) > 64:
        raise ValueError("OPTIMIZATION_BOUND_EXCEEDED")
    if len({c.artifact_id for c in candidates}) != len(candidates):
        raise ValueError("DUPLICATE_CANDIDATE")
    # 0/1 knapsack with descending budget avoids reusing an artifact. O(n*budget).
    table: list[tuple[float, tuple[str, ...]]] = [(0.0, ()) for _ in range(budget_units + 1)]
    for c in sorted(candidates, key=lambda c: c.artifact_id):
        for budget in range(budget_units, c.cost_units - 1, -1):
            gain, ids = table[budget - c.cost_units]
            choice = (gain + c.saved_sec, ids + (c.artifact_id,))
            old = table[budget]
            if choice[0] > old[0] or (choice[0] == old[0] and choice[1] < old[1]):
                table[budget] = choice
    gain, selected = table[-1]
    return {
        "classification": "ADVISORY_ONLY",
        "selected": list(selected),
        "saved_sec": gain,
        "budget_units": budget_units,
        "algorithm": "BOUNDED_EXACT_01_KNAPSACK",
        "input_hash": digest([c.model_dump(mode="json") for c in candidates]),
    }

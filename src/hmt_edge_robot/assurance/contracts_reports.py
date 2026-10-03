"""contracts: reports interface."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from ..contracts import Contract, Identifier, Nonnegative
from .contracts_base import Hash, Refs, Verdict
from .contracts_identity import WitnessScope


class AssuranceReport(Contract):
    component: Literal["MCC", "USEA", "AGC"]
    scope: WitnessScope
    verdict: Verdict
    reason_codes: Refs
    artifact_refs: Refs = ()
    observation_hash: Hash
    metrics: Annotated[tuple[tuple[Identifier, Nonnegative], ...], Field(max_length=32)] = ()
    dry_run: bool = True

class SealedReport(Contract):
    report: AssuranceReport
    report_hash: Hash
    event_hash: Hash

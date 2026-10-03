"""Closed, immutable admission evidence models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class AdmissionMode(StrEnum):
    ARCHITECTURE_ONLY = "architecture-only"
    CI = "ci"
    POST_BUILD = "post-build"
    RAINY_DAY = "rainy-day"


class Decision(StrEnum):
    PASS = "PASS"
    HOLD = "HOLD"
    FAIL = "FAIL"
    ESCALATE = "ESCALATE"


class RepositoryPosture(StrEnum):
    PRIMARY = "PRIMARY"
    ALTERNATE = "ALTERNATE"
    CONTINGENCY = "CONTINGENCY"
    EMERGENCY = "EMERGENCY"
    TERMINAL = "TERMINAL"


class LaneStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class FrozenModel(BaseModel):
    model_config = ConfigDict(
        allow_inf_nan=False,
        extra="forbid",
        frozen=True,
        strict=True,
    )


class Finding(FrozenModel):
    reason_code: str
    message: str
    path: str | None = None
    line: int | None = None
    route: Decision = Decision.FAIL


class LaneReport(FrozenModel):
    lane_id: str
    status: LaneStatus
    required: bool
    tool: str
    reason_codes: tuple[str, ...]
    evidence_paths: tuple[str, ...] = ()
    findings: tuple[Finding, ...] = ()


class AdmissionReport(FrozenModel):
    schema_id: str = "truth-serum.admission-report"
    schema_version: str = "1.0.0"
    attempt_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{2,79}$")
    mode: AdmissionMode
    decision: Decision
    posture: RepositoryPosture
    clear: bool
    reasons: tuple[str, ...]
    lanes: tuple[LaneReport, ...]
    evidence_dir: str
    policy_path: str

"""Shared contracts primitives and declarations."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

Finite = Annotated[float, Field(allow_inf_nan=False)]

Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]

Nonnegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]

Identifier = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")]

ModelIdentifier = Annotated[
    str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:/-]+$")
]

Vector3 = tuple[Finite, Finite, Finite]

def canonical(value: Any) -> str:
    """Reject non-JSON and nonfinite values at persistence boundaries."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)

def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, allow_inf_nan=False)

class Lane(StrEnum):
    PRIMARY = "PRIMARY"
    ALTERNATE = "ALTERNATE"
    CONTINGENCY = "CONTINGENCY"
    EMERGENCY = "EMERGENCY"

class TaskState(StrEnum):
    PLANNED = "PLANNED"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    SUCCEEDED = "SUCCEEDED"
    DENIED = "DENIED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

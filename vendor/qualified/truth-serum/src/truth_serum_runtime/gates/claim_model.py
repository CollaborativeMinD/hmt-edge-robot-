"""Closed evidence-claim boundary model."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EvidenceClaim(BaseModel):
    model_config = ConfigDict(
        allow_inf_nan=False,
        extra="forbid",
        frozen=True,
        strict=True,
    )

    claim_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{2,79}$")
    statement: str = Field(min_length=1)
    file_path: str = Field(min_length=1, max_length=512)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("file_path")
    @classmethod
    def repository_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in value
            or re.fullmatch(r"[A-Za-z0-9._/-]+", value) is None
        ):
            raise ValueError("file_path must be a safe repository-relative path")
        return value

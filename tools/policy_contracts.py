"""Closed software support profile; declarations cannot grant deployment authority."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class SupportProfile(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    schema_version: Literal[1]
    profile_id: Literal["HMT-CI-SUPPORT-02"]
    scope: Literal["managed_ci_support"]
    docker_build: Literal["HOLD"]
    deployment: Literal["HOLD"]
    full_tool_admission: Literal["HOLD"]
    documents: dict[str, list[str]]
    tool_interfaces: tuple[Literal["scaffold-document-validator", "truth-evidence-binding"], ...]
    policy_sources: dict[str, Hash]
    qualification_refs: dict[str, Hash]

    @model_validator(mode="after")
    def bounded_profile(self) -> SupportProfile:
        if set(self.documents) != {"README.md", "Start_here.md", "Index.md"}:
            raise ValueError("SUPPORT_DOCUMENT_SET_INVALID")
        if set(self.tool_interfaces) != {"scaffold-document-validator", "truth-evidence-binding"}:
            raise ValueError("SUPPORT_INTERFACE_SET_INVALID")
        if len(self.tool_interfaces) != 2 or not 1 <= len(self.policy_sources) <= 128:
            raise ValueError("SUPPORT_PROFILE_BOUNDS")
        if not 1 <= len(self.qualification_refs) <= 16:
            raise ValueError("QUALIFICATION_REFERENCES_REQUIRED")
        if any(not 1 <= len(headings) <= 16 for headings in self.documents.values()):
            raise ValueError("SUPPORT_HEADING_BOUNDS")
        return self

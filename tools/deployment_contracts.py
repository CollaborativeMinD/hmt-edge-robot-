"""Closed stage-3 design contract; all execution authority remains held."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Hash = Annotated[str, Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]*[a-f1-9][a-f0-9]*$")]
GitHash = Annotated[str, Field(min_length=40, max_length=40, pattern=r"^[a-f0-9]*[a-f1-9][a-f0-9]*$")]


class Closed(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def exact_version(cls, value: object) -> object:
        if isinstance(value, dict) and "schema_version" in value and type(value["schema_version"]) is not int:
            raise ValueError("SCHEMA_VERSION_INTEGER_REQUIRED")
        return value


class Baseline(Closed):
    commit: GitHash
    tree: GitHash


class Resources(Closed):
    request_cpu_m: int = Field(ge=100, le=2000)
    limit_cpu_m: int = Field(ge=100, le=2000)
    request_memory_mib: int = Field(ge=256, le=2048)
    limit_memory_mib: int = Field(ge=256, le=2048)
    qualification: Literal["HOLD"]

    @model_validator(mode="after")
    def requests_fit(self) -> Resources:
        if self.request_cpu_m > self.limit_cpu_m or self.request_memory_mib > self.limit_memory_mib:
            raise ValueError("RESOURCE_REQUEST_EXCEEDS_LIMIT")
        return self


class Boundaries(Closed):
    image_build: Literal["HOLD"]
    container_execution: Literal["HOLD"]
    target_qualification: Literal["HOLD"]
    cluster_deployment: Literal["HOLD"]
    physical_actuation: Literal["HOLD"]
    readiness_implementation: Literal["HOLD"]
    single_owner_qualification: Literal["HOLD"]
    storage_restore_qualification: Literal["HOLD"]
    private_access_qualification: Literal["HOLD"]
    cluster_inventory: Literal["HOLD"]
    protected_promotion: Literal["HOLD"]


class DeploymentPlan(Closed):
    schema_version: Literal[1]
    stage: Literal[3]
    scope: Literal["deployment_design_only"]
    baseline: Baseline
    os: Literal["linux"]
    architecture: Literal["arm64"]
    orchestrator: Literal["k3s"]
    namespace: Literal["hmt-edge-robot-sil"]
    driver: Literal["SIL"]
    replicas: Literal[0]
    workers: Literal[1]
    flux_suspended: Literal[True]
    image: None
    node_owner: Literal["qualification-required"]
    storage_class: Literal["hmt-edge-unqualified"]
    storage_gib: int = Field(ge=8, le=32)
    storage_access_mode: Literal["ReadWriteOnce"]
    upgrade: Literal["stop_verify_backup_replace"]
    rollback: Literal["compatible_image_preserve_ledger"]
    bind_host: Literal["127.0.0.1"]
    private_access: Literal["qualified_port_forward_only"]
    api_secret: Literal["hmt-edge-runtime"]
    operator_secret: Literal["hmt-edge-runtime"]
    registry_secret: Literal["hmt-edge-registry-read"]
    git_secret: Literal["hmt-edge-git-read"]
    resources: Resources
    boundaries: Boundaries

    @field_validator("schema_version", "stage", "replicas", "workers", mode="before")
    @classmethod
    def exact_integers(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("DEPLOYMENT_INTEGER_REQUIRED")
        return value

    @field_validator("flux_suspended", mode="before")
    @classmethod
    def exact_boolean(cls, value: object) -> object:
        if type(value) is not bool:
            raise ValueError("DEPLOYMENT_BOOLEAN_REQUIRED")
        return value

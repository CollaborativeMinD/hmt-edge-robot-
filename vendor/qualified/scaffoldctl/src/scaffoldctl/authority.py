from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from scaffoldctl.models import StrictFrozenModel
from scaffoldctl.phase2_models import PhaseTwoBuildAuthority
from scaffoldctl.phase3_models import PhaseThreeBuildAuthority
from scaffoldctl.semantics import (
    ONTOLOGY_PROVENANCE_ID,
    ONTOLOGY_SHA256,
    ONTOLOGY_VERSION,
    PHASE_THREE_SUBMITTED_TOKEN,
    PHASE_THREE_UPSTREAM_ARCHIVE_SHA256,
    PHASE_THREE_UPSTREAM_WHEEL_SHA256,
    PROMOTED_BASELINE_ARCHIVE_SHA256,
    PROMOTION_RECEIPT_ID,
    PROMOTION_RECEIPT_SHA256,
    PROMOTION_REPORT_SHA256,
    ArtifactDisposition,
    ValidationStatus,
)

Sha256 = Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$")]


class Criticality(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class RequirementId(StrEnum):
    REPOSITORY_ROOT_CONFINEMENT = "SCF-REQ-001"
    STAGED_INDEX_TRUTH = "SCF-REQ-002"
    TRIFECTA_SCHEMA_FIDELITY = "SCF-REQ-003"
    EXISTING_CONTENT_PRESERVATION = "SCF-REQ-004"
    DETERMINISTIC_RECEIPTS = "SCF-REQ-005"
    HOOK_CI_PARITY = "SCF-REQ-006"
    FAIL_CLOSED_DISCOVERY = "SCF-REQ-007"
    EXPLICIT_HOLD_REOPENING = "SCF-REQ-008"


class SourceArtifact(StrictFrozenModel):
    artifactRef: str
    sha256: Sha256
    disposition: ArtifactDisposition
    packaged: bool


class Requirement(StrictFrozenModel):
    requirementId: RequirementId
    statement: str
    criticality: Criticality
    phaseIntroduced: int = Field(strict=True, ge=0)


class Threat(StrictFrozenModel):
    threatId: str
    statement: str
    controllingRequirementIds: Annotated[tuple[RequirementId, ...], Field(min_length=1)]


class SemanticAuthorityPin(StrictFrozenModel):
    ontologyVersion: Literal["1.0.0"]
    ontologySha256: Sha256
    provenanceId: Literal["prov_semantic_scaffolding_plan_20260803_v1_0_0"]


class PhaseZeroBaseline(StrictFrozenModel):
    baselineId: str
    createdOn: Literal["2026-08-03"]
    semanticAuthority: SemanticAuthorityPin
    sourceArtifacts: tuple[SourceArtifact, ...]
    requirements: tuple[Requirement, ...]
    threats: tuple[Threat, ...]
    authorizedScope: tuple[str, ...]
    nonclaims: tuple[str, ...]
    validationStatus: ValidationStatus


class MachineHandoffBody(StrictFrozenModel):
    agent_role: str
    task_owned: str
    implementation: str | tuple[str, ...]
    risks: tuple[str, ...]
    assumptions: tuple[str, ...]
    follow_up_instructions: tuple[str, ...]
    validation_status: ValidationStatus
    artifact_refs: tuple[str, ...]
    provenance_id: str


class MachineHandoffResponse(StrictFrozenModel):
    response: MachineHandoffBody


PHASE_0_BASELINE = PhaseZeroBaseline(
    baselineId="scaffoldctl-phase-0-baseline-v1.0.0",
    createdOn="2026-08-03",
    semanticAuthority=SemanticAuthorityPin(
        ontologyVersion=ONTOLOGY_VERSION,
        ontologySha256=ONTOLOGY_SHA256,
        provenanceId=ONTOLOGY_PROVENANCE_ID,
    ),
    sourceArtifacts=(
        SourceArtifact(
            artifactRef="scaffoldctl_federated_semantic_scaffolding_v1_0_0.ttl",
            sha256=ONTOLOGY_SHA256,
            disposition=ArtifactDisposition.INHERITED,
            packaged=True,
        ),
        SourceArtifact(
            artifactRef="Scaffolding Engine.py",
            sha256="d89be5daa7ae3b5ab2a4dc4bd7efaea42c7ee01731493acc7b4513c699f02378",
            disposition=ArtifactDisposition.INHERITED,
            packaged=False,
        ),
        SourceArtifact(
            artifactRef="Pre-Commit.py",
            sha256="1800ad556f3277f7f8d7d3ea313df5f83284426b7d6bf23d4f2e453c769589f2",
            disposition=ArtifactDisposition.INHERITED,
            packaged=False,
        ),
        SourceArtifact(
            artifactRef="Pre-Commit.sh",
            sha256="1800ad556f3277f7f8d7d3ea313df5f83284426b7d6bf23d4f2e453c769589f2",
            disposition=ArtifactDisposition.INHERITED,
            packaged=False,
        ),
    ),
    requirements=(
        Requirement(
            requirementId=RequirementId.REPOSITORY_ROOT_CONFINEMENT,
            statement="Resolve and confine every governed path beneath the repository root.",
            criticality=Criticality.CRITICAL,
            phaseIntroduced=0,
        ),
        Requirement(
            requirementId=RequirementId.STAGED_INDEX_TRUTH,
            statement="Validate staged Git objects without substituting worktree content.",
            criticality=Criticality.CRITICAL,
            phaseIntroduced=0,
        ),
        Requirement(
            requirementId=RequirementId.TRIFECTA_SCHEMA_FIDELITY,
            statement="Enforce ontology-exact HMT Trifecta cardinality, paths, and line budgets.",
            criticality=Criticality.CRITICAL,
            phaseIntroduced=1,
        ),
        Requirement(
            requirementId=RequirementId.EXISTING_CONTENT_PRESERVATION,
            statement="Do not overwrite existing repository content without explicit authority.",
            criticality=Criticality.CRITICAL,
            phaseIntroduced=0,
        ),
        Requirement(
            requirementId=RequirementId.DETERMINISTIC_RECEIPTS,
            statement="Emit canonical, reason-coded, SHA-256-bound operation receipts.",
            criticality=Criticality.CRITICAL,
            phaseIntroduced=0,
        ),
        Requirement(
            requirementId=RequirementId.HOOK_CI_PARITY,
            statement="Require local hook and protected CI to consume one verdict engine.",
            criticality=Criticality.CRITICAL,
            phaseIntroduced=0,
        ),
        Requirement(
            requirementId=RequirementId.FAIL_CLOSED_DISCOVERY,
            statement="Distinguish discovery failure from a valid empty result and fail closed.",
            criticality=Criticality.CRITICAL,
            phaseIntroduced=0,
        ),
        Requirement(
            requirementId=RequirementId.EXPLICIT_HOLD_REOPENING,
            statement="Leave Hold only through typed, authorized, reason-coded reopening.",
            criticality=Criticality.CRITICAL,
            phaseIntroduced=1,
        ),
    ),
    threats=(
        Threat(
            threatId="SCF-THREAT-001",
            statement=(
                "Path traversal, absolute paths, or symlinks escape the repository perimeter."
            ),
            controllingRequirementIds=(RequirementId.REPOSITORY_ROOT_CONFINEMENT,),
        ),
        Threat(
            threatId="SCF-THREAT-002",
            statement="Unstaged worktree content masks different staged Git content.",
            controllingRequirementIds=(RequirementId.STAGED_INDEX_TRUTH,),
        ),
        Threat(
            threatId="SCF-THREAT-003",
            statement="Git or policy discovery failure is misclassified as an empty pass.",
            controllingRequirementIds=(RequirementId.FAIL_CLOSED_DISCOVERY,),
        ),
        Threat(
            threatId="SCF-THREAT-004",
            statement="Partial writes or overwrite behavior damage existing content.",
            controllingRequirementIds=(RequirementId.EXISTING_CONTENT_PRESERVATION,),
        ),
        Threat(
            threatId="SCF-THREAT-005",
            statement="Compiled schemas drift from ontology state or SHACL constraints.",
            controllingRequirementIds=(RequirementId.TRIFECTA_SCHEMA_FIDELITY,),
        ),
        Threat(
            threatId="SCF-THREAT-006",
            statement="Local hook bypass admits a repository state that required CI would reject.",
            controllingRequirementIds=(RequirementId.HOOK_CI_PARITY,),
        ),
        Threat(
            threatId="SCF-THREAT-007",
            statement="A Hold state reopens without explicit authorization or reason evidence.",
            controllingRequirementIds=(RequirementId.EXPLICIT_HOLD_REOPENING,),
        ),
    ),
    authorizedScope=(
        "Phase 0 authority, provenance, requirement, threat, and nonclaim freeze.",
        "Phase 1 strict contracts, lifecycle table, reason registry, and semantic parity tests.",
        "Read-only command surfaces for inspecting and validating Phase 0/1 artifacts.",
    ),
    nonclaims=(
        "No filesystem scaffolding or repository mutation engine is implemented.",
        "No worktree, Git-index, commit-tree, hook, or CI adapter is implemented.",
        "No production seal, release promotion, or external authority is asserted.",
        "No executable physics, optimization, estimation, or control mathematics is claimed.",
    ),
    validationStatus=ValidationStatus.PASS,
)


PHASE_2_BUILD_AUTHORITY = PhaseTwoBuildAuthority(
    authorityId="scaffoldctl-phase-2-build-authority-v0.2.0",
    promotedBaselineArchiveSha256=PROMOTED_BASELINE_ARCHIVE_SHA256,
    promotionReceiptId=PROMOTION_RECEIPT_ID,
    promotionReceiptSha256=PROMOTION_RECEIPT_SHA256,
    promotionReportSha256=PROMOTION_REPORT_SHA256,
    authorizationRef="user-directive:proceed-to-phase-2:2026-08-03",
    authorizedScope=(
        "Proof-carrying deterministic scaffold planning.",
        "Repository-root-confined worktree snapshots.",
        "No-overwrite HMT Trifecta and boundary-policy creation.",
        "Read-only worktree validation, audit, and receipt replay.",
    ),
    nonclaims=(
        "No Git-index or commit-tree adapter is implemented.",
        "No Git hook or CI admission authority is implemented.",
        "No repository seal, external promotion, or authenticated signature is asserted.",
        "No executable physics, optimization, estimation, or control mathematics is claimed.",
    ),
    validationStatus=ValidationStatus.PASS,
)


PHASE_3_BUILD_AUTHORITY = PhaseThreeBuildAuthority(
    schemaId="urn:scaffoldctl:evidence:phase-3-build-authority:0.3.0",
    schemaVersion="0.3.0",
    authorityId="scaffoldctl-phase-3-build-authority-v0.3.0",
    authorizationRef="user-directive:authorize-phase-3-planned-to-validated-sealed:2026-08-03",
    upstreamArchiveSha256=PHASE_THREE_UPSTREAM_ARCHIVE_SHA256,
    upstreamWheelSha256=PHASE_THREE_UPSTREAM_WHEEL_SHA256,
    submittedVerificationToken=PHASE_THREE_SUBMITTED_TOKEN,
    submittedTokenAccepted=False,
    tokenRejectionReason="SCF.PHASE3.UPSTREAM_TOKEN_MALFORMED",
    authorizedScope=(
        "Pure Git-index object-matrix capture and staged validation.",
        "Commit-tree object-matrix capture and protected CI parity.",
        "Fail-closed pre-commit and CI admission adapters.",
        "Ed25519-signed snapshot asset leases.",
        "Transactional DuckDB receipt, lease, replay, and seal ledger.",
    ),
    nonclaims=(
        "A local hook remains bypassable without required protected-branch CI.",
        "An ephemeral CI signing key proves run possession, not durable actor identity.",
        "No executable physics, optimization, estimation, or control mathematics is claimed.",
        "No external release promotion is self-authorized by the package.",
    ),
    validationStatus=ValidationStatus.PASS,
)

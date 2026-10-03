import pytest
from pydantic import ValidationError

from scaffoldctl.authority import (
    PHASE_0_BASELINE,
    PHASE_3_BUILD_AUTHORITY,
    MachineHandoffBody,
    MachineHandoffResponse,
    RequirementId,
)
from scaffoldctl.semantics import ArtifactDisposition, ValidationStatus


def test_phase_zero_baseline_is_complete() -> None:
    assert PHASE_0_BASELINE.validationStatus is ValidationStatus.PASS
    assert tuple(item.requirementId for item in PHASE_0_BASELINE.requirements) == tuple(
        RequirementId
    )
    assert len(PHASE_0_BASELINE.threats) == 7


def test_inherited_prototypes_are_not_packaged() -> None:
    inherited = tuple(
        item
        for item in PHASE_0_BASELINE.sourceArtifacts
        if item.disposition is ArtifactDisposition.INHERITED
    )
    assert len(inherited) == 4
    assert all(not item.packaged for item in inherited[1:])
    assert inherited[0].packaged


def test_prototype_hash_collision_is_preserved() -> None:
    sources = {item.artifactRef: item.sha256 for item in PHASE_0_BASELINE.sourceArtifacts}
    assert sources["Pre-Commit.py"] == sources["Pre-Commit.sh"]


def test_phase_three_authority_rejects_malformed_submitted_token() -> None:
    authority = PHASE_3_BUILD_AUTHORITY
    assert authority.validationStatus is ValidationStatus.PASS
    assert authority.submittedTokenAccepted is False
    assert len(authority.submittedVerificationToken) != 64
    assert authority.upstreamArchiveSha256.startswith("99f55164c2c8")


def test_machine_handoff_contract_forbids_unknown_fields() -> None:
    body = MachineHandoffBody(
        agent_role="chief_gen_ai_systems_engineer",
        task_owned="phase_0_1",
        implementation=("compiled",),
        risks=(),
        assumptions=("ontology authority supplied",),
        follow_up_instructions=(),
        validation_status=ValidationStatus.PASS,
        artifact_refs=("scaffoldctl-0.1.0.whl",),
        provenance_id="prov_semantic_scaffolding_plan_20260803_v1_0_0",
    )
    assert MachineHandoffResponse(response=body).response.validation_status is ValidationStatus.PASS
    with pytest.raises(ValidationError):
        MachineHandoffResponse.model_validate({"response": body, "extra": True})

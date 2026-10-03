import json

import pytest
from pydantic import ValidationError

import scaffoldctl.policy as policy_module
from scaffoldctl.exceptions import PhaseTwoError
from scaffoldctl.integrity import (
    canonical_json_bytes,
    deterministic_id,
    hash_payload,
    parse_strict_json,
    sha256_bytes,
    stamp_payload,
    verify_stamped_payload,
)
from scaffoldctl.phase2_models import (
    BoundaryPolicy,
    BoundarySpec,
    PlanAction,
    PlanActionKind,
    PolicyDocumentRule,
    PolicyPack,
    canonical_artifact_path,
    canonical_target_path,
    expected_governed_paths,
    joined_relative_path,
    state_for_validation,
)
from scaffoldctl.policy import (
    POLICY_RESOURCE,
    TEMPLATE_NAMES,
    boundary_policy_bytes,
    load_policy_pack,
    load_template_resources,
    make_boundary_policy,
    parse_boundary_policy,
    render_boundary,
    verify_phase_two_resource_authority,
)
from scaffoldctl.reason_codes import ReasonCode
from scaffoldctl.semantics import (
    HMT_REQUIRED_PATHS,
    ONTOLOGY_SHA256,
    PHASE_TWO_POLICY_PACK_SHA256,
    PHASE_TWO_TEMPLATE_PACK_SHA256,
    LifecycleState,
)


def _boundary(target: str = "systems/demo") -> BoundarySpec:
    return BoundarySpec(
        boundaryId="systems.demo",
        targetPath=target,
        title="Demo Boundary",
        purpose="Exercise deterministic repository scaffolding.",
    )


@pytest.mark.parametrize("target", [".", "systems/demo", ".github/policy", "lane_1/a-b.c"])
def test_boundary_accepts_portable_canonical_targets(target: str) -> None:
    assert _boundary(target).targetPath == target
    assert canonical_target_path(target) == target


@pytest.mark.parametrize(
    "target",
    ["", "/absolute", "../escape", "a/../b", "a//b", "a/./b", "a\\b", "a b", "é"],
)
def test_boundary_rejects_noncanonical_targets(target: str) -> None:
    with pytest.raises((ValueError, ValidationError)):
        _boundary(target)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("boundaryId", "Upper"),
        ("boundaryId", "bad space"),
        ("title", ""),
        ("title", " leading"),
        ("title", "line\nbreak"),
        ("purpose", "${UNRESOLVED}"),
        ("purpose", "bad\x00value"),
        ("title", "e\u0301"),
    ],
)
def test_boundary_rejects_invalid_identifiers_and_text(field: str, value: str) -> None:
    payload = _boundary().model_dump(mode="python")
    payload[field] = value
    with pytest.raises(ValidationError):
        BoundarySpec.model_validate(payload)


def test_path_helpers_are_exact() -> None:
    assert canonical_artifact_path("a/README.md") == "a/README.md"
    assert joined_relative_path(".", "README.md") == "README.md"
    assert joined_relative_path("a", "README.md") == "a/README.md"
    assert expected_governed_paths(".", "scaffold.policy.json") == (
        *HMT_REQUIRED_PATHS,
        "scaffold.policy.json",
    )
    assert state_for_validation(True) is LifecycleState.VALIDATED
    assert state_for_validation(False) is LifecycleState.HOLD


def test_resource_authority_and_policy_round_trip() -> None:
    pack = load_policy_pack()
    templates = load_template_resources()
    receipt = verify_phase_two_resource_authority()
    assert pack.ontologySha256 == ONTOLOGY_SHA256
    assert tuple(templates) == TEMPLATE_NAMES
    assert receipt.policyPackSha256 == PHASE_TWO_POLICY_PACK_SHA256
    assert receipt.templatePackSha256 == PHASE_TWO_TEMPLATE_PACK_SHA256
    assert receipt.reasonCodes[-1] is ReasonCode.PHASE_TWO_AUTHORITY_VERIFIED
    boundary = _boundary()
    boundary_policy = make_boundary_policy(boundary)
    assert parse_boundary_policy(boundary_policy_bytes(boundary)) == boundary_policy
    assert boundary_policy.boundary == boundary


def test_rendered_boundary_is_complete_bounded_and_deterministic() -> None:
    first = render_boundary(_boundary())
    second = render_boundary(_boundary())
    assert first == second
    assert tuple(first) == (*HMT_REQUIRED_PATHS, "scaffold.policy.json")
    pack = load_policy_pack()
    for rule in pack.requiredDocuments:
        text = first[rule.canonicalRelativePath].decode("utf-8")
        assert len(text.splitlines()) < 100
        assert all(heading in text for heading in rule.requiredHeadings)
        assert not any(token in text for token in pack.unresolvedPlaceholderTokens)
    parsed = parse_boundary_policy(first[pack.policyFileName])
    assert parsed.boundary == _boundary()


def test_policy_rejects_unknown_fields_and_duplicate_json_keys() -> None:
    payload = json.loads(boundary_policy_bytes(_boundary()))
    payload["unknown"] = True
    with pytest.raises(PhaseTwoError) as captured:
        parse_boundary_policy(canonical_json_bytes(payload))
    assert captured.value.reason_code is ReasonCode.POLICY_INVALID
    duplicate = b'{"schemaId":"x","schemaId":"y"}'
    with pytest.raises(PhaseTwoError) as captured:
        parse_boundary_policy(duplicate)
    assert captured.value.reason_code is ReasonCode.POLICY_INVALID


def test_policy_pack_rejects_document_order_and_duplicate_tokens() -> None:
    payload = load_policy_pack().model_dump(mode="python")
    payload["requiredDocuments"] = tuple(reversed(payload["requiredDocuments"]))
    with pytest.raises(ValidationError):
        PolicyPack.model_validate(payload)


@pytest.mark.parametrize("headings", [("## Same", "## Same"), ("# Wrong",)])
def test_document_rule_rejects_duplicate_or_wrong_level_headings(
    headings: tuple[str, ...],
) -> None:
    with pytest.raises(ValidationError):
        PolicyDocumentRule(
            canonicalRelativePath="README.md",
            maximumLineCountExclusive=100,
            requiredHeadings=headings,
        )
    payload = load_policy_pack().model_dump(mode="python")
    payload["unresolvedPlaceholderTokens"] = ("${", "${")
    with pytest.raises(ValidationError):
        PolicyPack.model_validate(payload)


def test_policy_hash_mismatch_is_reason_coded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(policy_module, "PHASE_TWO_POLICY_PACK_SHA256", "0" * 64)
    with pytest.raises(PhaseTwoError) as captured:
        load_policy_pack()
    assert captured.value.reason_code is ReasonCode.POLICY_HASH_MISMATCH


def test_invalid_embedded_policy_is_reason_coded(monkeypatch: pytest.MonkeyPatch) -> None:
    original = policy_module._resource
    malformed = b"not-json"
    monkeypatch.setattr(policy_module, "PHASE_TWO_POLICY_PACK_SHA256", sha256_bytes(malformed))
    monkeypatch.setattr(
        policy_module,
        "_resource",
        lambda name: malformed if name == POLICY_RESOURCE else original(name),
    )
    with pytest.raises(PhaseTwoError) as captured:
        load_policy_pack()
    assert captured.value.reason_code is ReasonCode.POLICY_INVALID


def test_embedded_policy_ontology_drift_is_reason_coded(monkeypatch: pytest.MonkeyPatch) -> None:
    original = policy_module._resource
    payload = parse_strict_json(original(POLICY_RESOURCE))
    payload["ontologySha256"] = "0" * 64
    drifted = canonical_json_bytes(payload)
    monkeypatch.setattr(policy_module, "PHASE_TWO_POLICY_PACK_SHA256", sha256_bytes(drifted))
    monkeypatch.setattr(
        policy_module,
        "_resource",
        lambda name: drifted if name == POLICY_RESOURCE else original(name),
    )
    with pytest.raises(PhaseTwoError) as captured:
        load_policy_pack()
    assert captured.value.reason_code is ReasonCode.POLICY_AUTHORITY_DRIFT


def test_boundary_policy_cannot_widen_pack_authority() -> None:
    payload = parse_strict_json(boundary_policy_bytes(_boundary()))
    payload["maximumDocumentUtf8Bytes"] = 1
    with pytest.raises(PhaseTwoError) as captured:
        parse_boundary_policy(canonical_json_bytes(payload))
    assert captured.value.reason_code is ReasonCode.POLICY_INVALID


def test_boundary_policy_detects_valid_schema_authority_drift() -> None:
    payload = parse_strict_json(boundary_policy_bytes(_boundary()))
    payload["ontologySha256"] = "0" * 64
    with pytest.raises(PhaseTwoError) as captured:
        parse_boundary_policy(canonical_json_bytes(payload))
    assert captured.value.reason_code is ReasonCode.POLICY_AUTHORITY_DRIFT


def test_template_hash_mismatch_is_reason_coded(monkeypatch: pytest.MonkeyPatch) -> None:
    original = policy_module._resource
    monkeypatch.setattr(
        policy_module,
        "_resource",
        lambda name: b"tampered" if name == TEMPLATE_NAMES[0] else original(name),
    )
    with pytest.raises(PhaseTwoError) as captured:
        load_template_resources()
    assert captured.value.reason_code is ReasonCode.TEMPLATE_HASH_MISMATCH


@pytest.mark.parametrize("mode", ["utf8", "placeholder", "heading"])
def test_render_failure_modes_are_reason_coded(
    mode: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    templates = load_template_resources()
    if mode == "utf8":
        templates[TEMPLATE_NAMES[0]] = b"\xff"
    elif mode == "placeholder":
        templates[TEMPLATE_NAMES[0]] += b"\n${UNKNOWN}\n"
    else:
        templates[TEMPLATE_NAMES[0]] = templates[TEMPLATE_NAMES[0]].replace(
            b"## Purpose", b"## Removed"
        )
    monkeypatch.setattr(policy_module, "load_template_resources", lambda: templates)
    with pytest.raises(PhaseTwoError) as captured:
        render_boundary(_boundary())
    assert captured.value.reason_code is ReasonCode.TEMPLATE_RENDER_INVALID


def test_render_rejects_oversized_template(monkeypatch: pytest.MonkeyPatch) -> None:
    templates = load_template_resources()
    templates[TEMPLATE_NAMES[0]] = (
        b"# Title\n\n## Purpose\n\nText\n\n## Lifecycle\n\nText\n\n"
        b"## Invariants\n\nText\n\n## Authority\n\n" + b"x" * 65536
    )
    monkeypatch.setattr(policy_module, "load_template_resources", lambda: templates)
    with pytest.raises(PhaseTwoError) as captured:
        render_boundary(_boundary())
    assert captured.value.reason_code is ReasonCode.TEMPLATE_RENDER_INVALID


def test_strict_json_rejects_duplicates_nonfinite_and_invalid_utf8() -> None:
    with pytest.raises(ValueError):
        parse_strict_json(b'{"a":1,"a":2}')
    with pytest.raises(ValueError):
        parse_strict_json(b'{"a":NaN}')
    with pytest.raises(UnicodeDecodeError):
        parse_strict_json(b"\xff")


def test_canonical_hash_and_identity_are_stable_and_tamper_evident() -> None:
    assert canonical_json_bytes({"b": 2, "a": 1}) == b'{"a":1,"b":2}'
    assert hash_payload({"a": 1}) == sha256_bytes(b'{"a":1}')
    identity = deterministic_id("test", "0" * 64)
    assert identity == deterministic_id("test", "0" * 64)
    stamped = stamp_payload(
        {"value": 1},
        kind="test",
        id_field="recordId",
        hash_field="recordHash",
    )
    assert verify_stamped_payload(
        stamped,
        kind="test",
        id_field="recordId",
        hash_field="recordHash",
    )
    assert not verify_stamped_payload(
        {**stamped, "value": 2},
        kind="test",
        id_field="recordId",
        hash_field="recordHash",
    )


def test_plan_action_strict_contract_rejects_bad_values() -> None:
    valid = {
        "relativePath": "README.md",
        "action": PlanActionKind.CREATE,
        "expectedSha256": "0" * 64,
        "sizeBytes": 1,
        "lineCount": 1,
    }
    assert PlanAction.model_validate(valid).action is PlanActionKind.CREATE
    with pytest.raises(ValidationError):
        PlanAction.model_validate({**valid, "relativePath": "../README.md"})
    with pytest.raises(ValidationError):
        PlanAction.model_validate({**valid, "lineCount": 100})
    with pytest.raises(ValidationError):
        PlanAction.model_validate({**valid, "extra": True})


def test_boundary_policy_contract_requires_boundary() -> None:
    with pytest.raises(ValidationError):
        BoundaryPolicy.model_validate(load_policy_pack().model_dump(mode="python"))

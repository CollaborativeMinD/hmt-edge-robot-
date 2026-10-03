from __future__ import annotations

import hashlib
from importlib.resources import files
from typing import Any

from pydantic import ValidationError

from scaffoldctl.exceptions import PhaseTwoError
from scaffoldctl.integrity import (
    canonical_json_bytes,
    hash_payload,
    parse_strict_json,
    sha256_bytes,
)
from scaffoldctl.models import document_from_text
from scaffoldctl.phase2_models import (
    BoundaryPolicy,
    BoundarySpec,
    PhaseTwoResourceAuthorityReceipt,
    PolicyPack,
    document_structure_status,
)
from scaffoldctl.reason_codes import ReasonCode
from scaffoldctl.semantics import (
    ONTOLOGY_SHA256,
    PHASE_TWO_POLICY_PACK_SHA256,
    PHASE_TWO_TEMPLATE_PACK_SHA256,
    ValidationStatus,
)

RESOURCE_DIRECTORY = "boundary_contract"
POLICY_RESOURCE = "hmt-root-policy.json"
TEMPLATE_NAMES = ("README.md.tmpl", "Start_here.md.tmpl", "Index.md.tmpl")


def _resource(name: str) -> bytes:
    return files("scaffoldctl.resources").joinpath(RESOURCE_DIRECTORY, name).read_bytes()


def _template_pack_digest(resources: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for name in sorted(resources):
        data = resources[name]
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def load_policy_pack() -> PolicyPack:
    data = _resource(POLICY_RESOURCE)
    if sha256_bytes(data) != PHASE_TWO_POLICY_PACK_SHA256:
        raise PhaseTwoError(ReasonCode.POLICY_HASH_MISMATCH, "embedded policy hash drifted")
    try:
        payload = parse_strict_json(data)
        policy = PolicyPack.model_validate_json(canonical_json_bytes(payload))
    except (UnicodeDecodeError, ValueError, ValidationError) as exc:
        raise PhaseTwoError(ReasonCode.POLICY_INVALID, "embedded policy is invalid") from exc
    if policy.ontologySha256 != ONTOLOGY_SHA256:
        raise PhaseTwoError(ReasonCode.POLICY_AUTHORITY_DRIFT, "policy ontology pin drifted")
    return policy


def load_template_resources() -> dict[str, bytes]:
    resources = {name: _resource(name) for name in TEMPLATE_NAMES}
    if _template_pack_digest(resources) != PHASE_TWO_TEMPLATE_PACK_SHA256:
        raise PhaseTwoError(ReasonCode.TEMPLATE_HASH_MISMATCH, "template pack hash drifted")
    return resources


def make_boundary_policy(boundary: BoundarySpec) -> BoundaryPolicy:
    payload = load_policy_pack().model_dump(mode="python")
    return BoundaryPolicy.model_validate({**payload, "boundary": boundary})


def boundary_policy_bytes(boundary: BoundarySpec) -> bytes:
    return canonical_json_bytes(make_boundary_policy(boundary)) + b"\n"


def _pack_payload(policy: BoundaryPolicy) -> dict[str, Any]:
    return {name: getattr(policy, name) for name in PolicyPack.model_fields}


def parse_boundary_policy(
    data: bytes,
    *,
    authority: PolicyPack | None = None,
) -> BoundaryPolicy:
    try:
        payload = parse_strict_json(data)
        policy = BoundaryPolicy.model_validate_json(canonical_json_bytes(payload))
    except (UnicodeDecodeError, ValueError, ValidationError) as exc:
        raise PhaseTwoError(ReasonCode.POLICY_INVALID, "boundary policy is invalid") from exc
    expected = load_policy_pack() if authority is None else authority
    if PolicyPack.model_validate(_pack_payload(policy)) != expected:
        raise PhaseTwoError(ReasonCode.POLICY_AUTHORITY_DRIFT, "boundary policy widens authority")
    return policy


def _render_one(template: bytes, replacements: dict[str, str]) -> str:
    try:
        text = template.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:  # pragma: no cover - authority hash prevents this path
        raise PhaseTwoError(ReasonCode.TEMPLATE_RENDER_INVALID, "template is not UTF-8") from exc
    for name, value in replacements.items():
        text = text.replace(f"${{{name}}}", value)
    if "${" in text:
        raise PhaseTwoError(ReasonCode.TEMPLATE_RENDER_INVALID, "template placeholder unresolved")
    return text


def render_boundary(boundary: BoundarySpec) -> dict[str, bytes]:
    policy = load_policy_pack()
    templates = load_template_resources()
    replacements = {
        "BOUNDARY_ID": boundary.boundaryId,
        "ONTOLOGY_SHA256": ONTOLOGY_SHA256,
        "PURPOSE": boundary.purpose,
        "TARGET_PATH": boundary.targetPath,
        "TITLE": boundary.title,
    }
    rendered: dict[str, bytes] = {}
    for rule, template_name in zip(policy.requiredDocuments, TEMPLATE_NAMES, strict=True):
        text = _render_one(templates[template_name], replacements)
        data = text.encode("utf-8")
        if len(data) > policy.maximumDocumentUtf8Bytes:
            raise PhaseTwoError(
                ReasonCode.TEMPLATE_RENDER_INVALID, "rendered document is too large"
            )
        document_from_text(rule.canonicalRelativePath, text)
        headings_admitted, sections_admitted = document_structure_status(
            text,
            rule.requiredHeadings,
        )
        if not headings_admitted or (rule.requireSectionContent and not sections_admitted):
            raise PhaseTwoError(
                ReasonCode.TEMPLATE_RENDER_INVALID,
                "rendered document structure is incomplete",
            )
        rendered[rule.canonicalRelativePath] = data
    rendered[policy.policyFileName] = boundary_policy_bytes(boundary)
    return rendered


def verify_phase_two_resource_authority() -> PhaseTwoResourceAuthorityReceipt:
    load_policy_pack()
    load_template_resources()
    payload = {
        "ontologySha256": ONTOLOGY_SHA256,
        "policyPackSha256": PHASE_TWO_POLICY_PACK_SHA256,
        "reasonCodes": (
            ReasonCode.POLICY_VERIFIED,
            ReasonCode.TEMPLATE_AUTHORITY_VERIFIED,
            ReasonCode.PHASE_TWO_AUTHORITY_VERIFIED,
        ),
        "templatePackSha256": PHASE_TWO_TEMPLATE_PACK_SHA256,
        "validationStatus": ValidationStatus.PASS,
    }
    return PhaseTwoResourceAuthorityReceipt(**payload, receiptHash=hash_payload(payload))

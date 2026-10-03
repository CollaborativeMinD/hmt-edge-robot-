import hashlib
from pathlib import Path

import pytest

import scaffoldctl.ontology as ontology
from scaffoldctl.ontology import (
    OntologyAuthorityError,
    load_ontology_snapshot,
    verify_ontology_authority,
)
from scaffoldctl.reason_codes import ReasonCode
from scaffoldctl.semantics import (
    HMT_REQUIRED_PATHS,
    LIFECYCLE_STATE_ORDER,
    ONTOLOGY_SHA256,
    SHACL_NODE_SHAPES,
)


def test_embedded_ontology_parses_and_matches_authority() -> None:
    snapshot = load_ontology_snapshot()
    receipt = verify_ontology_authority()
    assert snapshot.sourceSha256 == ONTOLOGY_SHA256
    assert snapshot.lifecycleStateOrder == LIFECYCLE_STATE_ORDER
    assert snapshot.shacl.nodeShapes == SHACL_NODE_SHAPES
    assert snapshot.shacl.requiredPaths == HMT_REQUIRED_PATHS
    assert receipt.validationStatus == "pass"
    assert receipt.reasonCodes == (ReasonCode.AUTHORITY_VERIFIED,)


def test_transition_cardinalities_are_exact() -> None:
    cardinalities = load_ontology_snapshot().transitionCardinalities
    assert cardinalities.sourceQualifiedCardinality == 1
    assert cardinalities.targetQualifiedCardinality == 1
    assert cardinalities.criterionMinimumQualifiedCardinality == 1


def test_tampered_ontology_fails_hash_gate() -> None:
    source = Path("src/scaffoldctl/resources/semantic-scaffolding.ttl").read_bytes()
    tampered = source.replace(b'owl:versionInfo "1.0.0"', b'owl:versionInfo "1.0.1"')
    with pytest.raises(OntologyAuthorityError) as captured:
        verify_ontology_authority(tampered)
    assert captured.value.reason_code is ReasonCode.ONTOLOGY_HASH_MISMATCH


def test_invalid_turtle_fails_parse_gate() -> None:
    with pytest.raises(OntologyAuthorityError) as captured:
        verify_ontology_authority(b"not turtle @@@")
    assert captured.value.reason_code is ReasonCode.ONTOLOGY_PARSE_FAILED


def _ontology_bytes() -> bytes:
    return Path("src/scaffoldctl/resources/semantic-scaffolding.ttl").read_bytes()


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        (
            b'owl:versionInfo "1.0.0"',
            b'owl:versionInfo "1.0.1"',
            ReasonCode.ONTOLOGY_METADATA_DRIFT,
        ),
        (
            b"sc:Uninitialized\n        sc:Planned",
            b"sc:Planned\n        sc:Uninitialized",
            ReasonCode.ONTOLOGY_STATE_DRIFT,
        ),
        (
            b'owl:qualifiedCardinality "1"^^xsd:nonNegativeInteger',
            b'owl:qualifiedCardinality "2"^^xsd:nonNegativeInteger',
            ReasonCode.ONTOLOGY_TRANSITION_CARDINALITY_DRIFT,
        ),
        (
            b'sh:maxExclusive "100"^^xsd:nonNegativeInteger',
            b'sh:maxExclusive "99"^^xsd:nonNegativeInteger',
            ReasonCode.ONTOLOGY_SHACL_DRIFT,
        ),
    ],
)
def test_semantic_drift_is_reason_coded_after_valid_hash_pin(
    old: bytes,
    new: bytes,
    expected: ReasonCode,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tampered = _ontology_bytes().replace(old, new, 1)
    assert tampered != _ontology_bytes()
    monkeypatch.setattr(ontology, "ONTOLOGY_SHA256", hashlib.sha256(tampered).hexdigest())
    with pytest.raises(OntologyAuthorityError) as captured:
        ontology.verify_ontology_authority(tampered)
    assert captured.value.reason_code is expected


def test_malformed_shacl_integer_is_rejected() -> None:
    malformed = _ontology_bytes().replace(
        b'sh:maxExclusive "100"^^xsd:nonNegativeInteger',
        b'sh:maxExclusive "invalid"',
        1,
    )
    with pytest.raises(OntologyAuthorityError) as captured:
        load_ontology_snapshot(malformed)
    assert captured.value.reason_code is ReasonCode.ONTOLOGY_SHACL_DRIFT


def test_external_lifecycle_state_is_rejected() -> None:
    malformed = _ontology_bytes().replace(
        b"        sc:Uninitialized\n",
        b"        <urn:outside:Uninitialized>\n",
        1,
    )
    with pytest.raises(OntologyAuthorityError) as captured:
        load_ontology_snapshot(malformed)
    assert captured.value.reason_code is ReasonCode.ONTOLOGY_METADATA_DRIFT

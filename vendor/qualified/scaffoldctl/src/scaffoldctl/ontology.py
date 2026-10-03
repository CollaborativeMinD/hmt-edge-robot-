from __future__ import annotations

import hashlib
import json
from importlib.resources import files
from typing import Literal

from pydantic import Field
from rdflib import Graph, Namespace, URIRef
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, RDFS, SH, XSD

from scaffoldctl.models import StrictFrozenModel
from scaffoldctl.reason_codes import ReasonCode
from scaffoldctl.semantics import (
    HMT_MAXIMUM_LINE_COUNT_EXCLUSIVE,
    HMT_MINIMUM_LINE_COUNT,
    HMT_REQUIRED_PATHS,
    LIFECYCLE_STATE_ORDER,
    ONTOLOGY_ARTIFACT_DISPOSITION,
    ONTOLOGY_CREATED_ON,
    ONTOLOGY_IRI,
    ONTOLOGY_PROVENANCE_ID,
    ONTOLOGY_SHA256,
    ONTOLOGY_VERSION,
    ONTOLOGY_VERSION_IRI,
    SC_NAMESPACE,
    SHACL_NODE_SHAPES,
    LifecycleState,
)

SC = Namespace(SC_NAMESPACE)
ONTOLOGY_NODE = URIRef(ONTOLOGY_IRI)
RESOURCE_NAME = "semantic-scaffolding.ttl"


class OntologyAuthorityError(RuntimeError):
    def __init__(self, reason_code: ReasonCode, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


class QualifiedDocumentCardinality(StrictFrozenModel):
    className: str
    minimum: int = Field(strict=True, ge=0)
    maximum: int = Field(strict=True, ge=0)


class TransitionCardinalities(StrictFrozenModel):
    sourceQualifiedCardinality: int = Field(strict=True, ge=0)
    targetQualifiedCardinality: int = Field(strict=True, ge=0)
    criterionMinimumQualifiedCardinality: int = Field(strict=True, ge=0)


class ShaclContract(StrictFrozenModel):
    nodeShapes: tuple[str, ...]
    rootDocumentMinimum: int = Field(strict=True, ge=0)
    rootDocumentMaximum: int = Field(strict=True, ge=0)
    qualifiedDocumentCardinalities: tuple[QualifiedDocumentCardinality, ...]
    documentPathMinimum: int = Field(strict=True, ge=0)
    documentPathMaximum: int = Field(strict=True, ge=0)
    lineCountMinimumCardinality: int = Field(strict=True, ge=0)
    lineCountMaximumCardinality: int = Field(strict=True, ge=0)
    lineCountMinimumInclusive: int = Field(strict=True, ge=0)
    lineCountMaximumExclusive: int = Field(strict=True, gt=0)
    requiredPaths: tuple[str, ...]


class OntologySnapshot(StrictFrozenModel):
    ontologyIri: str
    versionIri: str
    versionInfo: str
    provenanceId: str
    artifactDisposition: str
    createdOn: str
    sourceSha256: str
    tripleCount: int = Field(strict=True, gt=0)
    lifecycleStateOrder: tuple[LifecycleState, ...]
    transitionCardinalities: TransitionCardinalities
    shacl: ShaclContract


class OntologyAuthorityReceipt(StrictFrozenModel):
    validationStatus: Literal["pass"]
    reasonCodes: tuple[ReasonCode, ...]
    ontologySha256: str
    provenanceId: str
    lifecycleStateCount: int = Field(strict=True, ge=0)
    nodeShapeCount: int = Field(strict=True, ge=0)
    receiptHash: str


def _resource_bytes() -> bytes:
    return files("scaffoldctl.resources").joinpath(RESOURCE_NAME).read_bytes()


def _exactly_one(graph: Graph, subject: object, predicate: object) -> object:
    values = tuple(graph.objects(subject, predicate))
    if len(values) != 1:
        raise OntologyAuthorityError(
            ReasonCode.ONTOLOGY_METADATA_DRIFT,
            f"expected one value for {predicate!s}; found {len(values)}",
        )
    return values[0]


def _integer(graph: Graph, subject: object, predicate: object) -> int:
    value = _exactly_one(graph, subject, predicate)
    native = value.toPython()  # type: ignore[union-attr]
    if isinstance(native, bool) or not isinstance(native, int):
        raise OntologyAuthorityError(
            ReasonCode.ONTOLOGY_SHACL_DRIFT,
            f"expected integer for {predicate!s}",
        )
    return native


def _text(graph: Graph, subject: object, predicate: object) -> str:
    return str(_exactly_one(graph, subject, predicate))


def _local_name(value: object) -> str:
    text = str(value)
    if not text.startswith(SC_NAMESPACE):
        raise OntologyAuthorityError(
            ReasonCode.ONTOLOGY_METADATA_DRIFT,
            f"resource is outside the scaffoldctl namespace: {text}",
        )
    return text.removeprefix(SC_NAMESPACE)


def _property_shape(graph: Graph, shape: object, path: object, *, qualified: bool) -> object:
    candidates = [
        node
        for node in graph.objects(shape, SH.property)
        if graph.value(node, SH.path) == path
        and ((graph.value(node, SH.qualifiedValueShape) is not None) is qualified)
    ]
    if len(candidates) != 1:
        raise OntologyAuthorityError(
            ReasonCode.ONTOLOGY_SHACL_DRIFT,
            f"expected one property shape for {path!s}; found {len(candidates)}",
        )
    return candidates[0]


def _transition_cardinalities(graph: Graph) -> TransitionCardinalities:
    restrictions: dict[object, object] = {}
    for node in graph.objects(SC.LifecycleTransition, RDFS.subClassOf):
        if (node, RDF.type, OWL.Restriction) in graph:
            restrictions[_exactly_one(graph, node, OWL.onProperty)] = node
    required = (SC.hasTransitionSource, SC.hasTransitionTarget, SC.validatesAgainst)
    if set(restrictions) != set(required):
        raise OntologyAuthorityError(
            ReasonCode.ONTOLOGY_TRANSITION_CARDINALITY_DRIFT,
            "LifecycleTransition restriction set drifted",
        )
    return TransitionCardinalities(
        sourceQualifiedCardinality=_integer(
            graph, restrictions[SC.hasTransitionSource], OWL.qualifiedCardinality
        ),
        targetQualifiedCardinality=_integer(
            graph, restrictions[SC.hasTransitionTarget], OWL.qualifiedCardinality
        ),
        criterionMinimumQualifiedCardinality=_integer(
            graph, restrictions[SC.validatesAgainst], OWL.minQualifiedCardinality
        ),
    )


def _shacl_contract(graph: Graph) -> ShaclContract:
    node_shapes = tuple(
        sorted(_local_name(node) for node in graph.subjects(RDF.type, SH.NodeShape))
    )
    root_shape = SC.RepositoryRootDirectoryShape
    root_documents = _property_shape(graph, root_shape, SC.hasHMTTrifectaDocument, qualified=False)
    qualified: list[QualifiedDocumentCardinality] = []
    for class_name in ("ReadmeDocument", "StartHereDocument", "IndexDocument"):
        matches = []
        for node in graph.objects(root_shape, SH.property):
            if graph.value(node, SH.path) != SC.hasHMTTrifectaDocument:
                continue
            value_shape = graph.value(node, SH.qualifiedValueShape)
            if value_shape is not None and graph.value(value_shape, SH["class"]) == SC[class_name]:
                matches.append(node)
        if len(matches) != 1:
            raise OntologyAuthorityError(
                ReasonCode.ONTOLOGY_SHACL_DRIFT,
                f"qualified cardinality missing for {class_name}",
            )
        qualified.append(
            QualifiedDocumentCardinality(
                className=class_name,
                minimum=_integer(graph, matches[0], SH.qualifiedMinCount),
                maximum=_integer(graph, matches[0], SH.qualifiedMaxCount),
            )
        )

    document_shape = SC.HMTTrifectaDocumentShape
    path_shape = _property_shape(graph, document_shape, SC.canonicalRelativePath, qualified=False)
    line_shape = _property_shape(graph, document_shape, SC.lineCount, qualified=False)
    if _exactly_one(graph, path_shape, SH.datatype) != XSD.string:
        raise OntologyAuthorityError(ReasonCode.ONTOLOGY_SHACL_DRIFT, "path datatype drifted")
    if _exactly_one(graph, line_shape, SH.datatype) != XSD.nonNegativeInteger:
        raise OntologyAuthorityError(ReasonCode.ONTOLOGY_SHACL_DRIFT, "line datatype drifted")

    paths: list[str] = []
    for shape in (SC.ReadmeDocumentShape, SC.StartHereDocumentShape, SC.IndexDocumentShape):
        node = _property_shape(graph, shape, SC.canonicalRelativePath, qualified=False)
        paths.append(_text(graph, node, SH.hasValue))

    return ShaclContract(
        nodeShapes=node_shapes,
        rootDocumentMinimum=_integer(graph, root_documents, SH.minCount),
        rootDocumentMaximum=_integer(graph, root_documents, SH.maxCount),
        qualifiedDocumentCardinalities=tuple(qualified),
        documentPathMinimum=_integer(graph, path_shape, SH.minCount),
        documentPathMaximum=_integer(graph, path_shape, SH.maxCount),
        lineCountMinimumCardinality=_integer(graph, line_shape, SH.minCount),
        lineCountMaximumCardinality=_integer(graph, line_shape, SH.maxCount),
        lineCountMinimumInclusive=0,
        lineCountMaximumExclusive=_integer(graph, line_shape, SH.maxExclusive),
        requiredPaths=tuple(paths),
    )


def load_ontology_snapshot(data: bytes | None = None) -> OntologySnapshot:
    source = _resource_bytes() if data is None else data
    source_hash = hashlib.sha256(source).hexdigest()
    try:
        graph = Graph().parse(data=source.decode("utf-8", errors="strict"), format="turtle")
    except Exception as exc:
        raise OntologyAuthorityError(ReasonCode.ONTOLOGY_PARSE_FAILED, str(exc)) from exc

    union_head = _exactly_one(graph, SC.LifecycleState, OWL.disjointUnionOf)
    state_order = tuple(LifecycleState(_local_name(node)) for node in Collection(graph, union_head))
    return OntologySnapshot(
        ontologyIri=ONTOLOGY_IRI,
        versionIri=str(_exactly_one(graph, ONTOLOGY_NODE, OWL.versionIRI)),
        versionInfo=_text(graph, ONTOLOGY_NODE, OWL.versionInfo),
        provenanceId=_text(graph, ONTOLOGY_NODE, SC.provenanceId),
        artifactDisposition=_text(graph, ONTOLOGY_NODE, SC.artifactDisposition),
        createdOn=_text(graph, ONTOLOGY_NODE, SC.createdOn),
        sourceSha256=source_hash,
        tripleCount=len(graph),
        lifecycleStateOrder=state_order,
        transitionCardinalities=_transition_cardinalities(graph),
        shacl=_shacl_contract(graph),
    )


def _raise_if(condition: bool, reason_code: ReasonCode, message: str) -> None:
    if condition:
        raise OntologyAuthorityError(reason_code, message)


def _verify_snapshot_metadata(snapshot: OntologySnapshot) -> None:
    expected = (
        ONTOLOGY_VERSION_IRI,
        ONTOLOGY_VERSION,
        ONTOLOGY_PROVENANCE_ID,
        ONTOLOGY_ARTIFACT_DISPOSITION,
        ONTOLOGY_CREATED_ON,
    )
    observed = (
        snapshot.versionIri,
        snapshot.versionInfo,
        snapshot.provenanceId,
        snapshot.artifactDisposition,
        snapshot.createdOn,
    )
    _raise_if(
        observed != expected,
        ReasonCode.ONTOLOGY_METADATA_DRIFT,
        "ontology metadata does not match compiled authority",
    )


def _verify_transition_contract(snapshot: OntologySnapshot) -> None:
    transition = snapshot.transitionCardinalities
    observed = (
        transition.sourceQualifiedCardinality,
        transition.targetQualifiedCardinality,
        transition.criterionMinimumQualifiedCardinality,
    )
    _raise_if(
        observed != (1, 1, 1),
        ReasonCode.ONTOLOGY_TRANSITION_CARDINALITY_DRIFT,
        "LifecycleTransition cardinalities do not equal 1, 1, and minimum 1",
    )


def _shacl_values(contract: ShaclContract) -> tuple[object, ...]:
    qualified = tuple(
        (item.className, item.minimum, item.maximum)
        for item in contract.qualifiedDocumentCardinalities
    )
    return (
        contract.nodeShapes,
        contract.rootDocumentMinimum,
        contract.rootDocumentMaximum,
        qualified,
        contract.documentPathMinimum,
        contract.documentPathMaximum,
        contract.lineCountMinimumCardinality,
        contract.lineCountMaximumCardinality,
        contract.lineCountMinimumInclusive,
        contract.lineCountMaximumExclusive,
        contract.requiredPaths,
    )


def _expected_shacl_values() -> tuple[object, ...]:
    qualified = (
        ("ReadmeDocument", 1, 1),
        ("StartHereDocument", 1, 1),
        ("IndexDocument", 1, 1),
    )
    return (
        SHACL_NODE_SHAPES,
        3,
        3,
        qualified,
        1,
        1,
        1,
        1,
        HMT_MINIMUM_LINE_COUNT,
        HMT_MAXIMUM_LINE_COUNT_EXCLUSIVE,
        HMT_REQUIRED_PATHS,
    )


def _authority_receipt(snapshot: OntologySnapshot) -> OntologyAuthorityReceipt:
    payload = {
        "lifecycleStateCount": len(snapshot.lifecycleStateOrder),
        "nodeShapeCount": len(snapshot.shacl.nodeShapes),
        "ontologySha256": snapshot.sourceSha256,
        "provenanceId": snapshot.provenanceId,
        "reasonCodes": (ReasonCode.AUTHORITY_VERIFIED,),
        "validationStatus": "pass",
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return OntologyAuthorityReceipt(
        **payload,
        receiptHash=hashlib.sha256(encoded.encode()).hexdigest(),
    )


def verify_ontology_authority(data: bytes | None = None) -> OntologyAuthorityReceipt:
    snapshot = load_ontology_snapshot(data)
    _raise_if(
        snapshot.sourceSha256 != ONTOLOGY_SHA256,
        ReasonCode.ONTOLOGY_HASH_MISMATCH,
        "ontology SHA-256 does not match the authority pin",
    )
    _verify_snapshot_metadata(snapshot)
    _raise_if(
        snapshot.lifecycleStateOrder != LIFECYCLE_STATE_ORDER,
        ReasonCode.ONTOLOGY_STATE_DRIFT,
        "OWL lifecycle disjoint-union order does not match compiled states",
    )
    _verify_transition_contract(snapshot)
    _raise_if(
        _shacl_values(snapshot.shacl) != _expected_shacl_values(),
        ReasonCode.ONTOLOGY_SHACL_DRIFT,
        "SHACL constraints do not match compiled Pydantic boundaries",
    )
    return _authority_receipt(snapshot)

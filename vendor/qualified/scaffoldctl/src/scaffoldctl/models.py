from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from scaffoldctl.semantics import HMT_REQUIRED_PATHS, LifecycleState, LifecycleTrigger

Iri = Annotated[
    str,
    StringConstraints(
        strict=True,
        min_length=3,
        max_length=512,
        pattern=r"^[A-Za-z][A-Za-z0-9+.-]*:[^\s]+$",
    ),
]
EvidenceId = Annotated[
    str,
    StringConstraints(strict=True, min_length=1, max_length=256, pattern=r"^[A-Za-z0-9_.:-]+$"),
]
ReasonCodeValue = Annotated[
    str,
    StringConstraints(strict=True, min_length=1, max_length=128, pattern=r"^[A-Z0-9_.:-]+$"),
]
LineCountBelow100 = Annotated[int, Field(strict=True, ge=0, lt=100)]


class StrictFrozenModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class LifecycleTransition(StrictFrozenModel):
    hasTransitionSource: LifecycleState
    hasTransitionTarget: LifecycleState
    validatesAgainst: Annotated[tuple[Iri, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def criteria_are_unique(self) -> LifecycleTransition:
        if len(set(self.validatesAgainst)) != len(self.validatesAgainst):
            raise ValueError("validatesAgainst must contain unique criterion IRIs")
        return self


class HMTTrifectaDocument(StrictFrozenModel):
    canonicalRelativePath: str
    lineCount: LineCountBelow100


class ReadmeDocument(HMTTrifectaDocument):
    canonicalRelativePath: Literal["README.md"]


class StartHereDocument(HMTTrifectaDocument):
    canonicalRelativePath: Literal["Start_here.md"]


class IndexDocument(HMTTrifectaDocument):
    canonicalRelativePath: Literal["Index.md"]


HMTDocument = Annotated[
    ReadmeDocument | StartHereDocument | IndexDocument,
    Field(discriminator="canonicalRelativePath"),
]


class RepositoryRootDirectory(StrictFrozenModel):
    hasHMTTrifectaDocument: Annotated[tuple[HMTDocument, ...], Field(min_length=3, max_length=3)]

    @model_validator(mode="after")
    def exactly_one_of_each_document(self) -> RepositoryRootDirectory:
        paths = tuple(document.canonicalRelativePath for document in self.hasHMTTrifectaDocument)
        if len(set(paths)) != 3 or set(paths) != set(HMT_REQUIRED_PATHS):
            raise ValueError("root must contain exactly one document for each HMT Trifecta path")
        return self


def physical_line_count(text: str) -> int:
    if not isinstance(text, str):
        raise TypeError("text must be str")
    return len(text.splitlines())


def document_from_text(path: str, text: str) -> HMTDocument:
    payload = {"canonicalRelativePath": path, "lineCount": physical_line_count(text)}
    if path == "README.md":
        return ReadmeDocument.model_validate(payload)
    if path == "Start_here.md":
        return StartHereDocument.model_validate(payload)
    if path == "Index.md":
        return IndexDocument.model_validate(payload)
    raise ValueError(f"unsupported HMT Trifecta path: {path!r}")


class CriterionEvidence(StrictFrozenModel):
    criterionIri: Iri
    evidenceId: EvidenceId
    admitted: bool


class ReopeningAuthorization(StrictFrozenModel):
    authorizationId: EvidenceId
    targetState: LifecycleState
    reasonCode: ReasonCodeValue
    authorized: Literal[True]


class TransitionRequest(StrictFrozenModel):
    trigger: LifecycleTrigger
    criteria: Annotated[tuple[CriterionEvidence, ...], Field(min_length=1)]
    reopeningAuthorization: ReopeningAuthorization | None = None

    @model_validator(mode="after")
    def criteria_are_unique(self) -> TransitionRequest:
        identifiers = tuple(item.criterionIri for item in self.criteria)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("criteria must contain unique criterion IRIs")
        return self


class TransitionReceipt(StrictFrozenModel):
    transition: LifecycleTransition | None
    trigger: LifecycleTrigger
    transitionAdmitted: bool
    fromState: LifecycleState
    toState: LifecycleState
    reasonCodes: Annotated[tuple[ReasonCodeValue, ...], Field(min_length=1)]
    evidenceIds: tuple[EvidenceId, ...]
    receiptHash: Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$")]


class ContractValidationReceipt(StrictFrozenModel):
    validationStatus: Literal["pass", "fail"]
    reasonCodes: Annotated[tuple[ReasonCodeValue, ...], Field(min_length=1)]
    modelName: str
    payloadSha256: Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$")]
    errorCount: int = Field(strict=True, ge=0)
    errors: tuple[str, ...]

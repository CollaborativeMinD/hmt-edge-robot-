import json

import pytest
from pydantic import ValidationError

from scaffoldctl.models import (
    IndexDocument,
    LifecycleTransition,
    ReadmeDocument,
    RepositoryRootDirectory,
    StartHereDocument,
    document_from_text,
    physical_line_count,
)
from scaffoldctl.semantics import LifecycleState


def _valid_root_payload(line_count: int = 99) -> dict[str, object]:
    return {
        "hasHMTTrifectaDocument": [
            {"canonicalRelativePath": "README.md", "lineCount": line_count},
            {"canonicalRelativePath": "Start_here.md", "lineCount": line_count},
            {"canonicalRelativePath": "Index.md", "lineCount": line_count},
        ]
    }


def test_line_count_domain_accepts_zero_and_99() -> None:
    assert ReadmeDocument(canonicalRelativePath="README.md", lineCount=0).lineCount == 0
    assert ReadmeDocument(canonicalRelativePath="README.md", lineCount=99).lineCount == 99


@pytest.mark.parametrize("invalid", [-1, 100, True, 1.0, "1"])
def test_line_count_domain_rejects_out_of_range_or_non_strict_values(invalid: object) -> None:
    with pytest.raises(ValidationError):
        ReadmeDocument.model_validate({"canonicalRelativePath": "README.md", "lineCount": invalid})


def test_root_accepts_exact_trifecta_from_json() -> None:
    root = RepositoryRootDirectory.model_validate_json(json.dumps(_valid_root_payload()))
    assert tuple(type(item) for item in root.hasHMTTrifectaDocument) == (
        ReadmeDocument,
        StartHereDocument,
        IndexDocument,
    )


def test_root_rejects_duplicate_document_type() -> None:
    payload = _valid_root_payload()
    payload["hasHMTTrifectaDocument"] = [
        {"canonicalRelativePath": "README.md", "lineCount": 1},
        {"canonicalRelativePath": "README.md", "lineCount": 1},
        {"canonicalRelativePath": "Index.md", "lineCount": 1},
    ]
    with pytest.raises(ValidationError):
        RepositoryRootDirectory.model_validate_json(json.dumps(payload))


def test_root_rejects_wrong_case_and_extra_fields() -> None:
    payload = _valid_root_payload()
    payload["hasHMTTrifectaDocument"][0]["canonicalRelativePath"] = "Readme.md"  # type: ignore[index]
    with pytest.raises(ValidationError):
        RepositoryRootDirectory.model_validate_json(json.dumps(payload))
    payload = _valid_root_payload()
    payload["unexpected"] = True
    with pytest.raises(ValidationError):
        RepositoryRootDirectory.model_validate_json(json.dumps(payload))


def test_transition_requires_one_source_target_and_criterion() -> None:
    transition = LifecycleTransition(
        hasTransitionSource=LifecycleState.UNINITIALIZED,
        hasTransitionTarget=LifecycleState.PLANNED,
        validatesAgainst=("urn:scaffoldctl:criterion:phase-zero-admitted",),
    )
    assert transition.hasTransitionSource is LifecycleState.UNINITIALIZED
    with pytest.raises(ValidationError):
        LifecycleTransition(
            hasTransitionSource=LifecycleState.UNINITIALIZED,
            hasTransitionTarget=LifecycleState.PLANNED,
            validatesAgainst=(),
        )


def test_transition_rejects_duplicate_criteria_and_unknown_fields() -> None:
    criterion = "urn:scaffoldctl:criterion:phase-zero-admitted"
    with pytest.raises(ValidationError):
        LifecycleTransition(
            hasTransitionSource=LifecycleState.UNINITIALIZED,
            hasTransitionTarget=LifecycleState.PLANNED,
            validatesAgainst=(criterion, criterion),
        )
    with pytest.raises(ValidationError):
        LifecycleTransition.model_validate(
            {
                "hasTransitionSource": LifecycleState.UNINITIALIZED,
                "hasTransitionTarget": LifecycleState.PLANNED,
                "validatesAgainst": (criterion,),
                "extra": "rejected",
            }
        )


def test_physical_line_count_and_typed_document_factory() -> None:
    assert physical_line_count("") == 0
    assert physical_line_count("one\n") == 1
    assert isinstance(document_from_text("Index.md", "one\ntwo\n"), IndexDocument)
    with pytest.raises(TypeError):
        physical_line_count(b"not text")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        document_from_text("index.md", "")

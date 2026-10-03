from pathlib import Path

import scaffoldctl.validation as validation_module
from scaffoldctl.exceptions import PhaseTwoError
from scaffoldctl.phase2_models import (
    BoundarySpec,
    EntryKind,
    PolicyDocumentRule,
    SnapshotEntry,
)
from scaffoldctl.policy import boundary_policy_bytes, load_policy_pack, render_boundary
from scaffoldctl.reason_codes import ReasonCode
from scaffoldctl.snapshot import WorktreeSnapshot
from scaffoldctl.validation import validate_boundary, validate_document


def _boundary(target: str = "target") -> BoundarySpec:
    return BoundarySpec(
        boundaryId="target",
        targetPath=target,
        title="Target",
        purpose="Validate failure paths.",
    )


def _readme_rule() -> PolicyDocumentRule:
    return load_policy_pack().requiredDocuments[0]


def _validate_readme(root: Path) -> ReasonCode:
    finding, _ = validate_document(
        WorktreeSnapshot(root),
        "target",
        _readme_rule(),
        load_policy_pack().unresolvedPlaceholderTokens,
        load_policy_pack().maximumDocumentUtf8Bytes,
    )
    return finding.reasonCodes[0]


def test_document_validator_rejects_symlink_directory_and_invalid_utf8(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    readme = target / "README.md"
    readme.symlink_to(tmp_path / "missing")
    assert _validate_readme(tmp_path) is ReasonCode.PATH_SYMLINK_REJECTED
    readme.unlink()
    readme.mkdir()
    assert _validate_readme(tmp_path) is ReasonCode.DOCUMENT_NOT_FILE
    readme.rmdir()
    readme.write_bytes(b"\xff")
    assert _validate_readme(tmp_path) is ReasonCode.DOCUMENT_UTF8_INVALID


def test_document_validator_rejects_line_heading_placeholder_and_schema(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    readme = target / "README.md"
    readme.write_text("line\n" * 100, encoding="utf-8")
    assert _validate_readme(tmp_path) is ReasonCode.LINE_COUNT_INVALID
    readme.write_text("# Title\n\n## Purpose\n", encoding="utf-8")
    assert _validate_readme(tmp_path) is ReasonCode.DOCUMENT_HEADING_INVALID
    readme.write_text(
        "# Title\n\n## Purpose\n\n## Lifecycle\n\n## Invariants\n\n## Authority\n",
        encoding="utf-8",
    )
    assert _validate_readme(tmp_path) is ReasonCode.DOCUMENT_SECTION_EMPTY
    readme.write_text(
        (
            "# Title\n\n## Purpose\nText\n\n## Purpose\nText\n\n"
            "## Lifecycle\nText\n\n## Invariants\nText\n\n## Authority\nText\n"
        ),
        encoding="utf-8",
    )
    assert _validate_readme(tmp_path) is ReasonCode.DOCUMENT_HEADING_INVALID
    rendered = render_boundary(_boundary())["README.md"].decode("utf-8")
    readme.write_text(f"{rendered}\n${{OPEN}}\n", encoding="utf-8")
    assert _validate_readme(tmp_path) is ReasonCode.PLACEHOLDER_UNRESOLVED
    other = target / "Other.md"
    other.write_text("# Other\n\n## Required\n", encoding="utf-8")
    rule = PolicyDocumentRule(
        canonicalRelativePath="Other.md",
        maximumLineCountExclusive=100,
        requiredHeadings=("## Required",),
    )
    finding, _ = validate_document(
        WorktreeSnapshot(tmp_path),
        "target",
        rule,
        ("${",),
        65536,
    )
    assert finding.reasonCodes == (ReasonCode.SCHEMA_INVALID,)


class _ReadFailureSnapshot:
    root = Path("/")

    def kind(self, relative_path: str) -> EntryKind:
        return EntryKind.FILE

    def entry(self, relative_path: str, *, include_hash: bool = True) -> SnapshotEntry:
        return SnapshotEntry(relativePath=relative_path, kind=EntryKind.FILE, sizeBytes=1)

    def read_bytes(self, relative_path: str, *, maximum_bytes: int | None = None) -> bytes:
        raise PhaseTwoError(ReasonCode.DOCUMENT_NOT_FILE, "injected")

    def list_dir(self, relative_path: str) -> tuple[str, ...]:
        return ()

    def list_entries(self, relative_path: str) -> tuple[tuple[str, EntryKind], ...]:
        return ()


class _UnknownSizeSnapshot(_ReadFailureSnapshot):
    def entry(self, relative_path: str, *, include_hash: bool = True) -> SnapshotEntry:
        return SnapshotEntry(relativePath=relative_path, kind=EntryKind.FILE)


def test_document_validator_maps_snapshot_read_and_unknown_size_failures() -> None:
    finding, _ = validate_document(
        _ReadFailureSnapshot(),
        ".",
        _readme_rule(),
        ("${",),
        65536,
    )
    assert finding.reasonCodes == (ReasonCode.DOCUMENT_NOT_FILE,)
    finding, _ = validate_document(
        _UnknownSizeSnapshot(),
        ".",
        _readme_rule(),
        ("${",),
        65536,
    )
    assert finding.reasonCodes == (ReasonCode.DOCUMENT_SIZE_INVALID,)


def test_policy_validator_rejects_symlink_directory_invalid_and_boundary_drift(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    policy = target / "scaffold.policy.json"
    policy.symlink_to(tmp_path / "missing")
    outcome = validate_boundary(WorktreeSnapshot(tmp_path), "target")
    assert ReasonCode.PATH_SYMLINK_REJECTED in outcome.reason_codes
    policy.unlink()
    policy.mkdir()
    outcome = validate_boundary(WorktreeSnapshot(tmp_path), "target")
    assert ReasonCode.POLICY_INVALID in outcome.reason_codes
    policy.rmdir()
    policy.write_text("not-json", encoding="utf-8")
    outcome = validate_boundary(WorktreeSnapshot(tmp_path), "target")
    assert ReasonCode.POLICY_INVALID in outcome.reason_codes
    policy.write_bytes(boundary_policy_bytes(_boundary("other")))
    outcome = validate_boundary(WorktreeSnapshot(tmp_path), "target")
    assert ReasonCode.POLICY_AUTHORITY_DRIFT in outcome.reason_codes


def test_boundary_validator_rejects_file_symlink_and_transaction_remnant(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.write_text("file", encoding="utf-8")
    outcome = validate_boundary(WorktreeSnapshot(tmp_path), "target")
    assert outcome.reason_codes[0] is ReasonCode.TARGET_TYPE_INVALID
    target.unlink()
    target.symlink_to(tmp_path, target_is_directory=True)
    outcome = validate_boundary(WorktreeSnapshot(tmp_path), "target")
    assert outcome.reason_codes[0] is ReasonCode.PATH_SYMLINK_REJECTED
    target.unlink()
    target.mkdir()
    remnant = target / ".scaffoldctl-orphan.tmp"
    remnant.write_text("orphan", encoding="utf-8")
    outcome = validate_boundary(WorktreeSnapshot(tmp_path), "target")
    assert ReasonCode.TEMPORARY_ARTIFACT_PRESENT in outcome.reason_codes
    admitted = validate_boundary(
        WorktreeSnapshot(tmp_path),
        "target",
        admitted_temporary_names=(remnant.name,),
    )
    assert ReasonCode.TEMPORARY_ARTIFACT_PRESENT not in admitted.reason_codes


def test_expected_boundary_mismatch_is_rejected(tmp_path: Path) -> None:
    actual = _boundary()
    rendered = render_boundary(actual)
    target = tmp_path / actual.targetPath
    target.mkdir()
    for name, data in rendered.items():
        (target / name).write_bytes(data)
    expected = BoundarySpec(
        boundaryId="other",
        targetPath=actual.targetPath,
        title="Other",
        purpose="Different declared boundary.",
    )
    outcome = validate_boundary(
        WorktreeSnapshot(tmp_path),
        actual.targetPath,
        expected_boundary=expected,
    )
    assert ReasonCode.POLICY_AUTHORITY_DRIFT in outcome.reason_codes


def test_boundary_validation_loads_one_policy_snapshot(tmp_path: Path, monkeypatch: object) -> None:
    boundary = _boundary()
    target = tmp_path / boundary.targetPath
    target.mkdir()
    for name, data in render_boundary(boundary).items():
        (target / name).write_bytes(data)
    original = validation_module.load_policy_pack
    calls = 0

    def counted_load_policy_pack() -> object:
        nonlocal calls
        calls += 1
        return original()

    monkeypatch.setattr(validation_module, "load_policy_pack", counted_load_policy_pack)
    assert validate_boundary(WorktreeSnapshot(tmp_path), boundary.targetPath).admitted
    assert calls == 1

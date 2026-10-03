from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Protocol

from scaffoldctl.confinement import (
    ConfinedRoot,
    canonical_repository_root,
    collision_key,
    entry_kind,
)
from scaffoldctl.exceptions import PhaseTwoError
from scaffoldctl.integrity import hash_payload, sha256_bytes
from scaffoldctl.phase2_models import (
    EntryKind,
    SnapshotEntry,
    canonical_artifact_path,
    canonical_target_path,
)
from scaffoldctl.reason_codes import ReasonCode


class RepositorySnapshot(Protocol):
    root: Path

    def kind(self, relative_path: str) -> EntryKind: ...

    def read_bytes(self, relative_path: str, *, maximum_bytes: int | None = None) -> bytes: ...

    def list_dir(self, relative_path: str) -> tuple[str, ...]: ...

    def list_entries(self, relative_path: str) -> tuple[tuple[str, EntryKind], ...]: ...

    def entry(self, relative_path: str, *, include_hash: bool = True) -> SnapshotEntry: ...


class WorktreeSnapshot:
    def __init__(self, root: str | Path) -> None:
        self.root = canonical_repository_root(root)
        self._confined = ConfinedRoot(self.root)

    @staticmethod
    def _validate_relative(relative_path: str) -> str:
        try:
            return (
                canonical_target_path(relative_path)
                if relative_path == "."
                else canonical_artifact_path(relative_path)
            )
        except (TypeError, ValueError) as exc:
            reason = (
                ReasonCode.PATH_ABSOLUTE
                if str(relative_path).startswith("/")
                else ReasonCode.PATH_TRAVERSAL
            )
            raise PhaseTwoError(reason, "snapshot path is not canonical") from exc

    def kind(self, relative_path: str) -> EntryKind:
        self._validate_relative(relative_path)
        observed = self._confined.stat(relative_path)
        return EntryKind.MISSING if observed is None else entry_kind(observed.st_mode)

    def _open_file(self, relative_path: str) -> int:
        self._validate_relative(relative_path)
        return self._confined.open_file(relative_path)

    def read_bytes(self, relative_path: str, *, maximum_bytes: int | None = None) -> bytes:
        self._validate_relative(relative_path)
        return self._confined.read_file(relative_path, maximum_bytes=maximum_bytes)

    def list_dir(self, relative_path: str) -> tuple[str, ...]:
        return tuple(name for name, _ in self.list_entries(relative_path))

    def list_entries(self, relative_path: str) -> tuple[tuple[str, EntryKind], ...]:
        kind = self.kind(relative_path)
        if kind is EntryKind.MISSING:
            return ()
        if kind is not EntryKind.DIRECTORY:
            raise PhaseTwoError(ReasonCode.PATH_TYPE_INVALID, "path is not a directory")
        return self._confined.list_entries(relative_path)

    def _sha256_file(self, relative_path: str) -> str:
        self._validate_relative(relative_path)
        return self._confined.hash_file(relative_path)

    def entry(self, relative_path: str, *, include_hash: bool = True) -> SnapshotEntry:
        kind = self.kind(relative_path)
        if kind is EntryKind.MISSING:
            return SnapshotEntry(relativePath=relative_path, kind=kind)
        observed = self._confined.stat(relative_path)
        size = observed.st_size if observed is not None and kind is EntryKind.FILE else None
        digest = (
            self._sha256_file(relative_path) if kind is EntryKind.FILE and include_hash else None
        )
        return SnapshotEntry(relativePath=relative_path, kind=kind, sizeBytes=size, sha256=digest)


class OverlaySnapshot:
    def __init__(self, base: RepositorySnapshot, overlay: Mapping[str, bytes]) -> None:
        self.root = base.root
        self._base = base
        try:
            self._overlay = {
                canonical_artifact_path(path): bytes(data) for path, data in overlay.items()
            }
        except (TypeError, ValueError) as exc:
            raise PhaseTwoError(ReasonCode.PATH_TRAVERSAL, "overlay path is invalid") from exc
        self._directories = self._overlay_directories()

    def _overlay_directories(self) -> set[str]:
        directories: set[str] = {"."}
        for path in self._overlay:
            parent = PurePosixPath(path).parent
            while str(parent) != ".":
                directories.add(str(parent))
                parent = parent.parent
        return directories

    def kind(self, relative_path: str) -> EntryKind:
        if relative_path in self._overlay:
            return EntryKind.FILE
        if relative_path in self._directories:
            base_kind = self._base.kind(relative_path)
            return EntryKind.DIRECTORY if base_kind is EntryKind.MISSING else base_kind
        return self._base.kind(relative_path)

    def read_bytes(self, relative_path: str, *, maximum_bytes: int | None = None) -> bytes:
        if relative_path not in self._overlay:
            return self._base.read_bytes(relative_path, maximum_bytes=maximum_bytes)
        data = self._overlay[relative_path]
        if maximum_bytes is not None and len(data) > maximum_bytes:
            raise PhaseTwoError(ReasonCode.DOCUMENT_SIZE_INVALID, "document exceeds byte budget")
        return data

    def list_dir(self, relative_path: str) -> tuple[str, ...]:
        return tuple(name for name, _ in self.list_entries(relative_path))

    def list_entries(self, relative_path: str) -> tuple[tuple[str, EntryKind], ...]:
        entries = dict(self._base.list_entries(relative_path))
        prefix = "" if relative_path == "." else f"{relative_path}/"
        for path in (*self._overlay, *self._directories):
            if path == ".":
                continue
            if path.startswith(prefix):
                remainder = path.removeprefix(prefix)
                if remainder and "/" not in remainder:
                    if path in self._overlay:
                        entries[remainder] = EntryKind.FILE
                    else:
                        entries.setdefault(remainder, EntryKind.DIRECTORY)
        ordered = tuple(sorted(entries.items(), key=lambda item: item[0].casefold()))
        keys = tuple(collision_key(name) for name, _ in ordered)
        if len(set(keys)) != len(keys):
            raise PhaseTwoError(ReasonCode.PATH_CASE_COLLISION, "overlay contains name collision")
        return ordered

    def entry(self, relative_path: str, *, include_hash: bool = True) -> SnapshotEntry:
        if relative_path not in self._overlay:
            return self._base.entry(relative_path, include_hash=include_hash)
        data = self._overlay[relative_path]
        return SnapshotEntry(
            relativePath=relative_path,
            kind=EntryKind.FILE,
            sizeBytes=len(data),
            sha256=sha256_bytes(data) if include_hash else None,
        )


def snapshot_digest(
    snapshot: RepositorySnapshot,
    target_path: str,
    governed_paths: tuple[str, ...],
    *,
    ignored_names: tuple[str, ...] = (),
) -> str:
    ignored = set(ignored_names)
    direct_entries = tuple(
        {"kind": kind.value, "name": name}
        for name, kind in snapshot.list_entries(target_path)
        if name not in ignored
    )
    payload = {
        "directEntries": direct_entries,
        "governedEntries": tuple(
            snapshot.entry(path, include_hash=True).model_dump(mode="json")
            for path in governed_paths
        ),
        "targetKind": snapshot.kind(target_path).value,
        "targetPath": target_path,
    }
    return hash_payload(payload)

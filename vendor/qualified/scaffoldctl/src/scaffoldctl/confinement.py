from __future__ import annotations

import hashlib
import os
import stat
import unicodedata
from pathlib import Path, PurePosixPath

from scaffoldctl.exceptions import PhaseTwoError
from scaffoldctl.phase2_models import (
    EntryKind,
    canonical_artifact_path,
    canonical_target_path,
)
from scaffoldctl.reason_codes import ReasonCode

DIRECTORY_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
FILE_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
REQUIRED_DIRECTORY_OPERATIONS = (os.open, os.stat, os.mkdir, os.rmdir, os.unlink, os.link)


def platform_capabilities_available() -> bool:
    return (
        os.name == "posix"
        and all(operation in os.supports_dir_fd for operation in REQUIRED_DIRECTORY_OPERATIONS)
        and os.scandir in os.supports_fd
    )


def collision_key(name: str) -> str:
    return unicodedata.normalize("NFKC", name).casefold()


def canonical_repository_root(root: str | Path) -> Path:
    absolute = Path(os.path.abspath(Path(root)))
    chain = (*reversed(absolute.parents), absolute)
    try:
        for candidate in chain:
            if candidate.is_symlink():
                raise PhaseTwoError(ReasonCode.ROOT_INVALID, "repository root crosses a symlink")
        mode = absolute.lstat().st_mode
    except OSError as exc:
        raise PhaseTwoError(ReasonCode.ROOT_INVALID, "repository root is unavailable") from exc
    if not stat.S_ISDIR(mode):
        raise PhaseTwoError(ReasonCode.ROOT_INVALID, "repository root is not a directory")
    return absolute


def entry_kind(mode: int) -> EntryKind:
    if stat.S_ISLNK(mode):
        return EntryKind.SYMLINK
    if stat.S_ISREG(mode):
        return EntryKind.FILE
    if stat.S_ISDIR(mode):
        return EntryKind.DIRECTORY
    return EntryKind.OTHER


class ConfinedRoot:
    def __init__(self, root: str | Path) -> None:
        if not platform_capabilities_available():
            raise PhaseTwoError(
                ReasonCode.PLATFORM_UNSUPPORTED,
                "required directory-relative filesystem operations are unavailable",
            )
        self.root = canonical_repository_root(root)
        root_stat = self.root.lstat()
        self._identity = (root_stat.st_dev, root_stat.st_ino)

    @staticmethod
    def _canonical(relative_path: str, *, root_allowed: bool) -> str:
        try:
            return (
                canonical_target_path(relative_path)
                if root_allowed
                else canonical_artifact_path(relative_path)
            )
        except (TypeError, ValueError) as exc:
            reason = (
                ReasonCode.PATH_ABSOLUTE
                if str(relative_path).startswith("/")
                else ReasonCode.PATH_TRAVERSAL
            )
            raise PhaseTwoError(reason, "confined path is not canonical") from exc

    def open_root(self) -> int:
        try:
            descriptor = os.open(self.root, DIRECTORY_FLAGS)
        except OSError as exc:
            raise PhaseTwoError(
                ReasonCode.ROOT_INVALID, "repository root cannot be opened"
            ) from exc
        try:
            observed = os.fstat(descriptor)
        except OSError as exc:
            os.close(descriptor)
            raise PhaseTwoError(
                ReasonCode.ROOT_INVALID, "repository root identity cannot be read"
            ) from exc
        if (observed.st_dev, observed.st_ino) != self._identity:
            os.close(descriptor)
            raise PhaseTwoError(ReasonCode.ROOT_INVALID, "repository root identity changed")
        return descriptor

    @staticmethod
    def fsync_directory(descriptor: int) -> None:
        os.fsync(descriptor)

    @staticmethod
    def _matching_name(descriptor: int, expected: str) -> str | None:
        try:
            with os.scandir(descriptor) as iterator:
                matches = tuple(
                    entry.name
                    for entry in iterator
                    if collision_key(entry.name) == collision_key(expected)
                )
        except OSError as exc:
            raise PhaseTwoError(ReasonCode.PATH_TYPE_INVALID, "directory is unreadable") from exc
        if len(matches) > 1 or (matches and matches[0] != expected):
            raise PhaseTwoError(ReasonCode.PATH_CASE_COLLISION, "path spelling collision detected")
        return matches[0] if matches else None

    def open_directory(
        self,
        relative_path: str,
        *,
        create: bool = False,
        created_paths: list[str] | None = None,
    ) -> int | None:
        canonical = self._canonical(relative_path, root_allowed=True)
        descriptor = self.open_root()
        if canonical == ".":
            return descriptor
        prefix: list[str] = []
        try:
            for part in PurePosixPath(canonical).parts:
                prefix.append(part)
                match = self._matching_name(descriptor, part)
                if match is None:
                    if not create:
                        os.close(descriptor)
                        return None
                    os.mkdir(part, mode=0o755, dir_fd=descriptor)
                    self.fsync_directory(descriptor)
                    if created_paths is not None:
                        created_paths.append(PurePosixPath(*prefix).as_posix())
                observed = os.stat(part, dir_fd=descriptor, follow_symlinks=False)
                if stat.S_ISLNK(observed.st_mode):
                    raise PhaseTwoError(
                        ReasonCode.PATH_SYMLINK_REJECTED,
                        "symlink directory rejected",
                    )
                if not stat.S_ISDIR(observed.st_mode):
                    raise PhaseTwoError(
                        ReasonCode.PATH_TYPE_INVALID,
                        "path parent is not a directory",
                    )
                child = os.open(part, DIRECTORY_FLAGS, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = child
        except PhaseTwoError:
            os.close(descriptor)
            raise
        except OSError as exc:
            os.close(descriptor)
            raise PhaseTwoError(
                ReasonCode.PATH_SYMLINK_REJECTED,
                "directory traversal failed closed",
            ) from exc
        return descriptor

    def open_parent(
        self,
        relative_path: str,
        *,
        create: bool = False,
        created_paths: list[str] | None = None,
    ) -> tuple[int | None, str]:
        canonical = self._canonical(relative_path, root_allowed=False)
        path = PurePosixPath(canonical)
        parent = path.parent.as_posix()
        descriptor = self.open_directory(
            parent,
            create=create,
            created_paths=created_paths,
        )
        return descriptor, path.name

    def stat(self, relative_path: str) -> os.stat_result | None:
        if relative_path == ".":
            descriptor = self.open_root()
            try:
                return os.fstat(descriptor)
            finally:
                os.close(descriptor)
        parent, name = self.open_parent(relative_path)
        if parent is None:
            return None
        try:
            match = self._matching_name(parent, name)
            if match is None:
                return None
            return os.stat(name, dir_fd=parent, follow_symlinks=False)
        except OSError as exc:
            raise PhaseTwoError(ReasonCode.PATH_TYPE_INVALID, "path stat failed") from exc
        finally:
            os.close(parent)

    def open_file(self, relative_path: str) -> int:
        parent, name = self.open_parent(relative_path)
        if parent is None:
            raise PhaseTwoError(ReasonCode.DOCUMENT_NOT_FILE, "document parent is missing")
        try:
            match = self._matching_name(parent, name)
            if match is None:
                raise PhaseTwoError(ReasonCode.DOCUMENT_NOT_FILE, "document is missing")
            observed = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if stat.S_ISLNK(observed.st_mode):
                raise PhaseTwoError(ReasonCode.PATH_SYMLINK_REJECTED, "symlink document rejected")
            if not stat.S_ISREG(observed.st_mode):
                raise PhaseTwoError(ReasonCode.DOCUMENT_NOT_FILE, "document is not a regular file")
            descriptor = os.open(name, FILE_FLAGS, dir_fd=parent)
        except PhaseTwoError:
            raise
        except OSError as exc:
            raise PhaseTwoError(
                ReasonCode.DOCUMENT_NOT_FILE, "document could not be opened"
            ) from exc
        finally:
            os.close(parent)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            raise PhaseTwoError(ReasonCode.DOCUMENT_NOT_FILE, "document is not a regular file")
        return descriptor

    def read_file(self, relative_path: str, *, maximum_bytes: int | None = None) -> bytes:
        descriptor = self.open_file(relative_path)
        try:
            size = os.fstat(descriptor).st_size
        except OSError as exc:
            os.close(descriptor)
            raise PhaseTwoError(
                ReasonCode.DOCUMENT_NOT_FILE, "document size could not be read"
            ) from exc
        if maximum_bytes is not None and size > maximum_bytes:
            os.close(descriptor)
            raise PhaseTwoError(ReasonCode.DOCUMENT_SIZE_INVALID, "document exceeds byte budget")
        with os.fdopen(descriptor, "rb") as stream:
            return stream.read()

    def hash_file(self, relative_path: str) -> str:
        descriptor = self.open_file(relative_path)
        digest = hashlib.sha256()
        with os.fdopen(descriptor, "rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def list_entries(self, relative_path: str) -> tuple[tuple[str, EntryKind], ...]:
        descriptor = self.open_directory(relative_path)
        if descriptor is None:
            return ()
        try:
            with os.scandir(descriptor) as iterator:
                entries = tuple(
                    sorted(
                        (
                            (entry.name, entry_kind(entry.stat(follow_symlinks=False).st_mode))
                            for entry in iterator
                        ),
                        key=lambda item: item[0].casefold(),
                    )
                )
        except OSError as exc:
            raise PhaseTwoError(ReasonCode.PATH_TYPE_INVALID, "directory is unreadable") from exc
        finally:
            os.close(descriptor)
        keys = tuple(collision_key(name) for name, _ in entries)
        if len(set(keys)) != len(keys):
            raise PhaseTwoError(ReasonCode.PATH_CASE_COLLISION, "directory contains name collision")
        return entries

    def remove_directory(self, relative_path: str) -> None:
        parent, name = self.open_parent(relative_path)
        if parent is None:
            raise FileNotFoundError(relative_path)
        try:
            os.rmdir(name, dir_fd=parent)
            self.fsync_directory(parent)
        finally:
            os.close(parent)

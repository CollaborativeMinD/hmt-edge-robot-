from __future__ import annotations

import os
import secrets
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from scaffoldctl.confinement import ConfinedRoot
from scaffoldctl.exceptions import PhaseTwoError, TransactionError
from scaffoldctl.phase2_models import canonical_artifact_path
from scaffoldctl.reason_codes import ReasonCode


@dataclass(slots=True)
class StagedLink:
    parent_fd: int
    parent_relative: str
    temporary_name: str
    final_name: str
    final_relative: str
    inode_identity: tuple[int, int]
    published: bool = False


@dataclass(slots=True)
class CommitRecord:
    root: Path
    confined: ConfinedRoot
    links: tuple[StagedLink, ...]
    created_directories: tuple[str, ...]
    finalized: bool = False

    @property
    def created_paths(self) -> tuple[str, ...]:
        return tuple(link.final_relative for link in self.links if link.published)

    @property
    def temporary_names(self) -> tuple[str, ...]:
        return tuple(link.temporary_name for link in self.links)

    @property
    def staged_pairs(self) -> tuple[tuple[Path, Path], ...]:
        return tuple(
            (
                self.root / link.parent_relative / link.temporary_name,
                self.root / link.final_relative,
            )
            for link in self.links
        )

    @staticmethod
    def _stat_or_none(name: str, descriptor: int) -> os.stat_result | None:
        try:
            return os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        except FileNotFoundError:
            return None

    def finalize(self) -> None:
        if self.finalized:
            return
        for link in self.links:
            os.unlink(link.temporary_name, dir_fd=link.parent_fd)
            self.confined.fsync_directory(link.parent_fd)
        for link in self.links:
            os.close(link.parent_fd)
            link.parent_fd = -1
        self.finalized = True

    def _rollback_link(self, link: StagedLink) -> bool:
        if link.parent_fd < 0:
            return False
        complete = True
        try:
            temporary = self._stat_or_none(link.temporary_name, link.parent_fd)
            final = self._stat_or_none(link.final_name, link.parent_fd)
            if link.published and final is not None:
                same_inode = link.inode_identity == (final.st_dev, final.st_ino)
                if same_inode:
                    os.unlink(link.final_name, dir_fd=link.parent_fd)
                else:
                    complete = False
            if temporary is not None:
                os.unlink(link.temporary_name, dir_fd=link.parent_fd)
            self.confined.fsync_directory(link.parent_fd)
        except OSError:
            complete = False
        finally:
            os.close(link.parent_fd)
            link.parent_fd = -1
        return complete

    def rollback(self) -> bool:
        complete = True
        for link in reversed(self.links):
            if not self._rollback_link(link):
                complete = False
        for directory in reversed(self.created_directories):
            try:
                self.confined.remove_directory(directory)
            except (OSError, PhaseTwoError):
                complete = False
        self.finalized = True
        return complete


class AtomicBatchWriter:
    def __init__(self, root: str | Path) -> None:
        self.confined = ConfinedRoot(root)
        self.root = self.confined.root

    @staticmethod
    def _stage(parent_fd: int, data: bytes) -> str:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = -1
        name = ""
        for _ in range(32):
            name = f".scaffoldctl-{secrets.token_hex(16)}.tmp"
            try:
                descriptor = os.open(name, flags, 0o644, dir_fd=parent_fd)
                break
            except FileExistsError:
                continue
        if descriptor < 0:
            raise OSError("unable to allocate exclusive transaction file")
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            with suppress(OSError):
                os.unlink(name, dir_fd=parent_fd)
            raise
        return name

    def _publish(self, link: StagedLink) -> None:
        if self.confined._matching_name(link.parent_fd, link.final_name) is not None:
            raise PhaseTwoError(
                ReasonCode.EXISTING_CONTENT_PRESERVED,
                "exclusive publish refused an existing path",
            )
        os.link(
            link.temporary_name,
            link.final_name,
            src_dir_fd=link.parent_fd,
            dst_dir_fd=link.parent_fd,
            follow_symlinks=False,
        )
        link.published = True
        self.confined.fsync_directory(link.parent_fd)

    def _stage_link(
        self,
        relative_path: str,
        data: bytes,
        created_directories: list[str],
    ) -> StagedLink:
        parent_fd, final_name = self.confined.open_parent(
            relative_path,
            create=True,
            created_paths=created_directories,
        )
        if parent_fd is None:  # pragma: no cover - create=True guarantees a descriptor
            raise PhaseTwoError(ReasonCode.PATH_TYPE_INVALID, "artifact parent is unavailable")
        try:
            if self.confined._matching_name(parent_fd, final_name) is not None:
                raise PhaseTwoError(
                    ReasonCode.EXISTING_CONTENT_PRESERVED,
                    "exclusive publish refused an existing path",
                )
            temporary_name = self._stage(parent_fd, data)
            observed = os.stat(temporary_name, dir_fd=parent_fd, follow_symlinks=False)
        except Exception:
            os.close(parent_fd)
            raise
        return StagedLink(
            parent_fd=parent_fd,
            parent_relative=PurePosixPath(relative_path).parent.as_posix(),
            temporary_name=temporary_name,
            final_name=final_name,
            final_relative=relative_path,
            inode_identity=(observed.st_dev, observed.st_ino),
        )

    def commit(self, artifacts: dict[str, bytes]) -> CommitRecord:
        canonical = tuple(
            (canonical_artifact_path(path), bytes(data)) for path, data in artifacts.items()
        )
        created_directories: list[str] = []
        links: list[StagedLink] = []
        try:
            for relative_path, data in canonical:
                links.append(self._stage_link(relative_path, data, created_directories))
            for link in links:
                self._publish(link)
            return CommitRecord(
                self.root,
                self.confined,
                tuple(links),
                tuple(created_directories),
            )
        except Exception as exc:
            record = CommitRecord(
                self.root,
                self.confined,
                tuple(links),
                tuple(created_directories),
            )
            complete = record.rollback()
            raise TransactionError(
                "atomic no-overwrite batch publish failed",
                rollback_complete=complete,
                created_paths=tuple(link.final_relative for link in links if link.published),
                error_class=type(exc).__name__,
            ) from exc

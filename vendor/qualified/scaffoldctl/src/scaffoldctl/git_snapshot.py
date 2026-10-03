from __future__ import annotations

import os
import subprocess
from pathlib import Path, PurePosixPath

from pydantic import ValidationError

from scaffoldctl.confinement import canonical_repository_root, collision_key
from scaffoldctl.exceptions import PhaseThreeError
from scaffoldctl.integrity import hash_payload, sha256_bytes
from scaffoldctl.phase2_models import EntryKind, SnapshotEntry
from scaffoldctl.phase3_models import (
    GitObjectEntry,
    GitObjectFormat,
    GitObjectMatrix,
    GitSnapshotSource,
    canonical_git_path,
)
from scaffoldctl.reason_codes import ReasonCode

_MATRIX_FORMAT = "%(objectmode) %(objecttype) %(objectname) %(objectsize) %(stage)%x09%(path)"
_TREE_FORMAT = "%(objectmode) %(objecttype) %(objectname) %(objectsize)%x09%(path)"
_ZERO = b""


class GitRepository:
    def __init__(self, root: str | Path) -> None:
        requested = canonical_repository_root(root)
        discovered = self._bootstrap(requested, ("rev-parse", "--show-toplevel"))
        try:
            discovered_root = canonical_repository_root(discovered.decode("utf-8").strip())
        except (UnicodeDecodeError, PhaseThreeError, OSError) as exc:
            raise PhaseThreeError(
                ReasonCode.GIT_DISCOVERY_FAILED,
                "Git repository root is invalid",
                exit_code=1,
            ) from exc
        if discovered_root != requested:
            raise PhaseThreeError(
                ReasonCode.GIT_DISCOVERY_FAILED,
                "--root must identify the Git repository top level",
                exit_code=1,
            )
        self.root = discovered_root
        git_dir_raw = self._bootstrap(requested, ("rev-parse", "--absolute-git-dir"))
        try:
            git_dir_text = git_dir_raw.decode("utf-8", errors="strict").strip()
            git_dir = Path(git_dir_text)
            if not git_dir.is_absolute() or not git_dir.is_dir() or git_dir.is_symlink():
                raise ValueError("invalid Git directory")
        except (UnicodeDecodeError, OSError, ValueError) as exc:
            raise PhaseThreeError(
                ReasonCode.GIT_DISCOVERY_FAILED,
                "Git directory is invalid",
                exit_code=1,
            ) from exc
        self.git_dir = git_dir
        format_raw = self._run(("rev-parse", "--show-object-format=storage"))
        try:
            self.object_format = GitObjectFormat(format_raw.decode("ascii").strip())
        except (UnicodeDecodeError, ValueError) as exc:
            raise PhaseThreeError(
                ReasonCode.GIT_DISCOVERY_FAILED,
                "Git object format is unsupported",
                exit_code=1,
            ) from exc
        self._blob_cache: dict[str, bytes] = {}

    @staticmethod
    def _safe_environment() -> dict[str, str]:
        environment = {
            key: value for key, value in os.environ.items() if not key.startswith("GIT_")
        }
        environment.update(
            {
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_NO_REPLACE_OBJECTS": "1",
                "GIT_OPTIONAL_LOCKS": "0",
                "GIT_TERMINAL_PROMPT": "0",
                "LANG": "C",
                "LC_ALL": "C",
            }
        )
        return environment

    @classmethod
    def _bootstrap(cls, root: Path, arguments: tuple[str, ...]) -> bytes:
        try:
            result = subprocess.run(
                ("git", "-C", os.fspath(root), *arguments),
                check=False,
                capture_output=True,
                env=cls._safe_environment(),
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise PhaseThreeError(
                ReasonCode.GIT_DISCOVERY_FAILED,
                "Git discovery command failed",
                exit_code=1,
            ) from exc
        if result.returncode != 0:
            raise PhaseThreeError(
                ReasonCode.GIT_DISCOVERY_FAILED,
                "Git discovery rejected the repository",
                exit_code=1,
            )
        return result.stdout

    def _run(self, arguments: tuple[str, ...], *, input_bytes: bytes | None = None) -> bytes:
        result = self._run_status(arguments, input_bytes=input_bytes)
        if result.returncode != 0:
            raise PhaseThreeError(
                ReasonCode.GIT_COMMAND_FAILED,
                "Git object command returned a nonzero status",
                exit_code=1,
            )
        return result.stdout

    def _run_status(
        self,
        arguments: tuple[str, ...],
        *,
        input_bytes: bytes | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        environment = self._safe_environment()
        environment["GIT_INDEX_FILE"] = os.fspath(self.git_dir / "index")
        command = (
            "git",
            "--git-dir",
            os.fspath(self.git_dir),
            "--work-tree",
            os.fspath(self.root),
            *arguments,
        )
        try:
            result = subprocess.run(
                command,
                input=input_bytes,
                check=False,
                capture_output=True,
                env=environment,
                timeout=60,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise PhaseThreeError(
                ReasonCode.GIT_COMMAND_FAILED,
                "Git object command failed",
                exit_code=1,
            ) from exc
        return result

    def resolve_tree(self, treeish: str) -> str:
        if (
            not treeish
            or len(treeish) > 256
            or any(char.isspace() or ord(char) < 32 for char in treeish)
        ):
            raise PhaseThreeError(
                ReasonCode.GIT_REVISION_INVALID,
                "tree revision is malformed",
                exit_code=1,
            )
        try:
            output = self._run(("rev-parse", "--verify", "--end-of-options", f"{treeish}^{{tree}}"))
            object_id = output.decode("ascii", errors="strict").strip()
        except (PhaseThreeError, UnicodeDecodeError) as exc:
            raise PhaseThreeError(
                ReasonCode.GIT_REVISION_INVALID,
                "tree revision cannot be resolved",
                exit_code=1,
            ) from exc
        expected_length = 40 if self.object_format is GitObjectFormat.SHA1 else 64
        if len(object_id) != expected_length or any(
            char not in "0123456789abcdef" for char in object_id
        ):
            raise PhaseThreeError(
                ReasonCode.GIT_REVISION_INVALID,
                "resolved tree object id is invalid",
                exit_code=1,
            )
        return object_id

    def read_blob(self, entry: GitObjectEntry, *, maximum_bytes: int | None = None) -> bytes:
        if entry.objectType != "blob":
            raise PhaseThreeError(
                ReasonCode.GIT_OBJECT_TYPE_INVALID,
                "requested Git object is not a blob",
                exit_code=1,
            )
        if (
            maximum_bytes is not None
            and entry.objectSize is not None
            and entry.objectSize > maximum_bytes
        ):
            raise PhaseThreeError(
                ReasonCode.DOCUMENT_SIZE_INVALID,
                "Git blob exceeds the byte budget",
                exit_code=1,
            )
        cached = self._blob_cache.get(entry.objectId)
        if cached is not None:
            return cached
        output = self._run(("cat-file", "--batch"), input_bytes=f"{entry.objectId}\n".encode())
        header_end = output.find(b"\n")
        if header_end < 0:
            raise PhaseThreeError(
                ReasonCode.GIT_OBJECT_MISSING,
                "Git object response is incomplete",
                exit_code=1,
            )
        header = output[:header_end].split(b" ")
        if len(header) != 3 or header[1] != b"blob":
            raise PhaseThreeError(
                ReasonCode.GIT_OBJECT_TYPE_INVALID,
                "Git object response is not a blob",
                exit_code=1,
            )
        try:
            observed_id = header[0].decode("ascii")
            size = int(header[2])
        except (UnicodeDecodeError, ValueError) as exc:
            raise PhaseThreeError(
                ReasonCode.GIT_OBJECT_MISSING,
                "Git object response header is invalid",
                exit_code=1,
            ) from exc
        start = header_end + 1
        end = start + size
        data = output[start:end]
        if (
            observed_id != entry.objectId
            or size != entry.objectSize
            or len(data) != size
            or output[end:] != b"\n"
        ):
            raise PhaseThreeError(
                ReasonCode.GIT_OBJECT_MISSING,
                "Git object response does not match the matrix",
                exit_code=1,
            )
        self._blob_cache[entry.objectId] = data
        return data

    def capture_index_matrix(self) -> GitObjectMatrix:
        output = self._run(
            ("ls-files", "--cached", "--full-name", "-z", f"--format={_MATRIX_FORMAT}")
        )
        entries = _parse_matrix_records(output, include_stage=True)
        return _make_matrix(
            GitSnapshotSource.INDEX,
            "INDEX",
            self.object_format,
            entries,
        )

    def capture_tree_matrix(self, treeish: str) -> GitObjectMatrix:
        tree_id = self.resolve_tree(treeish)
        output = self._run(
            (
                "ls-tree",
                "-r",
                "-z",
                "--full-tree",
                f"--format={_TREE_FORMAT}",
                tree_id,
            )
        )
        entries = _parse_matrix_records(output, include_stage=False)
        return _make_matrix(
            GitSnapshotSource.TREE,
            tree_id,
            self.object_format,
            entries,
        )

    def capture_optional_head_matrix(self) -> GitObjectMatrix | None:
        resolved = self._run_status(("rev-parse", "--verify", "--end-of-options", "HEAD^{tree}"))
        if resolved.returncode == 0:
            try:
                tree_id = resolved.stdout.decode("ascii", errors="strict").strip()
            except UnicodeDecodeError as exc:
                raise PhaseThreeError(
                    ReasonCode.GIT_REVISION_INVALID,
                    "HEAD tree object id is invalid",
                    exit_code=1,
                ) from exc
            return self.capture_tree_matrix(tree_id)
        symbolic = self._run_status(("symbolic-ref", "--quiet", "HEAD"))
        if symbolic.returncode != 0:
            raise PhaseThreeError(
                ReasonCode.GIT_REVISION_INVALID,
                "HEAD is neither a commit nor an unborn branch",
                exit_code=1,
            )
        try:
            branch = symbolic.stdout.decode("utf-8", errors="strict").strip()
        except UnicodeDecodeError as exc:
            raise PhaseThreeError(
                ReasonCode.GIT_REVISION_INVALID,
                "unborn branch reference is invalid",
                exit_code=1,
            ) from exc
        if not branch.startswith("refs/heads/"):
            raise PhaseThreeError(
                ReasonCode.GIT_REVISION_INVALID,
                "unborn HEAD does not reference a local branch",
                exit_code=1,
            )
        present = self._run_status(("show-ref", "--verify", "--quiet", branch))
        if present.returncode == 1:
            return None
        raise PhaseThreeError(
            ReasonCode.GIT_REVISION_INVALID,
            "HEAD reference discovery failed closed",
            exit_code=1,
        )


def _parse_matrix_records(data: bytes, *, include_stage: bool) -> tuple[GitObjectEntry, ...]:
    entries: list[GitObjectEntry] = []
    for record in data.split(b"\0"):
        if record == _ZERO:
            continue
        metadata, separator, raw_path = record.partition(b"\t")
        expected_fields = 5 if include_stage else 4
        fields = metadata.split(b" ")
        if separator != b"\t" or len(fields) != expected_fields:
            raise PhaseThreeError(
                ReasonCode.GIT_MATRIX_INVALID,
                "Git object matrix record is malformed",
                exit_code=1,
            )
        try:
            mode = fields[0].decode("ascii", errors="strict")
            object_type = fields[1].decode("ascii", errors="strict")
            object_id = fields[2].decode("ascii", errors="strict")
            size = None if fields[3] == b"-" else int(fields[3])
            stage = int(fields[4]) if include_stage else 0
            path = raw_path.decode("utf-8", errors="strict")
        except (UnicodeDecodeError, ValueError) as exc:
            raise PhaseThreeError(
                ReasonCode.GIT_MATRIX_INVALID,
                "Git object matrix contains an invalid field",
                exit_code=1,
            ) from exc
        if stage != 0:
            raise PhaseThreeError(
                ReasonCode.GIT_INDEX_UNMERGED,
                "unmerged Git index stages are not admissible",
                exit_code=1,
            )
        try:
            entries.append(
                GitObjectEntry(
                    relativePath=path,
                    objectMode=mode,
                    objectType=object_type,
                    objectId=object_id,
                    objectSize=size,
                    stage=0,
                )
            )
        except ValidationError as exc:
            reason = (
                ReasonCode.GIT_OBJECT_MODE_INVALID
                if mode not in {"100644", "100755", "120000", "160000"}
                else ReasonCode.GIT_PATH_INVALID
            )
            raise PhaseThreeError(
                reason, "Git object matrix violates its schema", exit_code=1
            ) from exc
    return tuple(sorted(entries, key=lambda entry: entry.relativePath.encode("utf-8")))


def _make_matrix(
    source: GitSnapshotSource,
    source_ref: str,
    object_format: GitObjectFormat,
    entries: tuple[GitObjectEntry, ...],
) -> GitObjectMatrix:
    entries_payload = tuple(entry.model_dump(mode="json") for entry in entries)
    content_hash = hash_payload(entries_payload)
    matrix_hash = hash_payload(
        {
            "contentMatrixSha256": content_hash,
            "objectFormat": object_format,
            "sourceKind": source,
            "sourceRef": source_ref,
        }
    )
    try:
        return GitObjectMatrix(
            schemaId="urn:scaffoldctl:schema:git-object-matrix:0.3.0",
            schemaVersion="0.3.0",
            sourceKind=source,
            sourceRef=source_ref,
            objectFormat=object_format,
            entryCount=len(entries),
            entries=entries,
            contentMatrixSha256=content_hash,
            matrixSha256=matrix_hash,
        )
    except ValidationError as exc:
        raise PhaseThreeError(
            ReasonCode.GIT_MATRIX_INVALID,
            "Git object matrix is not canonical",
            exit_code=1,
        ) from exc


class GitObjectSnapshot:
    def __init__(self, repository: GitRepository, matrix: GitObjectMatrix) -> None:
        self.root = repository.root
        self.repository = repository
        self.matrix = matrix
        self._entries = {entry.relativePath: entry for entry in matrix.entries}
        self._directories = {"."}
        for path in self._entries:
            parent = PurePosixPath(path).parent
            while str(parent) != ".":
                self._directories.add(parent.as_posix())
                parent = parent.parent

    @classmethod
    def from_index(cls, root: str | Path) -> GitObjectSnapshot:
        repository = GitRepository(root)
        return cls(repository, repository.capture_index_matrix())

    @classmethod
    def from_tree(cls, root: str | Path, treeish: str) -> GitObjectSnapshot:
        repository = GitRepository(root)
        return cls(repository, repository.capture_tree_matrix(treeish))

    @staticmethod
    def _canonical_path(relative_path: str) -> str:
        if relative_path == ".":
            return relative_path
        try:
            return canonical_git_path(relative_path)
        except (TypeError, ValueError) as exc:
            raise PhaseThreeError(
                ReasonCode.GIT_PATH_INVALID,
                "snapshot path is invalid",
                exit_code=1,
            ) from exc

    def kind(self, relative_path: str) -> EntryKind:
        canonical = self._canonical_path(relative_path)
        entry = self._entries.get(canonical)
        if entry is not None:
            if entry.objectMode == "120000":
                return EntryKind.SYMLINK
            if entry.objectMode == "160000":
                return EntryKind.OTHER
            return EntryKind.FILE
        return EntryKind.DIRECTORY if canonical in self._directories else EntryKind.MISSING

    def read_bytes(self, relative_path: str, *, maximum_bytes: int | None = None) -> bytes:
        canonical = self._canonical_path(relative_path)
        entry = self._entries.get(canonical)
        if entry is None or self.kind(canonical) is not EntryKind.FILE:
            raise PhaseThreeError(
                ReasonCode.DOCUMENT_NOT_FILE,
                "Git snapshot path is not a regular blob",
                exit_code=1,
            )
        return self.repository.read_blob(entry, maximum_bytes=maximum_bytes)

    def list_dir(self, relative_path: str) -> tuple[str, ...]:
        return tuple(name for name, _ in self.list_entries(relative_path))

    def list_entries(self, relative_path: str) -> tuple[tuple[str, EntryKind], ...]:
        canonical = self._canonical_path(relative_path)
        if self.kind(canonical) is EntryKind.MISSING:
            return ()
        if self.kind(canonical) is not EntryKind.DIRECTORY:
            raise PhaseThreeError(
                ReasonCode.PATH_TYPE_INVALID,
                "Git snapshot path is not a directory",
                exit_code=1,
            )
        prefix = "" if canonical == "." else f"{canonical}/"
        children: dict[str, EntryKind] = {}
        for path in (*self._entries, *self._directories):
            if path == "." or not path.startswith(prefix):
                continue
            remainder = path.removeprefix(prefix)
            if not remainder or "/" in remainder:
                continue
            children[remainder] = self.kind(path)
        ordered = tuple(sorted(children.items(), key=lambda item: item[0].encode("utf-8")))
        keys = tuple(collision_key(name) for name, _ in ordered)
        if len(set(keys)) != len(keys):
            raise PhaseThreeError(
                ReasonCode.PATH_CASE_COLLISION,
                "Git snapshot directory contains a spelling collision",
                exit_code=1,
            )
        return ordered

    def entry(self, relative_path: str, *, include_hash: bool = True) -> SnapshotEntry:
        canonical = self._canonical_path(relative_path)
        kind = self.kind(canonical)
        entry = self._entries.get(canonical)
        size = entry.objectSize if entry is not None and kind is EntryKind.FILE else None
        digest = None
        if include_hash and entry is not None and kind is EntryKind.FILE:
            digest = sha256_bytes(self.repository.read_blob(entry))
        return SnapshotEntry(relativePath=canonical, kind=kind, sizeBytes=size, sha256=digest)

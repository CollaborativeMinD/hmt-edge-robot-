"""Effect conformance is bounded by explicit observation coverage, never by a tool receipt."""

from __future__ import annotations

import hashlib
from pathlib import Path

from ..contracts import digest
from .contracts import AssuranceReport, Effect, EffectContract, EffectTrace
from .kernel import AssuranceKernel, witnessed


class UndeclaredSideEffectAttestor:
    def __init__(self, kernel: AssuranceKernel):
        self.kernel = kernel

    @witnessed
    def attest(self, contract: EffectContract, trace: EffectTrace) -> AssuranceReport:
        allowed = {(e.kind, e.target) for e in contract.allowed}
        violations = [e for e in trace.observed if (e.kind, e.target) not in allowed]
        scope = self.kernel.scope(
            contract.executable_id,
            contract.executable_hash,
            contract,
            trace.collector_id,
            trace.started_at,
            contract.witness_ttl_sec,
            tuple(trace.coverage),
        )
        reasons = tuple(sorted({"UNDECLARED_" + e.kind.upper() + "_ACCESS" for e in violations}))
        if (
            violations
            or trace.runtime_sec > contract.max_runtime_sec
            or trace.exit_code not in contract.allowed_exit_codes
        ):
            verdict = "SIDE_EFFECT_OUTSIDE_CONTRACT"
            reasons += ("EXECUTION_BOUNDARY_VIOLATION",)
        elif (
            trace.origin != "SOFTWARE_COLLECTED"
            or not trace.complete
            or not set(contract.required_coverage).issubset(trace.coverage)
            or trace.executable_hash != contract.executable_hash
            or trace.epochs != scope.epochs
            or not self.kernel.valid(scope)
        ):
            verdict, reasons = (
                "ATTESTATION_INCOMPLETE",
                ("COVERAGE_IDENTITY_OR_FRESHNESS_INCOMPLETE",),
            )
        else:
            verdict, reasons = (
                "DECLARED_EFFECT_CONFIRMED",
                ("EFFECTS_CONFORM_WITHIN_DECLARED_COVERAGE",),
            )
        return AssuranceReport(
            component="USEA",
            scope=scope,
            verdict=verdict,
            reason_codes=reasons,
            artifact_refs=trace.artifact_refs,
            observation_hash=digest(trace.model_dump(mode="json")),
            metrics=(
                ("runtime_sec", trace.runtime_sec),
                ("observed_effect_count", float(len(trace.observed))),
            ),
        )


def file_manifest(root: Path, max_files: int = 256, max_bytes: int = 16_777_216) -> dict[str, str]:
    """Bounded regular-file snapshot; cannot observe reads, transient writes, sockets or processes."""
    if (
        type(max_files) is not int
        or not 1 <= max_files <= 1024
        or type(max_bytes) is not int
        or not 1 <= max_bytes <= 16_777_216
    ):
        raise ValueError("MANIFEST_BOUNDS_INVALID")
    root = root.resolve(strict=True)
    result, total, visited = {}, 0, 0
    import os
    import stat

    # Directory descriptors anchor traversal; final open refuses links and special files.
    for directory, dirs, files, descriptor in os.fwalk(root, follow_symlinks=False):
        for name in dirs + files:
            visited += 1
            info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            if visited > max_files * 2 or stat.S_ISLNK(info.st_mode):
                raise ValueError("MANIFEST_INCOMPLETE")
        for name in sorted(files):
            if len(result) >= max_files:
                raise ValueError("MANIFEST_INCOMPLETE")
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
            with os.fdopen(fd, "rb") as handle:
                if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                    raise ValueError("MANIFEST_INCOMPLETE")
                data = handle.read(max_bytes - total + 1)
            total += len(data)
            if total > max_bytes:
                raise ValueError("MANIFEST_BYTE_BOUND_EXCEEDED")
            path = Path(directory) / name
            result[path.relative_to(root).as_posix()] = hashlib.sha256(data).hexdigest()
    return result


def manifest_effects(before: dict[str, str], after: dict[str, str]) -> tuple[Effect, ...]:
    if len(before) > 256 or len(after) > 256:
        raise ValueError("MANIFEST_DIFF_BOUND_EXCEEDED")
    return tuple(
        Effect(kind="write", target=path)
        for path in sorted(before.keys() | after.keys())
        if before.get(path) != after.get(path)
    )

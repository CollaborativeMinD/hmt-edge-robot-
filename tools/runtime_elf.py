"""Resolve trusted build artifacts' ELF dependencies; missing libraries fail closed."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from appliance_process import run


def dependencies(output: str) -> set[Path]:
    if "not found" in output:
        raise ValueError("RUNTIME_LIBRARY_MISSING")
    paths = set()
    for line in output.splitlines():
        match = re.search(r"(?:=>\s+|^\s*)(/\S+)\s+\(", line)
        if match:
            paths.add(Path(match[1]))
    return paths


def closure(files: list[Path]) -> set[Path]:
    result: set[Path] = set()
    pending = list(files)
    examined: set[Path] = set()
    while pending:
        file = pending.pop().resolve(strict=True)
        if file in examined or not file.is_file():
            continue
        examined.add(file)
        with file.open("rb") as stream:
            if stream.read(4) != b"\x7fELF":
                continue
        try:
            linked = dependencies(run(["/usr/bin/ldd", str(file)]).decode())
        except subprocess.CalledProcessError as exc:
            raise ValueError("RUNTIME_ELF_INSPECTION_FAILED: " + str(file)) from exc
        result.update(linked)
        pending.extend(linked)
    return result

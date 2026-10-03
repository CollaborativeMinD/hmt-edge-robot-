from __future__ import annotations

import os
import subprocess
from pathlib import Path

from scaffoldctl.phase2_models import BoundarySpec
from scaffoldctl.policy import render_boundary


def git(root: Path, *arguments: str, input_bytes: bytes | None = None) -> bytes:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update({"GIT_CONFIG_NOSYSTEM": "1", "LC_ALL": "C"})
    result = subprocess.run(
        ("git", "-C", os.fspath(root), *arguments),
        input=input_bytes,
        check=False,
        capture_output=True,
        env=environment,
        timeout=30,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr.decode("utf-8", errors="replace"))
    return result.stdout


def write_boundary(root: Path, target: str = ".", *, boundary_id: str = "root") -> None:
    boundary = BoundarySpec(
        boundaryId=boundary_id,
        targetPath=target,
        title=f"Boundary {boundary_id}",
        purpose=f"Own semantic perimeter {boundary_id}",
    )
    directory = root if target == "." else root.joinpath(*target.split("/"))
    directory.mkdir(parents=True, exist_ok=True)
    for name, data in render_boundary(boundary).items():
        directory.joinpath(name).write_bytes(data)


def init_repository(root: Path, *, commit: bool = True, nested: bool = False) -> None:
    root.mkdir()
    git(root, "init", "--quiet")
    git(root, "config", "user.email", "scaffoldctl@example.invalid")
    git(root, "config", "user.name", "scaffoldctl crucible")
    write_boundary(root)
    if nested:
        write_boundary(root, "docs/system", boundary_id="system")
    git(root, "add", "--all")
    if commit:
        git(root, "commit", "--quiet", "-m", "baseline")

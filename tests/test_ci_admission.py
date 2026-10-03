"""Negative admission and lock freshness regressions."""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

import pytest
from ci_admission import ROOT, evaluate, main


def copy_admission(tmp_path: Path) -> Path:
    policy = json.loads((ROOT / "policy/ci_admission.json").read_text())
    names = ["policy/ci_admission.json", *policy["files"], *policy["qualified_sources"]]
    names.extend(candidate["path"] for candidate in policy["candidates"])
    for name in names:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    return tmp_path


def test_ci_admission_and_candidates_remain_hold(tmp_path: Path) -> None:
    root = copy_admission(tmp_path)
    assert main(root) == 0
    receipt = json.loads((root / "evidence/ci/admission.json").read_text())
    assert receipt["status"] == "PASS" and receipt["alert"] is False
    assert all(candidate["status"] == "HOLD" for candidate in receipt["candidates"])
    assert receipt["target"]["deployment"] == "HOLD"


@pytest.mark.parametrize("name", ["uv.lock", "tools/validate.py", ".github/workflows/ci.yml",
                                 "vendor/qualified/scaffoldctl/src/scaffoldctl/models.py"])
def test_ci_admission_denies_tampering(tmp_path: Path, name: str) -> None:
    root = copy_admission(tmp_path)
    with (root / name).open("a") as stream:
        stream.write("\n# tampered\n")
    assert main(root) == 1
    receipt = json.loads((root / "evidence/ci/admission.json").read_text())
    assert receipt["alert"] is True and "DIGEST_MISMATCH" in receipt["reason_codes"][0]


@pytest.mark.parametrize("mutation", ["candidate", "escape", "unknown", "version", "missing", "duplicate", "type", "tools"])
def test_ci_admission_denies_invalid_policy(tmp_path: Path, mutation: str) -> None:
    root = copy_admission(tmp_path)
    path = root / "policy/ci_admission.json"
    policy = json.loads(path.read_text())
    if mutation == "candidate":
        policy["candidates"][0]["status"] = "ADMITTED"
    elif mutation == "escape":
        policy["files"]["../outside"] = "0" * 64
    elif mutation == "unknown":
        policy["extra"] = True
    elif mutation == "version":
        policy["tools"]["ruff"] = "0.0.0"
    elif mutation == "duplicate":
        policy["candidates"][1] = policy["candidates"][0]
    elif mutation == "type":
        policy["candidates"][0]["reason"] = True
    elif mutation == "tools":
        policy["tools"] = list(policy["tools"])
    else:
        (root / "uv.lock").unlink()
    path.write_text(json.dumps(policy))
    assert main(root) == 1


def test_ci_admission_denies_link(tmp_path: Path) -> None:
    root = copy_admission(tmp_path)
    lock = root / "uv.lock"
    lock.unlink()
    lock.symlink_to(ROOT / "uv.lock")
    with pytest.raises(ValueError, match="SYMLINK"):
        evaluate(root)


def test_uv_stale_lock_denied_without_rewrite(tmp_path: Path) -> None:
    for name in ("pyproject.toml", "uv.lock"):
        shutil.copyfile(ROOT / name, tmp_path / name)
    project = tmp_path / "pyproject.toml"
    project.write_text(project.read_text().replace('version = "1.0.0"', 'version = "1.0.1"'))
    before = (tmp_path / "uv.lock").read_bytes()

    async def check() -> int | None:
        process = await asyncio.create_subprocess_exec(
            "uv", "lock", "--check", "--offline", cwd=tmp_path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
        try:
            await asyncio.wait_for(process.communicate(), 15)
        except TimeoutError:
            process.kill()
            await process.communicate()
            raise
        return process.returncode

    assert asyncio.run(check()) != 0
    assert (tmp_path / "uv.lock").read_bytes() == before

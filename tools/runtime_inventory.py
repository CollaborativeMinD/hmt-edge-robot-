"""Preserve genuine Debian metadata for every shipped system-library owner."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


def owners(files: set[Path], database: Path) -> set[str]:
    wanted = {file.resolve(strict=True) for file in files}
    packages = set()
    covered = set()
    for listing in (database / "info").glob("*.list"):
        for name in listing.read_text().splitlines():
            file = Path(name)
            if file.is_file() and file.resolve() in wanted:
                packages.add(listing.stem)
                covered.add(file.resolve())
    if covered != wanted:
        raise ValueError("RUNTIME_LIBRARY_OWNER_MISSING")
    return packages


def inventory(root: Path, files: set[Path], database: Path) -> None:
    packages = owners(files, database) | {"base-files", "ca-certificates"}
    paragraphs = []
    for stanza in (database / "status").read_text().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in stanza.splitlines() if ": " in line and not line.startswith(" "))
        name = fields.get("Package", "")
        if name in packages or name + ":" + fields.get("Architecture", "") in packages:
            paragraphs.append(stanza)
    if len(paragraphs) != len(packages):
        raise ValueError("RUNTIME_PACKAGE_METADATA_MISSING")
    destination = root / "var/lib/dpkg"
    (destination / "info").mkdir(parents=True)
    (destination / "status").write_text("\n\n".join(paragraphs) + "\n\n")
    for package in sorted(packages):
        copyright_file = Path("/usr/share/doc") / package.split(":", 1)[0] / "copyright"
        if copyright_file.is_file():
            target = root / copyright_file.relative_to("/")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(copyright_file, target)
        for file in (database / "info").glob(package + ".*"):
            if file.suffix in {".copyright", ".md5sums"}:
                shutil.copyfile(file, destination / "info" / file.name)
        listing = database / "info" / (package + ".list")
        shipped = [name for name in listing.read_text().splitlines() if name.startswith("/") and (root / name.lstrip("/")).is_file()]
        (destination / "info" / listing.name).write_text("\n".join(shipped) + "\n")
    records = [{"path": str(file), "sha256": hashlib.sha256(file.read_bytes()).hexdigest()} for file in sorted(files)]
    target = root / "usr/share/hmt"
    target.mkdir(parents=True)
    (target / "runtime-libraries.json").write_text(json.dumps({"packages": sorted(packages), "libraries": records}, indent=2) + "\n")

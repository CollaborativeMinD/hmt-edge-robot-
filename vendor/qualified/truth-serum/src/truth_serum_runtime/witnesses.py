"""External witness command contracts."""

from __future__ import annotations

from pathlib import Path

from .files import relative, repository_files

TOOLS = ("ruff", "pylint", "mypy", "bandit", "semgrep", "yamllint", "pytest", "pip-audit")


def has_target(tool: str, root: Path) -> bool:
    if tool == "pytest":
        return any((root / "tests").rglob("test_*.py"))
    if tool == "yamllint":
        return any(root.rglob("*.yml")) or any(root.rglob("*.yaml"))
    if tool == "pip-audit":
        return (root / "pyproject.toml").is_file()
    return any((root / "src").rglob("*.py")) or (root / "truth_serum.py").is_file()


def command(tool: str, root: Path, out: Path) -> list[str]:
    source = ["src", "truth_serum.py", "tools"]
    commands = {
        "ruff": ["ruff", "check", "--no-cache", "."],
        "pylint": [
            "pylint",
            "--persistent=n",
            "--reports=n",
            "--score=n",
            "--disable=all",
            "--enable=E,F,W",
            *source,
        ],
        "mypy": ["mypy", *source],
        "bandit": [
            "bandit",
            "-q",
            "-ll",
            "-r",
            "src",
            "truth_serum.py",
            "tools",
            "-f",
            "json",
        ],
        "semgrep": [
            "semgrep",
            "--metrics=off",
            "--disable-version-check",
            "--json",
            "--error",
            "--config",
            "src/truth_serum_runtime/witness_rules.yml",
            ".",
        ],
        "yamllint": [
            "yamllint",
            "-d",
            "{extends: default, rules: {line-length: disable, "
            "document-start: disable, truthy: disable}}",
            *_yaml_targets(root, out),
        ],
        "pytest": ["pytest", "-q", "-p", "no:cacheprovider"],
        "pip-audit": [
            "pip-audit",
            "--local",
            "--format",
            "json",
            "--progress-spinner",
            "off",
            "--timeout",
            "15",
        ],
    }
    return commands[tool]


def _yaml_targets(root: Path, out: Path) -> list[str]:
    suffixes = {".yaml", ".yml"}
    return [
        relative(path, root)
        for path in repository_files(root, out)
        if path.suffix.lower() in suffixes
    ]

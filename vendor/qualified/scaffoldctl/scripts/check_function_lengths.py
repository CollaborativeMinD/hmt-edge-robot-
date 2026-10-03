from __future__ import annotations

import ast
from pathlib import Path

MAX_FUNCTION_LINES = 60
ROOT = Path(__file__).resolve().parents[1]


def _violations() -> tuple[str, ...]:
    violations: list[str] = []
    for source_root in (ROOT / "src", ROOT / "scripts", ROOT / "adapters"):
        for path in sorted(source_root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    line_count = (node.end_lineno or node.lineno) - node.lineno + 1
                    if line_count > MAX_FUNCTION_LINES:
                        relative = path.relative_to(ROOT).as_posix()
                        violations.append(f"{relative}:{node.lineno}:{node.name}:{line_count}")
    return tuple(violations)


def main() -> int:
    violations = _violations()
    if violations:
        print("\n".join(violations))
        return 1
    print(f"PASS: production functions <= {MAX_FUNCTION_LINES} lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

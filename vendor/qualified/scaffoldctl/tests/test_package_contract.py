import ast
import os
from pathlib import Path

from scaffoldctl.models import document_from_text


def test_repository_trifecta_meets_ontology_line_budget() -> None:
    for path in ("README.md", "Start_here.md", "Index.md"):
        document = document_from_text(path, Path(path).read_text(encoding="utf-8"))
        assert 0 <= document.lineCount < 100


def test_inherited_prototype_sources_are_excluded() -> None:
    packaged = {path.name for path in Path("src").rglob("*") if path.is_file()}
    assert "Scaffolding Engine.py" not in packaged
    assert "Pre-Commit.py" not in packaged
    assert "Pre-Commit.sh" not in packaged


def test_delivery_adapters_are_present_and_executable() -> None:
    paths = (
        Path("src/scaffoldctl/resources/git_perimeter/pre-commit"),
        Path("scripts/seal_ledger.py"),
    )
    assert all(path.is_file() and os.access(path, os.X_OK) for path in paths)
    assert Path(".github/workflows/scaffoldctl-perimeter.yml").is_file()


def test_operational_orchestration_documents_are_present() -> None:
    assert Path("Agents.md.md").is_file()
    assert Path("Humans.md").is_file()


def test_production_functions_respect_sixty_line_limit() -> None:
    violations: list[str] = []
    for root in (Path("src"), Path("scripts"), Path("adapters")):
        for path in sorted(root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    lines = (node.end_lineno or node.lineno) - node.lineno + 1
                    if lines > 60:
                        violations.append(f"{path}:{node.lineno}:{node.name}:{lines}")
    assert violations == []

"""JSON and YAML contract checks."""

from __future__ import annotations

import json
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from ..files import relative, repository_files
from ..lanes import lane
from ..models import Finding, LaneReport, LaneStatus
from .data_parse import NonfiniteError, load


def run(root: Path, out: Path) -> LaneReport:
    suffixes = {".json", ".yaml", ".yml"}
    paths = [path for path in repository_files(root, out) if path.suffix.lower() in suffixes]
    if not paths:
        return lane(
            "structured-data",
            LaneStatus.NOT_APPLICABLE,
            "local",
            ("NOT_APPLICABLE_STRUCTURED_DATA",),
        )
    findings = tuple(item for path in paths for item in _inspect(path, root))
    if findings:
        return lane(
            "structured-data",
            LaneStatus.FAIL,
            "local",
            tuple(item.reason_code for item in findings),
            findings,
        )
    return lane("structured-data", LaneStatus.PASS, "local", ("PASS_STRUCTURED_DATA",))


def _inspect(path: Path, root: Path) -> list[Finding]:
    rel = relative(path, root)
    is_json = path.suffix.lower() == ".json"
    try:
        load(path)
    except NonfiniteError as error:
        code = "FAIL_JSON_NONFINITE" if is_json else "FAIL_YAML_NONFINITE"
        return [Finding(reason_code=code, message=str(error), path=rel)]
    except json.JSONDecodeError as error:
        return [
            Finding(
                reason_code="FAIL_JSON_SYNTAX",
                message=error.msg,
                path=rel,
                line=error.lineno,
            )
        ]
    except ValueError as error:
        return [Finding(reason_code="FAIL_JSON_DUPLICATE_KEY", message=str(error), path=rel)]
    except yaml.YAMLError as error:
        code = "FAIL_YAML_DUPLICATE_KEY" if "duplicate key" in str(error) else "FAIL_YAML_SYNTAX"
        return [Finding(reason_code=code, message=str(error).splitlines()[0], path=rel)]
    return []

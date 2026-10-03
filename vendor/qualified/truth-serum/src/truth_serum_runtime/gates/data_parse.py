"""Strict structured-data parsers."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]


class NonfiniteError(ValueError):
    """A structured-data number is NaN or infinite."""


class UniqueLoader(yaml.SafeLoader):  # type: ignore[misc]
    """YAML loader that refuses duplicate mapping keys."""


def load(path: Path) -> Any:
    content = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        payload = loads_json(content)
    else:
        payload = list(yaml.load_all(content, Loader=UniqueLoader))
    _finite(payload)
    return payload


def loads_json(content: str) -> Any:
    return json.loads(
        content,
        object_pairs_hook=_unique_json,
        parse_constant=_reject_constant,
    )


def _mapping(loader: UniqueLoader, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in result
        except TypeError as error:
            raise yaml.constructor.ConstructorError(
                "mapping", node.start_mark, "unhashable mapping key", key_node.start_mark
            ) from error
        if duplicate:
            raise yaml.constructor.ConstructorError(
                "mapping", node.start_mark, f"duplicate key: {key}", key_node.start_mark
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def _unique_json(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise NonfiniteError(f"non-finite number: {value}")


def _finite(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise NonfiniteError("non-finite number")
    if isinstance(value, dict):
        for key, item in value.items():
            _finite(key)
            _finite(item)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            _finite(item)

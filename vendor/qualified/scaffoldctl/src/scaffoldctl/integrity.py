from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from pydantic import BaseModel

IDENTITY_NAMESPACE = uuid.UUID("58d49ae2-1c73-56f5-b09d-efcb80f8c98d")


def jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    raise TypeError(f"value is not canonically JSON serializable: {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    root = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    return json.dumps(
        root,
        allow_nan=False,
        default=jsonable,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def hash_payload(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def deterministic_id(kind: str, semantic_hash: str) -> str:
    return str(uuid.uuid5(IDENTITY_NAMESPACE, f"{kind}:{semantic_hash}"))


def stamp_payload(
    payload: dict[str, Any],
    *,
    kind: str,
    id_field: str,
    hash_field: str,
) -> dict[str, Any]:
    semantic_hash = hash_payload(payload)
    stamped = {**payload, id_field: deterministic_id(kind, semantic_hash)}
    return {**stamped, hash_field: hash_payload(stamped)}


def verify_stamped_payload(
    payload: dict[str, Any],
    *,
    kind: str,
    id_field: str,
    hash_field: str,
) -> bool:
    supplied_id = payload.get(id_field)
    supplied_hash = payload.get(hash_field)
    semantic = {key: value for key, value in payload.items() if key not in {id_field, hash_field}}
    expected = stamp_payload(
        semantic,
        kind=kind,
        id_field=id_field,
        hash_field=hash_field,
    )
    return supplied_id == expected[id_field] and supplied_hash == expected[hash_field]


def parse_strict_json(data: bytes) -> Any:
    text = data.decode("utf-8", errors="strict")

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_nonfinite(value: str) -> None:
        raise ValueError(f"non-finite JSON value: {value}")

    return json.loads(
        text,
        object_pairs_hook=reject_duplicate_keys,
        parse_constant=reject_nonfinite,
    )

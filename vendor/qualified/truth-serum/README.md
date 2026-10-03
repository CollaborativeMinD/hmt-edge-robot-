# Truth Serum

Repository-admission kernel, version 1.0.0.

## Purpose

Truth Serum admits or rejects a repository state from reproducible local evidence. It validates
architecture trace closure, structure, typed data, evidence bindings, source aperture, secrets,
shell syntax, tests, and configured witness tools. It does not deploy or certify a product.

## Lifecycle

The supported flow is `scaffold -> validate -> admit -> closeout -> seal -> verify`. Admission is
read-only outside its explicit evidence output. `PASS`, `HOLD`, `FAIL`, and `ESCALATE` are distinct;
unavailable mandatory evidence is `HOLD`, never an inferred pass.

Quick path:

```bash
export UV_CACHE_DIR=/tmp/truth-serum-uv
export UV_PROJECT_ENVIRONMENT=/tmp/truth-serum-venv
export PYTHONDONTWRITEBYTECODE=1
uv sync --frozen
uv run --frozen python -B -m pytest -p no:cacheprovider
uv run --frozen python -B truth_serum.py --mode ci --out evidence/runtime
```

## Invariants

- Root scope is repository admission only; physical AI, product runtime, and deployment are external.
- Unknown modes, boundary fields, and states fail closed before authority transfer.
- Every requirement `REQ-TS-001..011` closes through a matching invariant and oracle.
- Runtime admission replaces only the explicitly selected runtime-named evidence output.
- Functions are at most 60 physical lines; production Python modules are fewer than 100 lines.
- Evidence hashes are recomputed from bytes; stale or malformed claims fail.
- Only `REPOSITORY_SEAL.json` is a repository checksum artifact.

## Authority

`scaffold.policy.json` governs repository shape. Truth Serum governs local admission. The seal binds
the admitted file tree but grants no operational, certification, or human promotion authority. The
human architect owns final acceptance. See `Runbook.md`, `Agents.md`, and `architecture/non_claims.md`.

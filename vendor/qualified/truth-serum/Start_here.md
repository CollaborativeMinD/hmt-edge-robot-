# Start Here — Truth Serum

## Boundary

This repository admits source and evidence; it does not validate target hardware, a cluster, or a
deployed product. Read `architecture/non_claims.md` before widening scope.

## First Action

Use Python 3.12. From the repository root:

```bash
export UV_CACHE_DIR=/tmp/truth-serum-uv
export UV_PROJECT_ENVIRONMENT=/tmp/truth-serum-venv
export PYTHONDONTWRITEBYTECODE=1
uv sync --frozen
uv run --frozen python -B -m pytest -p no:cacheprovider
```

Then read `evidence/BLUF.md` and `Runbook.md`.

## Validation

```bash
scaffoldctl validate --worktree --root .
uv run --frozen python -B truth_serum.py --mode ci --out evidence/runtime
uv run --frozen python -B tools/repository_seal.py verify --repo .
```

Stop on any nonzero exit. Exit 3 means evidence is unavailable and the decision is `HOLD`.

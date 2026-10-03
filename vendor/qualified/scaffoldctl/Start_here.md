# Start Here

## Boundary

Python 3.12, Git, uv 0.11.33, and a POSIX filesystem are required. The hook installer copies the
packaged wrapper into the target Git repository and keeps its private key and DuckDB ledger beneath
that repository's Git directory. The source tree carries no active `.git` state.

## First Action

```sh
uv sync --locked --all-groups
uv run scaffoldctl install-hook --root /path/to/repository
git add README.md Start_here.md Index.md scaffold.policy.json
```

For CI, commit the pinned wheel and `.github/workflows/scaffoldctl-perimeter.yml`, then make the
`scaffoldctl-perimeter` check required on protected branches.

## Validation

```sh
uv run scaffoldctl pre-commit --root /path/to/repository
uv run scaffoldctl verify-ledger --ledger /path/to/evidence.duckdb
uv run scaffoldctl seal-ledger --ledger /path/to/evidence.duckdb \
  --private-key /path/to/lease-signing-key.pem --output ledger-seal.json
uv run ruff check .
uv run python scripts/check_function_lengths.py
uv run pytest --cov=scaffoldctl --cov-report=term-missing
```

`provenance/sealed_source_release_v0_3_0/` preserves the incoming release's closeout evidence,
reproducible wheel, and sdist. Those files are reference inputs, not current-tree evidence or
writable runtime state.

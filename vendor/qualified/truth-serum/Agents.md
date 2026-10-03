# Agent SOP

## 1. Mission and authority

Operate only the repository-admission boundary. `scaffoldctl` owns repository shape, Truth Serum
owns admission decisions, and `tools/repository_seal.py` binds the final bytes. No agent may convert
a local PASS into product readiness, certification, deployment approval, or human acceptance.

The human architect is the promotion authority. Forge role `6_14` owns Edge DevSecOps and IaC
implementation evidence. Role `6_15` reconciles traceability and seal readiness. Architecture,
ontology, or deterministic-seam disputes route to their governing roles before implementation.

## 2. Admissible regions

| Region | Admissible work | Required proof |
| --- | --- | --- |
| `architecture/` | REQ/INV/oracle, interfaces, namespaces, non-claims | trace test + architecture mode |
| `contracts/` | closed schemas and lane policy | schema tests + architecture mode |
| `src/` | admission logic and local/witness gates | unit, negative, lint, type, security |
| `tests/` | deterministic fixtures and regressions | full suite |
| `scripts/` | thin, fail-closed operator wrappers | `bash -n` + shell gate |
| root docs | operator and agent contracts | scaffoldctl worktree/staged/tree |
| `evidence/closeout/` | generated V&V records only | schema validation + admission |

Do not edit `REPOSITORY_SEAL.json`; recreate it only after all gates pass. Do not write runtime
evidence outside the requested `--out`. Do not add parallel `Evidence/` trees, checksum ledgers,
self-referential manifests, caches, build outputs, secret files, generated binaries, or symlinks.

## 3. Change SOP

1. Read `README.md`, `architecture/non_claims.md`, the affected contract, and its tests.
2. State the requirement and invariant IDs affected. Formula/equation IDs are `N/A` in this scope.
3. Make the smallest patch. Keep functions at most 60 lines and production modules below 100.
4. Run the narrow test for the change.
5. Rerun every previously passing gate in `scripts/verify.sh`; stop on regression.
6. For a defect, apply Reverse RCA: ask, “For this output to be true, what cascading effects
   upstream happened, allowed admission, or transferred authority?” Continue to the first invalid
   state, repair it, reproduce the original failure, and regress down the causal chain.
7. Update traceability, tests, evidence, and non-claims together. Never patch evidence to hide code.
8. Remove generated debris, run clean-room validation, then recreate and verify the sole seal.

## 4. Command law

Safe read-only checks:

```bash
scaffoldctl validate --worktree --root .
UV_CACHE_DIR=/tmp/truth-serum-uv UV_PROJECT_ENVIRONMENT=/tmp/truth-serum-venv uv lock --check
PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR=/tmp/truth-serum-uv UV_PROJECT_ENVIRONMENT=/tmp/truth-serum-venv uv run --frozen python -B -m pytest -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR=/tmp/truth-serum-uv UV_PROJECT_ENVIRONMENT=/tmp/truth-serum-venv uv run --frozen python -B truth_serum.py --mode architecture-only --out evidence/runtime-architecture
PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR=/tmp/truth-serum-uv UV_PROJECT_ENVIRONMENT=/tmp/truth-serum-venv uv run --frozen python -B truth_serum.py --mode ci --out evidence/runtime-ci
PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR=/tmp/truth-serum-uv UV_PROJECT_ENVIRONMENT=/tmp/truth-serum-venv uv run --frozen python -B tools/repository_seal.py verify --repo .
```

Creating a seal is authorized only after a current CI admission PASS:

```bash
PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR=/tmp/truth-serum-uv UV_PROJECT_ENVIRONMENT=/tmp/truth-serum-venv uv run --frozen python -B tools/repository_seal.py create --repo .
```

Never use broad deletion, forced Git reset, bypass flags, or a fabricated witness. A missing
mandatory tool routes `HOLD` with exit 3. A target-dependent check stays a non-claim until executed.

## 5. Handoff contract

Hand off the changed paths, requirement/invariant/oracle IDs, commands and return codes, failures
reproduced, repairs made, evidence paths, assumptions, residual risks, and artifact dispositions.
Machine handoff must validate against `contracts/schemas/machine_handoff.schema.json`. If any mandatory
field or witness is absent, report `hold`; never infer `pass` from silence.

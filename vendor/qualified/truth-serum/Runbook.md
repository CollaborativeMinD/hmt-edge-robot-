# Truth Serum Operator Runbook

## 1. Purpose

This SOP installs, admits, audits, troubleshoots, seals, and verifies the repository. Run commands
from the repository root. The tool is read-only except for the chosen evidence path and the explicit
seal command.

## 2. Prerequisites and bootstrap

Required: Linux, Python 3.12, `uv`, Git, Bash, and `scaffoldctl` 0.3.x. CI admission also expects the
witnesses pinned in `pyproject.toml`. Put the cache in a writable, non-repository path:

```bash
export UV_CACHE_DIR=/tmp/truth-serum-uv
export UV_PROJECT_ENVIRONMENT=/tmp/truth-serum-venv
export PYTHONDONTWRITEBYTECODE=1
uv python pin 3.12
uv lock --check
uv sync --frozen
uv run --frozen python --version
```

If synchronization fails, preserve the error, check registry reachability and credentials, and
leave the decision at HOLD. Do not substitute unlocked dependencies.

## 3. Normal verification

```bash
scaffoldctl validate --worktree --root .
uv run --frozen python -B -m pytest -p no:cacheprovider
uv run --frozen python -B truth_serum.py --repo . --mode ci --out evidence/runtime
uv run --frozen python -B tools/repository_seal.py verify --repo .
```

Exit codes are `0 PASS`, `1 FAIL`, `2 contract error`, `3 HOLD`, and `4 ESCALATE`. Inspect
`evidence/runtime/admission_report.json`, then the lane evidence named in that report. A zero exit
is meaningful only when `decision=PASS` and `clear=true` agree.

## 4. Admission modes

| Mode | Use | Authority |
| --- | --- | --- |
| `architecture-only` | REQ/INV/oracle, shape, and contract diagnosis | no release seal |
| `ci` | required local and witness gates | source handoff admission |
| `post-build` | Full CI profile after an external build; no artifact existence is inferred | source re-admission only |
| `rainy-day` | maximum diagnostics during degraded operation | never masks HOLD/FAIL |

An unknown mode must exit 2 before creating evidence. Unavailable required witnesses must exit 3.

## 5. Evidence and observability

```bash
jq '{decision,posture,reasons}' evidence/runtime/admission_report.json
jq -r '.lanes[] | [.lane_id,.status,.required,(.reason_codes|join(","))] | @tsv' \
  evidence/runtime/admission_report.json
sed -n '1,120p' evidence/runtime/admission_trace.jsonl
find evidence/runtime -maxdepth 3 -type f -print | sort
```

All evidence paths must remain beneath a runtime-named output in `evidence/`. Each attempt replaces
that selected output to prevent stale receipts and must not change any other file. Compare
`git status --short` before and after a run when auditing immutability.

## 6. Troubleshooting

| Symptom | Meaning | Response |
| --- | --- | --- |
| exit 2, no output | CLI/schema contract violation | correct mode/path/input; rerun |
| exit 3, `UNAVAILABLE` | required witness absent | install pinned group; do not waive |
| `TRACE_*` | orphan or drifted REQ/INV/oracle | repair all four trace surfaces together |
| `CLAIM_*` | evidence path/hash mismatch | recompute source bytes; repair producer |
| `SOURCE_*` | aperture, syntax, or stub violation | split module/function; implement or remove |
| `SECRET_*` | probable credential material | revoke if real, remove, scan history, rerun |
| `SHELL_*` | syntax or strict-mode failure | repair script; run `bash -n` and admission |
| seal mismatch | post-seal byte change | quarantine artifact, identify changed path, re-admit |

For every failure, work backward with the Reverse RCA question in `Agents.md`; then reproduce the
bad state and prove the fixed state. Do not regenerate reports until the producer is correct.

## 7. Git and pre-commit

```bash
git status --short
git add --all
scaffoldctl validate --staged --root .
bash scripts/pre_commit.sh
```

Protected CI must run the same staged/tree policy. A local hook is convenience, not promotion
authority. Never commit `.env`, `.secrets/`, `secrets/`, caches, runtime evidence, or build output.

## 8. Closeout and sealing

Before sealing, remove only confirmed generated caches and `evidence/runtime`; ensure no unrelated
user content is targeted. Then run:

```bash
scaffoldctl validate --worktree --root .
uv run --frozen python -B -m pytest -p no:cacheprovider
uv run --frozen python -B truth_serum.py --mode ci --out evidence/closeout/runtime
uv run --frozen python -B tools/repository_seal.py create --repo .
uv run --frozen python -B tools/repository_seal.py verify --repo .
```

`REPOSITORY_SEAL.json` is the only whole-repository checksum artifact. It covers every delivered
file except itself and the explicitly ephemeral `evidence/runtime/` tree, using sorted path, size,
and content hashing. Any governed edit requires full re-admission and a new seal.

## 9. Clean-room and tamper proof

Extract the distribution into a new temporary directory, sync from the frozen lock, run the normal
verification, copy one file to a backup, change one byte, confirm seal verification fails, restore
the file, and confirm it passes again. Never run mutation tests against the only retained copy.

## 10. Operational boundaries

No Docker, Kubernetes, LiteLLM, Tailscale, Pi4/Pi5, physical-AI, or product-runtime execution is
claimed. No official SysML semantic compiler was available; local textual trace closure is proven.
These limits do not weaken repository-source admission, but they prohibit downstream readiness
claims until the owning environment supplies and records those tests.

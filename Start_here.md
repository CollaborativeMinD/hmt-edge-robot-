# Start Here — HMT Edge Robot

## Boundary

This repository validates supervisory system software and evidence. Docker builds,
container execution, Pi qualification, K3s deployment, and physical actuation remain HOLD.

## First Action

Run `python3 tools/ci_admission.py`, then `uv lock --check` and
`uv sync --locked --extra dev`. Run `uv run --no-sync python tools/validate.py`.

## Validation

Inspect current `evidence/validation.json`, `evidence/ci/admission.json`, and
`evidence/ci/phase2`. Stop on failed gates. Read `Runbook.md` and `docs/ci_phase2.md`.
For stage-3 deployment design, inspect `evidence/cd/stage3` and `docs/cd/stage3.md`.
Contract PASS does not activate the zero-replica or suspended templates.

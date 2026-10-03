#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command -v uv >/dev/null || {
  printf '%s\n' 'HOLD: uv is unavailable.' >&2
  exit 3
}
cd "$repo_root"
export PYTHONDONTWRITEBYTECODE=1
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/truth-serum-uv}"
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-/tmp/truth-serum-venv}"
exec uv run --frozen python -B truth_serum.py "$@" \
  --repo . --mode ci --out evidence/runtime

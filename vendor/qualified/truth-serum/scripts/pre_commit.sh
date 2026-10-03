#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command -v scaffoldctl >/dev/null || {
  printf '%s\n' 'HOLD: scaffoldctl is unavailable.' >&2
  exit 3
}
cd "$repo_root"
scaffoldctl validate --staged --root .
exec "$repo_root/scripts/verify.sh"

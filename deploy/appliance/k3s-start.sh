#!/bin/bash
set -euo pipefail
role=$(cat /etc/hmt/role)
case "$role" in
  server|agent) exec /usr/local/bin/k3s "$role" --config /etc/rancher/k3s/config.yaml ;;
  *) echo 'Invalid provisioned k3s role' >&2; exit 1 ;;
esac

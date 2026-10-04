#!/bin/bash
set -euo pipefail
for _attempt in $(seq 1 120); do
  if /usr/local/bin/k3s ctr images ls >/dev/null 2>&1; then break; fi
  sleep 2
done
/usr/local/bin/k3s ctr images import --digests /usr/share/hmt/runtime.oci.tar
image_tag=$(cat /usr/share/hmt/image-tag)
image_ref=$(cat /usr/share/hmt/image-ref)
/usr/local/bin/k3s ctr images tag --force "$image_tag" "$image_ref"
if [[ $(cat /etc/hmt/role) == server ]]; then
  for _attempt in $(seq 1 120); do
    if /usr/local/bin/k3s kubectl get --raw=/readyz >/dev/null 2>&1; then break; fi
    sleep 2
  done
  /usr/local/bin/k3s kubectl apply -f /usr/share/hmt/namespace.json
  /usr/local/bin/k3s kubectl apply -f /etc/hmt/runtime-secret.json
  /usr/local/bin/k3s kubectl apply -f /usr/share/hmt/workload.json
  /usr/local/bin/k3s kubectl -n hmt-edge-robot-sil rollout status deployment/hmt-edge-robot --timeout=240s
fi

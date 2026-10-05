#!/bin/bash
# Native ephemeral k3s; never connects to the Pi fleet.
set -euo pipefail
repo=$(realpath "$1")
work="$repo/build"
name="hmt-k3s-${GITHUB_RUN_ID:-local}"
version=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["k3s"]["version"].replace("+", "-"))' "$repo/deploy/appliance/inputs.json")
cleanup() { docker rm -f "$name" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker pull "rancher/k3s:$version"
docker image inspect "rancher/k3s:$version" > "$work/smoke-base.json"
docker run -d --privileged --name "$name" --network bridge \
  --mount "type=bind,src=$work/inputs/k3s-airgap-images-arm64.tar.zst,dst=/var/lib/rancher/k3s/agent/images/k3s.tar.zst,readonly" \
  "rancher/k3s:$version" server --node-name forge-pi-02 --disable traefik --disable servicelb --disable metrics-server
for _attempt in $(seq 1 120); do
  if docker exec "$name" k3s kubectl get --raw=/readyz >/dev/null 2>&1; then break; fi
  sleep 2
done
docker exec "$name" mkdir -p /var/lib/hmt/ledger
docker exec "$name" chown 10001:10001 /var/lib/hmt/ledger
docker cp "$work/payload/runtime.oci.tar" "$name:/tmp/runtime.oci.tar"
image_tag=$(cat "$work/payload/image-tag")
image_ref=$(cat "$work/payload/image-ref")
docker exec "$name" k3s ctr images import --digests --base-name "${image_tag%:*}" /tmp/runtime.oci.tar
docker exec "$name" k3s ctr images tag --force "$image_tag" "$image_ref"
docker exec -i "$name" k3s kubectl apply -f - < "$work/payload/namespace.json"
# These ephemeral test tokens are never used on devices or stored in the image.
docker exec "$name" k3s kubectl -n hmt-edge-robot-sil create secret generic hmt-edge-runtime \
  --from-literal=api_token=isolated-sil-api-test-token --from-literal=operator_token=isolated-sil-operator-test-token
# Prove offline import by disabling registry fallback during this deployment.
python3 - "$work/payload/workload.json" > "$work/smoke-workload.json" <<'PY'
import json, sys
value = json.load(open(sys.argv[1]))
for item in value['items']:
    if item['kind'] == 'Deployment':
        item['spec']['template']['spec']['containers'][0]['imagePullPolicy'] = 'Never'
print(json.dumps(value))
PY
docker exec -i "$name" k3s kubectl apply -f - < "$work/smoke-workload.json"
docker exec "$name" k3s kubectl -n hmt-edge-robot-sil rollout status deployment/hmt-edge-robot --timeout=240s
docker exec "$name" k3s kubectl -n hmt-edge-robot-sil exec deployment/hmt-edge-robot -- python /etc/hmt/readiness.py
docker exec "$name" k3s kubectl -n hmt-edge-robot-sil exec deployment/hmt-edge-robot -- python -c \
  'import os,urllib.request; r=urllib.request.Request("http://127.0.0.1:8000/simulation/observe",data=b"",headers={"Authorization":"Bearer "+os.environ["HMT_API_TOKEN"]},method="POST"); urllib.request.urlopen(r,timeout=5).close()'
docker exec "$name" k3s kubectl -n hmt-edge-robot-sil exec deployment/hmt-edge-robot -- hmt-edge-robot replay --database /data/cell.db > "$work/replay-before.json"
docker exec "$name" k3s kubectl -n hmt-edge-robot-sil delete pod -l app.kubernetes.io/name=hmt-edge-robot --wait=true
docker exec "$name" k3s kubectl -n hmt-edge-robot-sil rollout status deployment/hmt-edge-robot --timeout=240s
docker exec "$name" k3s kubectl -n hmt-edge-robot-sil exec deployment/hmt-edge-robot -- python /etc/hmt/readiness.py
docker exec "$name" k3s kubectl -n hmt-edge-robot-sil exec deployment/hmt-edge-robot -- hmt-edge-robot replay --database /data/cell.db > "$work/replay-after.json"
python3 - "$work/replay-before.json" "$work/replay-after.json" <<'PY'
import json, sys
before, after = [json.load(open(path)) for path in sys.argv[1:]]
assert before['verified_events'] > 0 and after['verified_events'] >= before['verified_events']
assert before['tail'] == after['tail'][:len(before['tail'])]
PY
printf '{"status":"PASS","scope":"HOSTED_ARM64_K3S_SIL","native_pi":"NOT_RUN","offline_import":true,"restart":true}\n' > "$work/smoke.json"

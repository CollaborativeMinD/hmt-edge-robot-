# Stage 3 — deployment design admission

Stage 3 creates and proves deployment contracts, dormant manifests and design-only
release receipts. It does not build an image, apply Kubernetes resources, install
Flux, provision credentials, call a model or activate a physical driver.

## Source and authority

Baseline main commit: `3f2ebe3280e09c13612526c02d107a3448435477`.
Baseline tree: `7eb6a2598db5c400c619322d2424b49aa89adab8`.
The baseline tree is the tested PR #7 tree. `policy/deployment_admission.json`
binds the complete runtime source inventory, deployment plan, SIL runtime policy,
candidate, original promotion overlay, lock, project metadata, schemas and manifests.
CI admission independently pins this catalog and all new gate sources before install.
An edit to both code and its catalog still requires human review: these hashes are
integrity bindings, not an independent signature or executable deployment grant.

## Contracts and artifacts

`policy/deployment.json` declares Linux/arm64 K3s, a private SIL namespace, one
future writer/worker, zero present replicas, loopback API binding and eleven HOLDs.
Strict Pydantic schemas reject coercion, extra fields, nonfinite resource budgets,
zero placeholder hashes and authority widening. `policy/release_candidate.json`
declares UNBUILT, a null image digest and no target observation. No fictitious
image, device measurement, cluster version or readiness result is supplied.

`deploy/stage3/workload` contains JSON Kubernetes templates and a JSON-form YAML
Kustomization. `namespace.json` is a separate bootstrap template deliberately
excluded from the namespace-scoped workload resource list. Bootstrap is a future
operator task. The namespace enforces restricted pod security. The workload has
zero replicas, Recreate strategy, no host access, a non-root identity, read-only
root filesystem, dropped capabilities and no automatic service-account token.
Credentials appear only as required external Secret references. No Secret values,
public Service or ingress, device mounts, provider endpoint or paid inference exists.

The explicit `{{QUALIFIED_IMAGE_DIGEST_REQUIRED}}` template token is not an image
reference or digest. Rendering an active workload requires a later reviewed
contract version and a real qualified artifact; editing this token fails stage 3.
The Flux source likewise has `{{APPROVED_RELEASE_COMMIT_REQUIRED}}` as an explicit
unresolved commit token. A later release must bind an approved immutable Git revision;
switching this template to a moving branch fails the closed stage-3 grammar.
Both Flux source and reconciliation templates are suspended. Their reconciler
Role is namespace-scoped, excludes Secrets and cluster resources, and permits no
delete. Reconciliation uses prune=false; the ledger PVC also disables pruning.
Git and registry read credentials, Flux installation and RBAC fit remain unverified.

## Storage, placement and private access

The proposed budget is 500m CPU/512Mi requested, 2000m CPU/2048Mi limited, 64Mi
scratch and an 8Gi ledger PVC. These are design bounds, not measured performance.
Storage class `hmt-edge-unqualified` and node owner label `qualification-required`
are explicit unresolved bindings. Pin a verified SSD-backed storage class/node in
the target phase, check PVC retention/reclaim policy and test full-disk behavior.
ReadWriteOnce permits multiple pods on one node; it does not prove single-writer
exclusion. No automatic failover, HPA, shared SQLite writer or overlap upgrade is
allowed. Prove the old owner stopped before replacement; uncertain termination
holds the release. Never force-delete an owner to manufacture that proof.

The API remains on 127.0.0.1 with distinct operator and API tokens. Future access
is restricted to a separately qualified authenticated port-forward path. Default
deny ingress/egress is a declared policy, pending network-plugin enforcement tests.
Loopback exec startup/liveness probes use /health. Readiness intentionally returns
failure: policy integrity, ledger integrity and startup reconciliation have no
qualified runtime readiness implementation yet. Do not substitute /health or
weaken the readiness probe to promote the pod. Shutdown/stop behavior also needs
target trials; the 30-second grace period is only a proposed configuration.

## Validation and receipts

Run `uv run --no-sync python tools/deployment_gate.py` and
`uv run --no-sync python tools/deployment_campaign.py`, then the full cumulative
`uv run --no-sync python tools/validate.py`. G-CD-CONTRACT-017 validates exact
closed manifest grammar and source/byte bindings. G-CD-NEGATIVE-018 repeats the
adversarial suite with >=90% branch-aware coverage on the contract/admission modules.
This is local schema/semantic validation, not Kubernetes server-side dry-run or
proof that the target API accepts these resources. No new dependencies are needed.

`evidence/cd/stage3/release_receipt.json` binds every input and catalog hash, baseline,
source inventory, deterministic release ID, receipt hash and reason-coded HOLDs.
Replaying unchanged inputs produces the same receipt. Verification compares it
against a fresh assessment; stale inputs, forged authority or a changed hash fail.
`require_execution` always denies stage-3 execution. A valid design emits PASS
and release_decision=HOLD; rejection atomically replaces any old receipt with FAIL,
HOLD and an alert. An evidence write failure exits unsuccessfully.
The published receipt schema is a discriminated union: PASS records carry source
bindings and a receipt hash; FAIL records carry bounded rejection codes, HOLD and
an alert. `parse_outcome` validates either variant, while `verify_receipt` admits
only a fresh PASS design record and rejects a well-formed rejection explicitly.

Negative cases include rescaling, worker/driver changes, unsuspending Flux,
privilege escalation, host mounts, inline credentials, readiness bypass, broad RBAC,
network exposure, storage changes, resource overflow, schema drift, duplicate JSON,
path escape, symlinks, absent evidence, source inventory drift and receipt forgery.
The campaign wrapper and substantive admission modules have a separate coverage
gate, while host regression and source bounds remain cumulative. The wrapper
replaces any old PASS with FAIL before spawning tests. Its 60-second test deadline
and bounded five-second reap leave margin under the 120-second outer gate deadline.
Hung or unstartable subprocesses cannot retain a prior PASS campaign record.

## Next acceptance boundary

Stage 4 must supply an actual locked ARM64 image, digest, SBOM, vulnerability
disposition and verified provenance. Stage 5 must supply Pi/OS/K3s/Flux inventory,
node/storage/CNI evidence, readiness implementation, native resource measurements,
single-owner stop/restart, private access and restore trials. Stage 6 admits SIL
cluster deployment only after those gates and protected human promotion are proven.
Version immutable ConfigMap names by the reviewed policy hash before active upgrades.
Image rollback is allowed only for compatible ledger/schema/policy versions; retain
append-only evidence. A schema-changing rollback requires a rehearsed migration or
explicit restore plan, not an automatic database rewind. Hardware gates stay separate.

References: https://kubernetes.io/docs/tasks/configure-pod-container/security-context/
https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
https://kubernetes.io/docs/concepts/storage/persistent-volumes/
https://kubernetes.io/docs/tasks/run-application/force-delete-stateful-set-pod/
https://fluxcd.io/flux/components/kustomize/kustomizations/

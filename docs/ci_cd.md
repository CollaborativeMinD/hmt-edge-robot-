# CI/CD phase 1 — software admission

## Purpose and boundary

Phase 1 qualifies repository software changes on GitHub-hosted Ubuntu 24.04.
The intended deployment target is Linux/aarch64 Raspberry Pi with K3s.
Host CI does not qualify the Pi, control plane, container, timing or actuation.
Deployment is HOLD. No runner on the control plane receives pull-request code.

## Gate sequence

1. Checkout immutable event revision using a SHA-pinned action, without persisted credentials.
2. Standard-library preflight checks the reviewed admission catalog and critical input hashes.
3. SHA-pinned setup-uv installs uv 0.9.7 without shared cache reuse.
4. `uv lock --check` rejects stale metadata. `uv sync --locked --extra dev` installs it.
5. `uv run --no-sync python tools/validate.py` repeats admission, Pyrefly, Ruff, regression,
   traceability, coverage, analytics and assurance campaigns.
6. Upload evidence on success or failure; annotate failed jobs for the operator.

Pull requests cancel superseded runs. Main runs are not cancelled. Token permission is
contents/read. No repository secrets, paid inference, deployment token or cluster credentials
are passed into these jobs. All external actions use full commit SHA references.

## Tool policy and change procedure

`policy/ci_admission.json` binds the workflow, validator, bootstrap, project metadata and uv lock.
The core checker versions are exact versions from that lock. Critical file tampering, missing
inputs, links, path escape, unknown policy fields and candidate promotion fail closed.
Update the catalog only after reviewing the changed inputs and rerunning negative tests.
The receipt contains policy and lock hashes, decisions, notifications and failure alerts.
Evidence write failure fails the job. Evidence is retained for 30 days in Actions artifacts.

The catalog is an integrity check, not an independent signature or authorization service.
A contributor can propose changes to both policy and code. Human review and protected branch
settings remain the authority boundary. Configure required `verify`, PR review, dismissal of
stale approvals, restriction of bypass and review of workflow/policy changes before relying on
this check as enforced repository admission. These administrative settings are not attested here.

## Reusable tool candidates

The original scaffoldctl 0.3.0 and Truth Serum 1.0.0 ZIPs are retained byte-for-byte in
`vendor/admission`. Their hashes and HOLD dispositions are in the catalog.
The selected scaffoldctl source states HOLD pending locked tests, lint, distribution and review.
Neither archive is installed, extracted or executed in CI. Upstream evidence cannot establish
host-repository admission. Core CI PASS does not change candidate HOLD.

Before promotion: verify provenance/seals, inspect executable effects and dependencies,
qualify each isolated Linux environment, exercise rejection and incomplete-evidence cases,
and bind the host policy to immutable Git trees. Resolve scaffold document-boundary rules and
Truth Serum lane/schema compatibility explicitly. Do not invoke scaffold mutation or mint
signing leases from a pull-request job. Retain Pyrefly and Ruff as host gates regardless of
upstream checker choices. Package requalification and integration are a separate continuation.

## Requirements and validation

REQ-CI-01 binds the allowed tools and candidate HOLD. REQ-CI-02 rejects altered critical
inputs and records alerts. REQ-CI-NFR-01 proves stale locks fail without rewriting them.
`tests/test_ci_admission.py` contains positive and injected-negative cases. G-CI-013 repeats
the bootstrap in the cumulative evidence ledger. All inherited software gates remain required.

## Subsequent phases

| Phase | Required evidence before advancement |
|---|---|
| 2: Policy/tool qualification | Read-only interfaces, regressions, pinned policy assessment; see ci_phase2.md |
| Later: Container build | Locked build, non-root image, SBOM, vulnerability disposition, provenance and digest |
| 3: Linux/aarch64 | Container smoke, architecture dependencies, resource and bounded recovery measurements |
| 4: K3s staging | Protected environment, least-privilege deployment, readiness, rollout and rollback rehearsal |
| 5: Promotion | Exact tested digest, retained evidence, admission decision and operator authorization |

Control-plane scheduling and Pi OS/architecture must be confirmed before deployment design.
No phase advances on a successful workflow alone. Preserve prior archive/source seals.

## References

- https://docs.astral.sh/uv/concepts/projects/sync/
- https://docs.github.com/en/actions/reference/security/secure-use

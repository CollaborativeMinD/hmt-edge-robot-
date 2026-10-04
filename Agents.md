# Orchestration and interception interface

Objective OBJ-EDGE-01: evolve the five supplied subsystems into one coherent,
evidenced supervisory robotics cell with analytics and resident HMT.

`docs/requirements.json` is the requirement/test binding. `src/hmt_edge_robot`
is executable architecture truth; `docs/architecture.md` declares external seams.
`Runbook.md` is the operator SOP. Evidence outranks narrative.

Before editing, inspect the affected contract, caller authority, event transition,
policy bounds, regression test and requirement. Trace any surprising terminal
output backward through feedback, acknowledgment, admission, identity, observation,
and durable intent. Stop at the last evidenced causal edge. Apply the smallest
coherent correction and recheck the downstream outcome and all previously good
gates with `uv run python tools/validate.py`.

Interceptions: block unknown/coerced/nonfinite contract data; unknown authority;
stale observations; changed epochs; duplicate intents; illegal transitions;
evidence write/verification failures; unqualified model profiles; unbounded calls;
neural actuation; and hardware or compliance claims without physical evidence.

Keep functions at most 60 physical lines including decorators and modules at most 100
nonblank, non-comment-only physical lines including docstrings. Keep dependencies locked, runtime histories
bounded, and critical state guarded by the cell lock. Do not suppress failing tests,
invent measurements, auto-home on failure, bypass the stop latch, rewrite inherited
evidence, expose credentials, or enable paid probes in normal CI. Preserve source
hashes without shipping unchanged inherited files. Python's dynamic allocation is
permitted only in the supervisory/SIL partition; firmware static-memory and MISRA
gates remain explicit deployment blockers.

Every handoff identifies requirements, tests and failures, assumptions, unresolved
risks, interface deltas, source provenance and evidence artifacts. Maintain
`docs/incidents.json` and the seven-column cumulative and RRCA ledgers. Only mark
an incident INVESTIGATION_COMPLETE at a reproducible initiating condition or an
explicit external boundary. Operator escalation must say which evidence is missing.

Objective OBJ-SAT-03: system-software substrate assurance before deployment.
MCC readiness, USEA effect evidence and AGC reference closure must interlock through
scoped hashes and current epochs. All admitted lifecycle mutations are confined to
the managed artifact catalog. Reject declared traces as positive collected evidence;
reject incomplete coverage, dangling references, forged witnesses, stale plans,
expired/replayed grants, changed sessions and missing projection rows. Persist
notifications and alerts; failure to write evidence blocks acceptance. Recheck the
triad software campaign with all prior gates. No physical verification, native
tracing deployment, external deletion or paid inference is authorized by this SOP.

REQ-NFR-11 / G-TYPES-012: use the pinned Pyrefly checker alongside Ruff on the full
active Python project. Zero warnings or errors are required. Fix contract boundaries
and retain negative runtime tests; do not suppress typing diagnostics or substitute
an empty checking scope. Preserve historical source seals.

Phase 1 CI: critical inputs and tool versions are bound by `policy/ci_admission.json`.
Check uv lock freshness before locked installation. Reject unreviewed candidate promotion;
never execute the retained candidate ZIPs or expose cluster/provider credentials in PR CI.
Preserve existing gates and archive seals. Refer to `docs/ci_cd.md` for continuation boundaries.

Phase 2 permits only the pinned read-only support interfaces in `policy/ci_support.json`.
Qualified source copies are independently hash-bound before installation. Preserve original
archives and record deltas. Assessment PASS never promotes a policy with unresolved HOLDs.
No hook, lease, full-engine admission, Docker build, or deployment is admitted by this profile.

Human-approved policy promotion is recorded in `policy/promotion.json`. The overlay binds
the original package and source set for system-software validation. The sole historical SQL
archive reference is explicitly disregarded by the owner. Enforce the promoted ceilings
on every active Python module and rerun all gates. Runtime activation of external policy
roles, full tool engines, Docker builds, deployment and hardware verification remain HOLD.

Stage 3 is deployment design only. Follow `docs/cd/stage3.md`; keep all execution
boundaries held. Preserve dormant replicas, suspended reconciliation, private API,
external secret references and the ledger. Reject rehashed manifest authority drift,
stale receipts or invented image/target evidence. Rerun both new CD gates and every
prior gate. Never apply resources, install Flux, build images or provision credentials
from this stage's contract PASS. Target readiness and single-owner proof remain HOLD.

Stage 4 is independently admitted by `policy/artifact_admission.json`; follow
`docs/cd/stage4.md`. Image builds and isolated hosted ARM64 SIL container execution
are now in scope. Stage-3 contracts never grant this authority. Require frozen
packages, digest-bound OCI closure, complete scans and fresh cryptographic provenance
verification. Keep every Pi/cluster/deployment/physical gate HOLD. Preserve old seals.

Stage 5: follow `docs/cd/stage5.md` and the separate `policy/target.json` microSD
lab profile. Bind all three owner inventories while preserving Pi 03's kernel/OS
difference and existing Tailscale enrollment. Ordinary CI proves only target-tool
contracts and negative cases; it never runs the collector against a Pi. Explicit
operator collection writes bounded local evidence only. Inventory consistency
cannot admit bootstrap, image promotion, CNI/readiness, fencing, restore, private
access, measured workload bounds, or actuation. Keep those HOLDs independent;
never rewrite historical stage-3 evidence or dormant manifests to manufacture PASS.

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

Keep functions at most 60 physical lines, dependencies locked, runtime histories
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

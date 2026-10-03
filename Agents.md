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

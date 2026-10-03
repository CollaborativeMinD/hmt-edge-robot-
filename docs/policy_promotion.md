# Policy promotion and module decomposition

## Authority and scope

The repository owner explicitly approved the supplied policy package for promotion and
instructed that the missing historical SQL archive reference be disregarded. The approval
text, recording time, original ZIP digest, complete reviewed policy source set and exact
reference disposition are in `policy/promotion.json`. This is a repository review record,
not a cryptographic identity signature. Its integrity is bound by CI admission.

Effective promotion applies to system-software validation and supervisory governance.
Authored candidate/version metadata remains unchanged in the original sources. Inventory
reports both that historical status and the effective promoted adoption. External role,
provider, MCP or infrastructure declarations do not activate absent runtime integrations.
The SQL archive is explicitly unnecessary; its historical UNAVAILABLE observation remains
visible alongside DISREGARDED_BY_HUMAN. Other missing or mismatched pins fail closed.

## Decomposition contract

All 26 oversized active modules were divided by responsibility. Public contract/class/function
imports remain available from their previous paths. Runtime owners retain constructor state,
locks, transaction boundaries and coordination. Statically bound, typed role functions use
that same owning instance. No dynamic loading, proxy state, diagnostic suppression or altered
algorithm is introduced. API routes separate request contracts, queries and commands. Resident
composition separates fitted health analytics, provider contracts, transport and governance.
Assurance separates admission, collection, planning, mutation, replay and observer responsibilities.
Validation separates ledger, execution, structure, incidents, regression and reporting.
Tests retain their original behavior and parameterizations under responsibility-based paths;
requirement and RRCA test references point to the new locations.

Every active Python module must contain at most 100 nonblank physical lines excluding
comment-only lines and including docstrings. Functions must occupy at most 60 physical lines,
including decorators. The gate rejects violations in runtime, tests, tools and notebooks.
The decomposition manifest records original module hashes, destinations and normalized
function-body parity; this supports review and does not replace behavioral validation.

## Acceptance procedure

1. Check lock freshness and install the locked development graph.
2. Run admission, promotion assessment and the scoped document/evidence profiles.
3. Rerun both qualified upstream tool suites, Pyrefly, Ruff and every host regression.
4. Rerun analytics, assurance, ontology, requirement bindings and notebook export using
   `uv run --no-sync python tools/validate.py`.
5. Inspect `evidence/validation.json` and the seven-column cumulative/RRCA ledgers.
   Inspect `evidence/ci/phase2/policy_evaluation.json` for PROMOTED, an empty policy HOLD
   register, the explicit SQL disposition and observer notification.

Missing approval, changed source sets, package digest mismatch, undeclared approval fields,
authority widening or source-limit violations reject promotion. The assessment writes a
failure receipt, exits nonzero and emits a CI error annotation. Evidence-write failure
blocks completion. Re-pin changed approved policy bytes only after renewed human review.

Malformed Python syntax or incomplete token streams replace any prior PASS assessment
with a fresh FAIL receipt and explicit policy, tool, Docker and deployment HOLDs. The
negative regression injects both parser failures and verifies the stale receipt is replaced.

## Remaining boundaries

Whole scaffoldctl perimeter admission and the full Truth Serum engine remain HOLD pending
host-specific fit. Their scoped read-only support interfaces remain admitted. Docker build,
container execution, delivery, Pi/K3s deployment and hardware verification remain HOLD.
Original archives and the five inherited source seals remain immutable. This continuation
has a separate source manifest under `evidence/ci/promotion`.

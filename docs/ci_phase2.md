# CI/CD phase 2 — policy assessment and scoped tool reuse

## Mission and authority

Phase 2 evaluates the supplied HMT declarations and integrates verified CI support interfaces.
Docker builds, container execution, delivery activation, Pi testing, and deployment remain HOLD.
This phase replaces the previously proposed container-build phase 2. Container work is later.
No candidate policy is globally promoted, and no full tool admission is claimed.

## Evaluation

| Asset | Evidence and fit | Disposition |
|---|---|---|
| HMT policy bundle | Original ZIP preserved; extracted sources individually pinned; versions and candidate status retained | Evaluate; apply a closed CI support profile |
| RRCA v4 | Existing seven-column SQLite ledgers and cumulative gates; new incidents and regression bindings | Reuse canonical ledger vocabulary |
| Axioms | Function gate satisfied; measured module-ceiling violations in legacy active Python files | Full adoption HOLD; new support modules enforce both ceilings |
| Testing/admission | Existence, assumption, boundary, integration, replay, and RRCA tests bound to requirements | Compose with existing CI gates |
| Reuse/transformation | Original artifacts retained; structural and authority deltas named; no self-promotion | Adapt only the required software seam |
| MCP/model-role/PACE policies | Separate authority and domain-specific interfaces; no host CI model or mission-control role | Inventory; no runtime activation |
| scaffoldctl | 253 regression tests; repaired lint and archive execute-bit defects; read-only root contract works | Scoped document validation |
| Truth Serum | 28 tests and 22 subtests; original 93-file seal verifies cleanly; byte-binding tracer works | Scoped evidence binding |
| Field cards / exploration | Geometry and calculus cards do not implement repository admission; scratch/whiteboard are exploration only | Reference and discovery; no copied control algorithms |

The supplied axioms use nonblank physical module lines, excluding comment-only lines and including
docstrings. Existing host enforcement uses a stricter 60-physical-line function measure. The new
assessment reports module gaps without laundering them into PASS. The legacy module decomposition
is a separate, explicit follow-up; no exception or waiver is minted by this profile.
Historical pin availability is reported as PASS, MISMATCH, or UNAVAILABLE. Missing originating
artifacts are not substituted with current bytes. Receipt hashes establish integrity, not signatures.

## Reuse boundary

scaffoldctl's full perimeter pins its own headings, policy pack, and ontology. Changing the host
root policy cannot widen that embedded authority. This integration calls `validate_document` with
explicit host heading rules, then validates the unchanged root-document schema. It never calls
scaffold, hook installation, signing, leases, or full perimeter admission. README remains the only
public-facing document with flair.

Truth Serum's full engine requires its own architecture tree and REQ/INV/ORACLE-TS-001..011 set.
Its CI mode also requires its own witness suite, including mypy. The host retains Pyrefly and Ruff.
The integration calls its strict EvidenceClaim and byte-binding implementation. This establishes
reference/hash integrity, not the semantic truth of arbitrary claims or full engine PASS.

`vendor/admission` keeps original ZIPs. `vendor/qualified` contains the bound support source copies.
scaffoldctl changes are two import-order fixes, two equivalent test context consolidations, and two
executable-mode repairs. Truth Serum runtime source is unchanged; host distribution metadata is new.
The upstream seal remains historical; it is not reused to seal the altered host distribution.
`evidence/ci/phase2/source_delta.json` identifies every byte and mode delta.

## Software validation sequence

1. Pre-install bootstrap checks critical inputs and every qualified source/policy hash.
2. uv lock freshness and locked install admit only the declared dependency graph.
3. G-POLICY-014 measures source limits, qualification pins, and policy-source integrity.
4. G-PROFILE-015 runs read-only document and evidence-binding profiles with failure receipts.
5. G-QUALIFY-016 reruns both upstream regression suites in disposable test contexts, with a
   120-second timeout per tool. scaffoldctl requires at least 95% coverage.
6. Pyrefly, Ruff, every host regression, architecture/ontology, analytics, and assurance gates rerun.

The cumulative software result and the full-policy adoption result are separate fields.
A successful assessment means the assessment ran correctly, including its HOLD observations.
CI annotations flag unresolved policy gaps. An interface failure or changed source exits nonzero.
Evidence write failure blocks completion. No simulated external witness is credited as host
qualification; upstream witness-stub tests prove protocol/failure behavior only.

## Operator procedure and recovery

Run `uv run --no-sync python tools/policy_evaluation.py` and inspect
`evidence/ci/phase2/policy_evaluation.json`. Run `uv run --no-sync python tools/ci_profiles.py`
and inspect `profiles.json`. Run `uv run --no-sync python tools/tool_qualification.py` and inspect
`current/results.json`, logs, JUnit, and coverage. Use `tools/validate.py` for cumulative acceptance.

On changed policy/source: stop, inspect the delta, update pins only after review, and rerun all gates.
On HOLD: read the named missing evidence or ceiling violation; do not translate HOLD to PASS.
On full-engine fit failure: use the declared scoped interface or design a versioned host adapter;
do not copy another product's trace files to manufacture apparent compliance.

## Continuation

Before full policy adoption, decompose oversized active modules and verify import/API/contract
parity, all requirements, full coverage, replay, and every previous gate. Before full tool admission,
qualify the host-specific perimeter and Truth Serum profile plus provenance and distributions.
These steps do not authorize Docker or deployment. Branch protection remains independently required.

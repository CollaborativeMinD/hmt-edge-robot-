# Substrate assurance software specification

## 1. Objective and acceptance partition

OBJ-SAT-03 adds the Mission Cold-Start Cartographer (MCC), Undeclared Side-Effect
Attestor (USEA), and Autonomy Garbage Collector (AGC) to the resident system
software. Functional and nonfunctional acceptance precede deployment. All
requirements are bound in `requirements.json` and `implementation_traceability.json`.
Physical verification, native substrate tracing, and distributed infrastructure
adapters are deferred until a qualified containerized deployment is available.
No hardware verification is executed by this change.

## 2. Software interfaces and transformation law

`RobotCell.assurance` composes the three components with one canonical
transformation kernel and the existing SQLite evidence ledger. Immutable artifact
identity is separate from reference state, scoped observations, and reclamation
decisions. Identity includes content SHA-256, logical ID, owner, generation and
size. A logical ID cannot be overwritten; a replacement requires a new ID.

Each report binds subject identity, contract hash, collector, runtime/policy/
department/membership epochs, observation/expiry, observation hash, coverage,
reason codes and dry-run state. Canonical JSON becomes a report hash and a ledger
chain event. The `witnessed` decorator publishes results and alerts on exceptions.
The `storage_guard` decorator converts SQLite failures to `EvidenceError` after
transaction rollback. Runtime composition uses the live policy epoch; other epochs
remain zero in this single-owner software partition. Distributed epoch adapters
are required before claiming federated authority.

Reports are observations with explicit scopes. They are not signatures, safety
proofs, actuation permissions, or automatic PACE transitions. Watchdogs and
admission continue to enforce live authority. Hash chains require host storage
controls; an administrator able to replace the full database remains a trust root.

## 3. Mission readiness

`mcc.collect(spec, probe)` persists intent and invokes cooperative async stage
adapters using remaining horizon as a timeout. It captures monotonic elapsed time,
initial epochs, and the final transaction's exact expected hash. Adapters must
actually validate the specified transaction; an echoed hash is not independent
validation. Exceptions emit durable alerts; evidence failure propagates.

`mcc.assess(spec, trace)` requires ordered, successful, complete stages, an exact
validated transaction, fresh epochs and scope, and elapsed time no later than the
observation clock. The affordability criterion is strictly:

`mission_ready_sec + reserve_sec < recovery_horizon_sec`.

Equality is not affordable. Container health cannot substitute for the mission
transaction. Cold, warm, missing-model, policy-refresh, and restored-state scenarios
have separate specifications. The campaign executes an actual software admission
and durable SQLite round trip; it does not measure image pulls or physical readiness.

`mcc.envelope` reports observed p95 using the higher order statistic, sample maximum,
failure count, and a Wilson 95% upper endpoint for the observed failure proportion.
These are empirical software observations. The binomial interpretation requires
representative independent samples; no independence or WCET qualification is claimed
for the synthetic/repeated campaign. Blocking adapters or adapters that suppress
cancellation require process isolation before operational use.

## 4. Effect attestation

Effect contracts specify exact kind/target pairs: read, write, network, secret,
spawn and mount, plus runtime and exit-code bounds. No wildcard, prefix allowlist,
path normalization assumption, or implicit secret permission is granted.
Known violations remain violations even if coverage is incomplete. Positive
conformance requires matching executable identity, epochs and freshness, complete
collection, and all required coverage.

The portable file manifest anchors traversal with directory descriptors and refuses
links and nonregular files. It measures persistent file changes only. It cannot
observe reads, reverted writes, transient files, sockets, process descendants,
mounts or secret accesses; its collected trace remains incomplete. A native
strace/proc/container/eBPF adapter is an explicit deployment seam. This release
implements the evaluator and truthful portable observation, not a kernel sandbox.

In-process collectors and fixtures are trusted software adapters. Private API
submissions are forcibly classified `DECLARED_TRACE` regardless of supplied origin.
They cannot produce positive mission-ready or effect-confirmed witnesses. Neither
an API token nor a tool receipt upgrades declared observations into collected truth.

## 5. Reclamation domain and state machine

AGC can reclaim only bytes registered in `assurance_catalog`. It has no filesystem,
container, Kubernetes, model-store or external evidence deletion capability. Its
census completeness applies only to this managed domain. Owners must declare all
live authority, recovery and evidence references before relying on reclamation.
Unknown dependencies, stale epochs, incomplete census or expiry yield UNKNOWN_HOLD.

Dependency closure protects cycles and transitive dependencies in O(V+E) traversal;
one census hash is computed for all decisions. Direct protection precedence is
LIVE, RECOVERY_REQUIRED, EVIDENCE_REQUIRED. Side-effect references conservatively
retain both outputs and touched dependencies as evidence; they never imply garbage.
`bind_witness` verifies the sealed ledger event and atomically adds MCC/USEA references.
Reference removal requires explicit operator review through the reference interface.
Witness expiry does not automatically remove retention references.

The lifecycle is ACTIVE -> QUARANTINE -> RECLAIMED, with QUARANTINE -> ACTIVE
restoration. Planning is dry-run. Quarantine is already an availability mutation
and needs a current reset-authorized operator session. Every mutation needs a
persisted single-use grant, exact plan hash, live epoch and session, matching catalog
revision, unexpired scope, and a reconstructed census/decision. Quarantine keeps
bytes and makes the managed read interface unavailable until restoration. Deletion needs at least 60 seconds dwell and a fresh plan and grant; dwell
alone conveys no authority. Restoration remains permitted for protected quarantined
artifacts. RECLAIMED preserves identity, reference metadata, and immutable receipts.

BEGIN IMMEDIATE fences reference changes against mutation. Catalog state, content,
full membership, revision, quarantine timestamp and evidence are replay checked.
Mutation, revision, grant consumption, receipt and notice commit in one transaction.
A failed evidence append rolls them all back. The managed artifact may be retired;
its authority and evidence records are never garbage collected by this component.
Reclamation is logical SQLite deletion, not secure erasure of WAL, freelist pages
or backups; storage media lifecycle remains a deployment responsibility.

## 6. Observer and alert contract

All three components publish durable `assurance_notice` records. Holds, violations,
and analysis failures produce ALERT with `requires_ack=true`. AGC protection
verdicts are conservative alerts even when expected. An observer polls by monotonically
increasing ledger sequence and acknowledges with a current inspect-authorized
session through `/assurance/ack`. Acknowledgments are appended, never destructive.
Delivery is at-least-once; consumers persist their cursor and deduplicate by sequence.
Alerts remain available after restart. No webhook, email, callback, or human paging
is implied; an operational alert transport must consume the durable outbox.

## 7. Data orchestration and optimization

SQLite reports are verified then transformed to bounded Polars frames. DuckDB
aggregates actual reports. Atomic per-file exports include the readiness atlas,
recovery-margin witnesses, effect JSONL and contract report, reclamation plan,
reclaim receipts, reference GraphML and manifest SHA-256 values. The export is a
bounded recent window, not a backup or complete evidence history. Files are individually
atomic; consumers verify the manifest and retry a concurrent multi-file publication.

The exact 0/1 knapsack optimizer selects a recommended warm set within a declared
integer resource budget. Descending budget iteration prevents duplicate artifact use;
canonical ordering gives deterministic ties. It is advisory only. The independent
brute-force oracle checks optimality on small instances. Its worst-case work is
64 candidates times 1024 budget units. No benefit estimate grants admission or
removes recovery references. Do not substitute optimization scores for verdicts.

## 8. Nonfunctional bounds and gates

| Surface | Bound |
|---|---|
| Artifact catalog | 1024 retained identities; 16 MiB per blob; content verification streams one blob at a time |
| Reference lists | 256 per category; 1024 census records |
| Recovery | 16 stages; 256 campaign traces; horizon/reserve <= 86400 sec; witness TTL <= 3600 sec |
| Effect records | 256 allowed effects; 1024 observed effects; six coverage kinds |
| File manifest | Default 256 regular files / 16 MiB total; descriptor-anchored traversal |
| Notices / analytics | 256 notices per read / 1024 recent notices per report window |
| Private API | Existing 16 KiB body, five-second receive deadline, global rate cap; use local SDK for large plans |
| Optimization | 64 candidates, 1024 budget units; finite saved time <= 86400 sec per artifact |
| Software performance | 258-record campaign planning <10 sec; max optimizer campaign <2 sec; host observations only |
| Regression | All existing gates plus G-TRIAD-011; combined branch/line coverage >=90%; functions <=60 physical lines |

No paid inference is needed or invoked. Physical performance, memory allocation
compliance and hardware readiness are outside these software acceptance claims.

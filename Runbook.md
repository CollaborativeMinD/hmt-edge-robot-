# Operator SOP

## 1. Install and accept the supervisory build

Prerequisites: Python 3.12+ and uv. Run from the repository root.

```bash
uv sync --frozen --extra dev
uv run pyrefly check --min-severity warn
uv run ruff check src tests tools notebooks
uv run python tools/validate.py
```

Inspect `evidence/validation.json`, `evidence/cumulative_gate_ledger.csv`,
`evidence/reverse_rca_ledger.csv`, and `evidence/verification.sqlite`.
PASS applies to each evidenced software gate. HOLD blocks the associated external
partition; it must not be renamed PASS because unrelated tests passed.

## 2. Run the composed mission and inspect truth

```bash
uv run hmt-edge-robot demo --database runtime/cell.db
uv run hmt-edge-robot replay --database runtime/cell.db
uv run hmt-edge-robot analytics --database runtime/cell.db
uv run hmt-edge-robot export --database runtime/cell.db --output runtime/evidence.parquet
```

Expected demo outcome: SUCCEEDED, resident ADMIT for inspect, ML HOLD for the
deliberately out-of-envelope sample. SUCCEEDED requires both acknowledgments and
finite, matching gripper/position feedback. Replay checks event hashes and task
projections without changing pending tasks. Analytics preserves invalid thermal
readings as gaps. Export is a bounded recent window, not a complete archive.

## 3. Start the private SIL API

```bash
read -rs HMT_OPERATOR_TOKEN
export HMT_OPERATOR_TOKEN
read -rs HMT_API_TOKEN
export HMT_API_TOKEN
uv run hmt-edge-robot serve --database runtime/api.db
```

Supply independently chosen tokens of at least 16 characters through these prompts
or a secret manager. The server listens on `127.0.0.1:8000`, one worker. `/health`
reports only liveness and SIL mode. `/docs` supplies the typed wire contracts.
All operational routes require `Authorization: Bearer <HMT_API_TOKEN>`.

1. POST `/sessions` with operator_id `operator` and the operator proof.
2. POST `/simulation/observe` to acquire explicitly synthetic telemetry.
3. POST `/tasks` with the returned session, current epoch, a unique request ID,
   robot-base target in millimetres, speed in metres/second, and monotonic issue
   and expiry times. Obtain current monotonic time in the composing client;
   a production remote client needs a qualified clock-domain adapter.
4. POST `/cycle` to execute one admitted queued SIL task. Inspect its receipt.
5. POST `/sessions/heartbeat` before presence expires. Revoke when work ends.
6. POST `/resident` for an advisory answer. Tools recheck the same session after
   inference; generated text conveys no authority.

Bodies are limited to 16 KiB, with a five-second receive deadline and a process-wide
120-request/minute cap. A public endpoint requires a separately validated ingress,
TLS, OIDC and operational deployment; this SOP does not publish the API.

## 4. Resident operation

```bash
uv run hmt-edge-robot resident --database runtime/resident.db --question 'Inspect evidence'
```

This uses the explicit deterministic offline provider. For a local compatible
server, supply both `--model-url http://127.0.0.1:8080/v1` and `--model-id` matching
its exact served identity. The endpoint must support strict JSON-schema responses
and complete Chat Completions receipts. Startup runs a qualification canary.
Cloud requires `allow_cloud: true` in a complete validated Policy JSON and
`HMT_MODEL_KEY` provisioned as a secret. Ordinary validation never calls a provider.
The paid campaign harness reserves worst-case spend before each attempt, caps four
calls and $1, and does not retry or authorize repeated GitHub run attempts.
The build workflow contains no live-provider invocation.

## 5. Stop, recover, and troubleshoot

| Symptom | Required action and evidence |
|---|---|
| STOP_LATCHED / PROTECTIVE_STOP | Stop further submissions; inspect spatial_observation. Restore fresh safe geometry, then explicitly reset using a current reset-authorized session. Physical reset remains unqualified. |
| SUBSTRATE_NOT_READY | Inspect sensor_assessment, sequence, sample age, voltage and thermal gaps. Acquire the next fresh SIL observation; do not replace a missing measurement with a normal value. |
| AUTHORITY_NOT_ADMITTED | Inspect operator identity, session expiry/presence and policy epoch. Log in again after policy changes. Never invent permissions from an identifier prefix. |
| DRIVER_ACK_REJECTED / feedback mismatch | Keep stop latched. Trace intent, EXECUTING and VERIFYING evidence; diagnose the adapter. Submit a new request only after explicit recovery. |
| RESTART_RECONCILIATION_REQUIRED | Writable startup marks unfinished work FAILED without replaying motion. Confirm physical state independently before new work. |
| EVIDENCE_UNAVAILABLE / hash or projection mismatch | Stop. Preserve the database and investigate storage/tampering. Never delete events, drop integrity triggers, or auto-repair a corrupted chain. |
| Resident HOLD | Inspect model ID, policy/schema/context hashes and rejection code. Resolve qualification or evidence validity. Do not coerce raw text into commands. |
| 413 / 408 / 429 | Reduce payload, finish within the receive deadline, or wait for the rate window. Do not raise bounds to bypass a malfunctioning client. |

## 6. Maintenance and release

Stop the service before copying `runtime/cell.db` and its WAL/SHM if present; use
SQLite's online backup API when copying a running database. Verify the backup by
opening it with the read-only replay command. Protect runtime evidence and secrets
with host access controls. The hash chain detects alteration; it is not a signature
against an administrator able to replace the entire database.

After any contract, policy, model, algorithm or dependency change, rerun all gates
using `tools/validate.py`, add the causal incident to `docs/incidents.json` where
applicable, and review the seven-column ledgers. Advance policy epochs and revoke
old leases. Train the health model only on a reviewed labelled baseline; the demo
baseline is synthetic. Preserve all failed/HOLD evidence. Deploy physical firmware
only after the hardware and compliance gates in `docs/compliance.md` pass.

## 7. Validate and operate substrate assurance software

Run all gates and the standalone offline campaign:

```bash
uv run python tools/validate.py
uv run python tools/assurance_campaign.py
```

Inspect `evidence/triad/campaign.json`, `capability_readiness_atlas.parquet`,
`cold_start_recovery_margin_report.json`, `effect_attestation.jsonl`,
`side_effect_contract_report.json`, `safe_reclamation_plan.json`,
`artifact_reference_graph.graphml`, `reclaim_receipt.json`, and `export_manifest.json`
inside `evidence/triad/`. The file-manifest attestation must remain
ATTESTATION_INCOMPLETE; the campaign PASS verifies that honest software behavior.
The campaign has zero driver moves and performs no live provider or hardware calls.

For the private API, use `/docs` for the strict assurance request schemas:

1. Obtain a current operator session using section 3. Use bearer authentication on
   all `/assurance/*` routes. Renew the heartbeat during longer operations.
2. Register explicitly managed software bytes through `/assurance/artifacts`;
   declare authority/recovery/evidence/dependency references through
   `/assurance/references` before planning. Existing host files are not registered
   or deleted implicitly.
3. Evaluate declared traces with `/assurance/readiness` or `/assurance/attest`.
   API declarations do not qualify as collected observation. Use trusted local
   software adapters for `cell.assurance.mcc.collect` and the USEA evaluator.
4. Bind fresh sealed MCC/USEA evidence with `/assurance/bind-witness`. Binding is
   conservative retention, and requires a reset-authorized current session.
5. POST `/assurance/plan` with the session context. Inspect every decision and the
   domain scope. It performs no lifecycle mutation.
6. POST `/assurance/grant` with that exact plan, artifact ID and requested action.
   POST `/assurance/execute` with the exact plan and returned grant. A new reference,
   changed epoch, expiry, used grant or changed revision requires a fresh plan.
7. Restore a quarantined artifact using a fresh plan and `restore` grant. For
   deletion, wait at least 60 seconds, acquire a fresh plan and current session,
   then request a new `delete` grant. Preserve the resulting receipt and identity.
8. Poll `/assurance/notices?after_seq=0&limit=32`, persist the greatest processed
   sequence, and deduplicate by sequence. POST `/assurance/ack` with session,
   operator and report hash after reviewing each alert. Use `/assurance/analytics`
   for bounded report counts. Acknowledgment does not resolve the underlying condition.

| Condition | Required action |
|---|---|
| Mission not ready / horizon exhausted | Inspect stage order, exact acceptance transaction, elapsed time, reserve and scenario. Correct the adapter or recovery plan; do not replace the mission check with liveness. |
| ATTESTATION_INCOMPLETE | Identify missing effect coverage, executable identity or expiry. Retain a HOLD until an appropriate collector supplies evidence. File snapshots cannot close process-wide coverage. |
| SIDE_EFFECT_OUTSIDE_CONTRACT | Preserve contract and observed trace. Trace the actual effect back to admission and execution; amend code or re-admit a reviewed effect contract. |
| UNKNOWN_HOLD | Inspect census completeness, record epochs and dangling dependencies. Do not delete or fabricate absent references. |
| Mutation fence / authority denied | Recheck operator session, heartbeat, epochs, revision, issued grant and current references; acquire a new plan and grant. |
| Catalog hash / projection mismatch | Stop mutations; preserve database/WAL and immutable events. Investigate full membership and revision as well as bytes; never auto-repair projections. |
| ASSURANCE_STORAGE_UNAVAILABLE | Treat as evidence failure. Stop, preserve storage and resolve database availability before retry. |

For large plans use the local typed SDK; do not raise the 16 KiB request limit.
Back up the whole SQLite database using section 6. Hardware verification is deferred
until a qualified containerized deployment exists. The software requirement scope,
trust assumptions, optimization bounds and adapter seams are specified in
`docs/substrate_assurance.md`.


## 8. Maintain the static typing gate

Pyrefly 1.3.2 is pinned in the development extra and `uv.lock`; Ruff remains the
lint gate. The `tool.pyrefly` configuration checks `src`, `tests`, `tools`, and the
executable notebook, including unannotated definitions and generated code. The
G-TYPES-012 gate runs `pyrefly check --min-severity warn` through the same cumulative
validator used by GitHub Actions. A warning or error blocks software acceptance.
Locked `types-jsonschema` and `types-defusedxml` provide upstream type interfaces.

On a failure, read the current run's `G-TYPES-012.log`. Resolve the violated type
contract at its defining boundary, narrow optional values before use, and preserve
runtime schema guards. Deliberately invalid input tests must use `model_validate`
and mutation attempts must use `setattr`; neither is a diagnostic suppression.
Do not add baselines, ignore comments, missing-import bypasses, or blanket error
exclusions to obtain PASS. Run all cumulative gates after each correction. Historical
acceptance seals remain unchanged; the typing update has its own source receipt.

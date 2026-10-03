# Operator SOP

## 1. Install and accept the supervisory build

Prerequisites: Python 3.12+ and uv. Run from the repository root.

```bash
uv sync --frozen --extra dev
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

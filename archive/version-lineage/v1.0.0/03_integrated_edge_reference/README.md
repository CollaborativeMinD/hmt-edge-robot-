# HMT Edge Robot

Five composed robotics subsystems with durable evidence, analytics, and an embedded
HMT resident. Python 3.12+, Pydantic v2, uv, FastAPI, SQLite, Polars, DuckDB,
OpenCV, PGA geometry, and a fitted classical ML health model.

```bash
uv sync --frozen --extra dev
uv run hmt-edge-robot demo
uv run hmt-edge-robot replay
uv run hmt-edge-robot analytics
uv run hmt-edge-robot export
uv run python tools/validate.py
```

The demo performs calibrated grasp planning, operator admission, fresh substrate
and proximity checks, acknowledged simulated movement, gripper feedback
verification, evidence replay, and a resident proposal. All simulation acquisition
is explicit. The resident can inspect, diagnose, or plan; it cannot actuate.

| Subsystem | Implemented depth |
|---|---|
| AccessManager | Provisioned identities, scoped leases, presence heartbeat, expiry, revocation, policy epochs |
| HaloSafe | Freshness and frame guards, path separation, derived stopping margin, speed scaling, latched stop, SIL admittance |
| Waialua | Bounded telemetry, hysteresis, power and thermal lanes, invalid-data gaps, durable critical shutdown |
| NeuroGrasp | Multiple ranked PCA candidates, ambiguity rejection, calibration, PGA coordinate transforms, frame provenance |
| FactoryOrchestrator | Bounded queue, transactional admission, duplicate prevention, state law, acknowledgment and feedback gates, restart reconciliation |
| Data and analytics | Append-only SQLite hash chain, verified projections, Polars trends, DuckDB aggregation, atomic Parquet export |
| Resident HMT | Explicit ML training envelope, bounded evidence context, schema admission, allowlisted tools, qualified local or opt-in cloud LLM seam |

Acceptance is partitioned: supervisory software and SIL are executable here.
Physical actuator deployment, calibrated stopping behavior, static-memory firmware,
MISRA certification, distributed HA, and statistical ML qualification remain HOLD
until their external evidence exists. The architecture's cloud and deployment
components are mapped explicitly; absent services are never reported as running.

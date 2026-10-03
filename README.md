# 🦾 HMT Edge Robot

**Five subsystems. One coherent cell.**

Governed edge robotics, resident HMT, and evidence you can replay.

[![CI](https://github.com/CollaborativeMinD/hmt-edge-robot-/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/CollaborativeMinD/hmt-edge-robot-/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-137_passing-2ea043?style=flat-square)](evidence/validation.json)
[![Coverage](https://img.shields.io/badge/coverage-97.78%25-2ea043?style=flat-square)](evidence/coverage.json)
[![Supervisory SIL](https://img.shields.io/badge/supervisory_SIL-PASS-2ea043?style=flat-square)](evidence/validation.json)
[![Physical deployment](https://img.shields.io/badge/physical_deployment-HOLD-d29922?style=flat-square)](docs/compliance.md)

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776ab?style=flat-square&logo=python&logoColor=white)](pyproject.toml)
[![Pyrefly](https://img.shields.io/badge/Pyrefly-1.3.2-8b5cf6?style=flat-square)](pyproject.toml)
[![Pydantic](https://img.shields.io/badge/Pydantic-v2-e92063?style=flat-square)](docs/contracts.schema.json)
[![Resident HMT](https://img.shields.io/badge/resident_HMT-advisory-7c3aed?style=flat-square)](docs/architecture.md)
[![Lineage](https://img.shields.io/badge/lineage-v1.0.0-0969da?style=flat-square)](archive/version-lineage/v1.0.0/VERSION_LINEAGE.md)

Five composed robotics subsystems with durable evidence, analytics, and an embedded
HMT resident. Python 3.12+, Pydantic v2, uv, FastAPI, SQLite, Polars, DuckDB,
OpenCV, PGA geometry, and a fitted classical ML health model.

**Reflex before cognition. Evidence before trust.** The resident helps inspect,
diagnose, and plan. Operator authority and deterministic guards control execution.

## Run the cell

```bash
uv sync --frozen --extra dev
uv run hmt-edge-robot demo
uv run hmt-edge-robot replay
uv run hmt-edge-robot analytics
uv run hmt-edge-robot export
uv run pyrefly check --min-severity warn
uv run python tools/validate.py
```

The demo performs calibrated grasp planning, operator admission, fresh substrate
and proximity checks, acknowledged simulated movement, gripper feedback
verification, evidence replay, and a resident proposal. All simulation acquisition
is explicit. The resident can inspect, diagnose, or plan; it cannot actuate.

## Inside the cell

| Subsystem | Implemented depth |
|---|---|
| AccessManager | Provisioned identities, scoped leases, presence heartbeat, expiry, revocation, policy epochs |
| HaloSafe | Freshness and frame guards, path separation, derived stopping margin, speed scaling, latched stop, SIL admittance |
| Waialua | Bounded telemetry, hysteresis, power and thermal lanes, invalid-data gaps, durable critical shutdown |
| NeuroGrasp | Multiple ranked PCA candidates, ambiguity rejection, calibration, PGA coordinate transforms, frame provenance |
| FactoryOrchestrator | Bounded queue, transactional admission, duplicate prevention, state law, acknowledgment and feedback gates, restart reconciliation |
| Data and analytics | Append-only SQLite hash chain, verified projections, Polars trends, DuckDB aggregation, atomic Parquet export |
| Substrate assurance | MCC mission readiness, USEA coverage-scoped effects, AGC governed catalog lifecycle, durable observer alerts |
| Resident HMT | Explicit ML training envelope, bounded evidence context, schema admission, allowlisted tools, qualified local or opt-in cloud LLM seam |

## Proof and lineage

The test, coverage, and PASS badges describe the committed validation snapshot;
the CI badge links to current workflow results. The evidence pack includes a
32-cycle composed SIL campaign, requirement and ontology bindings, cumulative
gate and RRCA ledgers, and a bounded live resident canary with zero driver moves.

[Executable notebook](notebooks/cell_ssot.py) ·
[Validation receipt](evidence/validation.json) ·
[Triad software campaign](evidence/triad/campaign.json) ·
[Live canary receipt](evidence/live_session.json) ·
[Version lineage archive](archive/version-lineage/v1.0.0/VERSION_LINEAGE.md)

**Checkpoint preserved.** The archive carries the five V1 prototypes, their five
Lambda revalidation packs, and the immutable reference to this integration.
The next software update adds the [Substrate Assurance Triad](docs/substrate_assurance.md).
The archived checkpoint remains immutable; future lineage additions use a new archive version.

Start with [Runbook.md](Runbook.md). See [architecture](docs/architecture.md),
[requirements](docs/requirements.md), [compliance boundaries](docs/compliance.md),
and [Agents.md](Agents.md) before extending the cell.

## Acceptance boundary

Acceptance is partitioned: supervisory software and SIL are executable here.
Physical actuator deployment, calibrated stopping behavior, static-memory firmware,
MISRA certification, distributed HA, and statistical ML qualification remain HOLD
until their external evidence exists. The architecture's cloud and deployment
components are mapped explicitly; absent services are never reported as running.

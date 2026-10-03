# Partition acceptance and deployment gates

Python, NumPy, SQLite and the resident are a dynamically allocated supervisory/SIL
partition. They must not be promoted into static-memory real-time safety firmware.
The supplied cyber-physical overlays require evidence for deployment; the following
boundaries are enforced by HOLD rather than invented compliance.

| Gate | Disposition | Evidence required to close |
|---|---|---|
| G-HARDWARE-001 | HOLD | Qualified actuator adapter, independent watchdog/stop, measured deadline enforcement and true feedback |
| G-CALIBRATION-002 | HOLD | Camera extrinsics, robot frame, human sensing coverage, reaction/stop time, braking distance and uncertainty measurements |
| G-MISRA-003 | HOLD | Actual critical firmware source, MISRA C++23 assessment, deviations and compiler/target evidence |
| G-MEMORY-004 | HOLD | Static allocation and target resource proof for critical firmware; Python cannot satisfy this gate |
| G-UB-005 | HOLD | Target sanitizers/static analysis and qualified toolchain; Python SAST is a different gate |
| G-DISTRIBUTED-006 | HOLD | Single-owner election, split-brain fencing, replicated evidence and deployment failover trials |
| G-ML-007 | HOLD | Reviewed real training data, drift/OOD studies and task-specific holdout evaluation |

Ruff security rules and strict finite contracts check the supervisory source.
They do not certify the underlying native libraries. Locked versions make the
environment reproducible; dependency security updates still require review and
cumulative regression. The live language-model canary establishes only a narrow
schema/policy integration result. No provider output grants safety authority.

Driver timeout arguments and post-return deadline checks detect a late driver;
they cannot preempt a blocking physical adapter. Deployment requires an independent
bounded actuator/watchdog implementation. No automatic homing or replay recovery
is permitted. The synthetic vision and telemetry tools are explicitly SIL.

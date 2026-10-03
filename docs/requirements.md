# Functional and nonfunctional requirements

Scope: supervisory software and explicit SIL. Gate PASS means the stated acceptance criterion was checked in that partition. External gates remain in `compliance.md`.

| Requirement | Acceptance criterion | Primary source | Regression |
|---|---|---|---|
| REQ-AM-01 | Provisioned identity and permission scope; false proof creates no lease | src/hmt_edge_robot/access.py | test_access_auth_scope_expiry_and_revocation |
| REQ-AM-02 | Expiry, monotonic presence and revocation prevent stale authority | src/hmt_edge_robot/access.py | test_access_clock_and_capacity |
| REQ-AM-03 | Policy epoch update revokes leases and pending authority | src/hmt_edge_robot/runtime.py | test_policy_update_revokes_pending_authority |
| REQ-HS-01 | Reject stale, repeated and mismatched-frame spatial observations | src/hmt_edge_robot/safety.py | test_safety_invalid_stale_frame_and_reset |
| REQ-HS-02 | Check path segment separation and scale speed within protective bounds | src/hmt_edge_robot/safety.py | test_safety_path_distance_not_endpoint |
| REQ-HS-03 | Finite bounded SIL admittance preserves declared dynamical law | src/hmt_edge_robot/safety.py | test_admittance_law_and_bounds |
| REQ-WN-01 | Power/thermal assessments choose bounded PACE lanes with hysteresis | src/hmt_edge_robot/edge.py | test_edge_lanes_gaps_hysteresis_halt |
| REQ-WN-02 | Overtemperature readings remain null gaps; critical power halts and flushes | src/hmt_edge_robot/edge.py | test_edge_lanes_gaps_hysteresis_halt |
| REQ-WN-03 | Reject stale or repeated samples and bound retained history | src/hmt_edge_robot/edge.py | test_edge_sequence_age_and_history_bounds |
| REQ-NG-01 | Return bounded ranked PCA grasp candidates and reject ambiguous shapes | src/hmt_edge_robot/vision.py | test_vision_rejects_ambiguity_empty_small_and_format |
| REQ-NG-02 | Calibrate candidates through PGA with classical transform/inverse parity | src/hmt_edge_robot/geometry.py | test_pga_classical_parity_and_inverse |
| REQ-NG-03 | Bind each grasp to calibration ID and deterministic frame hash | src/hmt_edge_robot/vision.py | test_grasp_candidates_calibration_determinism |
| REQ-FO-01 | Admit only valid current-session, epoch, time, substrate and geometry requests | src/hmt_edge_robot/orchestrator.py | test_admission_denials |
| REQ-FO-02 | SUCCEEDED requires both driver acknowledgments and matching finite feedback | src/hmt_edge_robot/orchestrator.py | test_driver_ack_and_feedback_regressions |
| REQ-FO-03 | Bound queue, reject duplicate concurrent claims and permit authorized cancellation | src/hmt_edge_robot/orchestrator.py | test_duplicate_atomic_admission |
| REQ-FO-04 | Revalidate authority after movement and stop on deadline or evidence failure | src/hmt_edge_robot/orchestrator.py | test_authority_rechecked_after_movement |
| REQ-DB-01 | Atomically persist intent and lawful state transition before side effects | src/hmt_edge_robot/ledger.py | test_evidence_failure_stops_before_side_effect |
| REQ-DB-02 | Verify append-only hash chain, projection and restart without motion replay | src/hmt_edge_robot/ledger.py | test_projection_tamper_detected |
| REQ-AN-01 | Aggregate actual persisted events with Polars and DuckDB | src/hmt_edge_robot/analytics.py | test_analytics_actual_engines_and_parquet |
| REQ-AN-02 | Preserve sensor gaps and bound analytics windows | src/hmt_edge_robot/analytics.py | test_empty_analytics |
| REQ-AN-03 | Atomic Parquet export matches validated database records | src/hmt_edge_robot/analytics.py | test_analytics_actual_engines_and_parquet |
| REQ-HMT-01 | Fit explicit seeded ML baseline; HOLD nonfinite, unfit and out-of-envelope samples | src/hmt_edge_robot/resident.py | test_classical_ml_fit_inference_and_determinism |
| REQ-HMT-02 | Bind bounded model context to policy, schema, profile and real evidence hashes | src/hmt_edge_robot/resident.py | test_resident_context_tools_and_bounds |
| REQ-HMT-03 | Reject malformed or unsupported proposals; model has no actuator tool | src/hmt_edge_robot/resident.py | test_resident_invalid_provider_holds |
| REQ-HMT-04 | Explicit provider qualification, no retries, bounded time/body/budget and usage certainty | src/hmt_edge_robot/resident.py | test_paid_adapter_incomplete_or_uncertain_usage_holds |
| REQ-UI-01 | Authenticated FastAPI operator flow uses strict JSON wire contracts | src/hmt_edge_robot/api.py | test_api_full_operator_flow |
| REQ-UI-02 | CLI demo, read-only replay, analytics and export compose the same runtime | src/hmt_edge_robot/cli.py | test_read_only_queries_do_not_recover_pending_tasks |
| REQ-SYS-01 | Nominal coupled mission yields consistent terminal state and evidence | src/hmt_edge_robot/runtime.py | test_nominal_outcome_chain |
| REQ-NFR-01 | Strict, frozen, extra-forbidden finite contracts at domain seams | tools/validate.py | test_contracts_forbid_unknown_mutation_coercion |
| REQ-NFR-02 | Bounded request bodies, receive deadlines and process rate window | tools/validate.py | test_global_body_and_rate_bounds |
| REQ-NFR-03 | Queue, session, sensor and context capacities enforced | tools/validate.py | test_queue_backpressure_and_cancel |
| REQ-NFR-04 | Replay detects payload corruption and never mutates pending state | tools/validate.py | test_read_only_queries_do_not_recover_pending_tasks |
| REQ-NFR-05 | Evidence failures stop execution before first side effect | tools/validate.py | test_evidence_failure_stops_before_side_effect |
| REQ-NFR-06 | Observed SIL p95 cycle below 100 ms and Linux host peak RSS below 512 MiB | tools/validate.py | test_nominal_outcome_chain |
| REQ-NFR-07 | Functions <=60 physical lines; security lint and locked reproducible dependencies | tools/validate.py | test_nonfinite_boundary_rejected |
| REQ-NFR-08 | Every declared requirement has implementation/test binding; every contract field has ontology binding | tools/validate.py | test_contracts_forbid_unknown_mutation_coercion |
| REQ-NFR-09 | Resident proposals remain advisory; unknown tools and cloud defaults blocked | tools/validate.py | test_resident_context_tools_and_bounds |
| REQ-NFR-10 | Full offline suite passes with >=90% combined line/branch coverage | tools/validate.py | test_nominal_outcome_chain |

## Substrate assurance software requirements

Scope: system software. Physical deployment verification is deferred. The normative test and gate bindings are in `requirements.json`; operating assumptions are in `substrate_assurance.md`.

| Requirement | Kind | Acceptance criterion | Regression |
|---|---|---|---|
| REQ-MCC-01 | functional | Mission readiness requires ordered successful stages and the exact validated transaction hash; deadline equality holds | test_mcc_mission_readiness_and_boundary |
| REQ-MCC-02 | functional | Stage failure, stale epochs, future or expired traces cannot certify mission readiness | test_mcc_incomplete_invalid_and_stale |
| REQ-MCC-03 | functional | Cooperative asynchronous software probes use remaining recovery budget and persist intent; timeout or malformed adapter fails closed | test_software_probe_durable_failure_and_no_returned_readiness |
| REQ-MCC-04 | functional | Bound campaigns to 256; report empirical p95, maximum and Wilson failure endpoint without a worst-case guarantee | test_mcc_empirical_envelope_is_not_wcet |
| REQ-USEA-01 | functional | Compare exact effect kind and target, runtime and exit contract; a valid receipt cannot substitute for effect conformance | test_usea_effect_receipt_distinction |
| REQ-USEA-02 | functional | Incomplete coverage, unbound executable identity, expiry or changed epochs cannot produce conformance | test_usea_incomplete_is_hold |
| REQ-USEA-03 | functional | Actual file manifests detect persistent writes, refuse links and special files, and never claim reads or transient effects | test_manifest_actual_writes_and_coverage_limit |
| REQ-AGC-01 | functional | Compute transitive protection across cycles; retain authority, recovery, evidence and effect dependencies | test_agc_transitive_reference_closure_and_cycles |
| REQ-AGC-02 | functional | Incomplete, stale, mismatched-epoch or dangling-reference census yields UNKNOWN_HOLD | test_agc_unknown_hold |
| REQ-AGC-03 | functional | Plan is dry-run; quarantine preserves bytes, restoration is reversible, deletion requires fresh authority and dwell | test_agc_dry_run_quarantine_restore_and_governed_delete |
| REQ-AGC-04 | functional | Atomic revision fence, issued single-use grants, live session recheck and decision reconstruction reject stale or forged mutation | test_agc_fence_changed_reference_and_no_grant_replay |
| REQ-AGC-05 | functional | Catalog content, full membership, revision, quarantine time and state replay match durable events | test_catalog_missing_record_and_revision_tamper |
| REQ-SAT-01 | functional | Persist cursor-addressed notices and alerts with admitted acknowledgments; survive restart and propagate failures | test_observer_durable_cursor_ack_and_restart |
| REQ-SAT-02 | functional | Atomically bind MCC recovery and USEA effect witnesses into catalog retention; reject forged or unknown evidence | test_cross_component_witness_retention |
| REQ-SAT-03 | functional | Transform validated SQLite reports through Polars/DuckDB into hashed JSONL, GraphML and Parquet software evidence | test_assurance_export_sql_parquet_jsonl_graphml |
| REQ-SAT-04 | functional | Private strict JSON API admits sessions and grants; submitted trace claims cannot become collected observations | test_assurance_api_native_json_and_declared_trace_hold |
| REQ-SAT-NFR-01 | nonfunctional | Finite frozen contracts reject coercion and unknown fields; every witness binds identity, contract, collector, epochs and expiry | test_assurance_contracts_strict_finite_frozen |
| REQ-SAT-NFR-02 | nonfunctional | Bound managed catalog to 1024 records and 16 MiB per blob; manifests to 256 files/16 MiB by default; observer reads to 256 and analytics to 1024 | test_catalog_and_census_bounds |
| REQ-SAT-NFR-03 | nonfunctional | No committed lifecycle mutation or consumed grant when evidence fails; storage failures propagate as EvidenceError | test_agc_evidence_failure_rolls_back_mutation |
| REQ-SAT-NFR-04 | nonfunctional | Exact bounded 0/1 knapsack matches independent brute-force oracle and never grants authority | test_optimization_exact_against_brute_force |
| REQ-SAT-NFR-05 | nonfunctional | Read-only assurance census and analytics leave projections and pending work unchanged | test_catalog_readonly_no_recovery_or_writes |
| REQ-SAT-NFR-06 | nonfunctional | Software campaign plans 258 records within 10 sec and optimizes 64 candidates/1024 budget within 2 sec on acceptance host, with zero driver moves | test_optimization_exact_against_brute_force |

| REQ-NFR-11 | nonfunctional | Pinned Pyrefly checks source, tests, tools and notebook; zero warnings/errors, static mismatch rejects CI alongside Ruff | test_pyrefly_rejects_invalid_return |

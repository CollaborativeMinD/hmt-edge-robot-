# HMT Baseline MCP Tools Policy v1.2.0

> Human-readable projection of `HMT_Baseline_MCP_Tools_v1.2.0.json`.

## Policy identity

- Baseline: `HMT-MCP-BASELINE/1.2.0`
- Status: `FROZEN`
- Canonical tool count: `13`
- Supersedes: `HMT-MCP-BASELINE/1.1.0`
- Freeze authority: `human_architect_explicit_order`

Version 1.2.0 preserves the thirteen-tool v1.1.0 surface. It changes only the completion behavior of `task_update` and the review-readiness evaluation performed by `working_agreement`. No tool was added, removed, renamed, or granted new authority.

## Tool groups

| Group | Count | Tools |
|---|---:|---|
| `repository_operations` | 4 | `list_files`, `read_file`, `write_file`, `run_command` |
| `task_control` | 6 | `tasks_list`, `task_get`, `task_update`, `task_create`, `working_agreement`, `verify_task_board` |
| `capability_discovery` | 1 | `list_skills` |
| `evidence_retrieval` | 1 | `memory_search` |
| `version_control` | 1 | `git_lane` |

## Canonical tool surface

| # | Tool | Group | Effect | Mission packet | Purpose |
|---:|---|---|---|---:|---|
| 1 | `list_files` | `repository_operations` | `observe` | `true` | List admitted files within the bounded repository root. |
| 2 | `read_file` | `repository_operations` | `observe` | `true` | Read an admitted text file from the bounded repository root. |
| 3 | `write_file` | `repository_operations` | `mutate` | `true` | Create or update an admitted file within the bounded repository root. |
| 4 | `run_command` | `repository_operations` | `execute` | `true` | Execute an admitted deterministic command without a shell. |
| 5 | `tasks_list` | `task_control` | `observe` | `false` | Return authoritative task-board cards and lifecycle states. |
| 6 | `task_get` | `task_control` | `mutate` | `true` | Claim one admitted unstarted task for the assigned agent. |
| 7 | `task_update` | `task_control` | `mutate` | `true` | Submit progress through the completion firewall, run all admitted package tests, and emit corrective feedback when rejected. |
| 8 | `task_create` | `task_control` | `mutate` | `true` | Create an admitted follow-up or repair task without granting execution authority. |
| 9 | `working_agreement` | `task_control` | `observe` | `false` | Return the next lawful action and require a current passing package-test receipt before review. |
| 10 | `verify_task_board` | `task_control` | `observe` | `false` | Detect task lifecycle contradictions and completion-policy breaches. |
| 11 | `list_skills` | `capability_discovery` | `observe` | `false` | Return capabilities visible to a registered agent in its authoritative state. |
| 12 | `memory_search` | `evidence_retrieval` | `observe` | `false` | Retrieve task-scoped GraphRAG evidence for a registered agent. |
| 13 | `git_lane` | `version_control` | `execute` | `true` | Execute one schema-selected, policy-governed Git-lane operation inside the exact admitted repository root. |

## Mandatory controls by tool

### `list_files`

`repository_root_containment`, `path_normalization`, `bounded_result_count`, `fail_closed_on_boundary_violation`, `execution_receipt`

### `read_file`

`repository_root_containment`, `path_normalization`, `secret_and_binary_rejection`, `bounded_input_bytes`, `execution_receipt`

### `write_file`

`repository_root_containment`, `path_normalization`, `authority_and_assignment_admission`, `bounded_write_bytes`, `content_hash`, `execution_receipt`

### `run_command`

`shell_false`, `command_allowlist`, `fixed_timeout`, `bounded_stdout_stderr`, `working_directory_containment`, `execution_receipt`

### `tasks_list`

`authoritative_state_source`, `typed_task_rows`, `bounded_result_count`, `no_state_mutation`

### `task_get`

`authority_and_assignment_admission`, `single_task_claim`, `legal_state_transition`, `execution_receipt`

### `task_update`

`authority_and_assignment_admission`, `package_hash`, `truth_serum_check`, `reverse_rca_check`, `cumulative_gate_check`, `scaffoldctl_check`, `strict_package_test_manifest`, `complete_test_inventory`, `no_test_suppressions`, `sandboxed_shell_false_test_execution`, `server_owned_test_execution_policy`, `bounded_test_resources`, `current_package_test_receipt`, `append_only_receipt`, `corrective_feedback_outbox`, `reverse_rca_resubmission`, `verify_task_board_coupling`, `working_agreement_coupling`, `no_self_promotion_to_done`

### `task_create`

`authority_and_assignment_admission`, `parent_task_reference_when_derived`, `reason_code_when_derived`, `bounded_task_creation`, `idempotency_key`, `execution_receipt`

### `working_agreement`

`authoritative_task_state`, `deterministic_priority_order`, `current_package_test_receipt_required_for_review`, `stale_or_failed_test_receipt_routes_repair`, `no_test_execution_authority`, `no_authority_grant`, `human_completion_confirmation`

### `verify_task_board`

`stable_reason_codes`, `authoritative_task_state`, `no_state_mutation`, `automatic_task_update_coupling`

### `list_skills`

`server_side_agent_state_resolution`, `availability_filter`, `agent_allowlist_filter`, `state_allowlist_filter`, `visibility_does_not_grant_call_authority`

### `memory_search`

`server_side_agent_state_resolution`, `task_and_agent_scope`, `bounded_top_k`, `read_only_memory_lane`, `evidence_lineage`

### `git_lane`

`exact_repository_root`, `authority_and_assignment_admission`, `operation_discriminated_input_schema`, `server_owned_protected_branch_policy`, `dry_run_default_for_mutation`, `shell_false_argv_execution`, `hooks_and_signing_disabled`, `no_push_or_force_operations`, `explicit_history_rewrite_admission`, `secret_path_rejection`, `bounded_timeout_and_output`, `execution_receipt`

Admitted operations: `repo_context`, `clean_check`, `staged_diff`, `working_diff`, `commit`, `pr_description`, `changelog`, `branch`, `tag`.

## Completion transaction

Entry tool: `task_update`.

Fixed order: `validate_mission_authority_and_assignment` → `hash_submitted_package` → `run_truth_serum` → `check_reverse_rca_ledger` → `check_cumulative_gate_ledger` → `run_scaffoldctl` → `validate_package_test_manifest` → `run_bounded_package_tests` → `persist_immutable_receipt` → `verify_task_board` → `working_agreement` → `apply_review_quarantine_or_escalation_disposition` → `emit_corrective_feedback_if_rejected`.

Permitted dispositions: `REVIEW`, `QUARANTINED`, `ESCALATED`.

Prohibited behavior: `model_selected_firewall_bypass`, `missing_test_bypass`, `test_suppression`, `stale_test_receipt_review`, `task_update_self_promotion_to_done`, `unreceipted_task_mutation`.

## Package-test firewall

Every submitted package must contain `tests/test_manifest.json` conforming to `urn:hmt:package-test-manifest:1.0.0`. The manifest must enumerate every executable Python test file, bind required task gates, include at least one smoke file and one regression file, and use the runtime-owned `python_unittest` execution profile.

The completion firewall rejects missing tests, unmanifested tests, declared files with no executable tests, skips, conditional skips, expected failures, xfails, count mismatches, timeouts, excessive output, sandbox mutation, and nonzero test exits. Tests run lexically in a disposable package copy with a clean bounded environment, `shell=False`, disabled stdin, no inherited credentials, server-owned file/memory/CPU/output limits, per-test wall time, and a cumulative time limit. Callers cannot override the execution policy through tool input.

`working_agreement` remains observe-only. It does not run tests. A task in `review` is eligible for `await human review` only when its current immutable completion receipt binds the current attempt, package hash, passing test manifest, and passing package-test sweep. A missing, stale, or failed receipt routes the task to `repair and resubmit`.

Rejected integration attempts emit a content-addressed corrective packet to `<state-dir>/outbox/`, outside the submitted package hash boundary. The packet carries the failed checks, precise reason codes, receipt and package hashes, remaining attempts, Reverse RCA starting instruction, and resubmission requirements. Runtime-lease validity remains owned by authoritative admission and is never inferred by the tool.

## Internal control plane

`CORE_CAPABILITIES`, `TOOL_SCHEMAS`, `skills_df`, `_TOOL_FUNCS`, `_execute_tool`, `tool_routing_index`, `verify_capability_registry`, `resolve_agent_state`, `typed_task_board_store`, `append_only_execution_receipts`.

## Sovereign adapter interfaces

`truth-serum`, `scaffoldctl`, `rrca-build`, `sysml-build`, `control-build`.

## Extension policy

Repository-specific target: `5`.

Extensions must be: `executable`, `typed`, `bounded`, `auditable`, `repository_specific`, `independently_tested`.

Extensions must not: `replace_a_baseline_tool`, `silently_widen_authority`, `duplicate_a_baseline_tool_under_a_new_name`, `exist_only_as_prose_instructions`.

## Change control

- `baseline_mutation_policy`: `NEW_VERSION_REQUIRED`
- `tool_removal_policy`: `HUMAN_ARCHITECT_APPROVAL_REQUIRED`
- `authority_widening_policy`: `EXPLICIT_HUMAN_PROMOTION_REQUIRED`
- `model_self_modification`: `PROHIBITED`
- `schema_implementation_drift`: `HOLD`

## v1.2.0 change record

- Change ID: `HMT-BASELINE-TEST-FIREWALL-002`
- Change type: `BEHAVIORAL_MINOR_VERSION`
- Authority: `human_architect_explicit_task_update_work_agreement_update`
- Changed: `task_update`, `working_agreement`
- Added: `0`
- Removed: `0`
- Authority widening: `NONE`
- Implementations: `hmt-tool-task-update-1.1.0`, `hmt-tool-working-agreement-1.1.0`

## Non-claims

The policy does not grant task assignment, protected-branch override, force operation, push authority, human closeout, or permission to bypass call-time admission.

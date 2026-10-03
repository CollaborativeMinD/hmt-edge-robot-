# HMT Baseline MCP Tool Surface v1.3.0 (Promotion Candidate)

Generated from the corresponding JSON policy; both versions carry the same values.
Paths identify the authoritative machine fields. No runtime or promotion authority is implied.

Baseline Id (`baseline_id`): HMT-MCP-BASELINE

Baseline Version (`baseline_version`): 1.3.0

Canonical Tool Count (`canonical_tool_count`): 14

## Change Control

Machine path: `change_control`

Authority Widening Policy (`change_control/authority_widening_policy`): EXPLICIT_HUMAN_PROMOTION_REQUIRED

Baseline Mutation Policy (`change_control/baseline_mutation_policy`): NEW_VERSION_REQUIRED

Model Self Modification (`change_control/model_self_modification`): PROHIBITED

Schema Implementation Drift (`change_control/schema_implementation_drift`): HOLD

Tool Removal Policy (`change_control/tool_removal_policy`): HUMAN_ARCHITECT_APPROVAL_REQUIRED

## Change Record

Machine path: `change_record`

Change Id (`change_record/change_id`): HMT-REFERENCE-BUILD-003

Change Type (`change_record/change_type`): ADDITIVE_MINOR_VERSION

Authority (`change_record/authority`): human_architect_explicit_principle_build_order

Authority Widening (`change_record/authority_widening`): NO_RUNTIME_AUTHORITY_WIDENING

### Added Tools

Machine path: `change_record/added_tools`

- reference_build

### Changed Tools

Machine path: `change_record/changed_tools`

Empty list (`[]`).

### Removed Tools

Machine path: `change_record/removed_tools`

Empty list (`[]`).

### Implementation Bundles

Machine path: `change_record/implementation_bundles`

- hmt-reference-build-1.0.0

## Completion Transaction

Machine path: `completion_transaction`

Entry Tool (`completion_transaction/entry_tool`): task_update

### Fixed Order

Machine path: `completion_transaction/fixed_order`

- validate_mission_authority_and_assignment
- hash_submitted_package
- run_truth_serum
- check_reverse_rca_ledger
- check_cumulative_gate_ledger
- run_scaffoldctl
- validate_package_test_manifest
- run_bounded_package_tests
- persist_immutable_receipt
- verify_task_board
- working_agreement
- apply_review_quarantine_or_escalation_disposition
- emit_corrective_feedback_if_rejected

### Permitted Dispositions

Machine path: `completion_transaction/permitted_dispositions`

- REVIEW
- QUARANTINED
- ESCALATED

### Prohibited Behavior

Machine path: `completion_transaction/prohibited_behavior`

- model_selected_firewall_bypass
- missing_test_bypass
- test_suppression
- stale_test_receipt_review
- task_update_self_promotion_to_done
- unreceipted_task_mutation

Document Type (`document_type`): hmt_baseline_mcp_tool_manifest

## Extension Policy

Machine path: `extension_policy`

Repository Specific Skill Target (`extension_policy/repository_specific_skill_target`): 5

### Repository Specific Skills Must Be

Machine path: `extension_policy/repository_specific_skills_must_be`

- executable
- typed
- bounded
- auditable
- repository_specific
- independently_tested

### Repository Specific Skills Must Not

Machine path: `extension_policy/repository_specific_skills_must_not`

- replace_a_baseline_tool
- silently_widen_authority
- duplicate_a_baseline_tool_under_a_new_name
- exist_only_as_prose_instructions

Freeze Authority (`freeze_authority`): human_architect_explicit_order

Frozen At (`frozen_at`): null

## Internal Control Plane

Machine path: `internal_control_plane`

- CORE_CAPABILITIES
- TOOL_SCHEMAS
- skills_df
- _TOOL_FUNCS
- _execute_tool
- tool_routing_index
- verify_capability_registry
- resolve_agent_state
- typed_task_board_store
- append_only_execution_receipts

Schema Version (`schema_version`): 1.2.0

## Source Lineage

Machine path: `source_lineage`

Git Lane Source (`source_lineage/git_lane_source`): reusable mcp tool setup for git-lane skills.py

Last Verified Source (`source_lineage/last_verified_source`): Agent Building Quickstarter Kit v10 - Control and GraphRAG_notebook.py

Lineage Note (`source_lineage/lineage_note`): v1.3.0 adds reference_build. The v1.2.0 thirteen-tool definitions, test firewall, corrective feedback and completion transaction are unchanged.

### Quickstarter Versions Reviewed

Machine path: `source_lineage/quickstarter_versions_reviewed`

- v1
- v2
- v3
- v4
- v5
- v6
- v7
- v8
- v9
- v10

Reference Build Source (`source_lineage/reference_build_source`): HMT_Transformation_Kernel_v4.0.0(7).zip

## Sovereign Adapter Interfaces

Machine path: `sovereign_adapter_interfaces`

- truth-serum
- scaffoldctl
- rrca-build
- sysml-build
- control-build

Status (`status`): CANDIDATE_FOR_HUMAN_ARCHITECT_PROMOTION

Supersedes (`supersedes`): HMT-MCP-BASELINE/1.2.0

Title (`title`): HMT Baseline MCP Tool Surface v1.3.0 (Promotion Candidate)

## Tool Groups

Machine path: `tool_groups`

### 0

Machine path: `tool_groups/0`

Group Id (`tool_groups/0/group_id`): repository_operations

Tool Count (`tool_groups/0/tool_count`): 4

#### Tools

Machine path: `tool_groups/0/tools`

- list_files
- read_file
- write_file
- run_command

### 1

Machine path: `tool_groups/1`

Group Id (`tool_groups/1/group_id`): task_control

Tool Count (`tool_groups/1/tool_count`): 6

#### Tools

Machine path: `tool_groups/1/tools`

- tasks_list
- task_get
- task_update
- task_create
- working_agreement
- verify_task_board

### 2

Machine path: `tool_groups/2`

Group Id (`tool_groups/2/group_id`): capability_discovery

Tool Count (`tool_groups/2/tool_count`): 1

#### Tools

Machine path: `tool_groups/2/tools`

- list_skills

### 3

Machine path: `tool_groups/3`

Group Id (`tool_groups/3/group_id`): evidence_retrieval

Tool Count (`tool_groups/3/tool_count`): 1

#### Tools

Machine path: `tool_groups/3/tools`

- memory_search

### 4

Machine path: `tool_groups/4`

Group Id (`tool_groups/4/group_id`): version_control

Tool Count (`tool_groups/4/tool_count`): 1

#### Tools

Machine path: `tool_groups/4/tools`

- git_lane

### 5

Machine path: `tool_groups/5`

Group Id (`tool_groups/5/group_id`): reference_bounded_engineering

Tool Count (`tool_groups/5/tool_count`): 1

#### Tools

Machine path: `tool_groups/5/tools`

- reference_build

## Tools

Machine path: `tools`

### 0

Machine path: `tools/0`

Effect (`tools/0/effect`): observe

Group (`tools/0/group`): repository_operations

#### Mandatory Controls

Machine path: `tools/0/mandatory_controls`

- repository_root_containment
- path_normalization
- bounded_result_count
- fail_closed_on_boundary_violation
- execution_receipt

Name (`tools/0/name`): list_files

Ordinal (`tools/0/ordinal`): 1

Purpose (`tools/0/purpose`): List admitted files within the bounded repository root.

Requires Mission Packet (`tools/0/requires_mission_packet`): true

### 1

Machine path: `tools/1`

Effect (`tools/1/effect`): observe

Group (`tools/1/group`): repository_operations

#### Mandatory Controls

Machine path: `tools/1/mandatory_controls`

- repository_root_containment
- path_normalization
- secret_and_binary_rejection
- bounded_input_bytes
- execution_receipt

Name (`tools/1/name`): read_file

Ordinal (`tools/1/ordinal`): 2

Purpose (`tools/1/purpose`): Read an admitted text file from the bounded repository root.

Requires Mission Packet (`tools/1/requires_mission_packet`): true

### 2

Machine path: `tools/2`

Effect (`tools/2/effect`): mutate

Group (`tools/2/group`): repository_operations

#### Mandatory Controls

Machine path: `tools/2/mandatory_controls`

- repository_root_containment
- path_normalization
- authority_and_assignment_admission
- bounded_write_bytes
- content_hash
- execution_receipt

Name (`tools/2/name`): write_file

Ordinal (`tools/2/ordinal`): 3

Purpose (`tools/2/purpose`): Create or update an admitted file within the bounded repository root.

Requires Mission Packet (`tools/2/requires_mission_packet`): true

### 3

Machine path: `tools/3`

Effect (`tools/3/effect`): execute

Group (`tools/3/group`): repository_operations

#### Mandatory Controls

Machine path: `tools/3/mandatory_controls`

- shell_false
- command_allowlist
- fixed_timeout
- bounded_stdout_stderr
- working_directory_containment
- execution_receipt

Name (`tools/3/name`): run_command

Ordinal (`tools/3/ordinal`): 4

Purpose (`tools/3/purpose`): Execute an admitted deterministic command without a shell.

Requires Mission Packet (`tools/3/requires_mission_packet`): true

### 4

Machine path: `tools/4`

#### Aliases

Machine path: `tools/4/aliases`

- task_board

Effect (`tools/4/effect`): observe

Group (`tools/4/group`): task_control

#### Mandatory Controls

Machine path: `tools/4/mandatory_controls`

- authoritative_state_source
- typed_task_rows
- bounded_result_count
- no_state_mutation

Name (`tools/4/name`): tasks_list

Ordinal (`tools/4/ordinal`): 5

Purpose (`tools/4/purpose`): Return authoritative task-board cards and lifecycle states.

Requires Mission Packet (`tools/4/requires_mission_packet`): false

### 5

Machine path: `tools/5`

Effect (`tools/5/effect`): mutate

Group (`tools/5/group`): task_control

#### Mandatory Controls

Machine path: `tools/5/mandatory_controls`

- authority_and_assignment_admission
- single_task_claim
- legal_state_transition
- execution_receipt

Name (`tools/5/name`): task_get

Ordinal (`tools/5/ordinal`): 6

Purpose (`tools/5/purpose`): Claim one admitted unstarted task for the assigned agent.

Requires Mission Packet (`tools/5/requires_mission_packet`): true

### 6

Machine path: `tools/6`

Effect (`tools/6/effect`): mutate

Group (`tools/6/group`): task_control

#### Mandatory Controls

Machine path: `tools/6/mandatory_controls`

- authority_and_assignment_admission
- package_hash
- truth_serum_check
- reverse_rca_check
- cumulative_gate_check
- scaffoldctl_check
- strict_package_test_manifest
- complete_test_inventory
- no_test_suppressions
- sandboxed_shell_false_test_execution
- server_owned_test_execution_policy
- bounded_test_resources
- current_package_test_receipt
- append_only_receipt
- corrective_feedback_outbox
- reverse_rca_resubmission
- verify_task_board_coupling
- working_agreement_coupling
- no_self_promotion_to_done

Name (`tools/6/name`): task_update

Ordinal (`tools/6/ordinal`): 7

Purpose (`tools/6/purpose`): Submit progress through the coupled completion firewall, run all admitted package tests, and emit corrective feedback when rejected.

Requires Mission Packet (`tools/6/requires_mission_packet`): true

### 7

Machine path: `tools/7`

Effect (`tools/7/effect`): mutate

Group (`tools/7/group`): task_control

#### Mandatory Controls

Machine path: `tools/7/mandatory_controls`

- authority_and_assignment_admission
- parent_task_reference_when_derived
- reason_code_when_derived
- bounded_task_creation
- idempotency_key
- execution_receipt

Name (`tools/7/name`): task_create

Ordinal (`tools/7/ordinal`): 8

Purpose (`tools/7/purpose`): Create an admitted follow-up or repair task without granting execution authority.

Requires Mission Packet (`tools/7/requires_mission_packet`): true

### 8

Machine path: `tools/8`

Effect (`tools/8/effect`): observe

Group (`tools/8/group`): task_control

#### Mandatory Controls

Machine path: `tools/8/mandatory_controls`

- authoritative_task_state
- deterministic_priority_order
- current_package_test_receipt_required_for_review
- stale_or_failed_test_receipt_routes_repair
- no_test_execution_authority
- no_authority_grant
- human_completion_confirmation

Name (`tools/8/name`): working_agreement

Ordinal (`tools/8/ordinal`): 9

Purpose (`tools/8/purpose`): Return the next lawful task-board action and require a current passing package-test receipt before review.

Requires Mission Packet (`tools/8/requires_mission_packet`): false

### 9

Machine path: `tools/9`

Effect (`tools/9/effect`): observe

Group (`tools/9/group`): task_control

#### Mandatory Controls

Machine path: `tools/9/mandatory_controls`

- stable_reason_codes
- authoritative_task_state
- no_state_mutation
- automatic_task_update_coupling

Name (`tools/9/name`): verify_task_board

Ordinal (`tools/9/ordinal`): 10

Purpose (`tools/9/purpose`): Detect task lifecycle contradictions and completion-policy breaches.

Requires Mission Packet (`tools/9/requires_mission_packet`): false

### 10

Machine path: `tools/10`

Effect (`tools/10/effect`): observe

Group (`tools/10/group`): capability_discovery

#### Mandatory Controls

Machine path: `tools/10/mandatory_controls`

- server_side_agent_state_resolution
- availability_filter
- agent_allowlist_filter
- state_allowlist_filter
- visibility_does_not_grant_call_authority

Name (`tools/10/name`): list_skills

Ordinal (`tools/10/ordinal`): 11

Purpose (`tools/10/purpose`): Return capabilities visible to a registered agent in its authoritative state.

Requires Mission Packet (`tools/10/requires_mission_packet`): false

### 11

Machine path: `tools/11`

Effect (`tools/11/effect`): observe

Group (`tools/11/group`): evidence_retrieval

#### Mandatory Controls

Machine path: `tools/11/mandatory_controls`

- server_side_agent_state_resolution
- task_and_agent_scope
- bounded_top_k
- read_only_memory_lane
- evidence_lineage

Name (`tools/11/name`): memory_search

Ordinal (`tools/11/ordinal`): 12

Purpose (`tools/11/purpose`): Retrieve task-scoped GraphRAG evidence for a registered agent.

Requires Mission Packet (`tools/11/requires_mission_packet`): false

### 12

Machine path: `tools/12`

Effect (`tools/12/effect`): execute

Group (`tools/12/group`): version_control

#### Mandatory Controls

Machine path: `tools/12/mandatory_controls`

- exact_repository_root
- authority_and_assignment_admission
- operation_discriminated_input_schema
- server_owned_protected_branch_policy
- dry_run_default_for_mutation
- shell_false_argv_execution
- hooks_and_signing_disabled
- no_push_or_force_operations
- explicit_history_rewrite_admission
- secret_path_rejection
- bounded_timeout_and_output
- execution_receipt

Name (`tools/12/name`): git_lane

#### Operations

Machine path: `tools/12/operations`

- repo_context
- clean_check
- staged_diff
- working_diff
- commit
- pr_description
- changelog
- branch
- tag

Ordinal (`tools/12/ordinal`): 13

Purpose (`tools/12/purpose`): Execute one schema-selected, policy-governed Git-lane operation inside the exact admitted repository root.

Requires Mission Packet (`tools/12/requires_mission_packet`): true

### 13

Machine path: `tools/13`

Name (`tools/13/name`): reference_build

Ordinal (`tools/13/ordinal`): 14

Group (`tools/13/group`): reference_bounded_engineering

Effect (`tools/13/effect`): execute

Purpose (`tools/13/purpose`): Derive JSON or sectioned Markdown artifacts from pinned references, reject unsupported delta, and publish revalidated local receipts before the unchanged baseline completion transaction.

Requires Mission Packet (`tools/13/requires_mission_packet`): true

#### Operations

Machine path: `tools/13/operations`

- load_reference
- transform_from_reference
- validate_against_reference
- diff_candidate
- emit_receipt

#### Mandatory Controls

Machine path: `tools/13/mandatory_controls`

- external_policy_hash_pin
- exact_assignment_and_operation_admission
- strict_operation_schema
- reference_and_schema_hash_pins
- closed_schema_keyword_profile
- explicit_semantic_invariants
- exact_path_delta_admission
- requested_candidate_equivalence
- no_shell_or_network
- bounded_resources
- revalidation_before_emit
- append_only_receipt
- no_activation_or_task_completion_authority


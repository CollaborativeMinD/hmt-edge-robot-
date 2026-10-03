# HMT Reuse, Extension, and Promotion Policy

**Policy ID:** `HMT-REUSE-EXTENSION-PROMOTION`  
**Version:** `1.0.0`  
**Status:** **CANDIDATE_FOR_HUMAN_ARCHITECT_PROMOTION**  
**Authority:** Human Architect only  
**Machine-readable SSOT:** `HMT_Reuse_Extension_and_Promotion_Policy_v1.0.0.json`

> **Core principle:** Search before forge. Reuse known-good steel when it satisfies the mission; preserve the reasoning and invariants that made it lawful; engineer only the true unresolved delta; measure and validate that delta; promote repeated success into discoverable organizational capability.

## Executive BLUF

Repeatedly solved engineering problems SHALL NOT remain tribal knowledge.

HMT builds begin by discovering and classifying existing reusable steel. Builders preserve the source reasoning, requirements, invariants, authority boundaries, failure semantics, qualification state, and evidence that made that steel lawful. New engineering is limited to the smallest unresolved mission-specific delta. When a project-local capability demonstrates evidence-backed utility across materially distinct problem contexts, it enters Human Architect promotion review for shared organizational reuse.

This policy does **not** require every new artifact to look like its reference. Structural inheritance is one path. Reasoning inheritance is equally valid when a different implementation shape better satisfies the mission and remains traceable to the governing requirements and invariants.

## 1. Purpose

This policy operationalizes HMT's **Reusable Steel** axiom into an explicit lifecycle for organizational learning, system stamping, agentic engineering, and human engineering.

```text
DISCOVER
→ CLASSIFY
→ SELECT
→ TRACE REASONING
→ IDENTIFY TRUE DELTA
→ TRACER VALIDATE
→ IMPLEMENT / COMPOSE
→ VERIFY DELTA + INVARIANTS
→ PUBLISH RECEIPT
→ PROMOTE OR HOLD
→ HOST + REGISTER
→ SUPERSEDE EXPLICITLY
```

> Prevent repeatedly solved engineering problems from remaining tribal knowledge. Once a solution survives materially distinct problem contexts, treat it as a candidate organizational capability that must be documented, versioned, evidenced, hosted, discoverable, and referenced by default.

## 2. Governing Relationships

| Governing item | Relationship |
|---|---|
| `HMT-AX-003` | Reuse or extension does not waive tracer-bullet admission. |
| `HMT-AX-004` | This policy operationalizes Reusable Steel into a governed lifecycle. |
| `HMT-AX-005` | Reusable capability must be self-explaining and discoverable without original-builder presence. |
| `HMT-AX-006` | Extension and promotion require cumulative regression and Reverse RCA closure. |
| `HMT-REFERENCE-BOUNDED-TRANSFORMATION` | reference_build is a strict enforcement mechanism for reference-bounded transformation; this policy is broader and also permits reasoning inheritance, composition, and alternate compliant implementations. |
| `HMT-MCP-BASELINE/1.3.0` | Reuse tooling does not alter the existing completion transaction or grant task-completion authority. |

## 3. Reuse Dispositions

Every materially applicable existing capability SHALL receive one explicit disposition.

| Disposition | Meaning |
|---|---|
| `REUSE_AS_IS` | Use the admitted capability without internal modification; bind it to the new mission through declared adapters/configuration only. |
| `ADAPT` | Apply bounded interface, configuration, or representation changes while preserving the underlying capability and authority semantics. |
| `EXTEND` | Add new behavior around or beneath an admitted capability while preserving inherited contracts and explicitly validating the added delta. |
| `COMPOSE` | Combine two or more admitted capabilities through typed seams without silently merging authority or failure semantics. |
| `SUPERSEDE` | Replace an older canonical capability only through explicit versioned promotion, migration guidance, and human disposition. |
| `NO_FIT` | No admitted capability can satisfy the unresolved requirement without violating mission, invariant, authority, fidelity, or interface constraints. |

`NO_FIT` is not permission to ignore existing work. It is an evidence-bearing determination that admitted steel cannot close the active mission without violating a requirement, invariant, authority boundary, fidelity constraint, or interface contract.

## 4. Reuse Discovery Gate

**Gate:** `G-REUSE-DISCOVERY`

The gate executes before:
- architecture_generation
- new_framework_creation
- new_kernel_creation
- new_tool_creation
- new_plant_creation
- new_repository_specific_skill_creation
- substantial_custom_implementation

Required actions:
- Inventory applicable admitted kernels, tools, plants, field cards, schemas, policies, ontologies, reference implementations, and prior evidence.
- Record artifact identity, version, source location, and content hash for each selected candidate.
- Record one reuse disposition for each materially applicable candidate.
- Record rejection reason for any applicable candidate not selected.
- Identify the unresolved mission-specific delta before authorizing new engineering.
- Bind the selected steel and unresolved delta to the active mission/assignment.

Prohibited shortcuts:
- skip_discovery_because_builder_prefers_custom_code
- new_framework_by_default
- silent_reimplementation_of_existing_capability
- rejection_without_requirement_or_invariant_basis
- reuse_claim_without_version_or_source_identity

Failure disposition: `HOLD_REUSE_DISCOVERY_INCOMPLETE`

> **Required question:** What already exists that lawfully satisfies part of this problem, and what remains genuinely unresolved?

A build that cannot answer that question is not ready for new architecture generation.

## 5. Valid Forms of Inheritance

### 5.1 Structural inheritance

Candidate preserves the admitted structure and applies an explicit bounded delta. Use reference_build when exact reference-bounded transformation is appropriate.

### 5.2 Reasoning inheritance

Candidate may have a different structure, but must preserve and trace the source requirements, invariants, assumptions, trade decisions, failure semantics, and non-claims that remain applicable.

A downstream builder may produce a different shape when it can show:

```text
source reasoning
+ applicable requirements
+ invariants
+ assumptions
+ failure semantics
+ authority boundaries
        ↓
independently derived candidate
        ↓
traceable satisfaction + evidence
```

### 5.3 Composition inheritance

Candidate composes multiple admitted assets; each source keeps its lineage, authority boundary, qualification status, and failure semantics.

## 6. True Delta Rule

> New engineering SHALL be limited to the smallest mission-specific delta that cannot be satisfied through REUSE_AS_IS, ADAPT, EXTEND, or COMPOSE.

Every build manifest SHALL classify artifacts as:
- inherited
- modified
- new

At minimum, review:
- requirement_delta
- invariant_delta
- interface_delta
- authority_delta
- failure_semantics_delta
- dependency_delta
- qualification_delta
- evidence_delta

Failure disposition: `HOLD_TRUE_DELTA_NOT_ISOLATED`

The purpose is not to suppress creativity. It is to spend creativity only where the problem is actually new.

## 7. NO_FIT / New Steel Gate

**Gate:** `G-REUSE-NO-FIT`

NO_FIT authorizes investigation of new steel, not unrestricted architecture generation.

Required evidence:
- unmet_requirement_ids
- applicable_invariant_ids
- selected_candidate_assets_and_hashes
- why_reuse_as_is_fails
- why_adapt_fails
- why_extend_fails
- why_compose_fails
- bounded_new_engineering_scope
- tracer_plan

Insufficient reasons:
- builder_preference
- model_preference
- cleaner_to_start_over
- new_framework_is_more_interesting
- not_invented_here
- no_time_to_inspect_existing_steel

Failure disposition: `HOLD_NEW_STEEL_NOT_JUSTIFIED`

## 8. Lineage Contract

Every inherited capability carries, where applicable:
- artifact_id
- artifact_version
- source_location
- source_hash
- owner_or_authority
- applicable_requirements
- applicable_invariants
- assumptions
- known_limitations
- non_claims
- authority_boundary
- failure_semantics
- qualification_status
- verification_evidence_refs
- supersession_status

> Copied code without preserved reasoning and evidence lineage is not compliant reuse. Different implementation shape is permitted when source reasoning and requirements remain traceable.

## 9. Reasoning Trace Contract

Every build SHALL be able to answer:

> **Which inherited requirements, invariants, assumptions, and prior decisions constrained this candidate, and how are they satisfied now?**

Acceptance rule:

> A candidate need not duplicate the source structure when its reasoning lineage is explicit, the resulting shape satisfies the governing requirements and invariants, and verification closes the delta.

Documentation expectation:

> Documentation SHOULD read as build-time reasoning and evidence, not post-hoc inference from finished code.

This is how independent builders can receive the same project history and produce different, yet traceable, solutions whose documentation reads like build-time engineering rather than post-hoc narration.

## 10. Verification and Consumption

Reuse reduces rediscovery. It does **not** reduce mission assurance.

- Reuse SHALL NOT waive mission-specific tracer validation.
- Reuse SHALL NOT waive package tests, cumulative gates, Reverse RCA, scaffold verification, or human review where required.
- Prior evidence MAY reduce rediscovery effort only after applicability to the new mission is explicitly checked.
- Inherited capability failures discovered in a new mission SHALL route upstream through Reverse RCA and may trigger a shared-steel repair or qualification hold.
- No reused capability gains operational authority merely because it was previously promoted elsewhere.

Failure disposition: `HOLD_REUSE_QUALIFICATION_INCOMPLETE`

## 11. Promotion to Organizational Capability

**Gate:** `G-REUSE-PROMOTION`

Promotion trigger:

> A local capability becomes a promotion candidate after it has solved at least two materially distinct problem contexts with evidence-backed verification and without unresolved authority or fidelity mismatch.

Promotion is never automatic.

Required promotion packet:
- capability_summary
- problem_contexts_and_distinguishing_features
- versioned_artifact_and_hash
- requirements_and_invariants
- reuse_map
- known_limitations_and_non_claims
- cross_context_regression_receipts
- reverse_rca_incident_summary
- interface_and_adapter_contracts
- operator_and_agent_documentation
- hosting_location
- discovery_registry_entry
- supersession_or_coexistence_plan
- human_architect_disposition

Human disposition:
- PROMOTE_SHARED_STEEL
- RETAIN_PROJECT_LOCAL
- HOLD_FOR_MORE_EVIDENCE
- REJECT_REUSE_CANDIDATE

## 12. Hosting and Discoverability

> A promoted reusable capability SHALL be hosted in an authoritative versioned location and discoverable through the normal human/agent discovery surface before it is treated as organizational steel.

Minimum published metadata:
- canonical_name
- capability_class
- version
- source_location
- content_hash
- purpose
- invocation_or_consumption_contract
- authority_boundary
- qualification_status
- requirements_and_invariants
- known_limitations
- replacement_or_supersession_relationship

A built capability not yet published into an authoritative discovery surface is classified as `UNPUBLISHED_STEEL`.

## 13. Supersession

> Canonical reusable steel SHALL NOT be silently replaced or left ambiguous after a successor is promoted.

Required actions:
- Assign a new version or new canonical capability ID.
- Declare predecessor and successor relationship.
- Declare compatibility and migration posture.
- Preserve predecessor hashes and evidence.
- Update discovery registries and references.
- Do not delete historical evidence required for audit or replay.

Lifecycle states:
- PROJECT_LOCAL
- CANDIDATE_SHARED_STEEL
- PROMOTED_SHARED_STEEL
- DEPRECATED
- SUPERSEDED
- RETIRED
- HOLD

## 14. Reuse Decision Receipt

Receipt type: `HMT_REUSE_DECISION_RECEIPT`

Required fields:
- mission_or_project_id
- timestamp
- builder_or_agent_id
- discovery_gate_status
- candidate_assets
- selected_assets
- reuse_dispositions
- rejected_assets_and_reasons
- unresolved_true_delta
- inheritance_modes
- requirement_and_invariant_trace
- artifact_manifest_inherited_modified_new
- tracer_receipt_refs
- verification_receipt_refs
- rrca_refs
- final_package_hash
- disposition

The receipt is `append_only_or_content_addressed`.

It is not:
- operational_authority
- task_completion
- human_approval
- proof_of_universal_reusability

## 15. Normative Requirements

| Requirement | Rule | Verification |
|---|---|---|
| `HMT-REUSE-R01` | Every substantial build SHALL execute the Reuse Discovery Gate before new architecture or implementation is admitted. | `reuse_discovery_receipt_check` |
| `HMT-REUSE-R02` | Applicable existing steel SHALL receive an explicit reuse disposition and any rejection SHALL cite requirement, invariant, authority, fidelity, or interface evidence. | `reuse_disposition_and_rejection_basis_check` |
| `HMT-REUSE-R03` | New engineering SHALL be limited to the identified true mission-specific delta. | `inherited_modified_new_manifest_and_delta_check` |
| `HMT-REUSE-R04` | Reuse SHALL preserve source reasoning, requirements, invariants, authority boundaries, failure semantics, qualification status, and evidence lineage. | `reuse_lineage_contract_check` |
| `HMT-REUSE-R05` | Different implementation shape MAY be admitted when reasoning lineage is preserved and the resulting artifact independently satisfies applicable requirements and invariants. | `reasoning_inheritance_trace_and_verification` |
| `HMT-REUSE-R06` | NO_FIT SHALL be evidence-backed and SHALL only authorize the bounded new-steel scope required to close the unmet requirements. | `no_fit_gate_check` |
| `HMT-REUSE-R07` | Reuse SHALL NOT bypass tracer, V&V, RRCA, cumulative gates, package tests, or required human review. | `reuse_qualification_chain_check` |
| `HMT-REUSE-R08` | A repeatedly successful local solution SHALL enter promotion review rather than remain undocumented tribal knowledge. | `cross_context_promotion_trigger_check` |
| `HMT-REUSE-R09` | Promoted steel SHALL be versioned, hosted, documented, discoverable, and linked to its evidence and supersession status. | `shared_steel_registry_and_hosting_check` |
| `HMT-REUSE-R10` | Reuse, adaptation, extension, composition, and supersession SHALL NOT silently widen operational authority. | `authority_delta_and_mission_binding_check` |

## 16. Stable Reason Codes

- `HOLD_REUSE_DISCOVERY_INCOMPLETE`
- `HOLD_TRUE_DELTA_NOT_ISOLATED`
- `HOLD_NEW_STEEL_NOT_JUSTIFIED`
- `HOLD_REUSE_LINEAGE_INCOMPLETE`
- `HOLD_REUSE_QUALIFICATION_INCOMPLETE`
- `HOLD_REUSE_PROMOTION_EVIDENCE_INCOMPLETE`
- `HOLD_REUSABLE_CAPABILITY_NOT_DISCOVERABLE`
- `HOLD_SUPERSESSION_AMBIGUOUS`
- `HOLD_REUSE_AUTHORITY_WIDENING`
- `REJECT_REIMPLEMENTATION_WITHOUT_EVIDENCE`

## 17. Minimum Repository Reuse Packet

- `reuse_discovery_receipt`
- `reuse_map`
- `artifact_manifest_inherited_modified_new`
- `requirement_and_invariant_trace`
- `admitted_tracer_bullet_receipt`
- `delta_verification_receipt`
- `cumulative_gate_ledger`
- `reverse_rca_ledger`
- `final_package_hash`
- `human_architect_disposition_when_required`

## 18. Exclusions and Non-Claims

- This policy does not require literal template reuse when reasoning inheritance is the better engineering path.
- This policy does not treat code copying alone as reuse.
- This policy does not auto-promote a capability because it worked twice.
- This policy does not grant operational authority, task completion, deployment, or activation.
- This policy does not replace mission-specific architecture, physics, safety, cybersecurity, fidelity, or qualification requirements.
- This policy does not prohibit novel engineering; it requires the unresolved novelty to be identified and justified.

## 19. Change Control

| Rule | Value |
|---|---|
| `policy_change_requires_new_version` | `true` |
| `reuse_disposition_vocabulary_change_requires_new_version` | `true` |
| `promotion_threshold_change_requires_new_version` | `true` |
| `human_architect_approval_required` | `true` |
| `agent_may_self_promote_shared_steel` | `false` |
| `model_may_widen_authority` | `false` |
| `promotion_requires_preserved_hashes_and_lineage` | `true` |

## 20. Operator / Agent Build Sequence

```text
1. Read mission authority, HMT axioms, this policy, and repository operating documents.
2. Execute Reuse Discovery Gate.
3. Inventory and hash materially applicable steel.
4. Assign one reuse disposition to each applicable candidate.
5. Trace inherited reasoning, requirements, invariants, and authority boundaries.
6. Identify the true unresolved mission delta.
7. If NO_FIT is required, close the NO_FIT evidence gate before creating new steel.
8. Build and validate a tracer across the selected seams.
9. Reuse, adapt, extend, or compose admitted capability.
10. Verify delta, invariants, authority, failure semantics, and mission-specific qualification.
11. Emit the Reuse Decision Receipt and normal package evidence.
12. Run the existing completion firewall; this policy does not bypass it.
13. If the capability has succeeded across materially distinct contexts, open promotion review.
14. If promoted, host, register, document, version, and expose it through normal discovery.
15. If superseded, preserve predecessor evidence and update discovery references explicitly.
```

## 21. One-Line HMT Law

> **Search before forge. Preserve the reasoning. Engineer only the true delta. Prove the change. Promote repeated success into discoverable steel.**

# HMT Reference-Bounded Transformation Policy

Generated from the corresponding JSON policy; both versions carry the same values.
Paths identify the authoritative machine fields. No runtime or promotion authority is implied.

Document Type (`document_type`): hmt_reference_bounded_transformation_policy

Schema Version (`schema_version`): 1.0.0

Policy Id (`policy_id`): HMT-REFERENCE-BOUNDED-TRANSFORMATION

Policy Version (`policy_version`): 1.0.0

Title (`title`): HMT Reference-Bounded Transformation Policy

Status (`status`): CANDIDATE_FOR_HUMAN_ARCHITECT_PROMOTION

Authority (`authority`): human_architect_only

Principle (`principle`): Initialize reusable reference structures before engineering; derive candidates only from an admitted reference plus an explicit requested change; measure and validate the delta before handoff.

Tool Name (`tool_name`): reference_build

## Operations

Machine path: `operations`

- load_reference
- transform_from_reference
- validate_against_reference
- diff_candidate
- emit_receipt

Execution Profile (`execution_profile`): managed_runtime_support

Activation Allowed (`activation_allowed`): false

## Reference Locations

Machine path: `reference_locations`

### 0

Machine path: `reference_locations/0`

Location Id (`reference_locations/0/location_id`): EXAMPLE-JSON

Repository (`reference_locations/0/repository`): hmt-reference-build-1.0.0

Relative Location (`reference_locations/0/relative_location`): examples/references/build_object.json

Description (`reference_locations/0/description`): Executable schema-bound build object reference, not a production assignment.

#### Requirements

Machine path: `reference_locations/0/requirements`

- Use examples/references/build_object.schema.json.
- Raw-byte reference and schema hashes are pinned in examples/reference_registry.json.
- The only change paths are title, details/summary, and requirements.

### 1

Machine path: `reference_locations/1`

Location Id (`reference_locations/1/location_id`): EXAMPLE-MD

Repository (`reference_locations/1/repository`): hmt-reference-build-1.0.0

Relative Location (`reference_locations/1/relative_location`): examples/references/runbook.md

Description (`reference_locations/1/description`): Sectioned Markdown reference with immutable scope and section order.

#### Requirements

Machine path: `reference_locations/1/requirements`

- Use examples/references/runbook.schema.json.
- Only the Procedure section body is mutable.
- LF, ATX headings, unique headings and lossless projection roundtrip are mandatory.

### 2

Machine path: `reference_locations/2`

Location Id (`reference_locations/2/location_id`): OPERATOR-REGISTRY

Repository (`reference_locations/2/repository`): operator-selected local reference snapshot; no remote repository has been assigned

Relative Location (`reference_locations/2/relative_location`): <reference-root>/<policy-relative-path>

Description (`reference_locations/2/description`): Authoritative local snapshot root selected before the MCP process starts.

#### Requirements

Machine path: `reference_locations/2/requirements`

- Select a real local repository snapshot, version and owner; do not treat this placeholder as a configured repo.
- Declare artifact ID, version, description, relative artifact/schema locations, raw-byte hashes, requirements, exact allowed paths/operations, required and immutable paths, explicit invariants and max_delta.
- Validate with contracts/schemas/reference_registry.schema.json; externally pin the registry hash and bind exact mission triples to references and operations.
- Mount reference content read-only for the tool process; keep a dedicated mutable state directory outside the root.

### 3

Machine path: `reference_locations/3`

Location Id (`reference_locations/3/location_id`): KERNEL-PROVENANCE

Repository (`reference_locations/3/repository`): HMT_Transformation_Kernel_v4.0.0

Relative Location (`reference_locations/3/relative_location`): evidence/kernel_mission_bundle.json; src/hmt_reference_build/kernel/

Description (`reference_locations/3/description`): Actual kernel-generated mission bundle and byte-preserved canonical/model/error primitives used to derive this specialized tool.

#### Requirements

Machine path: `reference_locations/3/requirements`

- See evidence/kernel_derivation.json for source pins and exact reuse.
- The mission artifact is provenance, not a live mission assignment.
- Exact full-kernel Python 3.13 validation remains distinct from the tested Python 3.12 generation aperture.

## Initialization Order

Machine path: `initialization_order`

- Review this policy, the supplied HMT axioms/RRCA policies, Agents.md, and Runbook.md.
- Operator selects a versioned local reference snapshot and closed artifact schema.
- Operator declares only explicit requested-change paths and invariants, then pins the registry externally.
- Operator binds mission assignment and operation ceilings; no caller may supply a replacement policy.
- Run init to validate every reference and schema before creating the dedicated receipt outbox.
- Use load_reference and explicit transform/compare operations; do not infer permission from arbitrary prose.
- Emit the recomputed validation receipt, then submit its artifact/evidence through the existing baseline completion firewall.

## Requirements

Machine path: `requirements`

### 0

Machine path: `requirements/0`

Requirement Id (`requirements/0/requirement_id`): RBT-REQ-001

Rule (`requirements/0/rule`): Generate candidates from a pinned reference and explicit add/replace/remove requests; no unconstrained generation.

#### Modules

Machine path: `requirements/0/modules`

- registry.py
- transform.py

#### Gates

Machine path: `requirements/0/gates`

- G-RBT-SMOKE
- G-RBT-DRIFT

### 1

Machine path: `requirements/1`

Requirement Id (`requirements/1/requirement_id`): RBT-REQ-002

Rule (`requirements/1/rule`): Use strict frozen extra-forbid inputs and validate every supported schema constraint; unsupported keywords reject.

#### Modules

Machine path: `requirements/1/modules`

- request.py
- policy.py
- schema_profile.py
- schema_validation.py

#### Gates

Machine path: `requirements/1/gates`

- G-SCHEMA-002
- G-RBT-SCHEMA

### 2

Machine path: `requirements/2`

Requirement Id (`requirements/2/requirement_id`): RBT-REQ-003

Rule (`requirements/2/rule`): Measure all structural/value deltas and explicit semantic invariants; reject drift outside the request and policy.

#### Modules

Machine path: `requirements/2/modules`

- delta.py
- invariants.py
- evaluate.py

#### Gates

Machine path: `requirements/2/gates`

- G-RBT-DRIFT
- G-RBT-MARKDOWN

### 3

Machine path: `requirements/3`

Requirement Id (`requirements/3/requirement_id`): RBT-REQ-004

Rule (`requirements/3/rule`): Bind request, policy, reference, schema, candidate, rendering and delta into deterministic validation receipts; revalidate before append-only handoff.

#### Modules

Machine path: `requirements/3/modules`

- receipts.py
- service.py
- store.py

#### Gates

Machine path: `requirements/3/gates`

- G-REPLAY-005
- G-RBT-RECEIPT

### 4

Machine path: `requirements/4`

Requirement Id (`requirements/4/requirement_id`): RBT-REQ-005

Rule (`requirements/4/rule`): Expose one MCP tool with five schema-discriminated operations and direct/stdio decision parity.

#### Modules

Machine path: `requirements/4/modules`

- mcp_contract.py
- mcp_protocol.py
- mcp_server.py

#### Gates

Machine path: `requirements/4/gates`

- G-RBT-MCP
- G-RBT-PROTOCOL

### 5

Machine path: `requirements/5`

Requirement Id (`requirements/5/requirement_id`): RBT-REQ-006

Rule (`requirements/5/rule`): Constrain local files, input bytes/nodes/depth, paths, deltas and stored receipts; never execute artifact text.

#### Modules

Machine path: `requirements/5/modules`

- bounds.py
- paths.py
- pointers.py
- store.py

#### Gates

Machine path: `requirements/5/gates`

- G-AUTH-003
- G-RBT-BOUNDARY

### 6

Machine path: `requirements/6`

Requirement Id (`requirements/6/requirement_id`): RBT-REQ-007

Rule (`requirements/6/rule`): Derive the core from the supplied kernel, execute a tracer first and document bounded necessary extensions.

#### Modules

Machine path: `requirements/6/modules`

- kernel/canonical.py
- kernel/models/base.py

#### Gates

Machine path: `requirements/6/gates`

- G-RBT-TRACER
- G-ARCH-001

### 7

Machine path: `requirements/7`

Requirement Id (`requirements/7/requirement_id`): RBT-REQ-008

Rule (`requirements/7/rule`): Keep existing baseline tools and completion transaction unchanged; reference receipts never replace integration tests or review authority.

#### Modules

Machine path: `requirements/7/modules`

- service.py
- store.py

#### Gates

Machine path: `requirements/7/gates`

- G-RBT-POLICY
- G-RUNTIME-004

### 8

Machine path: `requirements/8`

Requirement Id (`requirements/8/requirement_id`): RBT-REQ-009

Rule (`requirements/8/rule`): Publish executable documentation, field bindings, module controls, complete test inventory, cumulative gates and RRCA evidence.

#### Modules

Machine path: `requirements/8/modules`

- cli.py
- mcp_contract.py

#### Gates

Machine path: `requirements/8/gates`

- G-ARCH-001
- G-RBT-DOCS
- G-RBT-POLICY

## Semantic Contract

Machine path: `semantic_contract`

- Semantic means only declared equals, unchanged, non_empty and subset constraints; no language-model judgment or general proof of behavioral equivalence is claimed.
- JSON objects are compared recursively by an iterative walker; arrays are atomic values. Numeric representation is strict: 1 and 1.0 are distinct for equality/enum/const and delta identity.
- JSON Pointer uses canonical ~0/~1 escapes, dictionary segments only, no root replacement, no empty key segments or array-index patching.
- Allowed paths are exact, not prefix permissions; replacing a parent object does not authorize unlisted child deltas.
- Replace/remove require the previous value digest; overlapping operations reject; add requires absence.
- A submitted candidate must exactly equal reconstruction from the admitted reference and requested change, even if its extra change uses an otherwise permitted path.
- Markdown is a strict ATX/LF section projection. Rendering must reparse identically, preventing body edits from introducing headings or dropping sections.
- Schema profile supports explicit JSON types, closed objects/properties/required, items, enum/const, min/max Length/Items, uniqueItems, minimum/maximum, title/description and the 2020-12 dialect marker. All other keywords reject.

## Boundary Limits

Machine path: `boundary_limits`

- 262144 bytes per input, policy, schema or reference; at most 4096 JSON nodes and depth 16.
- At most 32 references, 32 assignment triples, 64 patches, 64 delta entries, and a per-reference max_delta no greater than 64.
- Relative filesystem paths are at most 1024 characters; patch pointers are at most 256 characters and 16 nonempty segments.
- No symlinks, parent traversal, absolute caller paths, secret-path patterns or non-regular reference files.
- At most 4096 newline-framed MCP messages per process. Oversized or unterminated frames terminate with a protocol error; synchronous bounded processing only.
- At most 4096 immutable receipt rows and 1048576 bytes per stored envelope; SQLite lock wait is two seconds. Dedicated OS-level disk/process limits remain the operator responsibility.
- No hard real-time or allocation-free claim: Python, Pydantic and SQLite are managed-support components, not promoted safety/authority controllers.

## Handoff Contract

Machine path: `handoff_contract`

- transform/validate/diff yield PASS only after the same reducer checks; their artifacts remain unpersisted and handoff_ready=false.
- emit_receipt receives a candidate and prior validation receipt ID; it recomputes the decision, checks the ID, reloads pinned sources, then atomically appends the complete envelope. Only this returns handoff_ready=true.
- Handoff-ready means locally recorded engineering evidence, not task completion, runtime activation, or human approval.
- Rejected candidates are withheld from artifact/rendered output; available delta and reason codes explain rejection. Pin mismatches and storage capacity produce HOLD.
- Receipt IDs are integrity hashes, not signatures or authentication. Operator-controlled policy and process boundaries are the trust root; privileged filesystem tampering is outside this tool's guarantee.
- Downstream task_update still runs truth_serum, RRCA/cumulative checks, scaffoldctl and package tests; working_agreement still requires fresh passing receipts. Existing corrective feedback, lease and attempt limits are not bypassed or reimplemented.

## Exclusions

Machine path: `exclusions`

- No arbitrary shell, network, remote Git checkout, installation hooks, model calls, execution of generated artifacts, or template expressions.
- No YAML, binary files, arbitrary source-code refactoring, AST equivalence, cross-file transaction generator, full JSON Schema evaluator or semantic natural-language proof.
- No policy self-edit, policy-pin inference from caller input, authority escalation, DONE transition or operational activation.
- No automatic personal Codex skill installation, remote repository creation or deployment is performed by this package.

## Source Policies

Machine path: `source_policies`

- HMT_Axioms_Policy_v1.0.0.json
- HMT_rrca_policy_v4.json
- HMT_Baseline_MCP_Tools_v1.2.0.json
- default-pace-matrix_v1.json
- Ontology_FederatedBaseline_Core.ttl
- Ontology_FederatedBaseline_SubtypeCore.ttl

## Promotion Requirements

Machine path: `promotion_requirements`

- Human Architect reviews the new policy and baseline v1.3.0 successor; the frozen v1.2.0 source remains byte-preserved.
- Resolve real production reference repo paths, exact policies and assignment bindings; execute the supplied cumulative test manifest in the actual host.
- Run the actual sovereign truth_serum/scaffoldctl/rrca-build and upstream completion transaction where configured; local analogous tests are not sovereign receipts.
- For a claim of exact full-kernel reproduction, rerun its own validation under its pinned Python 3.13 environment. This package's verified Python 3.12 scope does not satisfy that separate claim.


# HMT Axioms Policy

**Policy ID:** `HMT-AXIOMS`  
**Version:** `1.0.0`  
**Status:** Candidate policy for Human Architect promotion  
**Issued:** 2026-09-02  
**Machine policy:** `HMT_Axioms_Policy_v1.0.0.json`  
**Frozen tool baseline:** `HMT_Baseline_MCP_Tools_v1.0.0.json`  
**Baseline SHA-256:** `ff34e5ed4e999e5c60ce84ba864ab1fe7d315f18b090f91d292f5c46e788face`

## 1. Purpose

This policy defines the six governing axioms for Human–Machine Teaming systems, repositories, tools, skills, notebooks, agents, adapters, control planes, and handoff packages.

The axioms turn architectural intent into executable admission law. A build is not acceptable because its design sounds plausible. It is acceptable only when its bounded implementation executes, produces evidence, survives its declared verification gates, and explains itself without depending on the builder's memory.

## 2. Normative language

- **SHALL** and **SHALL NOT** are mandatory.
- **SHOULD** identifies a preferred implementation that requires a documented reason when not followed.
- **MAY** identifies an allowed implementation choice.
- A violation of any SHALL requirement places the affected task, artifact, or build in `HOLD` until repaired or explicitly escalated to the Human Architect.
- An agent, model, tool, test, or receipt cannot promote its own authority.

## 3. Scope and execution profiles

This policy applies to:

- HMT repositories and packages;
- embedded MCP servers and tool adapters;
- agent and human operating interfaces;
- safety-critical control and actuation paths;
- deterministic build, verification, and handoff tools;
- notebooks, tracer bullets, digital twins, and Python plants;
- repository-specific skills and their evidence.

The safety-critical execution path is the code permitted to influence physical state, authority state, task completion, admission, or a controlled terminal decision. Managed-runtime components that cannot satisfy the safety-critical memory and timing rules SHALL remain outside that path and interact only through bounded, typed, fail-closed adapters.

## 4. The six HMT axioms

### HMT-AX-001 — Predictable Finite-State Core

**Axiom:** The safety-critical execution path SHALL operate as a bounded, predictable finite-state system. After initialization it SHALL perform no dynamic memory allocation, use no recursion, expose no hidden side-effect pointers, and accept no boundary parameter that is not explicitly admitted. Buffers, queues, state containers, and work pools SHALL be prefilled or preallocated before consequential execution.

**Tactical posture:** Structural stress must not cause unbounded loops, memory-pool exhaustion, silent state drift, or an authority transition that cannot be replayed.

**Required implementation:**

1. Every loop SHALL have a statically declared or configuration-bounded iteration ceiling.
2. Recursion SHALL be rejected by static verification.
3. Inputs SHALL enter through typed default-deny schemas.
4. Consequential state transitions SHALL be explicit and finite.
5. Mutable global state SHALL NOT be used as an unreceipted control channel.
6. Managed runtimes that allocate dynamically SHALL remain outside the hard safety path unless an evidence-backed equivalent bound is proven and promoted by the Human Architect.

**Minimum evidence:** static-analysis receipt, loop-bound inventory, allocation-bound statement, state-transition inventory, negative boundary tests, and replay receipt.

**Breach disposition:** `HOLD_SAFETY_CORE_UNBOUNDED`.

### HMT-AX-002 — Fold 7 Spatial Ceiling

**Axiom:** Every discrete business function SHALL contain no more than 60 source lines, and every encapsulated executable module SHALL contain no more than 100 source lines.

**Tactical posture:** Tight spatial bounds force semantic density, reduce cross-module entanglement, and keep the implementation within a reviewable human and agent working set.

**Counting rule:** Count nonblank physical source lines from the first decorator or declaration through the end of the function or module. Comment-only lines do not count. Decorators and docstrings count. Generated evidence, immutable data fixtures, and prose documents are not executable modules. Notebook cell functions are functions under this rule.

**Required implementation:**

1. Oversized routines SHALL be decomposed by responsibility, not hidden through formatting.
2. A module SHALL NOT evade the ceiling by dynamically injecting code or importing unbounded side effects.
3. Any unavoidable exception SHALL be placed in `HOLD` and require explicit Human Architect disposition before promotion.

**Minimum evidence:** deterministic LOC report naming every checked function and module, with stable reason codes for violations.

**Breach disposition:** `HOLD_FOLD7_CEILING_EXCEEDED`.

### HMT-AX-003 — Agent-Validated Tracer-Bullet Inception

**Axiom:** An agent or model SHALL NOT claim a solution, recommend an architectural direction for implementation, or admit work into the repository until it has compiled, executed, and validated a thin end-to-end slice in a live disposable sandbox such as `scratch_pad.py`, with human inspection support such as `white_board.html` where useful.

**Tactical posture:** The builder acts as an accountable systems compiler. Environmental initialization, integration viability, and the first complete execution path are proven before the master repository absorbs the direction.

**Required implementation:**

1. The tracer SHALL cross every critical seam necessary to prove the proposed direction.
2. It SHALL include at least one valid path and one fail-closed or negative path.
3. Inputs, outputs, configuration, environment, evidence, and artifact hashes SHALL be captured.
4. A conversational description, partial code fragment, mocked success response, or “complete the environment yourself” handoff SHALL NOT satisfy this axiom.
5. If the executing agent cannot validate the tracer bullet, the direction SHALL be classified `HOLD_AGENT_VALIDATION_INCOMPLETE`, not feasible-by-assertion.
6. The full build MAY begin only after the tracer receipt is admitted.

**Minimum evidence:** compile receipt, execution receipt, negative-path receipt, environment manifest, seam inventory, artifact hash, and admission decision.

**Breach disposition:** `HOLD_TRACER_BULLET_NOT_PROVEN`.

### HMT-AX-004 — Reusable Steel

**Axiom:** Simplicity SHALL preserve rigor. Once a deterministic capability has been hardened, it SHALL be packaged as reusable steel through a narrow typed interface instead of being repeatedly rebuilt, copied, or replaced with prose orchestration.

**Tactical posture:** Work hard once. Reuse the proven mechanism through adapters. Keep the system small without watering down its constraints, evidence, or failure behavior.

**Required implementation:**

1. Shared capabilities SHALL remain independently executable and model-agnostic.
2. MCP exposure SHALL use a bounded adapter rather than absorb or duplicate the sovereign tool.
3. Direct execution and MCP execution SHALL produce semantically equivalent decisions and receipts.
4. Repository-specific skills SHALL add repository-specific work and SHALL NOT rename or wrap baseline tools without new functionality.
5. The simplest design that satisfies every governing requirement SHALL be preferred.

**Minimum evidence:** adapter contract, direct/MCP parity receipt, reuse map, dependency boundary, and regression tests.

**Breach disposition:** `HOLD_REUSABLE_STEEL_PARITY_FAILED`.

### HMT-AX-005 — Self-Explaining Operational Scaffold

**Axiom:** The system and each consequential module SHALL be documented, functionally scaffolded, wired, and evidenced well enough to explain operation, authority, troubleshooting, verification, and recovery without the original builder being present for mental refresh or cognitive hand-holding.

**Tactical posture:** Context saturation is treated as an engineering failure mode. Operational meaning belongs in executable interfaces, receipts, and concise root documents, not in the builder's memory.

**Required implementation:**

1. Every repository SHALL contain root-level `Runbook.md`, `Agents.md`, and `SKILLS.md` documents.
2. `Runbook.md` SHALL provide operator-ready execution, observability, maintenance, troubleshooting, recovery, and verification procedures.
3. `Agents.md` SHALL define authority, admission, interception, task, tool, failure, and escalation behavior.
4. `SKILLS.md` SHALL project executable skills, schemas, bounds, evidence, and invocation contracts.
5. Every consequential module SHALL identify its purpose, inputs, outputs, side effects, authority requirements, failure states, evidence, and verification command.
6. Documentation SHALL match the executable state and SHALL NOT claim unavailable, unbound, or unverified capability.

**Minimum evidence:** documentation parity report, clean-room operator replay, clean-room agent replay, capability registry parity, and dead-link or stale-command checks.

**Breach disposition:** `HOLD_OPERATIONAL_CONTEXT_INCOMPLETE`.

### HMT-AX-006 — Reverse RCA and Cumulative Verification

**Axiom:** Verification is a dynamic cumulative constraint. After each task item, every previously good applicable gate SHALL be rerun. When a regression or contradiction appears, work SHALL stop, Reverse RCA SHALL traverse the evidenced causal chain upstream to the initiating condition or lawful boundary, the coupling SHALL be repaired, and regression testing SHALL proceed back down the chain before work continues.

**Tactical posture:** The output is treated as a receipt of upstream admissions, authority transfers, state changes, and structural effects. Surface repair without causal closure is not completion.

**Required implementation:**

1. Begin with: “For this output to be true, what upstream effects admitted or caused it?”
2. Traverse only evidenced causal edges and stop at a reproducible initiating condition, immutable dependency, explicit architectural boundary, or evidence-backed environmental limitation.
3. Assign stable gate and incident identifiers.
4. Maintain a `Cumulative Gate Ledger` with no more than seven columns.
5. Maintain a `Reverse RCA Ledger` with no more than seven columns.
6. When supervised sub-agents are used, an eighth `sub_agent_task_attestation` column is authorized and required, with cross-spectrum contradiction checking.
7. A repaired branch SHALL rerun its causal regression chain and every previously good applicable gate.

**Minimum evidence:** cumulative gate ledger, Reverse RCA ledger, reproducer, initiating-condition evidence, repair diff, downstream regression receipts, and final disposition.

**Breach disposition:** `HOLD_RRCA_OR_REGRESSION_INCOMPLETE`.

## 5. Frozen baseline MCP tool surface

The baseline MCP surface is frozen at twelve tools. Repository-specific skills extend this surface but SHALL NOT replace, rename, duplicate, or widen its authority.

| Group | Frozen tools |
|---|---|
| Repository operations | `list_files`, `read_file`, `write_file`, `run_command` |
| Task control | `tasks_list`, `task_get`, `task_update`, `task_create`, `working_agreement`, `verify_task_board` |
| Capability discovery | `list_skills` |
| Evidence retrieval | `memory_search` |

The machine-authoritative definitions, controls, completion transaction, adapter interfaces, and extension policy are frozen in `HMT_Baseline_MCP_Tools_v1.0.0.json`.

## 6. Completion firewall

`task_update` SHALL execute the following non-optional transaction:

1. Validate mission, authority, assignment, and state.
2. Hash the submitted package.
3. Run Truth Serum.
4. Check the Reverse RCA ledger.
5. Check the cumulative gate ledger.
6. Run `scaffoldctl`.
7. Persist an immutable receipt.
8. Run `verify_task_board`.
9. Run `working_agreement`.
10. Apply `REVIEW`, `QUARANTINED`, or `ESCALATED`.

The model SHALL NOT choose whether the firewall runs. `task_update` SHALL NOT self-promote a task to `DONE`. Human closeout remains a separate admitted act.

## 7. Repository-specific skill policy

The default target is five repository-specific executable skills in addition to the frozen baseline.

Each skill SHALL:

- perform repository-specific work;
- expose a typed and bounded contract;
- execute independently of a specific model vendor;
- pass direct and MCP parity tests;
- emit deterministic receipts and stable reason codes;
- participate in repository admission, task control, and evidence lineage;
- appear in `SKILLS.md` only after implementation and validation.

A prose-only workflow is not a skill. A renamed baseline tool is not bespoke. A tool the builder cannot execute and validate is not admitted.

## 8. Admission and change control

- Any axiom breach produces `HOLD` for the affected scope.
- Evidence may narrow a HOLD to one task, tool, or package. Lack of evidence SHALL NOT widen acceptance.
- A model or agent SHALL NOT waive an axiom, expand its authority, or modify the frozen tool baseline.
- Baseline changes require a new version and explicit Human Architect approval.
- Policy promotion from Candidate to Active requires Human Architect disposition and preservation of the promoted artifact hashes.

## 9. Minimum repository acceptance packet

An HMT repository is not ready for handoff until it contains:

1. `Runbook.md`, `Agents.md`, and `SKILLS.md`;
2. frozen-baseline compatibility receipt;
3. admitted tracer-bullet receipt;
4. capability registry and implementation parity receipt;
5. direct/MCP parity receipt for every consequential tool;
6. deterministic Fold 7 and safety-core reports;
7. cumulative gate and Reverse RCA ledgers;
8. repository-specific skill tests and evidence;
9. one final package hash and Human Architect disposition.

# scaffoldctl Agent Orchestration

## Mission

Operate `scaffoldctl` as a deterministic repository-boundary tool. Agents may inspect, plan,
scaffold missing governed files, validate, audit, and verify evidence. No agent may widen authority,
overwrite governed content, infer an admission pass, or promote an external repository.

## Roles

| Role | Owns | Must hand off |
|---|---|---|
| Boundary planner | Root identity, policy, and immutable plan | Canonical plan and pre-state digest |
| Scaffold executor | Exclusive creation and owned rollback | Mutation receipt and remaining HOLDs |
| Perimeter verifier | Worktree, index, or tree validation | Reason-coded perimeter receipt |
| Evidence custodian | Lease, DuckDB append, replay, and seal | Chain head, signatures, and non-claims |
| Human promoter | Protected-branch and release decision | Explicit approval or refusal |

## Execution Order

1. Read `README.md`, `Start_here.md`, `Index.md`, `AGENTS.md`, and `Humans.md`.
2. Verify ontology, policy, template, lockfile, and requested repository-root authority.
3. Select exactly one operation and bind every path beneath the requested root.
4. Execute through the `scaffoldctl` CLI or public Python API, never an improvised write path.
5. Preserve the complete JSON receipt, reason codes, hashes, and rollback disposition.
6. Stop before promotion and hand evidence to the named human authority.

For MCP+ invocation, use only `adapters/contract_adapter.py`. Present authority, equal admission and
current epochs, exact outer fields, and bounded string arguments are mandatory. The adapter exposes
no scaffolding, hook installation, key generation, ledger sealing, direct actuation, architecture
mutation, or promotion capability.

## State Ownership

Runtime keys and DuckDB ledgers belong beneath the governed target repository's Git directory, not
this source tree. Plans and receipts are immutable values. A caller cannot supply its own verdict,
lease, evidence sequence, chain head, or lifecycle transition result.

## Stop and Handoff Law

Stop on authority drift, discovery ambiguity, symlinks, case collisions, existing-content conflict,
stale plans, temporary transaction remnants, Git matrix drift, signature failure, ledger mismatch,
or any missing HMT document. Return the typed failure or HOLD receipt unchanged. Only a human may
authorize protected-branch requirements, trusted release-key binding, or external promotion.

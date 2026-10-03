# Inherited Worktree Scaffolding Contract

`phase2` remains the frozen schema and resource compatibility identifier for these operations. The
operational repository and command title is `scaffoldctl`.

## Authority Boundary

The promoted Phase 0/1 archive is the immutable upstream code baseline. The embedded Turtle
ontology controls lifecycle semantics. The embedded policy and templates control Phase 2 boundary
content. Hash drift in any authority source rejects the operation before mutation.

## Operations

| Operation | Reads | Writes | Successful lifecycle result |
|---|---|---|---|
| `plan` | Worktree and embedded authority | None | `Planned` |
| `scaffold` | Exact plan, worktree, embedded authority | Approved missing files only | `ScaffoldedUnvalidated` |
| `validate --worktree` | Worktree and embedded authority | None | `Validated` |
| `audit --worktree` | Worktree and optional receipt | None | No state transition |

## Plan Law

A plan binds the boundary identity, target, complete four-artifact action set, pre-operation snapshot
digest, ontology hash, policy hash, template hash, lifecycle receipt, deterministic UUIDv5 identity,
and canonical payload hash. Scaffolding recomputes the plan and rejects stale or altered input.

## Mutation Law

The engine opens the repository root without following links and pins its device/inode identity.
Each path component is traversed with a directory file descriptor. Missing parents are created only
for the current operation. Candidate files are staged exclusively, fsynced, published with
no-overwrite hard links, validated as a complete overlay, and then finalized.

Rollback records the staged inode identity. It removes a published destination only when that inode
still belongs to the current operation. Replaced or foreign content is preserved and produces an
incomplete-rollback receipt. Abandoned transaction remnants cause HOLD; Phase 2 never deletes them
without a live operation ownership record.

## Existing Content Law

An existing governed file is never overwritten. It may be preserved only when it already satisfies
the same strict policy and, for `scaffold.policy.json`, exactly matches the requested boundary. An
invalid or authority-widening existing file rejects planning.

Each required section heading must occur exactly once and own non-empty, non-heading content before
the next peer heading. Heading-only boilerplate is not conformant.

## Receipt Law

Every operation emits one strict JSON document with closed reason codes, authority hashes, snapshot
hashes where available, artifact evidence, findings, mutation dispositions, rollback status, a
deterministic UUIDv5 identity, and a SHA-256 receipt hash. Serialization is sorted compact UTF-8 JSON
with duplicate keys and non-finite values rejected.

## Compatibility Boundary

Git-index and commit-tree truth, hooks, CI admission, leases, and DuckDB sealing are implemented by
the subsequent compatibility epoch described in `Git_Admission_and_Evidence_Contract.md`. External promotion and
cross-platform parity remain outside this inherited worktree contract.

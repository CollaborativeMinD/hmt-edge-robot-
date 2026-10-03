# scaffoldctl

## Purpose

`scaffoldctl` is an ontology-governed repository semantic-perimeter control plane. It plans and
creates missing HMT boundary documents without overwriting existing content, validates worktrees or
immutable Git objects, signs short-lived asset leases, and chains evidence in DuckDB.

## Lifecycle

The operational path is `Uninitialized` to `Planned` to `ScaffoldedUnvalidated` to `Validated` to
`Sealed`. `Hold`, `Fail`, and `Rejected` are explicit terminal-control states. A rejected admission
gate returns exit code 1 and cannot mint a lease or enter `Sealed`.

## Invariants

- Git-index validation reads staged object IDs and blobs, never worktree substitutes.
- Every declared boundary contains exactly one README, Start Here, and Index document.
- Each governed document is strict UTF-8, structurally complete, and below 100 physical lines.
- Hook, direct staged validation, and CI commit-tree validation use the same verdict engine.
- Passing receipts and Ed25519 leases are atomically appended to DuckDB before admission.
- Unknown contract fields are forbidden; all public evidence contracts are strict and immutable.
- Production functions are bounded to 60 physical source lines by a static test gate.

## Authority

The embedded ontology controls lifecycle and HMT semantics. Pinned policies and templates control
document validation. Historical schema epochs remain named `phase2` and `phase3` for compatibility;
they are implementation identifiers, not repository titles. A local hook is convenience enforcement,
while the protected CI check is repository admission authority. This normalized source snapshot is
**HOLD** until its complete locked test, lint, distribution, and human review gates run again.

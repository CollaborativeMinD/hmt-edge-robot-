# Git Admission and Evidence Contract

`phase3` remains the frozen schema compatibility identifier for these operations. The operational
repository and command title is `scaffoldctl`.

## Git Truth

Staged validation consumes a complete, canonical matrix of index path, stage, mode, type, object ID,
and size records. Content is read from the named object database blob. The index is recaptured after
validation; any matrix change rejects the operation. Commit-tree CI uses the same snapshot protocol.

## Perimeter Law

The repository root is always a boundary. Additional boundaries are declared by a strict
`scaffold.policy.json`. Discovery uses the union of candidate and baseline snapshots, so deleting an
entire boundary cannot erase its validation obligation. Every boundary requires the exact trifecta,
valid headings and sections, strict UTF-8, no unresolved placeholders, and fewer than 100 lines.

## Hook and CI Law

The native hook is a thin wrapper around `scaffoldctl pre-commit`. Missing executables, repository
discovery failures, missing keys, invalid evidence, missing documents, and line-budget violations all
terminate with explicit exit code 1. The hook is bypassable locally; protected CI is authoritative.

## Lease Law

A passing perimeter receipt receives one Ed25519 lease bound to its receipt hash, content matrix,
boundary set, purpose, source, signer provenance, key fingerprint, and a lifetime no longer than 900
seconds. A failed perimeter cannot receive a lease. Signatures prove key possession, not operator
identity unless deployment binds that key externally.

## Ledger Law

DuckDB is the native writer for validation receipts, signed asset leases, evidence-chain rows, and
signed ledger seals. One transaction appends a validation and its optional lease, typed rows, payload
hashes, previous hash, and record hash. Commit is followed by checkpoint. Failure rolls back and
rejects the hook. Replay verifies canonical payloads, sequence continuity, typed-row parity, receipt
hashes, lease signatures, and seal signatures.

## Seal Law

The ontology lifecycle remains explicit: Planned, ScaffoldedUnvalidated, Validated, then Sealed.
`VALIDATED_SEALED` is the release disposition produced only after all four legal transition receipts,
the Phase 3 crucible, distribution reproducibility, installed-wheel execution, and signed DuckDB seal
are present.

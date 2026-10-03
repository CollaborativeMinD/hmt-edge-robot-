# scaffoldctl Operational Threat Model

## Protected Assets

- Existing repository content and root confinement
- Ontology, policy, template, and Git-object authority
- Deterministic plans, receipts, leases, ledger rows, and lifecycle decisions
- Operator-controlled promotion and trusted-key bindings

## Threats and Controls

| Threat | Primary controls | Residual posture |
|---|---|---|
| Absolute or traversing path | Canonical paths; root-pinned descriptor traversal | Reject |
| Symlink or path-component swap | No-follow opens; inode and object-matrix recapture | Reject/Hold |
| Case or Unicode collision | NFKC plus casefold collision keys | Reject |
| Existing-content overwrite | Preserve-only planning; exclusive publication | Reject |
| Partial publication | Owned inode records; reverse rollback; directory fsync | Receipt-bound rollback |
| Stale or tampered plan | Snapshot recomputation; deterministic identity and hash | Reject |
| Invalid HMT document | UTF-8, byte, line, heading, placeholder, and schema gates | Hold |
| Worktree masks staged content | Git index and blob object matrix | Reject |
| Boundary deletion hides duty | Candidate and baseline boundary union | Reject |
| Hook bypass or CI divergence | Shared verdict engine; protected required check | CI governs |
| Forged admission or lease | Closed models; receipt binding; Ed25519 signatures | Reject |
| Ledger rollback or row drift | Monotonic hash chain; typed-row parity; signed seal | Reject |

## Trusted Computing Boundary

The tool trusts the local Python runtime, Git object database, DuckDB engine, operating-system
filesystem semantics, installed package bytes after authority checks, and the operator-selected
repository root. SHA-256 proves payload integrity. Ed25519 proves key possession. Neither proves a
human identity unless deployment binds the key externally.

## Residual Limits

- A local hook remains bypassable; protected CI must be required for admission authority.
- Windows filesystem parity is not verified by the sealed v0.3.0 closeout evidence.
- Crash remnants require operator review; automatic deletion is intentionally forbidden.
- External release promotion and consequential runtime authorization remain human decisions.
- The tool asserts repository governance, not executable physics, optimization, or control claims.

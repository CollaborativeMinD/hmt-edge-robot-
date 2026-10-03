# scaffoldctl Human Operations

## Operator Boundary

Humans choose the repository root, boundary purpose, protected-branch policy, trusted signing-key
binding, and promotion decision. `scaffoldctl` validates evidence and enforces bounded mutations; it
does not authenticate an operator or self-authorize a release.

## Safe Workflow

1. Inspect `README.md`, `Start_here.md`, `Index.md`, and the applicable contract in `docs/`.
2. Run `scaffoldctl authority` and preserve its JSON output.
3. Generate a plan, review its target and complete action set, then run `scaffold` exactly once.
4. Stage intended changes and run `scaffoldctl pre-commit`, or validate a named commit tree in CI.
5. Verify the DuckDB ledger and require the protected `scaffoldctl-perimeter` check before promotion.

MCP+ integrations must consume `adapters/mcp_tool_contract.json` and invoke the subprocess-only
adapter. Do not expose implementation imports or expand its capability map without a new review.

## Approval Boundary

An exit code of 0 proves only the declared local validation contract. Ed25519 proves possession of
the embedded public key. A human-controlled deployment process must bind that key to an identity,
review residual risks, and approve any consequential use. The normalized source remains HOLD until
the complete locked test, lint, distribution, and review gates pass for its exact digest.

## Recovery

Never delete `.scaffoldctl-*.tmp` remnants blindly. Preserve the failure receipt, compare recorded
device and inode ownership, and recover only through an operation-specific procedure. Do not replace
an existing hook, policy, key, ledger, or governed document merely to obtain a passing result.

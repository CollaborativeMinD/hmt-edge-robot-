# Index

## Boundary

This root owns the operational `scaffoldctl` package, worktree and Git-object adapters, hook and CI
wrappers, cryptographic leases, DuckDB evidence ledger, conformance tests, and sealed closeout record.

## Governed Documents

- `README.md`: purpose, lifecycle, invariants, and authority
- `Start_here.md`: installation, first action, and validation
- `Index.md`: topology and artifact register
- `scaffold.policy.json`: executable root-boundary policy
- `Agents.md.md`: machine orchestration, ownership, and handoff law
- `AGENTS.md`: machine-facing authority and stop law
- `Humans.md`: operator workflow, approval boundary, and recovery law
- `adapters/mcp_tool_contract.json`: bounded MCP+ capability and authority contract

## Registered Artifacts

- `src/scaffoldctl/git_snapshot.py`: immutable Git object-matrix adapters
- `src/scaffoldctl/perimeter.py`: shared boundary discovery and verdict engine
- `src/scaffoldctl/phase3_models.py`: strict frozen Phase 3 contracts
- `src/scaffoldctl/lease.py`: Ed25519 key and asset-lease operations
- `src/scaffoldctl/ledger.py`: DuckDB chain, replay verification, and sealing
- `src/scaffoldctl/hook.py`: hook orchestration and fail-closed installation
- `src/scaffoldctl/resources/boundary_contract/`: HMT policy and document templates
- `src/scaffoldctl/resources/git_perimeter/pre-commit`: packaged native hook wrapper
- `.github/workflows/scaffoldctl-perimeter.yml`: protected CI adapter
- `adapters/contract_adapter.py`: subprocess-only MCP+ invocation seam
- `docs/Worktree_Scaffolding_Contract.md`: inherited worktree and no-overwrite contract
- `docs/Git_Admission_and_Evidence_Contract.md`: Git admission, lease, and ledger contract
- `docs/Threat_Model.md`: consolidated operational threats and residual limits
- `scripts/check_function_lengths.py`: static 60-line production-function gate
- `scripts/seal_ledger.py`: standalone ledger-sealing utility
- `tests/`: contract, Git, hook, signature, ledger, parity, and tamper crucible
- `evidence/`: current normalization inventory, validation receipt, and qualification blockers
- `provenance/sealed_source_release_v0_3_0/closeout_evidence/`: incoming sealed receipts and ledger
- `provenance/sealed_source_release_v0_3_0/distributions/`: incoming verified wheel and sdist

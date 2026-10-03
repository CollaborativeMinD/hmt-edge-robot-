# Truth Serum Index

## Boundary

The root is governed by `scaffold.policy.json`; runtime scope is constrained by `architecture/`.

## Governed Documents

- `README.md`: mission, lifecycle, invariants, and authority.
- `Start_here.md`: shortest safe operator path.
- `Runbook.md`: full human SOP and troubleshooting.
- `Agents.md`: agent regions, commands, stop law, and handoff contract.
- `architecture/`: textual SSOT, traceability, namespace, and non-claims.
- `contracts/`: closed data schemas and lane policy.

## Registered Artifacts

- `truth_serum.py` and `src/`: admission entry point and implementation.
- `tests/`: positive, negative, mutation, schema, and seal regressions.
- `scripts/`: admission, pre-commit, and cumulative verification wrappers.
- `evidence/`: final BLUF, convergence, provenance, manifest, and closeout results.
- `REPOSITORY_SEAL.json`: sole whole-repository checksum and closeout seal.

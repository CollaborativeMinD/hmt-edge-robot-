# Repo-runner integration note

Recommended destination inside `hmt-edge-robot-`:

`archive/version-lineage/v1.0.0/`

Keep the contents intact. Do not unpack the ten predecessor ZIPs into the live source tree.

Suggested admission checks before commit:

1. Verify `05_manifests/SHA256SUMS.txt` from the extracted archive root.
2. Confirm `03_integrated_edge_reference/integration_receipt.json` points at the intended main commit or update only the integration receipt in a new archive version.
3. Preserve the archive version immutably. Future lineage additions should create `v1.1.0`, `v1.2.0`, etc., rather than mutating `v1.0.0`.
4. Do not interpret archived predecessor claims as current integrated acceptance. Current acceptance is defined by the live repository validation evidence and explicit HOLD register.

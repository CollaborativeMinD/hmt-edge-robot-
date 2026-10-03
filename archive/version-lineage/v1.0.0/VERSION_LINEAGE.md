# HMT Edge Robot — Version Lineage Archive

## Purpose

Preserve the engineering paper trail from the five original subsystem projects, through their Lambda-aligned revalidation packages, to the composed HMT Edge Robot integration.

## Lineage

**V1 proved the mechanisms.**

- AccessManager
- Factory Orchestrator
- HaloSafe
- Neuro-Grasp
- Waialua Edge Node v11

**Lambda revalidation proved the subsystems as bounded engineering artifacts.**

The revalidation packs add combinations of strict contracts, SysML slices, requirements traceability, interface control documents, SIL campaigns, regression evidence, and run artifacts while preserving each subsystem's core intent.

**HMT Edge Robot proves the composition in the supervisory/SIL partition.**

Current integrated reference:

- Repository: `CollaborativeMinD/hmt-edge-robot-`
- Main commit: `57b2d8e313955ef598c7b7bf90d13ced6bb54f37`
- Tree: `2624da6ee236811069326e5a35743a28067a2fa2`
- Merge: `Compose the edge robotics cell with resident HMT and verified analytics`
- Software validation: PASS
- External physical deployment: HOLD

## Preservation law

The ten source ZIP archives under `01_v1_prototypes/` and `02_lambda_revalidation/` are copied byte-for-byte from the supplied originals. Their SHA-256 hashes are the archival identity. Do not unpack, modify, recompress, or overwrite them when promoting this archive into the repository.

The integrated repository is deliberately referenced by immutable commit/tree identifiers rather than recursively archiving the repository inside itself. Selected current architecture, requirement, and validation snapshots are included only to make the handoff intelligible if the archive is viewed independently.

## Verification

From the archive root after extraction:

```bash
sha256sum -c 05_manifests/SHA256SUMS.txt
```

A mismatch means the archive lineage is no longer identical to the packaged receipt.

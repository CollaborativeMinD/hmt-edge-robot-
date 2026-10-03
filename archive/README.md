# Preserved project checkpoint

The project is paused following supervisory/SIL integration and preservation of
its engineering lineage. The executable build, its acceptance evidence, and its
external HOLD boundaries remain at the repository root.

[Version lineage v1.0.0](version-lineage/v1.0.0/VERSION_LINEAGE.md) preserves five
original subsystem ZIPs, five Lambda revalidation ZIPs, their inventories and
manifests, and an immutable reference to the integrated build. The predecessor
archives remain byte-for-byte intact; their contents are not part of the live
source tree.

The separately recorded [admission receipt](version-lineage/admission-v1.0.0.json)
binds the uploaded bundle, extracted file hashes, and verified integration commit.

To verify the preserved contents:

```bash
cd archive/version-lineage/v1.0.0
sha256sum -c 05_manifests/SHA256SUMS.txt
```

Resume lineage work in a new version directory, such as `v1.1.0`; preserve
`v1.0.0` unchanged. Archived acceptance claims describe their historical artifacts.
Current system acceptance remains governed by the live repository's evidence and
explicit external HOLD register.

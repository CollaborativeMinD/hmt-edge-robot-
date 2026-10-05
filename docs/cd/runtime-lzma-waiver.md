# Owner-approved runtime LZMA risk acceptance

On 2026-10-05 the repository owner explicitly instructed: waive the remaining
runtime finding for the personal homelab, document it, observe green PR checks,
and continue the build. The machine-readable approval is recorded in
`policy/artifact_vulnerability_waiver.json` and bound into qualification hashes.

The acceptance covers exactly `TEMP-1147318-639065` on
`liblzma5=5.8.1-1+deb13u1`, severity `UNKNOWN`, without a published fixed version,
in this repository's Linux ARM64 Debian 13 runtime container. It is risk
acceptance, not a package fix or a claim that the finding is non-exploitable.
The issue lacks a useful description in the fetched Debian tracker evidence.
The owner accepts that uncertainty for homelab operation.

The raw Trivy JSON and SBOM remain complete. No scanner ignore flag, severity
rewrite or package-metadata removal is used. Qualification records the accepted
finding, approval and rationale; the private signed release manifest carries
the same record. Artifact/source/signature and restricted native runtime tests
continue to apply.

A different identifier, package, installed version, severity, architecture,
distribution, asset class or newly available fix cannot reuse this acceptance.
Other HIGH/CRITICAL/UNKNOWN findings and all secrets still reject admission.
If an official fix appears, update and requalify the package rather than treating
the accepted risk as permanently cleared.

This approval does not waive the Pi host filesystem's findings. The full appliance
rootfs scan remains strict, and live Pi boot/storage acceptance remains separate.
The stage is cleared only after the fresh PR checks are observed green under this
documented exception; raw scan output will still show the accepted UNKNOWN finding.

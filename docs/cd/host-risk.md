# Pi homelab host vulnerability assessment and owner acceptance

The owner authorized assessment, supported remedies, and scoped waivers on
2026-10-05: “Resolve, assess, and waive any remaining host findings that dont have
a reachable solution natively or within industry practices.” Acceptance is for
this private Raspberry Pi 4/5 SIL fleet with trusted administrators. It does not
establish production, hardware, or public-service suitability.

The assembled rootfs from release run 37273663052 contained 976 HIGH, 21 CRITICAL
and 44 UNKNOWN package matches: 164 vulnerability IDs, no secrets, and no scanner
fixed-version candidates. The eight earlier official updates had removed 29
blocking matches. The complete raw scan remains in that run's failure artifact;
its SHA-256 is recorded in [the assessment](../../evidence/cd/host-risk/assessment.json).
No scanner output, package version, or installed-package metadata is suppressed.

Signed official Debian stable/security and Raspberry Pi ARM64 indexes were
refreshed on 2026-10-05 using keyrings from the checksum-verified stock image.
[Package candidates](../../evidence/cd/host-risk/package-policy.txt) and the
[dependency simulation](../../evidence/cd/host-risk/removal-plan-4.txt) show the
supported path: purge 42 unused packages and install the newer official
wpasupplicant. Its vendor changelog contains SAE fixes, not claims to resolve
these two findings. Both vendor kernels, initramfs tooling, swap, NetworkManager,
Wi-Fi, SSH key generation, Python and authenticated package maintenance remain.
The minimal container carries the application environment; host compilers,
headers, editors, cloud-init and its unused HTTP/JWT stack are unnecessary.
Unused Bluetooth, packet-capture, XML, curl/wget and rpi-update tools are also
removed. Official camera libraries and supported firmware remain.

The planned removal eliminates 462 blocking package matches (432 HIGH, nine
CRITICAL, 21 UNKNOWN) and 61 vulnerability IDs. Native dpkg purge, dependency
audit, required-package readback and a new complete rootfs scan verify the actual
result. A failed purge or new finding stops the pipeline. Removing ack would
remove vendor rpi-swap, so ack stays. Removing busybox/dracut-install, essential
system libraries, or either Pi kernel would compromise supported boot or
maintenance. Mixing unstable packages or unqualified replacement kernels is not
an appropriate fix for this supported Pi appliance. Upstream source patches may
exist; their applicability and a maintained, boot-qualified vendor backport are
not established by the generic Debian source-package scanner match.

Mitigations mask Bluetooth, block unused Bluetooth/SMB/NFS/F2FS/JFS/SCTP module
loading, remove SUID/SGID from mount/umount, and restrict SSH to key-only edgeadmin
with GSSAPI, forwarding and tunnels disabled. No unprivileged fstab mounts or
delegated nsenter access are configured. These controls reduce attack paths;
they do not patch the retained packages or prove the kernel safe. Trusted SSH
clients and root tools must not process untrusted peers, archives or files.
Wi-Fi and core networking remain available. Use on other hardware, enabling
blocked features, public exposure, or untrusted local users requires reassessment.

Every source/CVE decision, retained/removed binary package and relevant upstream
reference is enumerated in the assessment. Specific affected components absent
from the image include systemd-homed, GnuPG tpm2daemon, dracut network boot modules,
tiffcrop; the libxml2 package is removed entirely. These observations justify scoped
acceptance of source-package matches; they do not erase other vulnerabilities
in those libraries. Architecture/driver-specific kernel matches are recorded as
potential overmatches rather than asserted non-exploitable without Pi tests.

[The host policy](../../policy/host_vulnerability_waivers.json) permits only the
579 explicitly enumerated remaining matches, covering 103 IDs, at their exact
package/version/severity on Debian 13 ARM64. This includes residual HIGH and
CRITICAL risks accepted by the homelab owner. The disposition is
`OWNER_ACCEPTED_RISK_NOT_FIXED`, and approval expires 2027-01-03 (90 days).
Every PR and release reruns the scanner. Secrets, an available scanner fix, new
IDs/packages/versions/severities, inventory drift, expired approval, and
container/application findings continue to fail. New official vendor fixes
require refreshing the pinned update catalog and retiring their exceptions.

The raw scan, host update report, hardening inventory and fresh acceptance
receipt enter the release evidence bundle. The protected publisher recomputes
acceptance from those exact bytes and the reviewed policy, rejects stale or
changed receipts, and includes accepted findings and hashes in the signed
manifest. The image and evidence bundle themselves are hash-bound by that
manifest. Full green PR checks and signed image publication are required;
physical Pi boot/storage acceptance remains a separate NOT_RUN/HOLD gate.

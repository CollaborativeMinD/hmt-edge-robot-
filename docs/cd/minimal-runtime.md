# Minimal runtime and official host fixes

The runtime is assembled from a digest-resolved Python 3.12 Trixie builder into
`scratch`, retaining the locked application environment and all dependencies of
its shipped ELF objects. No shell, package manager, Perl, mount or terminal tools
are shipped. Python's optional `_uuid`, `_curses`, `readline` and `_tkinter`
extensions are omitted; standard UUID fallback and LZMA compression are tested.
The Python interpreter and standard library remain available for readiness.

Every copied system library must have a genuine package owner. Its original
installed Debian package/version metadata remains in the image for scanning,
with a list of shipped package files, copyright notices and hashed library
inventory in `/usr/share/hmt/runtime-libraries.json`. Missing native libraries
or package metadata reject construction. The Debian distribution identity and
standard trust bundle are retained. Builder utilities and session proxy trust
are excluded; an optional BuildKit CA secret supports managed local builds.

Qualification tests the actual installed mission, ledger replay, analytics,
resident stop, SciPy/sklearn computations, OpenCV PNG encoding, UUID generation,
LZMA/joblib round trips, localhost resolution and standard TLS trust under the
existing unprivileged, read-only, network-disabled container restrictions.
Admission additionally requires `native_features=PASS` and `minimal_runtime=true`.
The rootfs assembly helpers are bound into unsigned qualification input hashes.

## Remediation outcome

The previous ARM64 runtime had 44 HIGH and 2 UNKNOWN package findings across ten
vulnerability identifiers. A local amd64 build of this minimal Trixie candidate
had no HIGH, CRITICAL or secret findings and one UNKNOWN finding:
`TEMP-1147318-639065`, `liblzma5=5.8.1-1+deb13u1`. It remains a release blocker.
This local result does not substitute for native ARM64 Actions qualification.

A minimal Bookworm candidate was rejected after its scan found SQLite and zlib
CRITICAL findings plus SQLite/OpenSSL HIGH findings. It is not the selected base.
No vulnerabilities are waived, no severities are remapped, and scanner package
metadata is not discarded to manufacture a pass.

## Official host fixes

On 2026-10-04, Raspberry Pi's official ARM64 Lite image index still listed
2026-09-15 as the newest image. Its checksum-pinned input remains unchanged.
The available Trixie ARM64 package versions match the previously flagged versions;
Debian's tracker still marks the ten previous identifiers unresolved in Trixie.
The inspected official Pi image contains all 18 affected package names. Its
systemd/networking/filesystem/package-maintenance dependencies prevent safely
removing the affected library families from this host design.

The full stock-host scan also found issues beyond those ten runtime identifiers:
1003 HIGH, 21 CRITICAL and 46 UNKNOWN package findings, often repeated matches
against the same source package. There were no secret findings. This baseline is
not a scan of the final appliance. Its raw report is retained in the workspace;
a compact summary and signed-repository update plan are committed as evidence.

Eight official ARM64 updates are now pinned by package name, exact version, URL
and SHA256 from signature-verified Debian/Raspberry Pi APT metadata: both PCRE2
libraries, PNG, rsync, mkvtoolnix and the Raspberry Pi OpenSSL library, executable
and legacy provider. APT's simulation against the actual Pi dpkg database selects
eight upgrades without additional installs or removals. These address 29 of the
baseline package findings; the final rootfs scan must verify the outcome.

`appliance_host.py` rechecks archive bytes, package identity and ARM64 architecture
before installation. It permits chroot installation only at the disposable mounted
`build/mount-root`, prevents service startup, audits package configuration and
reads back exact installed versions. It retains a host-update manifest and removes
the temporary .deb files. A separate native ARM64 Actions job checks installation
and Python/OpenSSL behavior even while runtime security admission is blocked.
Image assembly performs the same installation before its existing full rootfs
scan; the signed release includes the input pins and installation evidence.

The remaining work is to adopt and requalify official supported fixes for unresolved
issues. For future updates, refresh the package pins from verified official APT
metadata or select a new official Pi OS image and independently verified checksum,
refresh admission hashes, and rerun native qualification and the full rootfs scan.
There is no unrecorded `apt upgrade`. Do not mix unstable packages, patch installed
version metadata, or remove required boot components. Package-install PASS does
not grant security admission; outstanding HIGH/CRITICAL/UNKNOWN findings hold release.

Sources: https://downloads.raspberrypi.com/raspios_lite_arm64/images/ and
https://security-tracker.debian.org/tracker/data/json; native package repository
checks and selected affected-code presence are recorded in the assessment.

Host vulnerabilities can exceed the runtime's findings. A complete assembled-host
scan and actual Pi boot/storage qualification remain necessary, and no signed
flashable image is claimed by this runtime reduction.

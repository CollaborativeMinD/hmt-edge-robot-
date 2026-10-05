# Vulnerability remediation assessment

Assessment date: 2026-10-04. No project images, Dockerfile or security policy changed.

## Findings

The inspected ARM64 scan contains 44 HIGH and 2 UNKNOWN findings across 18 package names and 10 vulnerability IDs. Current Trixie ARM64 package versions match the flagged versions. All ten remain unresolved in the Debian Trixie tracker. Unstable resolves nine, but the Perl Pod::Text issue remains unresolved there too.

The checksum-verified Pi OS image was inspected through an ordinary copied partition file and unprivileged debugfs, without mounting a filesystem or writing a device. All 18 package names are installed in that ARM64 image. This is package/applicability assessment, not a complete host scan; additional host findings may exist.

Runtime dependency inspection used the current Python base in a disposable amd64 container. That supports design assessment but does not qualify a reduced ARM64 runtime. Native wheel dependencies and required imports still need ARM64 validation.

## Removal assessment

| Group | Application runtime | Pi boot image |
| --- | --- | --- |
| util-linux tools and libraries | Admin tools are candidates for omission from a newly assembled runtime. Python's optional _uuid extension links libuuid; retain it or deliberately exclude and test the fallback. | systemd needs mount/libmount; udev and e2fsprogs need libblkid; e2fsprogs needs libuuid. Retain boot/filesystem functions. mount is setuid root and nsenter exists. |
| libacl1 | Required by coreutils, sed and tar, although not by the Python executable itself. Omission requires a minimal runtime without those tools and verification of native wheels. | Required by systemd and coreutils. Cannot simply purge. |
| libsystemd0 and libudev1 | A systemd manager is unnecessary in this container. Libraries are omission candidates after checking the full dependency closure. Current apt/coreutils/PAM dependencies obstruct a simple purge. | Required by systemd, udev and NetworkManager in this design. |
| ncurses and libtinfo | Terminal utilities are omission candidates. Python _curses/readline and bash link these libraries; narrow Python capabilities deliberately and verify imports. | bash and other host dependencies require terminal libraries. Removing infocmp alone does not clear source-package matches on the remaining libraries. |
| perl-base | No declared application Perl execution requirement. Candidate for omission in a minimal runtime. Essential-package status makes forced apt removal unsuitable. | Perl and the affected Archive::Tar and Pod::Text modules are installed. Assess package-maintenance dependencies before any removal. |
| liblzma5 | Python _lzma links it; joblib optionally imports lzma and supports LZMA-compressed data. Retain unless that capability is explicitly excluded and tested. | dpkg directly pre-depends on it. Needed for supported package maintenance. |

A simulated purge failed on essential Debian dependencies. A minimal runtime must be constructed separately, with a complete ELF dependency closure and truthful scanner/package inventory; deleting package metadata or leaving broken Python extensions is not remediation.

## Applicability evidence

* CVE-2026-16742 concerns systemd-homed. Its executable is absent at the inspected Pi path and absent throughout /usr in the base runtime. This supports investigating affected-code absence, not calling the source package patched.
* CVE-2025-69720 concerns infocmp, which is present in both images. Other ncurses binary packages are source-package matches.
* CVE-2026-9538 and CVE-2026-82560 concern Archive::Tar and Pod::Text. Recursive inspection found neither module in the base runtime; both files are present in Pi OS.
* Four util-linux issues produce 36 of the runtime's findings through repeated source-package matches. They concern mount hooks, restricted mount paths and nsenter --join-cgroup. Host mount and nsenter exist; blanket non-applicability is unjustified. Review fstab, privilege modes, kernel behavior and attacker access.
* CVE-2026-54369 concerns privileged pathname-based ACL operations. Host applicability needs review of privileged callers and attacker-controlled path components.
* TEMP-1147318-639065 remains UNKNOWN, with no useful description in the fetched tracker entry. Obtain upstream details before disposition.

Debian describes several issues as minor or deferred while Trivy assigns HIGH to source-package findings. That discrepancy requires documented affected-code and exploit-prerequisite review; it does not override the current admission policy.

## Recommended next steps

1. Construct a minimal glibc-compatible Python runtime preserving locked dependencies. Omit unused admin tools, Perl, package management and terminal components only with dependency evidence. Validate native wheel linkage, ML/CV imports, UUID/compression behavior, API, ledger and analytics on ARM64, then rescan with the existing gate.
2. Keep the supported Pi OS package set and consume official fixes when available. The current builder copies a pinned stock image without an apt-upgrade step; use a newly pinned patched image or a reproducible pinned update procedure.
3. If release cannot wait, prepare per-vulnerability applicability decisions and narrowly scoped policy changes for explicit review. Bind any exception to asset/version, rationale, owner, expiry and rechecks. No exception was implemented or approved here.
4. A different supported host OS or custom backports requires separate Pi 4/5 boot, cgroup, networking, storage, k3s and recovery qualification. Mixing unstable packages is not a shortcut and still leaves one unresolved issue.

Runtime reduction alone cannot clear the full appliance gate: required host packages still carry findings.

## Evidence

See arm64-package-policy.txt, debian-security-findings.json, scan-blockers.json, runtime-dependencies.txt, pi-dpkg-status, pi-affected-packages.json, pi-affected-code.txt and runtime-affected-code.txt in this directory.

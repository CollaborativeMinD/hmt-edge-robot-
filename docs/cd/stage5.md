# Stage 5 — target qualification (in progress)

Owner assignment: forge-pi-01 is the Pi 5 8GB K3s server; forge-pi-02 and
forge-pi-03 are Pi 4B 8GB workers. 02 owns the application/ledger; 03 owns
backup copies and isolated restore verification. This is a single-server lab.

The owner supplied live Tailscale SSH inventories on 2026-10-04. All nodes are
AArch64 with 64-bit userspace and ext4 roots. The storage medium is microSD:
01 has 63,864,569,856 bytes; 02 and 03 each have 127,999,672,320 bytes.
01/02 report Debian 13.5; 03 reports Debian 13.2. Each reports 2GiB zram swap.
Preserve existing Tailscale enrollment and do not infer services from old endpoints.

This PR begins stage 5 with strict inventory contracts, a read-only collector,
negative admission tests and microSD lab bounds. Host observations do not establish
K3s installation, CNI enforcement, mission readiness or deployment permission.

Stage-3 evidence and dormant manifests remain immutable. The microSD lab profile
is a separate reviewed target policy; it never claims SSD endurance or power-loss
qualification. Single-writer ownership, disk pressure, consistent backup/restore,
private access and native resource checks must collect actual target evidence.

Stage-4 vulnerability/signing HOLDs remain independent. No image publication,
cluster mutation, disk formatting, Tailscale enrollment replacement, physical motion
or paid inference occurs from ordinary PR CI. Target qualification is not yet PASS.

# Stage 5 — mixed-Pi target qualification

Scope: read-only host qualification tooling for the owner's single-server,
microSD-backed lab. Baseline PR head: `783b5f39f02e2fabe3d25130edfb5bc729627d5a`.
No target access, bootstrap, cluster apply, registry publication, credential
provisioning, paid inference, or physical motion occurs in ordinary PR CI.

## Owner evidence and placement

| Host | Owner-assigned substrate and role | Disk bytes | Root partition bytes | Kernel | Debian full version |
|---|---|---:|---:|---|---|
| forge-pi-01 | Pi 5 8GB; control plane/master | 63864569856 | 63319310336 | 6.18.34+rpt-rpi-2712 | 13.5 |
| forge-pi-02 | Pi 4B 8GB; application/ledger worker | 127999672320 | 127454412800 | 6.18.34+rpt-rpi-v8 | 13.5 |
| forge-pi-03 | Pi 4B 8GB; backup/restore worker | 127999672320 | 127454412800 | 6.12.47+rpt-rpi-v8 | 13.2 |

`docs/cd/owner-inventory.json` is a transcription of the six owner-supplied
screenshots, with SHA-256 references to their original PNGs. All three show
AArch64, 64-bit userspace, ext4 roots, and 2147483648-byte zram. The screenshots
show rounded memory/free-space values; those remain strings and are not converted
into invented exact byte measurements. Their capture timestamps are unavailable.
Hardware model/8GB assignments and microSD medium come from the owner; the
collector independently reads the model and usable memory on the actual host.
Tailscale versions/addresses are inventory only, not reachability or access proof.
Preserve existing enrollment. Pi 03's different kernel/OS baseline is intentional.

## Contracts and admission

`policy/target.json` is a separate target profile. Stage-3 dormant manifests and
historical evidence remain unchanged; their old SSD qualification remains a HOLD.
This microSD lab profile does not assert endurance, power-loss tolerance, HA, or
production suitability. It proposes one future 8Gi ledger on 02 and at least 8Gi
additional free-space reserve, with >=7Gi usable host RAM. These are reviewed
admission bounds, not measured workload capacity. No shared SQLite writer, automatic
failover, or concurrent replacement owner is enabled. 03 is a backup destination;
it cannot assume writer authority merely because 02 is unavailable.

Frozen, strict Pydantic contracts reject unknown fields, numeric coercion,
contradictory probes, topology changes, wrong disks/filesystems, version drift,
insufficient capacity, stale/future/non-UTC captures, duplicate hosts/probes,
source/schema drift, and forged receipts. JSON arrays and ISO timestamps have
explicit transport adapters; primitive strictness remains intact. Every field is
bound to a governed subtype in `target-field-bindings.json`. The source catalog
is pinned before CI dependency installation. Hashes provide integrity, not signatures.

## Operator SOP: collect on each existing node

Prerequisite: an operator-managed checkout of this PR's reviewed commit and its
locked Python environment on each host. Follow Runbook dependency admission;
`--no-sync` below prevents an implicit dependency installation. Use the existing
Tailscale SSH connection and preserve host enrollment. Run from the repo root:

```bash
uv run --no-sync python tools/target_collect.py --output evidence/cd/stage5/forge-pi-01.json
```

Use `forge-pi-02.json` and `forge-pi-03.json` on their corresponding hosts. The
collector reads local host files and fixed version/inventory/service commands.
Each command has a five-second deadline and a 64KiB output cap. It checks boot
identity before/after and caps the capture interval at 120 seconds. It does not
SSH, query Kubernetes objects, install K3s/Flux, modify services, or read tokens.
It writes only the requested evidence file under `evidence/cd/stage5/` using atomic
replacement and fsync. It invalidates an earlier capture before starting; missing
required observations fail closed. Optional K3s/Flux absence is observed, not invented.

Bring the three files to the same reviewed checkout through your existing private
file-transfer method, and assess them within the 900-second freshness window:

```bash
uv run --no-sync python tools/target_gate.py evidence/cd/stage5/forge-pi-01.json evidence/cd/stage5/forge-pi-02.json evidence/cd/stage5/forge-pi-03.json
```

Exit zero means inventory consistency PASS only. The receipt still says target
qualification HOLD and deployment HOLD. Captures are unsigned operator-custodied
observations; fabricating one is outside the trust boundary. Synthetic test captures
are confined to temporary test directories and never emitted as target proof.

## Troubleshooting and continuation

A failed collector replaces prior evidence with FAIL. Check hostname, required
command paths, `/proc/device-tree/model`, `/etc/os-release`, `/proc/meminfo`, the
single mmcblk0/ext4 root, and Tailscale version/IP. Capture again after reboot;
never reuse a prior boot's report. For a rejected assessment, check completeness,
900-second freshness, UTC, policy/source hashes, exact node identities/versions,
capacity, and source/schema bindings. Review deliberate upgrades before rebinding.
Do not edit captures or loosen policy to manufacture admission.

The receipt lists separate HOLDs for qualified artifact/private signing/protected
promotion, K3s cluster readiness, CNI enforcement, runtime readiness, writer fencing,
disk pressure, consistent backup/isolated restore, authenticated private access,
and native resource trials. Active services alone close none of those trials.
Stage-4 VULNERABILITY_NOT_ADMITTED remains independent of host inventory.
The next bootstrap/deployment stage needs evidence-backed closure of these gates.
Do not apply stage-3 manifests or substitute health for readiness.

## Reproduce software verification

```bash
uv run --no-sync python tools/target_owner.py
uv run --no-sync python tools/target_campaign.py
uv run --no-sync python tools/validate.py
```

G-TARGET-BASELINE-021 binds owner evidence/profile/fields/schemas. G-TARGET-NEGATIVE-022
runs the adversarial campaign at >=90% branch-aware coverage. The cumulative
seven-column gate/RRCA ledgers include every prior gate. Software PASS never
supplies absent target trials. No new control/estimator equations are introduced;
this stage binds runtime guard predicates to REQ-CD5-01 through REQ-CD5-05.
Formula Family FF-V6-LOGIC-01 / LOGIC-EQ-04 supplies the conjunction/quantifier
law: every capture must satisfy identity, freshness, baseline, and capacity, and
the host domain must contain exactly the three assigned nodes. A counterexample
rejects inventory admission. Those predicates execute in `check_capture` and
`evaluate`; their regressions are bound above. GA/PGA propagation is not applicable
to this non-kinetic inventory boundary.

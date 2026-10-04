# Signed Raspberry Pi appliance pipeline

The owner requested a complete Docker/k3s deployment image and confirmed the
existing forge-pi-01/02/03 fleet and private-key signing through a GitHub Environment.
This authorizes pipeline implementation, offline image construction and publication
of passing software artifacts. It does not manufacture target acceptance, physical
verification, backup/restore evidence or permission to overwrite a live microSD card.
The existing stage-3 design resources, policies and source seals remain intact.

## Artifacts and flow

`artifact.yml` is reusable container prequalification. It repeats frozen software
gates, builds the native ARM64 OCI archive, exercises the installed software, and
scans that exact archive. PRs receive no release keys or cluster credentials.
Unsigned prequalification is distinct from signed release qualification. Historical
GitHub-native attestation verification remains available in `artifact_gate.py`;
the owner-selected private release lane does not claim a GitHub Sigstore attestation.

`release.yml` runs for `v*` tags or manual dispatch on main. The source must be on
main's history. It calls container prequalification, then rechecks the downloaded
archive against its source, config, package lock, SBOM and scans. It stages an OCI
archive with its real GHCR name, retaining the runtime manifest digest. A disposable
native hosted k3s instance proves import with imagePullPolicy Never, SIL service and
SQLite readiness, retained storage and pod recreation. Its infrastructure image
identity is recorded. This is hosted ARM64 software evidence, not a native Pi boot.

Image assembly expands a newly created disk image file to 12GiB, retains the official
Pi boot firmware/kernel, adds memory cgroup options, and installs k3s, its airgap
images, systemd units, sealed manifests and the application archive. No shared node
identity, registry credential, API token, SSH private key or Tailscale key is baked
in. The mounted OS filesystem receives a complete vulnerability/secret scan too.
Both container and OS reject HIGH, CRITICAL, UNKNOWN or secret findings. There are
no waivers or ignore-unfixed exceptions. A failure prevents publication.

After `appliance-release` Environment admission, the publisher freshly rechecks
the container evidence, signs a release manifest with RSA/SHA-256, and verifies the
signature against a separately pinned public key. The manifest binds the source,
runtime digest, original OCI archive, compressed boot image, evidence and inputs.
Only then is the exact OCI object copied to GHCR with digest preservation. The
registry digest is read back before recording success. No rebuild occurs here.
The signed Actions artifact lasts 90 days. Tagged builds also attach the assets
to a draft GitHub Release for durable review; manual dispatch produces an Actions
artifact. Re-running an existing release refuses to overwrite attached assets.

## One-time signing setup

The owner has configured `appliance-release`; its custom branch policies were
verified to allow only branch `main` and tags `v*`. The integration cannot list
Environment secrets or variables, so their values are verified by the publisher.
Require a designated release reviewer where the GitHub plan supports it. Source
ancestry remains enforced inside the workflow as well.

Generate an encrypted 3072- or 4096-bit RSA private key offline. Keep a recoverable
owner-controlled copy; never commit it. For example:

```sh
umask 077
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -aes-256-cbc -out signing-private.pem
openssl pkey -in signing-private.pem -pubout -out signing-public.pem
sha256sum signing-public.pem
```

Set Environment secrets `HMT_SIGNING_PRIVATE_KEY` (the encrypted PEM) and
`HMT_SIGNING_PASSWORD`. Set Environment variables `HMT_SIGNING_PUBLIC_KEY` (public
PEM, normalized to one trailing newline) and `HMT_SIGNING_PUBLIC_KEY_SHA256` (hash of
those exact PEM bytes). Empty, changed or mismatched keys fail closed. The tool
supports only RSA 3072/4096, not an arbitrary key type. The private key exists only
in a mode-0600 temporary file during signing and is deleted when the signer exits.
There is no public transparency service dependency.

Distribute the public key/fingerprint to operators through an independent trusted
channel. The public key bundled beside an artifact is convenience, not a trust
anchor. Use the independently pinned key to verify `release.sig`, then compare all
file hashes in `release.json`:

```sh
openssl dgst -sha256 -verify trusted-signing-public.pem -signature release.sig release.json
python3 - <<'PY'
import hashlib, json, pathlib
for name, expected in json.load(open('release.json'))['files'].items():
    digest = hashlib.sha256()
    with pathlib.Path(name).open('rb') as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    assert digest.hexdigest() == expected, name
PY
```

## Flashing and boot

The shared image supports the Pi 5 server and Pi 4B workers, with Ethernet DHCP.
It is a fresh OS installation, not an in-place update. Before an operator flashes
anything, back up the ledger with SQLite's online backup API and test recovery;
retain existing Tailscale state outside the image. The image does not overwrite or
re-enroll running devices through CI. Preserve/re-establish approved private access
locally; no Tailscale identity is cloned or enrollment key shipped in the artifact.

After signature/hash verification, flash `hmt-edge-robot.img.xz` with Raspberry Pi
Imager's custom-image option (do not apply conflicting OS customization). For CLI
flashing, decompress to a file and explicitly identify the microSD device before
using your normal disk-writing tool. CI never writes a physical disk.

Mount the flashed FAT boot partition and copy `hmt-node.example.json` to
`hmt-node.json`. Fill all five fields. Use one NEW random cluster token of at least
32 safe characters shared across this fleet (for example `openssl rand -hex 32`),
your real Ed25519 admin public key, and the private reachable server endpoint
`https://<forge-pi-01 LAN address or approved private DNS>:6443`. Configure an address
reservation for 01; it must be reachable by both workers at boot. For 01 use name
`forge-pi-01`, role `server`; for 02/03 use their names and role `agent`. Changing the
name/role pairing, unsafe token, missing SSH key or non-HTTPS endpoint rejects boot
provisioning. Treat the boot file as a credential until it is consumed; FAT deletion
is not secure erasure. Do not share populated boot media or images.

Boot 01 first, then 02 and 03. First boot creates unique machine/SSH identities,
key-only `edgeadmin` SSH access and per-server API/operator secrets, moves config
into root-only storage and consumes the boot file. `edgeadmin` has local sudo
authority. Missing config leaves k3s stopped; add a valid file and reboot. Services
are enabled on every boot. Worker images import the exact application digest
locally before it is used; no registry login or Internet download is needed at boot.

01 is tainted to keep the application off the control plane. The independent SIL
profile assigns one Recreate replica and a Retain local PV to 02. It does not fail
the ledger over to 03 or declare a Kubernetes PVC backup. 03 remains the worker
reserved for operator-managed backup and restore qualification. The local-PV 8GiB
capacity is a scheduling declaration, not a filesystem quota; monitor free space
and keep target disk-pressure/resource qualification open.

Inspect locally over your approved private SSH path:

```sh
sudo systemctl status hmt-firstboot k3s hmt-runtime
sudo k3s kubectl get nodes
sudo k3s kubectl -n hmt-edge-robot-sil get pods,pvc
sudo k3s kubectl -n hmt-edge-robot-sil exec deployment/hmt-edge-robot -- python /etc/hmt/readiness.py
```

There is no public API Service/Ingress. The application binds pod loopback; use
an authenticated local command through `kubectl exec` for inspection. Keep API and
operator tokens private. No startup code clears the stop latch, issues motion or
enables cloud inference. Readiness means the SIL HTTP service and SQLite storage
are usable; it does not mean the mission, sensors or hardware are ready.

## Update and rollback

Pull the runtime through `ghcr.io/collaborativemind/hmt-edge-robot-@sha256:<digest>`
from the signed receipt. GHCR is private; provision a read-only pull credential
locally for online updates, or import the signed offline OCI archive and tag its
runtime manifest reference with `k3s ctr`. Stop the old replica, verify/backup its
ledger and replace the digest. Keep only one writer. Roll back only to a compatible
signed digest with the ledger preserved; do not automatically restore an old ledger
over new durable intents. Reflashing is a separate operator recovery procedure.

## Current validation limits

The original stage-4 receipt recorded 44 HIGH and two UNKNOWN findings; fresh builds
must close them by scanning actual updated inputs. No historical result is changed
to PASS. Native Pi boot, CNI enforcement, disk pressure, single-owner fencing across
host failure, consistent backup/restore and physical acceptance remain explicit
target evidence requirements. The open target-qualification PR is independent.
The pipeline can produce/publish a release only when all actual software scans and
the hosted k3s test pass and the owner provisions the protected private signer.

# Stage 4 — ARM64 artifact qualification

## Authority and partition

The owner instruction to proceed with stage 4 authorizes image construction and
isolated software container qualification in GitHub Actions. It does not authorize
Pi access, cluster mutations, Flux installation/reconciliation, registry publication,
production credentials, physical actuation, or paid inference. The stage-3 contract
and dormant manifests remain design-only. Stage 4 has a separate admission catalog.

The runtime is Python supervisory SIL. The existing physical formula families and
PGA/classical parity remain bound to existing executable code and cumulative tests.
This phase adds no control equation or firmware. MISRA, static allocation, physical
stopping, real-time timing, and native Pi acceptance are separate HOLD gates.

## Campaign SOP

1. Review `policy/artifact_admission.json` and the exact workflow/source changes.
2. Run pre-install admission, frozen installation, and cumulative software gates.
3. Actions selects a fresh native `ubuntu-24.04-arm` hosted runner; no self-hosted
   runner or cluster credential is used. Fork PRs receive ordinary software CI only.
4. Resolve version-selected Python, uv, Trivy, and BuildKit images once into
   immutable digest references. Save `base-lock.json`; use only those digests for
   the build/scans. Tags bootstrap a new candidate, not a repeatability claim.
5. Build one OCI archive from the locked project. The runtime keeps `/opt/venv`
   stable across stages so installed script shebangs remain valid. No editable
   source, test tools, model keys, evidence database, or archive enters the image.
6. Import the exact ARM64 OCI image into the local daemon. Verify loaded config
   digest against the archive; bind BuildKit metadata to the exported OCI root digest. Execute installed composition
   with UID/GID 10001, read-only root, network disabled, all capabilities dropped,
   no-new-privileges, bounded CPU/memory/PIDs, and ephemeral data/scratch mounts.
7. Require verified synthetic motion, resident stop behavior, SQLite replay,
   DuckDB/Polars export parity, no paid calls, and installed-package lock parity.
8. Convert that archive to an OCI directory with digest preservation for Trivy
   0.69.3. Bind the scanner manifest and config identities to the original OCI image.
   Scan OS/Python vulnerabilities and secrets; produce SPDX 2.3.
   HIGH, CRITICAL, UNKNOWN severity, missing coverage, or any secret rejects.
   LOW/MEDIUM findings remain recorded, explicitly admitted only for this artifact
   qualification scope. No ignore-unfixed switch, waiver, or hidden allowlist exists.
9. Historical backend: generate GitHub-signed build provenance for the archive. The receipt gate itself
   invokes `/usr/bin/gh attestation verify` with fixed repository/workflow identity,
   source digest, and deadline. Saved JSON cannot substitute for successful verification.
10. Emit the unsigned prequalification report, archive, inventories, raw scanner
    evidence as an Actions artifact retained 30 days. The owner-selected private
    signing continuation is `release.yml`; see `appliance.md`. PR CI never receives
    the release key. `artifact_gate.py` retains the historical native verifier;
    private releases do not impersonate a GitHub attestation or rewrite old receipts.

## Gates and failure handling

G-ARTIFACT-DESIGN-019 checks the reviewed stage-4 input hashes before builds.
G-ARTIFACT-NEGATIVE-020 reruns bounded adversarial tests with >=90% branch-aware
coverage on artifact admission/verification modules. The installed-container probe
is integration-qualified separately; its evidence is not an x86-to-ARM inference.
G-ARTIFACT-RUNTIME-021 is the Actions job: all software gates plus real artifact,
container, scan, content-closure, and signed provenance checks must succeed.

The campaign writes FAIL before spawning tests/builds. A failed command prevents
qualification; evidence is uploaded with `always()`, and an Actions error alerts
the observer. Signature timeout kills/reaps its process. Receipt persistence errors
fail completion. No stale PASS can survive an incomplete campaign. Re-run the exact
PR revision after repair; never edit scanner evidence to manufacture acceptance.

Download the Actions artifact named `arm64-artifact-<commit>`. Verify the archive
SHA-256 and `qualification.json` source commit, OCI image manifest digest, locked
input hashes, and signed provenance. Requalification runs cryptographic verification
again; plain local JSON is not a deployment trust anchor. The manifest digest and
archive SHA identify different objects and must never be interchanged.

## Continuation

An artifact PASS remains deployment/HW HOLD. Stage 5 qualifies Pi/OS/K3s/Flux,
storage/CNI/private access, mission readiness, single-owner stop/restart, resource
budgets, and restore. Stage 6 requires protected human promotion before SIL deploy.
No stage-3 template is activated here. Stage-4 prequalification alone publishes no GHCR image and assigns no production
tag. The owner-authorized private appliance release lane is documented in
`appliance.md`; it preserves and rechecks the qualified OCI object before signing. Actions retention is finite: the later release lane
must preserve the exact qualified OCI object before promotion or retention expiry.

## Sources

- https://docs.astral.sh/uv/guides/integration/docker/
- https://docs.docker.com/build/exporters/oci-docker/
- https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- https://cli.github.com/manual/gh_attestation_verify
- https://trivy.dev/docs/v0.69/guide/target/container_image/

## Observed signing-service HOLD

Run 37151070400 built and exercised the native ARM64 image and completed the
SPDX/vulnerability/secret collectors. GitHub then refused attestation persistence:
`Feature not available for user-owned private repositories`. This is an observed
service entitlement boundary, not a missing token or a software qualification PASS.
`policy/artifact_signing.json` records the disposition. Repository visibility and
public transparency fallback are not changed by this build.

Unsigned prequalification is a separate observed result. It checks image/source,
loaded/scanned identities, installed package/behavior, SBOM completeness, and the
security threshold before attempting signing. It can PASS while final qualification
remains HOLD. The signed final gate still requires live cryptographic verification;
it cannot adopt the unsigned result. This describes the historical GitHub-native final qualification job. The current
artifact job ends at unsigned prequalification; the separate private release lane
still requires real signature verification before publication. A trusted owner-provisioned private
signer or owner-selected supported repository arrangement is a later closure input.

## Base-image rejection and bounded reselection

Run 37151721865 reported 58 HIGH, five CRITICAL, and one UNKNOWN finding in the
Bookworm candidate. Most blocking entries have no listed fixed version. No exception
is admitted. The newer `python:3.12-slim-trixie` base is a bounded candidate reselection;
its native build, installed composition, and full scans must pass before admission.
The locked project packages and runtime source remain unchanged.

The OCI exporter records `containerimage.digest` for its root OCI descriptor;
it does not promise `containerimage.config.digest`. The gate binds that root digest,
then independently binds the loaded/scanned config digest to the runtime manifest.

Trixie run 37152171398 eliminated CRITICAL findings but reported 45 HIGH and two
UNKNOWN findings. The one listed fix is pinned in the runtime recipe:
`libpcre2-8-0=10.46-1~deb13u3`. Remaining no-fix findings remain blockers, not waivers.

The later [minimal runtime](minimal-runtime.md) replaces this full-base candidate
with an ELF dependency closure assembled into scratch from the same Trixie
builder. It excludes the PCRE-dependent administration tools, preserving genuine
metadata for shipped libraries. Its scan threshold is unchanged; the remaining
LZMA UNKNOWN finding and unpatched host packages continue to block release.
The OS patch is installed through the base's signed Debian repository; its version
and bytes are retained by the image digest and SBOM. Python package pins do not change.

## Current campaign disposition

Run37152497376 built the pinned-patch ARM64 image, passed restricted installed SIL,
and produced SBOM/security evidence. The available PCRE2 fix closed; scanner counts
are44 HIGH2 UNKNOWN0 CRITICAL, with no listed fixes for the remaining blockers.
`evidence/cd/stage4/final_campaign_receipt.json` binds that run, tested merge/head,
artifact ID, raw blocking IDs and package versions. Artifact promotion remains HOLD
for these findings and signing eligibility. Software CI run37152497356 passes.
The final documentation commit preserves this tested runtime/source lineage; it
is not a new qualified image claim. No candidate is admitted to Pi/K3s operation.

Signed ARM64 Raspberry Pi SIL appliance for forge-pi-01/02/03.

Verify release.sig using your independently trusted signing public key, then
verify every SHA-256 in release.json before decompressing or flashing the image.
The release binds the source commit, qualified Docker image digest, boot image,
locked OS/k3s inputs, SBOMs, vulnerability scans and hosted ARM64 k3s smoke evidence.

The image includes Raspberry Pi OS, k3s, its airgap images and the application.
Populate hmt-node.json on the boot partition separately on each device. Boot 01
first, then 02 and 03. The application and retained SQLite ledger run only on 02.

See docs/cd/appliance.md for provisioning, private access and recovery. This is
supervisory SIL software; native Pi acceptance and physical actuation remain HOLD.

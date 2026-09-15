# Alpine reference images

Phase 2 uses version-pinned official Alpine cloud QCOW2 images as the clean VM base.
The filenames and release path live in `images.env`; CI verifies each downloaded image
against the matching upstream SHA-512 sidecar before using it.

The x86_64 lab starts with the BIOS tiny image. The aarch64 lab uses the UEFI tiny
image and will use QEMU's AArch64 UEFI firmware.

Guests are provisioned at first boot through a NoCloud `CIDATA` seed. The seed carries
the repository payload, node identity and lab startup script. A disposable QEMU user
network NIC is used only for package downloads; the DECnet NIC remains on the isolated
raw Ethernet bridge.

Alpine installs the module source under `/usr/src/decnet_iv-0.1.0` and uses AKMS.
AKMS installs the module under its managed module directory and keeps the source plus
kernel hook needed to rebuild it automatically when a new kernel package is installed.

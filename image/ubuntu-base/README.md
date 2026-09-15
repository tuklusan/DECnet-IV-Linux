# Ubuntu Base image

Phase 2 uses Ubuntu Base 26.04.1 LTS as the smallest official non-cloud Ubuntu root filesystem suitable for constructing a custom image. Both amd64 and arm64 release tarballs are 33 MiB and are pinned by SHA-256 in `images.env`.

The lab deliberately avoids an installer, cloud-init, NoCloud media, firmware boot dependencies and a second management NIC. CI expands the pinned rootfs into an ext4 disk, installs the virtual kernel plus the DECnet module/tools, copies out that exact kernel/initrd, and boots QEMU with `-kernel`/`-initrd` directly.

This is a Phase 2 test-image path, not the final release boot scheme. A self-booting release image can add a bootloader after the protocol stack is useful; the lab does not need one to prove native Ethernet behavior.

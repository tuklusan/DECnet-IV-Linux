<!-- ============================================================================ -->
<!-- Copyright (c) 2026 Supratim Sanyal of SANYALnet Labs. -->
<!-- Proprietary rights reserved except as expressly licensed herein. -->
<!-- -->
<!-- DO NOT PANIC PORTFOLIO VISUALIZER -->
<!-- This file is governed by the SANYALnet Labs Non-Commercial License in the -->
<!-- root LICENSE file. Non-Commercial use is permitted; Commercial Use and use -->
<!-- for AI/ML model training are prohibited unless separately authorized. -->
<!-- -->
<!-- Attribution is required: "Based on original work by Supratim Sanyal of -->
<!-- SANYALnet Labs." See LICENSE for full terms, warranty disclaimer, termination, -->
<!-- patent, trademark, and governing-law provisions. -->
<!-- ============================================================================ -->

# Ubuntu Base image

Phase 2 uses Ubuntu Base 26.04.1 LTS as the smallest official non-cloud Ubuntu root filesystem suitable for constructing a custom image. Both amd64 and arm64 release tarballs are 33 MiB and are pinned by SHA-256 in `images.env`.

The lab deliberately avoids an installer, cloud-init, NoCloud media, firmware boot dependencies and a second management NIC. CI expands the pinned rootfs into an ext4 disk, installs the virtual kernel plus the DECnet module/tools, copies out that exact kernel/initrd, and boots QEMU with `-kernel`/`-initrd` directly.

This is a Phase 2 test-image path, not the final release boot scheme. A self-booting release image can add a bootloader after the protocol stack is useful; the lab does not need one to prove native Ethernet behavior.

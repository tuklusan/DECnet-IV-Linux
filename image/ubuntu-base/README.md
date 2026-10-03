<!-- ============================================================================ -->
<!-- Copyright (c) 2026 Supratim Sanyal of SANYALnet Labs. -->
<!-- Proprietary rights reserved except as expressly licensed herein. -->
<!-- -->
<!-- DECnet-IV-Linux -->
<!-- This file is governed by the SANYALnet Labs Non-Commercial License in the -->
<!-- root LICENSE file. Non-Commercial use is permitted; Commercial Use and use -->
<!-- for AI/ML model training are prohibited unless separately authorized. -->
<!-- -->
<!-- Attribution is required: "Based on original work by Supratim Sanyal of -->
<!-- SANYALnet Labs." See LICENSE for full terms, warranty disclaimer, termination, -->
<!-- patent, trademark, and governing-law provisions. -->
<!-- ============================================================================ -->

# Lab-only Ubuntu Base images

Ubuntu Base 26.04.1 is pinned for amd64 and arm64 by SHA-256 in `images.env`.

`build-foundation.sh` builds a source-independent protocol-lab foundation containing Ubuntu, the pinned guest kernel/initrd, compiler/headers and independent-reference runtime dependencies. The foundation contains no DECnet-IV-Linux source, module, tools, smoke services or candidate SHA. The reference runtime includes `git` because the pinned PyDECnet implementation queries its Git revision while starting. All resulting filesystem/QCOW2 data is disposable lab infrastructure; none is a production deliverable.

Acceptance workflows cache one verified foundation per architecture/foundation fingerprint. Each candidate then uses `tests/lab/prepare-candidate-image.sh` to inject and build the exact checked-out source into a disposable derived image. This avoids reinstalling packages for ordinary source commits while retaining exact-SHA protocol testing.

The lab path avoids installer dependencies by copying out the guest kernel/initrd and booting QEMU directly with `-kernel`/`-initrd`. On arm64, `normalize-arm64-kernel.sh` converts a raw Image or gzip/Zstd EFI-zboot payload into a verified raw Linux `Image` and rejects unknown formats; there is no opaque direct-boot fallback. The foundation binds the exact normalizer SHA-256 into its own bytes so a normalizer change invalidates the cache fingerprint. A host `zstd` command is required when the pinned arm64 kernel uses Zstd EFI-zboot compression.

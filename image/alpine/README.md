# Alpine reference images

Phase 2 uses version-pinned official Alpine cloud QCOW2 images as the clean VM base.
The filenames and release path live in `images.env`; CI verifies each downloaded image
against the matching upstream SHA-512 sidecar before using it.

The x86_64 lab starts with the BIOS tiny image. The aarch64 lab uses the UEFI tiny image
and will use QEMU's AArch64 UEFI firmware. Both guests install the current `linux-virt`
package from the pinned Alpine 3.24 repository and build `decnet_iv.ko` against the
matching `linux-virt-dev` headers inside the image.

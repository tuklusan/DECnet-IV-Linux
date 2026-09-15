# Cross-distro portability lab

This lab is deliberately later than the Alpine Phase 2 acceptance gate. It proves
that the out-of-tree module lifecycle is portable without diluting the native
DECnet protocol work.

## Image selection

For every distro, pin the smallest official, maintained VM/cloud image that still
supports the distro's normal kernel update path. Pin its checksum and exact release.

Initial families:

- Alpine reference image, using AKMS;
- Debian stable, using DKMS;
- CentOS Stream, using DKMS;
- one maintained RHEL-compatible downstream image, using DKMS, selected by the same
  smallest-official-image rule.

Use x86_64 first, then aarch64 where the distro publishes a supported image.

## Lifecycle gate

Each guest must:

1. install the module source through its native AKMS or DKMS path;
2. load `decnet_iv.ko`;
3. install a newer supported kernel package through the distro package manager;
4. reboot into that kernel without a manual module build;
5. prove the module was automatically rebuilt for the new kernel;
6. join the isolated DECnet Ethernet and pass the same protocol tests as the Alpine
   reference guest.

A disposable management NIC may be used for package repositories. DECnet traffic
must never use that NIC.

## Mixed-distro stress

After basic portability is green, mix distro families on the same raw Ethernet
topology and increase node count, churn, packet load and kernel-update cycles.
These are native DECnet tests. DECnet-over-IP tunneling is outside this lab and is
deferred until the native stack has been stressed through the higher protocol layers.

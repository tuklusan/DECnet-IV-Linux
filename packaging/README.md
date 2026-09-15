# Out-of-tree module lifecycle

The DECnet Phase IV module must survive kernel package upgrades without a manual rebuild.

- Alpine uses AKMS. Install the project sources under `/usr/src/decnet_iv-0.1.0`,
  including `packaging/akms/AKMBUILD` as `AKMBUILD`. AKMS builds the module and its
  kernel hook rebuilds it for newly installed kernels.
- Debian and RHEL-family systems use DKMS. Install the same source tree under
  `/usr/src/decnet-iv-0.1.0` with `packaging/dkms/dkms.conf` copied to the source
  root, then register the module with DKMS.

Phase 2 proves the AKMS path in the Alpine VM lab. The native build workflow also
smoke-tests the DKMS metadata. Later portability labs boot the smallest maintained
official Debian and RHEL-family VM images and exercise real kernel package upgrades.

# Architecture

## Kernel

The target is an out-of-tree kernel module providing native DECnet Phase IV networking.

Initial areas of work:

1. Ethernet data-link integration
2. DECnet addressing and node identity
3. Phase IV routing packet handling
4. NSP transport
5. Session-control interface
6. Socket/API surface for userspace
7. Network management hooks

The module should remain separable from the Linux kernel tree so the distribution can track maintained upstream kernels without carrying a permanent kernel fork.

## Userspace

Userspace will be built against the new kernel ABI. Initial tools:

- sethost
- ncp
- phone
- dncopy
- node/query utilities

## Distribution image

The reference VM image will use a small, maintained Linux base with only the packages needed for boot, networking, the minimal GUI, DECnet, diagnostics, and test access.

## Testing

CI milestones:

- 2-node end-to-end connectivity
- 4-node routing tests
- 8-node mixed topology
- 16-node stress and routing convergence tests

Each node runs in an isolated VM or equivalent sandbox with virtual Ethernet links.

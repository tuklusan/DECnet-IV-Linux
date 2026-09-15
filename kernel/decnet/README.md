# DECnet Phase IV kernel module

This directory contains the fresh out-of-tree DECnet Phase IV kernel implementation.

The first milestone intentionally stays small:

- load/unload as `decnet_iv.ko`;
- default identity 31.70 / DN70, configurable through module parameters and the versioned control UAPI;
- receive registration for DEC DNA Routing EtherType `0x6003`;
- receive frame/byte counters;
- `/dev/decnet_iv` as a bootstrap diagnostic/control endpoint.

The character device is not the final application API. NSP will introduce the DECnet socket interface later. Compatibility behavior belongs primarily in userspace rather than freezing old implementation details into the kernel ABI.

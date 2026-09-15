# VM test lab

The acceptance lab uses separate VMs so each node has its own kernel, module state,
timers and interface state. The default address allocation comes from
`test-addresses.env` and starts at area 31, nodes 70 through 79.

## Phase 2 smoke test

The first lab boots DN70 (31.70) and DN71 (31.71) on one Linux bridge. Each guest:

1. loads `decnet_iv.ko` built against its installed Alpine `linux-virt` kernel;
2. configures its node identity with `dnctl`;
3. transmits raw DECnet Routing Layer EtherType `0x6003` frames to its peer;
4. prints receive counters to the serial console and powers off.

The host captures the bridge to `lan.pcap`. The gate succeeds only when both guests
report received routing frames and the capture contains DECnet EtherType traffic.
This proves VM/image/module/Ethernet plumbing only; it does not yet claim Phase IV
hello, adjacency, routing or NSP behavior.

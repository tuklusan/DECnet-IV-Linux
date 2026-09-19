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

# Pinned Implementation References

These are implementation references, not substitutes for the Digital functional specifications.

## Route20

- Repository: https://github.com/tuklusan/Route20
- Exact project pin: `564df0be75831aaf00590ce10152655460dd43dc`
- Upstream documentation at that pin states that Route20 implements version 2.0 of the DECnet routing specification.
- Best use here: Ethernet routing initialization, L1/L2 routing, adjacency, forwarding, native VDE Ethernet and an independent routing peer.
- Important limit: Route20 is narrower than a complete DECnet stack and its own documentation records historical test limitations. A Route20 failure is evidence to investigate, not permission to change candidate protocol behavior blindly.
- License at the pin: Microsoft Public License (Ms-PL).

## PyDECnet

- Repository: https://github.com/tuklusan/pydecnet
- Exact live/reference pin: `60778de8242793228ffb5ba6c9db23ae92620cb1`
- Exact tests pin: `9a844987bf3a1450632dee8d37e60a23a453bad3`
- Its README states that it is written to conform to published DNA Phase II, III and IV specifications and covers Ethernet, routing endnode/L1/L2, NSP, Session Control, NICE/NML, MOP, DAP/FAL and the MULTINET transport used by this project's Internet lab gateway.
- Best use here: independent whole-stack cross-check, edge cases and interoperability.
- Its `doc/protocols/` directory is explicitly different: those notes describe protocols seen in products but not officially specified and were reverse-engineered. Treat those notes as empirical evidence, not normative DNA.
- License at the live pin: BSD 3-Clause.

## LinuxDECnet

- Repository: https://github.com/tuklusan/LinuxDECnet
- Exact project pin: `ff39eef045d1e4b7b72a3d40111e89c07a473398`
- Best use here: Linux DECnet socket/API expectations; `dnlogin`, `dncopy`, `dndir`, `dndel`, `dnping`, `dnsubmit`, `dnprint`, PHONE, FAL, NML, libraries and daemon behavior.
- Its current README says the maintained external module is Ethernet-endnode only and that the older routing code was never supported. Therefore it is not the routing authority for this project.
- Its long revision history is valuable as a regression-test mine: flow control, retransmitted connects, ACK handling, segmentation and disconnect bugs should become negative/interoperability tests where applicable.
- Programs and libraries carry their own GPL/LGPL terms; check the exact component before reusing code.

## SIMH

- Repository: https://github.com/tuklusan/simh
- Exact project pin: `5b73b1032b52d19bf80752ea4d9cbbdc92e7b5e0`
- Best use here: hardware/network emulation and hosting genuine DEC operating systems as independent peers.
- The Ethernet documentation covers DEQNA/DELQA and DEUNA/DELUA emulation plus pcap/TAP attachment behavior.
- SIMH is not a DECnet protocol specification. Its value is that it lets a real DEC OS answer the useful question: "what does the peer actually do with these bytes?"
- Preserve the SIMH version/pin in evidence because its own redistribution guidance emphasizes retaining exact version identity.

## Conflict handling

When two independent implementations agree with each other but disagree with an unambiguous Digital specification, do not vote 2-to-1. Investigate the discrepancy. If shipping DEC systems require the non-spec behavior, document it as an interoperability compatibility rule with a focused test.

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

# External reference baselines

The project prefers the maintained `tuklusan` forks for automated gates and protocol comparison. Upstream repositories are comparison/provenance sources only.

## Route20

`ROUTE20_REF` pins the Route20 fork revision used for build and live interoperability. The current pin adds a native libvdeplug Ethernet line while retaining the previously accepted routing behavior. VDE transport proof is run separately from protocol acceptance before the VDE path is used for scale.

## PyDECnet

`PYDECNET_REF` pins the current fork revision used for documentation, packet behavior and live interoperability. The current live pin adds native VDE Ethernet support; its existing MULTINET TCP implementation is the authoritative source for the project's user-space MULTINET gateway behavior.

The current reference contains a pre-existing self-test contradiction in `Macaddr("1.24")`: the test requires DECnet `area.node` parsing while the code takes the hexadecimal path first. `PYDECNET_TEST_REF` therefore pins the immediately preceding internally consistent fork revision and its complete unit suite is run unmodified. No test is skipped or rewritten. Move the test pin forward when the contradiction is fixed.

## LinuxDECnet

`LINUXDECNET_REF` pins the preferred historical Linux DECnet fork for userspace behavior and compatibility comparison only. It is not the implementation base for the new kernel stack.

## SIMH

`SIMH_REF` pins the preferred simulator fork for later interoperability with real DEC operating-system images and mixed-system testing.

The exact revisions live in `refs.env`. Any direct source reuse remains subject to the source repository's license and project licensing policy.

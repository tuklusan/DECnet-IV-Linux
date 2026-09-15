# External reference baselines

These gates answer different questions and keep the answers reproducible. The project-owned forks are the primary pinned sources; upstream repositories remain comparison points.

## Route20

The `tuklusan/Route20` fork currently provides a build and live-interoperability reference. Its pinned source must compile in CI. Protocol interoperability tests are added as each relevant DECnet layer becomes functional.

## PyDECnet

`PYDECNET_REF` pins the current `tuklusan/pydecnet` reference used for documentation, packet behavior and live interoperability.

The current reference contains a pre-existing self-test regression in `Macaddr("1.24")`: its test requires DECnet `area.node` parsing, while a July 2024 change attempts to parse any separator-free string as hexadecimal first. The failing test is unrelated to this repository and fails before our implementation participates.

`PYDECNET_TEST_REF` therefore pins the immediately preceding revision. Its complete unit suite is run unmodified as the hard baseline. We do not skip or rewrite failing tests. When the reference resolves the self-test contradiction, move the test pin forward and remove this exception.

The revisions live in `refs.env` so changes to either reference baseline are explicit and reviewable.

# External reference baselines

These gates answer different questions and keep the answers reproducible.

## Route20

Route20 currently provides a build and live-interoperability reference. Its pinned source must compile in CI. Protocol interoperability tests are added as each relevant DECnet layer becomes functional.

## PyDECnet

`PYDECNET_REF` pins the current reference used for documentation, packet behavior and live interoperability.

The current reference contains a pre-existing upstream self-test regression in `Macaddr("1.24")`: its test requires DECnet `area.node` parsing, while a July 2024 change attempts to parse any separator-free string as hexadecimal first. The failing test is unrelated to this repository and fails before our implementation participates.

`PYDECNET_TEST_REF` therefore pins the immediately preceding upstream revision. Its complete upstream unit suite is run unmodified as the hard baseline. We do not skip or rewrite failing tests. When upstream resolves the current self-test contradiction, move the test pin forward and remove this exception.

The revisions live in `refs.env` so changes to either reference baseline are explicit and reviewable.

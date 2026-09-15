# External reference baselines

These gates answer two different questions.

Route20 currently provides a build and live-interoperability reference. Its pinned source must compile in CI; protocol interoperability tests are added as each relevant DECnet layer becomes functional.

PyDECnet provides both executable unit tests and a live peer. Its pinned upstream test suite runs unchanged in CI. Later protocol milestones add packet-vector and live Ethernet/DDCMP checks against the same pinned revision.

The revisions live in `refs.env` so changes to the reference baseline are explicit and reviewable.

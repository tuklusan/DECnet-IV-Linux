# External reference baselines

The project prefers the maintained `tuklusan` forks for automated gates. Upstream repositories are comparison/provenance sources only.

## Route20

`ROUTE20_REF` pins the Route20 fork revision used for the build and later live-interoperability reference. Protocol interoperability tests are added as each relevant DECnet layer becomes functional.

## PyDECnet

`PYDECNET_REF` pins the current fork revision used for documentation, packet behavior and live interoperability.

The current reference contains a pre-existing self-test contradiction in `Macaddr("1.24")`: the test requires DECnet `area.node` parsing while the code takes the hexadecimal path first. `PYDECNET_TEST_REF` therefore pins the immediately preceding internally consistent fork revision and its complete unit suite is run unmodified. No test is skipped or rewritten. Move the test pin forward when the contradiction is fixed.

The exact revisions live in `refs.env`. Any direct source reuse remains subject to the source repository's license and project licensing policy.

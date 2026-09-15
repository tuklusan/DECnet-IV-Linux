# External reference baselines

Reference gates use the user's forks as the normal sources and pin exact commits in `refs.env`. Upstream repositories are comparison sources only.

## Route20

Preferred source: `https://github.com/tuklusan/Route20`

Comparison upstream: `https://github.com/rjarratt/Route20`

Route20 provides a build and live-interoperability reference. Its pinned source must compile in CI; protocol interoperability gates are added as relevant DECnet layers become functional.

## PyDECnet

Preferred source: `https://github.com/tuklusan/pydecnet`

Comparison upstream: `https://github.com/pkoning2/pydecnet`

`PYDECNET_REF` pins the current reference for documentation, packet vectors/behavior, and live interoperability.

The current reference has a pre-existing self-test contradiction in `Macaddr("1.24")`: the implementation takes the hexadecimal path before DECnet `area.node`, while the test still requires `area.node`.

`PYDECNET_TEST_REF` therefore pins the last internally consistent revision immediately before that contradiction. Its complete usable unit suite is run unmodified as the hard baseline. Tests are not skipped or rewritten. Move the hard pin forward when the contradiction is resolved.

## Other preferred references

`tuklusan/LinuxDECnet` is the compatibility inventory for historical userspace, socket/application behavior, daemons, libraries, and administration tools. `tuklusan/simh` is the preferred simulator fork for later real DEC operating-system peers.

Pin exact SHAs before either becomes an automated gate. Respect each repository's license; upstreams remain comparison-only.

`refs.env` is the single source for repository URLs and revisions consumed by reference CI so source ownership and pins change together and remain reviewable.

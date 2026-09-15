#!/usr/bin/env python3
"""Render the copy/paste handover from the canonical project state."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

STATE = Path("docs/PROJECT_STATE.md")
HANDOVER = Path("docs/HANDOVER.md")


def section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    pos = text.find(marker)
    if pos < 0:
        raise ValueError(f"missing '{marker}'")
    body = text[pos + len(marker):]
    if body.startswith("\n"):
        body = body[1:]
    end = body.find("\n## ")
    if end >= 0:
        body = body[:end]
    body = body.strip()
    if not body:
        raise ValueError(f"empty '{marker}'")
    return body


def render_handover(state_text: str) -> str:
    goal = section(state_text, "Goal")
    resume = section(state_text, "Resume point")
    next_action = section(state_text, "Next action")

    return f"""# Next Chat Handover

This file is generated from `docs/PROJECT_STATE.md` by `tools/render_handover.py`.
Do not edit it by hand.

## Copy/paste into the next chat

```text
Continue the DECnet-IV-Linux project: https://github.com/tuklusan/DECnet-IV-Linux

Use repository state as canonical project memory. First read `docs/PROJECT_INSTRUCTIONS.md`,
`docs/PROJECT_STATE.md`, `docs/HANDOVER.md`, and `docs/ROADMAP.md`, then inspect the active
working branch and its CI status before changing code.

Goal:
{goal}

Resume point:
{resume}

Next action:
{next_action}

Continuity rules:
- Every substantive commit must update `docs/PROJECT_STATE.md` and generated `docs/HANDOVER.md` together.
- Work on a feature/working branch and promote only the exact commit whose required gates are green.
- Prefer `tuklusan/Route20`, `tuklusan/pydecnet`, `tuklusan/LinuxDECnet`, and `tuklusan/simh`; pin exact SHAs when used by a gate, and use upstreams only for comparison.
- Respect source licenses and implement independently when reuse is unclear or incompatible.
- Keep the fresh out-of-tree kernel design; do not fall back to the removed legacy Linux DECnet stack.
- Keep x86_64/aarch64, independent VMs, routed/mixed-media networks, independent/real DEC peers, fault injection, and stress as acceptance requirements.
- Apply the SoP rule to every updated deliverable: read the complete latest disk copy untruncated, fix defects/gaps, reset after any fix, require three consecutive clean full passes, and reset after any later change.

Proceed directly from the Next action. Do not reconstruct project state from prior chat history.
```
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--stdout", action="store_true")
    args = parser.parse_args()

    try:
        expected = render_handover(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"handover: {exc}", file=sys.stderr)
        return 1

    if args.stdout:
        sys.stdout.write(expected)
        return 0

    if args.check:
        try:
            actual = HANDOVER.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"handover: {exc}", file=sys.stderr)
            return 1
        if actual != expected:
            print(
                "handover: docs/HANDOVER.md is stale; run "
                "python3 tools/render_handover.py",
                file=sys.stderr,
            )
            return 1
        print("handover: generated handover is current")
        return 0

    HANDOVER.write_text(expected, encoding="utf-8")
    print(f"handover: wrote {HANDOVER}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

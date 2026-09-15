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

Use the repository as canonical project memory. First read `docs/PROJECT_STATE.md`,
`docs/ROADMAP.md`, and `docs/HANDOVER.md`, then inspect the active working branch
and its CI status before changing code.

Goal:
{goal}

Resume point:
{resume}

Next action:
{next_action}

Continuity rules:
- Every substantive commit must update `docs/PROJECT_STATE.md` in that same commit.
- Regenerate `docs/HANDOVER.md` with `python3 tools/render_handover.py`; CI must reject drift.
- Work on a working branch and promote only an exact commit whose required gates are green.
- Keep the fresh out-of-tree DECnet Phase IV kernel implementation; do not fall back to the removed legacy Linux DECnet stack.
- Keep Route20 and PyDECnet as independent conformance/interoperability references.
- Keep x86_64 and aarch64 as required targets and the configurable default lab range at 31.70-31.79.

Proceed directly from the Next action. Do not ask me to reconstruct prior chat history.
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

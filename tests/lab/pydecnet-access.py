#!/usr/bin/env python3
# ============================================================================
# Copyright (c) 2026 Supratim Sanyal of SANYALnet Labs.
# Proprietary rights reserved except as expressly licensed herein.
#
# DECnet-IV-Linux
# This file is governed by the SANYALnet Labs Non-Commercial License in the
# root LICENSE file. Non-Commercial use is permitted; Commercial Use and use
# for AI/ML model training are prohibited unless separately authorized.
#
# Attribution is required: "Based on original work by Supratim Sanyal of
# SANYALnet Labs." See LICENSE for full terms, warranty disclaimer, termination,
# patent, trademark, and governing-law provisions.
# ============================================================================

"""Verify Session Control access-data accept/reject behavior via PyDECnet."""

from __future__ import annotations

import sys

from decnet.connectors import SimpleApiConnector


def main() -> int:
    if len(sys.argv) != 9:
        raise SystemExit(
            f"usage: {sys.argv[0]} API-SOCKET AREA.NODE PYDECNET-SYSTEM "
            "OBJECT USER PASSWORD ACCOUNT EXPECT"
        )

    api_socket, destination, system, selector, user, password, account, expect = (
        sys.argv[1:]
    )
    remuser = int(selector) if selector.isdigit() else selector
    connector = SimpleApiConnector(api_socket)
    try:
        connection, response = connector.connect(
            system=system,
            dest=destination,
            remuser=remuser,
            localuser="PYACCESS",
            username=user,
            password=password,
            account=account,
        )
        if expect == "accept":
            if connection is None or response.type != "accept":
                raise RuntimeError(
                    f"access connect rejected: {getattr(response, 'reason', 'unknown')}"
                )
            if bytes(response) != b"\xff\xff":
                raise RuntimeError(f"bad access accept data: {bytes(response)!r}")
            connection.disconnect()
        elif expect.startswith("reject="):
            reason = int(expect.split("=", 1)[1], 10)
            if connection is not None or response.type != "reject":
                raise RuntimeError("access connect unexpectedly accepted")
            if getattr(response, "reason", None) != reason:
                raise RuntimeError(
                    f"bad access reject reason: {getattr(response, 'reason', None)!r}"
                )
        else:
            raise RuntimeError(f"bad expectation {expect!r}")
    finally:
        connector.close()

    print(
        f"pydecnet-access: pass peer={destination} object={selector} expect={expect}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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

"""Fail-closed parser/configuration selftests for dnmultinet."""

import os

import dnmultinet


BASE = [
    "--node", "31.80",
    "--name", "MNET80",
    "--vde", "vde:///tmp/dn31.ctl",
]


def expect_failure(argv, marker, env=None):
    saved = {}
    if env:
        for name, value in env.items():
            saved[name] = os.environ.get(name)
            os.environ[name] = value
    try:
        try:
            args = dnmultinet.parser().parse_args(argv)
            dnmultinet.load_runtime_peer(args)
            dnmultinet.validate(args)
        except SystemExit as exc:
            if marker not in str(exc):
                raise AssertionError(f"wrong failure for {argv!r}: {exc}") from exc
        else:
            raise AssertionError(f"unsafe dnmultinet input accepted: {argv!r}")
    finally:
        if env:
            for name, value in saved.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value


def main():
    expect_failure(
        BASE[:4] + ["--vde", "vde:///tmp/x\nlogging console --events 9.9",
                    "--mode", "listen", "--local-port", "700"],
        "VDE URL has invalid syntax",
    )
    expect_failure(
        BASE + ["--mode", "listen", "--local-address",
                "0.0.0.0\nlogging console --events 9.9", "--local-port", "700"],
        "local address has invalid syntax",
    )
    expect_failure(
        BASE + ["--mode", "connect", "--peer-host", "::1", "--peer-port", "700"],
        "peer host must be an IPv4 address or hostname",
    )
    expect_failure(
        BASE + ["--mode", "listen", "--local-address", "::", "--local-port", "700"],
        "local address must be an IPv4 address",
    )
    expect_failure(
        BASE + ["--mode", "listen", "--local-port", "700",
                "--api-socket", "/tmp/dniv\napi bad"],
        "api socket path has invalid syntax",
    )
    expect_failure(
        BASE + ["--mode", "connect", "--runtime-peer-env",
                "--config-out", "/tmp/dniv-runtime-peer.conf"],
        "refuses --config-out",
        {"MULTINET_REMOTE_HOST": "127.0.0.1", "MULTINET_REMOTE_PORT": "700"},
    )
    expect_failure(
        BASE + ["--mode", "connect", "--runtime-peer-env"],
        "MULTINET_REMOTE_HOST has invalid syntax",
        {"MULTINET_REMOTE_HOST": "bad\nhost", "MULTINET_REMOTE_PORT": "700"},
    )

    args = dnmultinet.parser().parse_args(
        BASE + ["--mode", "connect", "--peer-host", "example.invalid",
                "--peer-port", "700", "--local-address", "127.0.0.1"]
    )
    dnmultinet.validate(args)
    config = dnmultinet.build_config(args)
    if config.count("\n") != 5 or "example.invalid" not in config:
        raise AssertionError("valid dnmultinet config changed unexpectedly")
    print("dnmultinet config selftests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

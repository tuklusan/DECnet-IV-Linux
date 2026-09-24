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

"""Launch a PyDECnet VDE<->MULTINET router for DECnet-IV-Linux labs.

The transport semantics and configuration deliberately follow the pinned
PyDECnet MULTINET implementation.  TCP connect/listen are exposed; unreliable
MULTINET/UDP is intentionally not offered here.
"""

import argparse
import os
import pathlib
import re
import sys

NODE_RE = re.compile(r"^([0-9]{1,2})\.([0-9]{1,4})$")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,5}$")
HOST_RE = re.compile(r"^[A-Za-z0-9_.:%\\-\\[\\]]+$")


def node_address(value):
    match = NODE_RE.match(value)
    if not match:
        raise argparse.ArgumentTypeError("node must be AREA.NODE")
    area, node = (int(x) for x in match.groups())
    if not 1 <= area <= 63 or not 1 <= node <= 1023:
        raise argparse.ArgumentTypeError("node must be in area 1..63, node 1..1023")
    return f"{area}.{node}"


def node_name(value):
    if not NAME_RE.match(value):
        raise argparse.ArgumentTypeError("name must be 1..6 alphanumeric characters, starting with a letter")
    return value.upper()


def parser():
    p = argparse.ArgumentParser(
        description="Run a user-space VDE Ethernet to MULTINET TCP DECnet router"
    )
    p.add_argument("--node", required=True, type=node_address)
    p.add_argument("--name", required=True, type=node_name)
    p.add_argument("--type", choices=("l1router", "l2router"), default="l2router")
    p.add_argument("--vde", required=True, help="libvdeplug URL, e.g. vde:///tmp/dn31.ctl")
    p.add_argument("--mode", choices=("connect", "listen"), required=True)
    p.add_argument("--peer-host", help="remote MULTINET peer address/name")
    p.add_argument("--peer-port", type=int, help="remote MULTINET TCP port")
    p.add_argument(
        "--runtime-peer-env",
        action="store_true",
        help="read MULTINET_REMOTE_HOST/PORT from the environment",
    )
    p.add_argument("--local-address", default="0.0.0.0")
    p.add_argument("--local-port", type=int, help="local MULTINET TCP listen/source port")
    p.add_argument("--cost", type=int, default=4)
    p.add_argument("--lan-cost", type=int, default=3)
    p.add_argument("--priority", type=int, default=64)
    p.add_argument("--pydecnet-dir", help="directory containing the decnet package")
    p.add_argument("--config-out", help="write generated PyDECnet config here")
    p.add_argument("--api-socket", help="optional PyDECnet Unix API socket")
    p.add_argument("--dry-run", action="store_true", help="print config and exit")
    p.add_argument("--validate-only", action="store_true", help="validate configuration and exit")
    return p


def load_runtime_peer(args):
    if not args.runtime_peer_env:
        return
    if args.mode != "connect":
        raise SystemExit("--runtime-peer-env is valid only in connect mode")
    if args.peer_host or args.peer_port is not None:
        raise SystemExit("--runtime-peer-env cannot be combined with explicit peer options")

    missing = [
        name
        for name in ("MULTINET_REMOTE_HOST", "MULTINET_REMOTE_PORT")
        if not os.environ.get(name)
    ]
    if missing:
        raise SystemExit("runtime peer environment missing: " + ", ".join(missing))

    host = os.environ["MULTINET_REMOTE_HOST"]
    port_text = os.environ["MULTINET_REMOTE_PORT"]
    if not HOST_RE.fullmatch(host):
        raise SystemExit("MULTINET_REMOTE_HOST has invalid syntax")
    if not port_text.isdigit():
        raise SystemExit("MULTINET_REMOTE_PORT must be numeric")
    args.peer_host = host
    args.peer_port = int(port_text, 10)


def validate(args):
    for name, value in (("cost", args.cost), ("lan-cost", args.lan_cost)):
        if not 1 <= value <= 25:
            raise SystemExit(f"{name} must be 1..25")
    if not 0 <= args.priority <= 127:
        raise SystemExit("priority must be 0..127")
    for name in ("peer_port", "local_port"):
        value = getattr(args, name)
        if value is not None and not 1 <= value <= 65535:
            raise SystemExit(name.replace("_", "-") + " must be 1..65535")
    if args.mode == "connect":
        if not args.peer_host or args.peer_port is None:
            raise SystemExit("connect mode requires --peer-host and --peer-port")
        if not HOST_RE.fullmatch(args.peer_host):
            raise SystemExit("peer host has invalid syntax")
    else:
        if args.local_port is None:
            raise SystemExit("listen mode requires --local-port")
    if args.api_socket and (any(ch.isspace() for ch in args.api_socket) or "\n" in args.api_socket):
        raise SystemExit("api socket path must not contain whitespace")
    if args.runtime_peer_env and args.dry_run:
        raise SystemExit("dry-run refuses runtime peer environment")
    if args.dry_run and args.validate_only:
        raise SystemExit("--dry-run and --validate-only are mutually exclusive")


def build_config(args):
    lines = [
        f"routing {args.node} --type {args.type}",
        f"node {args.node} {args.name}",
        (
            f"circuit LAN-0 Ethernet {args.vde} --mode vde "
            f"--cost {args.lan_cost} --t3 2 --priority {args.priority}"
        ),
    ]
    if args.mode == "connect":
        circuit = (
            "circuit WAN-0 Multinet --mode connect "
            f"--remote-address {args.peer_host} --remote-port {args.peer_port} "
            f"--cost {args.cost} --t3 10"
        )
        if args.local_port is not None:
            circuit += f" --local-address {args.local_address} --local-port {args.local_port}"
    else:
        circuit = (
            "circuit WAN-0 Multinet --mode listen "
            f"--local-address {args.local_address} --local-port {args.local_port} "
            f"--cost {args.cost} --t3 10"
        )
        if args.peer_host:
            circuit += f" --remote-address {args.peer_host}"
        if args.peer_port is not None:
            circuit += f" --remote-port {args.peer_port}"
    lines.append(circuit)
    if args.api_socket:
        lines.append(f"api {args.api_socket} --mode 600")
    lines.append("logging console --events 4.8,4.10,4.15,4.16")
    return "\n".join(lines) + "\n"


def main():
    args = parser().parse_args()
    load_runtime_peer(args)
    validate(args)
    if args.validate_only:
        print("dnmultinet: configuration valid")
        return 0
    config = build_config(args)
    if args.dry_run:
        sys.stdout.write(config)
        return 0

    config_fd = None
    if args.config_out:
        path = pathlib.Path(args.config_out)
        path.write_text(config, encoding="utf-8")
        config_name = str(path)
    else:
        config_fd = os.memfd_create("dnmultinet.conf", flags=0)
        os.write(config_fd, config.encode("utf-8"))
        os.lseek(config_fd, 0, os.SEEK_SET)
        os.set_inheritable(config_fd, True)
        config_name = f"/proc/self/fd/{config_fd}"

    env = os.environ.copy()
    if args.pydecnet_dir:
        source = str(pathlib.Path(args.pydecnet_dir).resolve())
        old = env.get("PYTHONPATH")
        env["PYTHONPATH"] = source if not old else source + os.pathsep + old

    os.execve(
        sys.executable,
        [sys.executable, "-u", "-m", "decnet.main", config_name],
        env,
    )


if __name__ == "__main__":
    raise SystemExit(main())

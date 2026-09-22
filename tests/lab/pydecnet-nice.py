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

"""Query the candidate object-19 NICE listener from pinned PyDECnet."""

from __future__ import annotations

import sys

from decnet.connectors import SimpleApiConnector

REQUEST = bytes.fromhex("14 20 00 00 00")
STATUS_REQUEST = bytes.fromhex("14 10 00 00 00")
COUNTERS_REQUEST = bytes.fromhex("14 30 00 00 00")
CIRCUIT_REQUEST = bytes.fromhex("14 13 05") + b"ETH-0"
CIRCUIT_COUNTERS_REQUEST = bytes.fromhex("14 33 05") + b"ETH-0"
VERSION = bytes((4, 0, 0))
IDENT = b"DECnet-IV-Linux"


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit(
            f"usage: {sys.argv[0]} API-SOCKET AREA.NODE PYDECNET-SYSTEM"
        )
    api_socket, destination, system = sys.argv[1:]
    connector = SimpleApiConnector(api_socket)
    try:
        connection, response = connector.connect(
            system=system,
            dest=destination,
            remuser=19,
            localuser="NCP",
            data=VERSION,
        )
        if connection is None or response.type != "accept":
            raise RuntimeError(
                f"NML connect rejected: {getattr(response, 'reason', 'unknown')}"
            )
        if bytes(response) != VERSION:
            raise RuntimeError(f"bad NML accept data: {bytes(response)!r}")
        connection.data(REQUEST)
        response = connection.recv()
        if response.type != "data":
            raise RuntimeError(f"unexpected NICE response type {response.type!r}")
        data = bytes(response)
        if len(data) < 15 or data[0] != 1 or data[1:4] != b"\xff\xff\x00":
            raise RuntimeError(f"bad NICE reply header: {data!r}")
        address = int.from_bytes(data[4:6], "little")
        namelen = data[6] & 0x7f
        if not (data[6] & 0x80) or not namelen:
            raise RuntimeError(f"bad NICE node entity: {data!r}")
        name = data[7:7 + namelen]
        off = 7 + namelen
        if data[off:off + 2] != (100).to_bytes(2, "little"):
            raise RuntimeError(f"missing NICE identification: {data!r}")
        if data[off + 2] != 0x40 or data[off + 3] != len(IDENT):
            raise RuntimeError(f"bad NICE identification type: {data!r}")
        if data[off + 4:off + 4 + len(IDENT)] != IDENT:
            raise RuntimeError(f"bad NICE identification value: {data!r}")
        if address == 0 or not name:
            raise RuntimeError(f"invalid NICE executor identity: {data!r}")

        connection.data(STATUS_REQUEST)
        response = connection.recv()
        if response.type != "data":
            raise RuntimeError(
                f"unexpected NICE status response type {response.type!r}"
            )
        status = bytes(response)
        if len(status) < 20 or status[0] != 1 or status[1:4] != b"\xff\xff\x00":
            raise RuntimeError(f"bad NICE status header: {status!r}")
        status_name_len = status[6] & 0x7f
        status_off = 7 + status_name_len
        if status[status_off:status_off + 4] != b"\x00\x00\x81\x00":
            raise RuntimeError(f"missing NICE node state: {status!r}")
        status_off += 4
        if status[status_off:status_off + 3] != b"\x58\x02\x02":
            raise RuntimeError(f"missing NICE active-links parameter: {status!r}")
        active_links = int.from_bytes(status[status_off + 3:status_off + 5],
                                      "little")
        if active_links < 1:
            raise RuntimeError(f"invalid NICE active-links value: {status!r}")

        connection.data(COUNTERS_REQUEST)
        response = connection.recv()
        if response.type != "data":
            raise RuntimeError(
                f"unexpected NICE counters response type {response.type!r}"
            )
        counters = bytes(response)
        if len(counters) < 35 or counters[:4] != b"\x01\xff\xff\x00":
            raise RuntimeError(f"bad NICE counters header: {counters!r}")
        counters_name_len = counters[6] & 0x7f
        counters_off = 7 + counters_name_len
        if counters[counters_off:counters_off + 2] != b"\x60\xe2":
            raise RuntimeError(f"missing NICE total-bytes counter: {counters!r}")
        total_bytes = int.from_bytes(
            counters[counters_off + 2:counters_off + 6], "little"
        )
        counters_off += 6
        if counters[counters_off:counters_off + 2] != b"\x61\xe2":
            raise RuntimeError(
                f"missing NICE total-bytes-sent counter: {counters!r}"
            )
        total_bytes_sent = int.from_bytes(
            counters[counters_off + 2:counters_off + 6], "little"
        )
        counters_off += 6
        if counters[counters_off:counters_off + 2] != b"\x62\xe2":
            raise RuntimeError(
                f"missing NICE total-messages counter: {counters!r}"
            )
        total_messages = int.from_bytes(
            counters[counters_off + 2:counters_off + 6], "little"
        )
        counters_off += 6
        if counters[counters_off:counters_off + 2] != b"\x63\xe2":
            raise RuntimeError(
                f"missing NICE total-messages-sent counter: {counters!r}"
            )
        total_messages_sent = int.from_bytes(
            counters[counters_off + 2:counters_off + 6], "little"
        )
        if min(total_bytes, total_bytes_sent,
               total_messages, total_messages_sent) < 1:
            raise RuntimeError(f"invalid NICE counters: {counters!r}")

        connection.data(CIRCUIT_REQUEST)
        response = connection.recv()
        if response.type != "data":
            raise RuntimeError(
                f"unexpected NICE circuit response type {response.type!r}"
            )
        circuit = bytes(response)
        if len(circuit) < 25 or circuit[:4] != b"\x01\xff\xff\x00":
            raise RuntimeError(f"bad NICE circuit header: {circuit!r}")
        name_len = circuit[4]
        if circuit[5:5 + name_len] != b"ETH-0":
            raise RuntimeError(f"bad NICE circuit entity: {circuit!r}")
        off = 5 + name_len
        if circuit[off:off + 4] != b"\x00\x00\x81\x00":
            raise RuntimeError(f"missing NICE circuit state: {circuit!r}")
        off += 4
        if circuit[off:off + 4] != b"\x20\x03\xc1\x02":
            raise RuntimeError(f"missing NICE adjacent node: {circuit!r}")
        adjacent_node = int.from_bytes(circuit[off + 4:off + 6], "little")
        if adjacent_node == 0:
            raise RuntimeError(f"invalid NICE adjacent node: {circuit!r}")
        off += 6
        if circuit[off:off + 3] != b"\x2a\x03\x02":
            raise RuntimeError(f"missing NICE circuit block size: {circuit!r}")
        block_size = int.from_bytes(circuit[off + 3:off + 5], "little")
        if block_size < 576:
            raise RuntimeError(f"invalid NICE circuit block size: {circuit!r}")

        remote_status_request = bytes((
            0x14, 0x10, 0x00,
            adjacent_node & 0xff, (adjacent_node >> 8) & 0xff,
        ))
        connection.data(remote_status_request)
        response = connection.recv()
        if response.type != "data":
            raise RuntimeError(
                f"unexpected remote-node response type {response.type!r}"
            )
        remote = bytes(response)
        if len(remote) < 39 or remote[:4] != b"\x01\xff\xff\x00":
            raise RuntimeError(f"bad remote-node header: {remote!r}")
        if int.from_bytes(remote[4:6], "little") != adjacent_node:
            raise RuntimeError(f"wrong remote-node entity: {remote!r}")
        remote_name_len = remote[6] & 0x7f
        off = 7 + remote_name_len
        if remote[off:off + 4] != b"\x00\x00\x81\x04":
            raise RuntimeError(f"remote node not reachable: {remote!r}")
        off += 4
        if remote[off:off + 3] != b"\x2a\x03\x81":
            raise RuntimeError(f"missing remote node type: {remote!r}")
        remote_type = remote[off + 3]
        if remote_type not in (4, 5):
            raise RuntimeError(f"invalid remote node type: {remote!r}")
        off += 4
        if remote[off:off + 3] != b"\x34\x03\x02":
            raise RuntimeError(f"missing remote route cost: {remote!r}")
        remote_cost = int.from_bytes(remote[off + 3:off + 5], "little")
        off += 5
        if remote[off:off + 3] != b"\x35\x03\x01":
            raise RuntimeError(f"missing remote route hops: {remote!r}")
        remote_hops = remote[off + 3]
        off += 4
        if remote[off:off + 3] != b"\x36\x03\x40":
            raise RuntimeError(f"missing remote route circuit: {remote!r}")
        remote_circuit_len = remote[off + 3]
        remote_circuit = remote[off + 4:off + 4 + remote_circuit_len]
        off += 4 + remote_circuit_len
        if remote_circuit != b"ETH-0":
            raise RuntimeError(f"wrong remote route circuit: {remote!r}")
        if remote[off:off + 4] != b"\x3e\x03\xc1\x02":
            raise RuntimeError(f"missing remote next node: {remote!r}")
        remote_next = int.from_bytes(remote[off + 4:off + 6], "little")
        if remote_next != adjacent_node:
            raise RuntimeError(f"wrong remote next node: {remote!r}")

        for selector_code, selector_name in (
                (0xff, "known"), (0xfe, "active"), (0xfc, "adjacent")):
            connection.data(bytes((0x14, 0x10, selector_code)))
            response = connection.recv()
            if response.type != "data" or bytes(response) != b"\x02":
                raise RuntimeError(
                    f"missing {selector_name} multi-item header: "
                    f"{getattr(response, 'type', None)!r} "
                    f"{bytes(response)!r}"
                )
            seen = set()
            while True:
                response = connection.recv()
                if response.type != "data":
                    raise RuntimeError(
                        f"unexpected {selector_name} response type "
                        f"{response.type!r}"
                    )
                item = bytes(response)
                if item == b"\x80":
                    break
                if len(item) < 7 or item[0] != 1 or item[1:4] != b"\xff\xff\x00":
                    raise RuntimeError(
                        f"bad {selector_name} node item: {item!r}"
                    )
                seen.add(int.from_bytes(item[4:6], "little"))
            if adjacent_node not in seen:
                raise RuntimeError(
                    f"{selector_name} read omitted live adjacent node "
                    f"{adjacent_node}: {sorted(seen)}"
                )

        unknown = ((address & 0xfc00) | 1023)
        if unknown == address or unknown == adjacent_node:
            unknown = ((address & 0xfc00) | 1022)
        connection.data(bytes((
            0x14, 0x10, 0x00, unknown & 0xff, (unknown >> 8) & 0xff,
        )))
        response = connection.recv()
        if response.type != "data" or bytes(response) != b"\xf8":
            raise RuntimeError(
                f"unknown node did not return NICE -8: {bytes(response)!r}"
            )

        connection.data(bytes((
            0x14, 0x90, 0x00,
            adjacent_node & 0xff, (adjacent_node >> 8) & 0xff,
        )))
        response = connection.recv()
        if response.type != "data" or bytes(response) != b"\xff":
            raise RuntimeError(
                f"permanent read did not return NICE -1: {bytes(response)!r}"
            )

        for selector_code, selector_name in (
                (0xff, "known-circuit"), (0xfe, "active-circuit")):
            connection.data(bytes((0x14, 0x13, selector_code)))
            response = connection.recv()
            if response.type != "data" or bytes(response) != b"\x02":
                raise RuntimeError(
                    f"missing {selector_name} multi-item header: "
                    f"{bytes(response)!r}"
                )
            seen_circuits = set()
            while True:
                response = connection.recv()
                if response.type != "data":
                    raise RuntimeError(
                        f"unexpected {selector_name} response "
                        f"{response.type!r}"
                    )
                item = bytes(response)
                if item == b"\x80":
                    break
                if len(item) < 10 or item[:4] != b"\x01\xff\xff\x00":
                    raise RuntimeError(
                        f"bad {selector_name} item: {item!r}"
                    )
                item_name_len = item[4]
                item_name = item[5:5 + item_name_len]
                seen_circuits.add(item_name)
            if b"ETH-0" not in seen_circuits:
                raise RuntimeError(
                    f"{selector_name} omitted live ETH-0: "
                    f"{sorted(seen_circuits)!r}"
                )

        connection.data(CIRCUIT_COUNTERS_REQUEST)
        response = connection.recv()
        if response.type != "data":
            raise RuntimeError(
                f"unexpected NICE circuit counters type {response.type!r}"
            )
        circuit_counters = bytes(response)
        if (len(circuit_counters) < 34 or
                circuit_counters[:4] != b"\x01\xff\xff\x00"):
            raise RuntimeError(
                f"bad NICE circuit counters header: {circuit_counters!r}"
            )
        circuit_name_len = circuit_counters[4]
        if circuit_counters[5:5 + circuit_name_len] != b"ETH-0":
            raise RuntimeError(
                f"bad NICE circuit counters entity: {circuit_counters!r}"
            )
        counter_off = 5 + circuit_name_len
        values = []
        for encoded in (b"\xe8\xe3", b"\xe9\xe3",
                        b"\xf2\xe3", b"\xf3\xe3"):
            if circuit_counters[counter_off:counter_off + 2] != encoded:
                raise RuntimeError(
                    f"missing NICE circuit counter {encoded!r}: "
                    f"{circuit_counters!r}"
                )
            values.append(int.from_bytes(
                circuit_counters[counter_off + 2:counter_off + 6], "little"
            ))
            counter_off += 6
        if min(values) < 1:
            raise RuntimeError(
                f"invalid NICE circuit counters: {circuit_counters!r}"
            )
        (circuit_rx_bytes, circuit_tx_bytes,
         circuit_rx_blocks, circuit_tx_blocks) = values
        connection.disconnect()
    finally:
        connector.close()

    print(
        f"pydecnet-nice: pass peer={destination} "
        f"executor={address >> 10}.{address & 1023} name={name.decode('ascii')} "
        f"active_links={active_links} total_rx_bytes={total_bytes} "
        f"total_tx_bytes={total_bytes_sent} "
        f"total_rx_messages={total_messages} "
        f"total_tx_messages={total_messages_sent} "
        f"circuit=ETH-0 adjacent={adjacent_node >> 10}."
        f"{adjacent_node & 1023} block_size={block_size} "
        f"remote_type={remote_type} remote_cost={remote_cost} "
        f"remote_hops={remote_hops} remote_circuit={remote_circuit.decode('ascii')} "
        f"multi_node_reads=known,active,adjacent "
        f"multi_circuit_reads=known,active "
        f"circuit_rx_bytes={circuit_rx_bytes} "
        f"circuit_tx_bytes={circuit_tx_bytes} "
        f"circuit_rx_blocks={circuit_rx_blocks} "
        f"circuit_tx_blocks={circuit_tx_blocks}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

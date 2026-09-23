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

"""Serve bounded CTERM/Foundation probe and interactive sessions from PyDECnet."""

from __future__ import annotations
import asyncio
import sys
from decnet.async_connectors import AsyncApiConnector

FOUND_BIND = 1
FOUND_BIND_ACCEPT = 4
FOUND_COMMON_DATA = 9
CTERM_INITIATE = 1
CTERM_START_READ = 2
CTERM_READ_DATA = 3
CTERM_OOB = 4
CTERM_UNREAD = 5
CTERM_CLEAR_INPUT = 6
CTERM_WRITE = 7
CTERM_WRITE_COMPLETE = 8
CTERM_CHECK_INPUT = 12
CTERM_INPUT_COUNT = 13
CTERM_READ_CHARACTERISTICS = 10
CTERM_CHARACTERISTICS = 11
CTERM_INPUT_STATE = 14

def foundation_bind() -> bytes:
    msg = bytearray(17)
    msg[0] = FOUND_BIND
    msg[1:4] = bytes((2, 4, 0))
    msg[4:6] = (7).to_bytes(2, "little")
    return bytes(msg)

def common(body: bytes) -> bytes:
    return bytes((FOUND_COMMON_DATA, 0)) + len(body).to_bytes(2, "little") + body

def cterm_initiate() -> bytes:
    return common(bytes((CTERM_INITIATE, 0, 1, 4, 0)))

def cterm_unread() -> bytes:
    return common(bytes((CTERM_UNREAD, 0)))

def cterm_clear_input() -> bytes:
    return common(bytes((CTERM_CLEAR_INPUT, 0)))

def cterm_write(data: bytes, request_complete: bool = False) -> bytes:
    flags = 0x0400 if request_complete else 0
    return common(
        bytes((CTERM_WRITE, flags & 0xff, flags >> 8, 0, 0)) + data
    )

def cterm_check_input() -> bytes:
    return common(bytes((CTERM_CHECK_INPUT, 0)))

def cterm_set_characteristics(normal_echo: int, input_count_state: int) -> bytes:
    body = bytearray((CTERM_CHARACTERISTICS, 0))
    body += bytes((0x05, 0x02, normal_echo & 1))
    body += bytes((0x08, 0x02)) + input_count_state.to_bytes(2, "little")
    return common(bytes(body))

def cterm_read_characteristics() -> bytes:
    selectors = (
        0x0001, 0x0002, 0x0003, 0x0004, 0x0005,
        0x0101, 0x0102, 0x0103, 0x0104, 0x0107, 0x0109, 0x010A, 0x010E,
        0x0201, 0x0205, 0x0206, 0x0207, 0x0208,
    )
    body = bytearray((CTERM_READ_CHARACTERISTICS, 0))
    for selector in selectors:
        body += selector.to_bytes(2, "little")
    return common(bytes(body))

def cterm_start_read(maximum: int = 80) -> bytes:
    body = bytearray(17)
    body[0] = CTERM_START_READ
    flags = 2 << 14
    body[1:4] = flags.to_bytes(3, "little")
    body[4:6] = maximum.to_bytes(2, "little")
    return common(bytes(body))

def valid_bind_accept(msg: bytes) -> bool:
    return (
        len(msg) == 17
        and msg[0] == FOUND_BIND_ACCEPT
        and msg[1:4] == bytes((2, 4, 0))
        and int.from_bytes(msg[4:6], "little") == 193
    )

def valid_cterm_reply(msg: bytes) -> bool:
    if len(msg) < 5 or msg[0] != FOUND_COMMON_DATA:
        return False
    length = int.from_bytes(msg[2:4], "little")
    return length >= 1 and len(msg) == length + 4 and msg[4] == CTERM_INITIATE

def read_data(msg: bytes) -> tuple[int, bytes]:
    if len(msg) < 12 or msg[0] != FOUND_COMMON_DATA:
        raise RuntimeError(f"bad READ DATA foundation record: {msg!r}")
    length = int.from_bytes(msg[2:4], "little")
    if len(msg) != length + 4 or length < 8 or msg[4] != CTERM_READ_DATA:
        raise RuntimeError(f"bad READ DATA CTERM record: {msg!r}")
    body = msg[4:]
    return int.from_bytes(body[6:8], "little"), body[8:]

def common_body(msg: bytes, expected_type: int) -> bytes:
    if len(msg) < 5 or msg[0] != FOUND_COMMON_DATA:
        raise RuntimeError(f"bad common-data foundation record: {msg!r}")
    length = int.from_bytes(msg[2:4], "little")
    if len(msg) != length + 4 or length < 1 or msg[4] != expected_type:
        raise RuntimeError(
            f"bad CTERM type {expected_type} common-data record: {msg!r}"
        )
    return msg[4:]

async def handshake(conn) -> None:
    request = await conn.recv()
    if request.type != "connect":
        raise RuntimeError(f"expected connect, got {request.type!r}")
    await conn.accept()
    conn.data(foundation_bind())
    reply = await conn.recv()
    if reply.type != "data" or not valid_bind_accept(bytes(reply)):
        raise RuntimeError(
            f"bad Foundation bind accept type={reply.type!r} data={bytes(reply)!r}"
        )
    conn.data(cterm_initiate())
    reply = await conn.recv()
    if reply.type != "data" or not valid_cterm_reply(bytes(reply)):
        raise RuntimeError(
            f"bad CTERM initiate reply type={reply.type!r} data={bytes(reply)!r}"
        )

async def serve(api_socket: str, system: str) -> int:
    connector = AsyncApiConnector(api_socket)
    await connector.start()
    listener = await connector.bind(42, "CTERM", system=system)
    fal = await connector.bind(17, "FAL", system=system)
    try:
        print("pydecnet-cterm: ready", flush=True)
        probe = await listener.listen()
        await handshake(probe)
        probe.disconnect()

        sethost_probe = await listener.listen()
        await handshake(sethost_probe)
        sethost_probe.disconnect()

        dap = await fal.listen()
        dap_request = await dap.recv()
        if dap_request.type != "connect":
            raise RuntimeError(f"expected FAL connect, got {dap_request.type!r}")
        await dap.accept()
        dap_reply = await dap.recv()
        if dap_reply.type != "data":
            raise RuntimeError(f"expected DAP CONFIG, got {dap_reply.type!r}")
        dap_config = bytes(dap_reply)
        if len(dap_config) != 12 or dap_config[0] != 1 or dap_config[6:8] != bytes((4, 1)):
            raise RuntimeError(f"bad DAP CONFIG: {dap_config!r}")
        dap.data(dap_config)
        dap.disconnect()

        dap = await fal.listen()
        dap_request = await dap.recv()
        if dap_request.type != "connect":
            raise RuntimeError(f"expected FAL retrieval connect, got {dap_request.type!r}")
        await dap.accept()
        dap_reply = await dap.recv()
        if dap_reply.type != "data":
            raise RuntimeError(f"expected retrieval DAP CONFIG, got {dap_reply.type!r}")
        dap_config = bytes(dap_reply)
        if len(dap_config) != 12 or dap_config[0] != 1:
            raise RuntimeError(f"bad retrieval DAP CONFIG: {dap_config!r}")
        dap.data(dap_config)

        access = await dap.recv()
        if access.type != "data":
            raise RuntimeError(f"expected DAP ACCESS, got {access.type!r}")
        access_body = bytes(access)
        expected_name = b"PHASE7.TXT"
        if (
            len(access_body) != 5 + len(expected_name)
            or access_body[:5] != bytes((3, 0, 1, 0, len(expected_name)))
            or access_body[5:] != expected_name
        ):
            raise RuntimeError(f"bad DAP ACCESS: {access_body!r}")
        dap.data(bytes((2, 0, 0)))
        dap.data(bytes((6, 0)))

        control = await dap.recv()
        if control.type != "data" or bytes(control) != bytes((4, 0, 2)):
            raise RuntimeError(f"bad DAP CONTROL CONNECT: {bytes(control)!r}")
        dap.data(bytes((6, 0)))

        control = await dap.recv()
        if control.type != "data" or bytes(control) != bytes((4, 0, 1)):
            raise RuntimeError(f"bad DAP CONTROL GET: {bytes(control)!r}")
        dap.data(bytes((8, 0, 0)) + b"DAP-PHASE7\n")
        dap.data(bytes((9, 0, 0x27, 0x40)))

        accom = await dap.recv()
        if accom.type != "data" or bytes(accom) != bytes((7, 0, 1)):
            raise RuntimeError(f"bad DAP ACCOMP command: {bytes(accom)!r}")
        dap.data(bytes((7, 0, 2)))
        dap.disconnect()

        dap = await fal.listen()
        dap_request = await dap.recv()
        if dap_request.type != "connect":
            raise RuntimeError(f"expected FAL get-to connect, got {dap_request.type!r}")
        await dap.accept()
        dap_reply = await dap.recv()
        dap_config = bytes(dap_reply)
        if dap_reply.type != "data" or len(dap_config) != 12 or dap_config[0] != 1:
            raise RuntimeError(f"bad get-to DAP CONFIG: {dap_config!r}")
        dap.data(dap_config)
        access = await dap.recv()
        if access.type != "data" or b"PHASE7.TXT" not in bytes(access):
            raise RuntimeError(f"bad get-to DAP ACCESS: {bytes(access)!r}")
        dap.data(bytes((2, 0, 0)))
        dap.data(bytes((6, 0)))
        control = await dap.recv()
        if control.type != "data" or bytes(control) != bytes((4, 0, 2)):
            raise RuntimeError(f"bad get-to DAP CONTROL CONNECT: {bytes(control)!r}")
        dap.data(bytes((6, 0)))
        control = await dap.recv()
        if control.type != "data" or bytes(control) != bytes((4, 0, 1)):
            raise RuntimeError(f"bad get-to DAP CONTROL GET: {bytes(control)!r}")
        dap.data(bytes((8, 0, 0)) + b"DAP-PHASE7\n")
        dap.data(bytes((9, 0, 0x27, 0x40)))
        accom = await dap.recv()
        if accom.type != "data" or bytes(accom) != bytes((7, 0, 1)):
            raise RuntimeError(f"bad get-to DAP ACCOMP command: {bytes(accom)!r}")
        dap.data(bytes((7, 0, 2)))
        dap.disconnect()

        dap = await fal.listen()
        dap_request = await dap.recv()
        if dap_request.type != "connect":
            raise RuntimeError(f"expected FAL put connect, got {dap_request.type!r}")
        await dap.accept()
        dap_reply = await dap.recv()
        dap_config = bytes(dap_reply)
        if dap_reply.type != "data" or len(dap_config) != 12 or dap_config[0] != 1:
            raise RuntimeError(f"bad put DAP CONFIG: {dap_config!r}")
        dap.data(dap_config)

        attrib = await dap.recv()
        if attrib.type != "data" or bytes(attrib) != bytes((2, 0, 0)):
            raise RuntimeError(f"bad put DAP ATTRIBUTES: {bytes(attrib)!r}")
        access = await dap.recv()
        expected_name = b"UPLOAD.TXT"
        access_bytes = bytes(access)
        if (
            access.type != "data"
            or len(access_bytes) != 5 + len(expected_name)
            or access_bytes[:5] != bytes((3, 0, 2, 0, len(expected_name)))
            or access_bytes[5:] != expected_name
        ):
            raise RuntimeError(f"bad put DAP ACCESS: {access_bytes!r}")
        dap.data(bytes((2, 0, 0)))
        dap.data(bytes((6, 0)))

        control = await dap.recv()
        if control.type != "data" or bytes(control) != bytes((4, 0, 2)):
            raise RuntimeError(f"bad put DAP CONTROL CONNECT: {bytes(control)!r}")
        dap.data(bytes((6, 0)))

        control = await dap.recv()
        if control.type != "data" or bytes(control) != bytes((4, 0, 4)):
            raise RuntimeError(f"bad put DAP CONTROL PUT: {bytes(control)!r}")
        data_msg = await dap.recv()
        if data_msg.type != "data" or bytes(data_msg) != bytes((8, 0, 0)) + b"DAP-PUT-PHASE7\n":
            raise RuntimeError(f"bad put DAP DATA: {bytes(data_msg)!r}")

        accom = await dap.recv()
        if accom.type != "data" or bytes(accom) != bytes((7, 0, 1)):
            raise RuntimeError(f"bad put DAP ACCOMP command: {bytes(accom)!r}")
        dap.data(bytes((7, 0, 2)))
        dap.disconnect()

        dap = await fal.listen()
        dap_request = await dap.recv()
        if dap_request.type != "connect":
            raise RuntimeError(f"expected FAL directory connect, got {dap_request.type!r}")
        await dap.accept()
        dap_reply = await dap.recv()
        dap_config = bytes(dap_reply)
        if dap_reply.type != "data" or len(dap_config) != 12 or dap_config[0] != 1:
            raise RuntimeError(f"bad directory DAP CONFIG: {dap_config!r}")
        dap.data(dap_config)

        access = await dap.recv()
        access_bytes = bytes(access)
        expected_spec = b"*.TXT"
        if (
            access.type != "data"
            or len(access_bytes) != 5 + len(expected_spec)
            or access_bytes[:5] != bytes((3, 0, 6, 0, len(expected_spec)))
            or access_bytes[5:] != expected_spec
        ):
            raise RuntimeError(f"bad directory DAP ACCESS: {access_bytes!r}")
        for name in (b"PHASE7.TXT", b"UPLOAD.TXT"):
            dap.data(bytes((15, 0, 2, len(name))) + name)
        dap.data(bytes((7, 0, 2)))
        dap.disconnect()

        interactive = await listener.listen()
        await handshake(interactive)

        seen_oob = False
        seen_input_state = False
        while not (seen_oob and seen_input_state):
            reply = await interactive.recv()
            if reply.type != "data":
                raise RuntimeError(f"expected asynchronous CTERM input event, got {reply.type!r}")
            raw = bytes(reply)
            body = common_body(raw, raw[4])
            if body[0] == CTERM_OOB:
                if body != bytes((CTERM_OOB, 0, 3)):
                    raise RuntimeError(f"bad OOB body: {body!r}")
                seen_oob = True
            elif body[0] == CTERM_INPUT_STATE:
                if body != bytes((CTERM_INPUT_STATE, 1)):
                    raise RuntimeError(f"bad INPUT STATE body: {body!r}")
                seen_input_state = True
            else:
                raise RuntimeError(f"unexpected asynchronous CTERM body: {body!r}")

        interactive.data(cterm_write(b"CTERM-READY\r\n", request_complete=True))
        reply = await interactive.recv()
        if reply.type != "data":
            raise RuntimeError(f"expected WRITE COMPLETE, got {reply.type!r}")
        body = common_body(bytes(reply), CTERM_WRITE_COMPLETE)
        if body != bytes((CTERM_WRITE_COMPLETE, 0, 0, 0, 0, 0)):
            raise RuntimeError(f"bad WRITE COMPLETE body: {body!r}")

        interactive.data(cterm_check_input())
        reply = await interactive.recv()
        if reply.type != "data":
            raise RuntimeError(f"expected INPUT COUNT, got {reply.type!r}")
        body = common_body(bytes(reply), CTERM_INPUT_COUNT)
        if len(body) != 4 or int.from_bytes(body[2:4], "little") != 7:
            raise RuntimeError(f"bad INPUT COUNT body: {body!r}")

        interactive.data(cterm_read_characteristics())
        reply = await interactive.recv()
        if reply.type != "data":
            raise RuntimeError(f"expected CHARACTERISTICS, got {reply.type!r}")
        body = common_body(bytes(reply), CTERM_CHARACTERISTICS)
        expected_prefix = (
            bytes((CTERM_CHARACTERISTICS, 0))
            + bytes((0x01, 0x00)) + (9600).to_bytes(2, "little")
            + bytes((0x02, 0x00)) + (9600).to_bytes(2, "little")
            + bytes((0x03, 0x00)) + (8).to_bytes(2, "little")
            + bytes((0x04, 0x00, 0))
            + bytes((0x05, 0x00)) + (1).to_bytes(2, "little")
            + bytes((0x01, 0x01, 0))
            + bytes((0x02, 0x01)) + (3).to_bytes(2, "little")
            + bytes((0x03, 0x01, 5)) + b"VT200"
            + bytes((0x04, 0x01, 1))
            + bytes((0x07, 0x01, 1))
        )
        if not body.startswith(expected_prefix):
            raise RuntimeError(f"bad fixed CHARACTERISTICS prefix: {body!r}")
        rest = body[len(expected_prefix):]
        expected_tail = (
            bytes((0x09, 0x01)) + (80).to_bytes(2, "little")
            + bytes((0x0A, 0x01)) + (24).to_bytes(2, "little")
            + bytes((0x0E, 0x01)) + (1).to_bytes(2, "little")
            + bytes((0x01, 0x02, 0))
            + bytes((0x05, 0x02, 1))
            + bytes((0x06, 0x02, 1))
            + bytes((0x07, 0x02, 1))
            + bytes((0x08, 0x02)) + (1).to_bytes(2, "little")
        )
        if rest != expected_tail:
            raise RuntimeError(f"bad remaining CHARACTERISTICS body: {rest!r}")

        interactive.data(cterm_set_characteristics(0, 1))
        interactive.data(cterm_read_characteristics())
        reply = await interactive.recv()
        if reply.type != "data":
            raise RuntimeError(f"expected CHARACTERISTICS after set, got {reply.type!r}")
        body = common_body(bytes(reply), CTERM_CHARACTERISTICS)
        if bytes((0x05, 0x02, 0)) not in body:
            raise RuntimeError(f"normal-echo characteristic did not update: {body!r}")
        if bytes((0x08, 0x02, 1, 0)) not in body:
            raise RuntimeError(f"input-count-state characteristic did not persist: {body!r}")

        interactive.data(cterm_start_read())
        reply = await interactive.recv()
        if reply.type != "data":
            raise RuntimeError(f"expected READ DATA, got {reply.type!r}")
        term_pos, data = read_data(bytes(reply))
        if data != b"phase7\r" or term_pos != 6:
            raise RuntimeError(
                f"bad interactive input term_pos={term_pos} data={data!r}"
            )
        interactive.data(cterm_clear_input())
        interactive.data(cterm_unread())
        reply = await interactive.recv()
        if reply.type != "data":
            raise RuntimeError(f"expected UNREAD READ DATA, got {reply.type!r}")
        body = common_body(bytes(reply), CTERM_READ_DATA)
        if len(body) != 9 or body[1] != 6 or body[8] != 0:
            raise RuntimeError(f"bad UNREAD READ DATA body: {body!r}")

        interactive.data(cterm_write(b"CTERM-DONE\r\n"))
        interactive.disconnect()
        print("pydecnet-cterm: pass object=42 sessions=3 interactive=1 controls=oob,input-state,write-complete,input-count,characteristics-set-read,clear-input,unread", flush=True)
        return 0
    finally:
        fal.close()
        listener.close()
        await connector.close()

def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {sys.argv[0]} API-SOCKET PYDECNET-SYSTEM")
    return asyncio.run(serve(sys.argv[1], sys.argv[2]))

if __name__ == "__main__":
    raise SystemExit(main())

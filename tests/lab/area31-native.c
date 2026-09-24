// ============================================================================
// Copyright (c) 2026 Supratim Sanyal of SANYALnet Labs.
// Proprietary rights reserved except as expressly licensed herein.
//
// DECnet-IV-Linux
// This file is governed by the SANYALnet Labs Non-Commercial License in the
// root LICENSE file. Non-Commercial use is permitted; Commercial Use and use
// for AI/ML model training are prohibited unless separately authorized.
//
// Attribution is required: "Based on original work by Supratim Sanyal of
// SANYALnet Labs." See LICENSE for full terms, warranty disclaimer, termination,
// patent, trademark, and governing-law provisions.
// ============================================================================

#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

#include <linux/dn.h>
#include <decnet_iv_nice.h>
#include <netdnet/dnetdb.h>

static __le16 cpu_to_le16_u(uint16_t value)
{
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return (__le16)value;
#else
    return (__le16)__builtin_bswap16(value);
#endif
}

static int parse_node(const char *text, uint16_t *address)
{
    char *end;
    unsigned long area;
    unsigned long node;

    if (!text || !address)
        return -1;
    errno = 0;
    area = strtoul(text, &end, 10);
    if (errno || end == text || *end != '.' || area < 1U || area > 63U)
        return -1;
    text = end + 1;
    errno = 0;
    node = strtoul(text, &end, 10);
    if (errno || end == text || *end || node < 1U || node > 1023U)
        return -1;
    *address = (uint16_t)((area << 10) | node);
    return 0;
}

static int nice_query(uint16_t target, unsigned int info)
{
    static const unsigned char version[3] = {4U, 0U, 0U};
    unsigned char request[5] = {
        DNIV_NICE_FUNC_READ_INFO, 0U, 0U, 0U, 0U
    };
    unsigned char response[512];
    struct sockaddr_dn peer;
    struct optdata_dn conndata;
    struct optdata_dn acceptdata;
    struct timeval timeout = {10, 0};
    socklen_t optlen;
    ssize_t got;
    size_t off;
    uint16_t reply_addr;
    int fd;

    request[1] = (unsigned char)(info << 4);
    fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (fd < 0)
        return -1;
    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) ||
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout)))
        goto fail;

    memset(&conndata, 0, sizeof(conndata));
    conndata.opt_optl = cpu_to_le16_u(sizeof(version));
    memcpy(conndata.opt_data, version, sizeof(version));
    if (setsockopt(fd, DNPROTO_NSP, DSO_CONDATA, &conndata, sizeof(conndata)))
        goto fail;

    memset(&peer, 0, sizeof(peer));
    peer.sdn_family = AF_DECnet;
    peer.sdn_objnum = 19U;
    peer.sdn_nodeaddrl = cpu_to_le16_u(2U);
    peer.sdn_nodeaddr[0] = (unsigned char)(target & 0xffU);
    peer.sdn_nodeaddr[1] = (unsigned char)(target >> 8);
    if (connect(fd, (struct sockaddr *)&peer, sizeof(peer)))
        goto fail;

    memset(&acceptdata, 0, sizeof(acceptdata));
    optlen = sizeof(acceptdata);
    if (getsockopt(fd, DNPROTO_NSP, DSO_CONDATA, &acceptdata, &optlen) ||
        optlen != sizeof(acceptdata) ||
        acceptdata.opt_optl != cpu_to_le16_u(sizeof(version)) ||
        memcmp(acceptdata.opt_data, version, sizeof(version)))
        goto fail;

    if (send(fd, request, sizeof(request), MSG_EOR | MSG_NOSIGNAL) !=
        (ssize_t)sizeof(request))
        goto fail;
    got = recv(fd, response, sizeof(response), 0);
    if (got < 7 || response[0] != DNIV_NICE_RET_SUCCESS)
        goto fail;

    off = 4U + (size_t)response[3];
    if ((size_t)got < off + 3U)
        goto fail;
    reply_addr = (uint16_t)((uint16_t)response[off] |
                            ((uint16_t)response[off + 1U] << 8));
    if (reply_addr != target)
        goto fail;

    close(fd);
    return 0;
fail:
    close(fd);
    return -1;
}

static int mirror_query(const char *target)
{
    unsigned char tx[128];
    unsigned char rx[128];
    int fd;
    int i;

    fd = dnet_conn((char *)target, "MIRROR", SOCK_SEQPACKET,
                   NULL, 0, NULL, NULL);
    if (fd < 0)
        return -1;
    for (i = 0; i < 3; i++) {
        int got;
        size_t j;

        tx[0] = 0U;
        for (j = 1U; j < sizeof(tx); j++)
            tx[j] = (unsigned char)(j ^ (size_t)(0x31 + i));
        if (send(fd, tx, sizeof(tx), MSG_EOR | MSG_NOSIGNAL) !=
            (ssize_t)sizeof(tx))
            goto fail;
        got = dnet_recv(fd, rx, sizeof(rx), MSG_EOR);
        if (got != (int)sizeof(rx) || rx[0] != 1U ||
            memcmp(tx + 1, rx + 1, sizeof(tx) - 1U))
            goto fail;
    }
    close(fd);
    return 0;
fail:
    close(fd);
    return -1;
}

int main(void)
{
    const char *target_text = getenv("DNIV_AREA31_TARGET");
    uint16_t target;

    if (parse_node(target_text, &target) || (target >> 10) != 31U) {
        fputs("area31-native: invalid target environment\n", stderr);
        return 2;
    }
    if (nice_query(target, DNIV_NICE_INFO_SUMMARY) ||
        nice_query(target, DNIV_NICE_INFO_STATUS) ||
        nice_query(target, DNIV_NICE_INFO_COUNTERS)) {
        fputs("area31-native: NICE proof failed\n", stderr);
        return 1;
    }
    if (mirror_query(target_text)) {
        fputs("area31-native: MIRROR proof failed\n", stderr);
        return 1;
    }
    puts("area31-native: NICE summary/status/counters and MIRROR pass");
    return 0;
}

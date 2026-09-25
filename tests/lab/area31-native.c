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

static void nice_dump_frame(unsigned int info, const unsigned char *buf,
                            ssize_t length)
{
    size_t limit;
    size_t i;

    if (length < 0) {
        fprintf(stderr, "area31-native: NICE info=%u recv errno=%d\n",
                info, errno);
        return;
    }
    limit = (size_t)length < 4U ? (size_t)length : 4U;
    fprintf(stderr, "area31-native: NICE info=%u frame-len=%zd data=",
            info, length);
    for (i = 0U; i < limit; i++)
        fprintf(stderr, "%02x", buf[i]);
    if ((size_t)length > limit)
        fputs("...", stderr);
    fputc('\n', stderr);
}

static int nice_read_executor_reply(int fd, uint16_t target,
                                    unsigned int info)
{
    unsigned char response[512];
    int multiple = 0;
    int saw_item = 0;
    unsigned int frame;

    for (frame = 0U; frame < 64U; frame++) {
        struct dniv_nice_node_reply reply;
        ssize_t got;
        int code;

        got = recv(fd, response, sizeof(response), 0);
        if (got < 1) {
            nice_dump_frame(info, response, got);
            return -1;
        }
        code = (int)(int8_t)response[0];

        if (code == 2) {
            if (multiple || saw_item) {
                nice_dump_frame(info, response, got);
                return -1;
            }
            multiple = 1;
            continue;
        }
        if (code == -128) {
            if (multiple && saw_item)
                return 0;
            nice_dump_frame(info, response, got);
            return -1;
        }
        if (code != DNIV_NICE_RET_SUCCESS) {
            nice_dump_frame(info, response, got);
            return -1;
        }
        if (dniv_nice_parse_node_reply(response, (size_t)got, &reply) ||
            reply.address != target) {
            nice_dump_frame(info, response, got);
            return -1;
        }
        saw_item = 1;
        if (!multiple)
            return 0;
    }
    fprintf(stderr, "area31-native: NICE info=%u response frame limit\n",
            info);
    return -1;
}

static int nice_query(uint16_t target, unsigned int info)
{
    static const unsigned char version[3] = {4U, 0U, 0U};
    unsigned char request[5] = {
        DNIV_NICE_FUNC_READ_INFO, 0U, 0U, 0U, 0U
    };
    struct sockaddr_dn peer;
    struct optdata_dn conndata;
    struct optdata_dn acceptdata;
    struct timeval timeout = {10, 0};
    const char *stage = "socket";
    socklen_t optlen;
    int fd;

    request[1] = (unsigned char)(info << 4);
    fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (fd < 0) {
        fprintf(stderr, "area31-native: NICE info=%u stage=%s errno=%d\n",
                info, stage, errno);
        return -1;
    }

    stage = "timeouts";
    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) ||
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout)))
        goto fail;

    memset(&conndata, 0, sizeof(conndata));
    conndata.opt_optl = cpu_to_le16_u(sizeof(version));
    memcpy(conndata.opt_data, version, sizeof(version));
    stage = "connect-data";
    if (setsockopt(fd, DNPROTO_NSP, DSO_CONDATA, &conndata, sizeof(conndata)))
        goto fail;

    memset(&peer, 0, sizeof(peer));
    peer.sdn_family = AF_DECnet;
    peer.sdn_objnum = 19U;
    peer.sdn_nodeaddrl = cpu_to_le16_u(2U);
    peer.sdn_nodeaddr[0] = (unsigned char)(target & 0xffU);
    peer.sdn_nodeaddr[1] = (unsigned char)(target >> 8);
    stage = "connect";
    if (connect(fd, (struct sockaddr *)&peer, sizeof(peer)))
        goto fail;

    memset(&acceptdata, 0, sizeof(acceptdata));
    optlen = sizeof(acceptdata);
    stage = "accept-data";
    if (getsockopt(fd, DNPROTO_NSP, DSO_CONDATA, &acceptdata, &optlen) ||
        optlen != sizeof(acceptdata) ||
        acceptdata.opt_optl != cpu_to_le16_u(sizeof(version)) ||
        memcmp(acceptdata.opt_data, version, sizeof(version)))
        goto fail;

    stage = "request";
    if (send(fd, request, sizeof(request), MSG_EOR | MSG_NOSIGNAL) !=
        (ssize_t)sizeof(request))
        goto fail;
    stage = "reply";
    if (nice_read_executor_reply(fd, target, info))
        goto fail;

    close(fd);
    return 0;
fail:
    fprintf(stderr, "area31-native: NICE info=%u stage=%s errno=%d\n",
            info, stage, errno);
    close(fd);
    return -1;
}

static int mirror_query(const char *target, int matrix)
{
    static const size_t sizes[] = {1U, 127U, 128U, 255U, 256U, 511U, 512U};
    unsigned char tx[512];
    unsigned char rx[512];
    size_t count = matrix ? sizeof(sizes) / sizeof(sizes[0]) : 1U;
    int fd;
    size_t i;

    fd = dnet_conn((char *)target, "#25", SOCK_SEQPACKET,
                   NULL, 0, NULL, NULL);
    if (fd < 0)
        return -1;
    for (i = 0U; i < count; i++) {
        size_t len = matrix ? sizes[i] : 128U;
        int got;
        size_t j;

        tx[0] = 0U;
        for (j = 1U; j < len; j++)
            tx[j] = (unsigned char)(j ^ (size_t)(0x31U + i));
        if (send(fd, tx, len, MSG_EOR | MSG_NOSIGNAL) != (ssize_t)len)
            goto fail;
        got = dnet_recv(fd, rx, len, MSG_EOR);
        if (got != (int)len || rx[0] != 1U ||
            memcmp(tx + 1, rx + 1, len - 1U))
            goto fail;
    }
    close(fd);
    return 0;
fail:
    close(fd);
    return -1;
}

int main(int argc, char **argv)
{
    const char *target_text;
    uint16_t target;

    if (argc == 3 &&
        (!strcmp(argv[1], "--nice-summary") ||
         !strcmp(argv[1], "--mirror-once"))) {
        target_text = argv[2];
        if (parse_node(target_text, &target) || (target >> 10) != 31U) {
            fputs("area31-native: invalid probe target\n", stderr);
            return 2;
        }
        if (!strcmp(argv[1], "--nice-summary"))
            return nice_query(target, DNIV_NICE_INFO_SUMMARY) ? 1 : 0;
        return mirror_query(target_text, 0) ? 1 : 0;
    }
    if (argc != 1) {
        fprintf(stderr,
                "usage: %s | --nice-summary AREA.NODE | --mirror-once AREA.NODE\n",
                argv[0]);
        return 2;
    }

    target_text = getenv("DNIV_AREA31_TARGET");
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
    if (mirror_query(target_text, 1)) {
        fputs("area31-native: MIRROR proof failed\n", stderr);
        return 1;
    }
    if (nice_query(target, DNIV_NICE_INFO_COUNTERS)) {
        fputs("area31-native: post-MIRROR NICE counters failed\n", stderr);
        return 1;
    }
    puts("area31-native: NICE summary/status/counters and MIRROR matrix pass");
    return 0;
}

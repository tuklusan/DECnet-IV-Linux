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

#define ACCESS_USER "DNIVUSER"
#define ACCESS_PASS "DNIVPASS"
#define ACCESS_ACCOUNT "DNIVACCT"
#define CONNECT_DATA "dniv-connect"

static __le16 dniv_cpu_to_le16(uint16_t value)
{
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return (__le16)value;
#else
    return (__le16)__builtin_bswap16(value);
#endif
}

static uint16_t dniv_le16_to_cpu(__le16 value)
{
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return (uint16_t)value;
#else
    return __builtin_bswap16((uint16_t)value);
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
    if (errno || end == text || *end != '\0' || node < 1U || node > 1023U)
        return -1;

    *address = (uint16_t)((area << 10) | node);
    return 0;
}

int main(int argc, char **argv)
{
    static const size_t sizes[] = { 1U, 16U, 563U, 564U, 4096U };
    unsigned char tx[4096];
    unsigned char rx[4096];
    struct sockaddr_dn peer;
    struct accessdata_dn access;
    struct accessdata_dn access_check;
    struct optdata_dn conndata;
    struct optdata_dn acceptdata;
    struct linkinfo_dn linkinfo;
    struct timeval timeout = { .tv_sec = 20, .tv_usec = 0 };
    socklen_t optlen;
    uint16_t address;
    size_t test;
    int fd;

    if (argc != 2 || parse_node(argv[1], &address)) {
        fprintf(stderr, "usage: %s AREA.NODE\n", argv[0]);
        return 2;
    }

    fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (fd < 0) {
        perror("socket(AF_DECnet)");
        return 1;
    }

    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) ||
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout))) {
        perror("setsockopt(timeout)");
        close(fd);
        return 1;
    }

    memset(&access, 0, sizeof(access));
    access.acc_userl = sizeof(ACCESS_USER) - 1U;
    memcpy(access.acc_user, ACCESS_USER, access.acc_userl);
    access.acc_passl = sizeof(ACCESS_PASS) - 1U;
    memcpy(access.acc_pass, ACCESS_PASS, access.acc_passl);
    access.acc_accl = sizeof(ACCESS_ACCOUNT) - 1U;
    memcpy(access.acc_acc, ACCESS_ACCOUNT, access.acc_accl);
    if (setsockopt(fd, DNPROTO_NSP, DSO_CONACCESS,
                   &access, sizeof(access))) {
        perror("setsockopt(DSO_CONACCESS)");
        close(fd);
        return 1;
    }

    memset(&conndata, 0, sizeof(conndata));
    conndata.opt_optl = dniv_cpu_to_le16(sizeof(CONNECT_DATA) - 1U);
    memcpy(conndata.opt_data, CONNECT_DATA, sizeof(CONNECT_DATA) - 1U);
    if (setsockopt(fd, DNPROTO_NSP, DSO_CONDATA,
                   &conndata, sizeof(conndata))) {
        perror("setsockopt(DSO_CONDATA)");
        close(fd);
        return 1;
    }

    memset(&peer, 0, sizeof(peer));
    peer.sdn_family = AF_DECnet;
    peer.sdn_objnum = 25U;
    peer.sdn_nodeaddrl = (__le16)2U;
    peer.sdn_nodeaddr[0] = (unsigned char)(address & 0xffU);
    peer.sdn_nodeaddr[1] = (unsigned char)(address >> 8);

    if (connect(fd, (struct sockaddr *)&peer, sizeof(peer))) {
        perror("connect(MIRROR)");
        close(fd);
        return 1;
    }

    memset(&access_check, 0, sizeof(access_check));
    optlen = sizeof(access_check);
    if (getsockopt(fd, DNPROTO_NSP, DSO_CONACCESS,
                   &access_check, &optlen) ||
        optlen != sizeof(access_check) ||
        memcmp(&access_check, &access, sizeof(access))) {
        fprintf(stderr, "DSO_CONACCESS roundtrip failed\n");
        close(fd);
        return 1;
    }

    memset(&acceptdata, 0, sizeof(acceptdata));
    optlen = sizeof(acceptdata);
    if (getsockopt(fd, DNPROTO_NSP, DSO_CONDATA,
                   &acceptdata, &optlen) ||
        optlen != sizeof(acceptdata) ||
        dniv_le16_to_cpu(acceptdata.opt_optl) != 2U ||
        acceptdata.opt_data[0] != 0xffU ||
        acceptdata.opt_data[1] != 0xffU) {
        fprintf(stderr,
                "DSO_CONDATA accept-data read failed len=%u data=%02x%02x optlen=%u\n",
                (unsigned int)dniv_le16_to_cpu(acceptdata.opt_optl),
                acceptdata.opt_data[0], acceptdata.opt_data[1],
                (unsigned int)optlen);
        close(fd);
        return 1;
    }

    memset(&linkinfo, 0, sizeof(linkinfo));
    optlen = sizeof(linkinfo);
    if (getsockopt(fd, DNPROTO_NSP, DSO_LINKINFO,
                   &linkinfo, &optlen) ||
        optlen != sizeof(linkinfo) ||
        linkinfo.idn_linkstate != LL_RUNNING ||
        linkinfo.idn_segsize == 0U) {
        fprintf(stderr, "DSO_LINKINFO running-state read failed\n");
        close(fd);
        return 1;
    }

    for (test = 0; test < sizeof(sizes) / sizeof(sizes[0]); test++) {
        size_t size = sizes[test];
        size_t i;
        ssize_t sent;
        ssize_t got;

        tx[0] = 0U;
        for (i = 1; i < size; i++)
            tx[i] = (unsigned char)((i * 37U + test * 19U) & 0xffU);

        sent = send(fd, tx, size, MSG_EOR | MSG_NOSIGNAL);
        if (sent != (ssize_t)size) {
            if (sent < 0)
                perror("send(MIRROR)");
            else
                fprintf(stderr, "short MIRROR send: %zd/%zu\n", sent, size);
            close(fd);
            return 1;
        }

        got = recv(fd, rx, sizeof(rx), 0);
        if (got != (ssize_t)size || rx[0] != 1U ||
            (size > 1U && memcmp(rx + 1, tx + 1, size - 1U))) {
            if (got < 0)
                perror("recv(MIRROR)");
            else
                fprintf(stderr, "bad MIRROR reply: got=%zd expected=%zu\n",
                        got, size);
            close(fd);
            return 1;
        }
    }

    close(fd);
    printf("dnmrr: pass peer=%s records=%zu options=access+condata+linkinfo\n",
           argv[1], sizeof(sizes) / sizeof(sizes[0]));
    return 0;
}

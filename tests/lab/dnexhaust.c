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
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

#include <linux/dn.h>

#define EXHAUST_PAYLOAD "DNIV-EXHAUST-PROBE"
#define NODE_UNREACHABLE 39U

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
    unsigned long area, node;

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

int main(int argc, char **argv)
{
    unsigned char tx[128];
    unsigned char rx[128];
    struct sockaddr_dn peer;
    struct optdata_dn discdata;
    struct pollfd pfd;
    struct timeval timeout = { .tv_sec = 40, .tv_usec = 0 };
    socklen_t optlen;
    uint16_t address;
    size_t payload_len;
    ssize_t sent, got;
    int fd;
    int pret;

    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc != 4 || parse_node(argv[1], &address)) {
        fprintf(stderr, "usage: %s AREA.NODE SESSION SCENARIO\n", argv[0]);
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

    memset(&peer, 0, sizeof(peer));
    peer.sdn_family = AF_DECnet;
    peer.sdn_objnum = 25U;
    peer.sdn_nodeaddrl = (__le16)2U;
    peer.sdn_nodeaddr[0] = (unsigned char)(address & 0xffU);
    peer.sdn_nodeaddr[1] = (unsigned char)(address >> 8);
    if (connect(fd, (struct sockaddr *)&peer, sizeof(peer))) {
        perror("connect(MIRROR exhaust probe)");
        close(fd);
        return 1;
    }

    printf("DNIV-INTEROP-EXHAUST-READY session=%s scenario=%s peer=%s\n",
           argv[2], argv[3], argv[1]);
    sleep(2);

    tx[0] = 0U;
    memcpy(tx + 1U, EXHAUST_PAYLOAD, sizeof(EXHAUST_PAYLOAD) - 1U);
    payload_len = sizeof(EXHAUST_PAYLOAD);
    sent = send(fd, tx, payload_len, MSG_EOR | MSG_NOSIGNAL);
    if (sent != (ssize_t)payload_len) {
        if (sent < 0)
            perror("send(MIRROR exhaust probe)");
        else
            fprintf(stderr, "short exhaust-probe send: %zd/%zu\n", sent,
                    payload_len);
        close(fd);
        return 1;
    }

    errno = 0;
    got = recv(fd, rx, sizeof(rx), 0);
    if (got != -1 || errno != EHOSTUNREACH) {
        fprintf(stderr,
                "exhaust recv expected EHOSTUNREACH: got=%zd errno=%d (%s)\n",
                got, errno, strerror(errno));
        close(fd);
        return 1;
    }

    memset(&discdata, 0, sizeof(discdata));
    optlen = sizeof(discdata);
    if (getsockopt(fd, DNPROTO_NSP, DSO_DISDATA, &discdata, &optlen) ||
        optlen != sizeof(discdata) ||
        dniv_le16_to_cpu(discdata.opt_status) != NODE_UNREACHABLE ||
        dniv_le16_to_cpu(discdata.opt_optl) != 0U) {
        fprintf(stderr,
                "exhaust DSO_DISDATA mismatch status=%u len=%u optlen=%u\n",
                (unsigned int)dniv_le16_to_cpu(discdata.opt_status),
                (unsigned int)dniv_le16_to_cpu(discdata.opt_optl),
                (unsigned int)optlen);
        close(fd);
        return 1;
    }

    memset(&pfd, 0, sizeof(pfd));
    pfd.fd = fd;
    pfd.events = POLLIN | POLLOUT;
    pret = poll(&pfd, 1, 0);
    if (pret != 1 || !(pfd.revents & POLLERR) || !(pfd.revents & POLLHUP)) {
        fprintf(stderr, "exhaust poll mismatch ret=%d revents=0x%x\n",
                pret, pfd.revents);
        close(fd);
        return 1;
    }

    close(fd);
    printf("dnexhaust: pass peer=%s reason=%u\n",
           argv[1], NODE_UNREACHABLE);
    return 0;
}

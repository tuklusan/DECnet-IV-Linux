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

#define CI_EXHAUST_DATA "CI-EXHAUST"
#define CI_RECOVER_DATA "CI-RECOVER"
#define RECOVER_PAYLOAD "DNIV-CI-RECOVER-DATA"

static __le16 cpu_le16(uint16_t v)
{
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return (__le16)v;
#else
    return (__le16)__builtin_bswap16(v);
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

static void fill_peer(struct sockaddr_dn *peer, uint16_t address)
{
    memset(peer, 0, sizeof(*peer));
    peer->sdn_family = AF_DECnet;
    peer->sdn_objnum = 25U;
    peer->sdn_nodeaddrl = (__le16)2U;
    peer->sdn_nodeaddr[0] = (unsigned char)(address & 0xffU);
    peer->sdn_nodeaddr[1] = (unsigned char)(address >> 8);
}

static int make_socket(int seconds, const char *condata)
{
    struct timeval tv = { .tv_sec = seconds, .tv_usec = 0 };
    struct optdata_dn opt;
    size_t n = strlen(condata);
    int fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);

    if (fd < 0)
        return -1;
    if (n > DN_MAXOPTL) {
        close(fd);
        errno = EINVAL;
        return -1;
    }
    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv)) ||
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv))) {
        close(fd);
        return -1;
    }

    memset(&opt, 0, sizeof(opt));
    opt.opt_optl = cpu_le16((uint16_t)n);
    memcpy(opt.opt_data, condata, n);
    if (setsockopt(fd, DNPROTO_NSP, DSO_CONDATA, &opt, sizeof(opt))) {
        close(fd);
        return -1;
    }
    return fd;
}

static int recover(uint16_t address)
{
    struct sockaddr_dn peer;
    unsigned char tx[128], rx[128];
    const size_t n = sizeof(RECOVER_PAYLOAD);
    ssize_t got;
    int fd = make_socket(20, CI_RECOVER_DATA);

    if (fd < 0)
        return -1;
    fill_peer(&peer, address);
    if (connect(fd, (struct sockaddr *)&peer, sizeof(peer))) {
        close(fd);
        return -1;
    }
    tx[0] = 0U;
    memcpy(tx + 1U, RECOVER_PAYLOAD, n - 1U);
    if (send(fd, tx, n, MSG_EOR | MSG_NOSIGNAL) != (ssize_t)n) {
        close(fd);
        return -1;
    }
    got = recv(fd, rx, sizeof(rx), 0);
    if (got != (ssize_t)n || rx[0] != 1U ||
        memcmp(rx + 1U, tx + 1U, n - 1U)) {
        close(fd);
        errno = EPROTO;
        return -1;
    }
    close(fd);
    return 0;
}

int main(int argc, char **argv)
{
    struct sockaddr_dn peer;
    uint16_t address;
    int fd;

    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc != 4 || parse_node(argv[1], &address)) {
        fprintf(stderr, "usage: %s AREA.NODE SESSION SCENARIO\n", argv[0]);
        return 2;
    }

    fd = make_socket(45, CI_EXHAUST_DATA);
    if (fd < 0) {
        perror("CI loss setup");
        return 1;
    }
    fill_peer(&peer, address);
    printf("DNIV-INTEROP-CI-EXHAUST-READY session=%s scenario=%s peer=%s\n",
           argv[2], argv[3], argv[1]);
    sleep(2);

    errno = 0;
    if (connect(fd, (struct sockaddr *)&peer, sizeof(peer)) != -1 ||
        errno != EHOSTUNREACH) {
        fprintf(stderr, "CI exhaustion expected EHOSTUNREACH errno=%d (%s)\n",
                errno, strerror(errno));
        close(fd);
        return 1;
    }
    close(fd);
    printf("DNIV-INTEROP-CI-EXHAUSTED session=%s scenario=%s errno=%d\n",
           argv[2], argv[3], EHOSTUNREACH);

    sleep(5);
    if (recover(address)) {
        fprintf(stderr, "CI recovery failed errno=%d (%s)\n",
                errno, strerror(errno));
        return 1;
    }
    printf("dnconnectloss: pass peer=%s errno=%d recovery=1\n",
           argv[1], EHOSTUNREACH);
    return 0;
}

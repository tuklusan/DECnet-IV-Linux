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

#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <linux/dn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

#ifndef AF_DECnet
#define AF_DECnet 12
#endif

#define DNLOGIN_CTERM_OBJECT 42U
#define FOUND_BIND 1U
#define FOUND_BIND_ACCEPT 4U
#define FOUND_COMMON_DATA 9U
#define CTERM_INITIATE 1U

static uint16_t get_le16(const unsigned char *p)
{
    return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}

static void put_le16(unsigned char *p, uint16_t v)
{
    p[0] = (unsigned char)(v & 0xffU);
    p[1] = (unsigned char)(v >> 8);
}

static int parse_node(const char *text, uint16_t *address)
{
    char *end;
    unsigned long area;
    unsigned long node;

    errno = 0;
    area = strtoul(text, &end, 10);
    if (errno || end == text || *end != '.' || area > 63U)
        return -1;
    text = end + 1;
    errno = 0;
    node = strtoul(text, &end, 10);
    if (errno || end == text || *end != '\0' || node == 0U || node > 1023U)
        return -1;
    *address = (uint16_t)((area << 10) | node);
    return 0;
}

static size_t make_bind_accept(unsigned char out[17])
{
    memset(out, 0, 17);
    out[0] = FOUND_BIND_ACCEPT;
    out[1] = 2U;
    out[2] = 4U;
    out[3] = 0U;
    put_le16(out + 4, 193U);
    return 17U;
}

static size_t make_cterm_initiate(unsigned char *out, size_t cap)
{
    static const unsigned char body[] = {
        CTERM_INITIATE, 0x00, 0x01, 0x04, 0x00,
        'd','n','l','o','g','i','n',' ',
        0x01,0x02,0x00,0x02,
        0x02,0x02,0xf4,0x03,
        0x03,0x04,0xfe,0x7f,0x00,0x00,
        0x00
    };
    size_t need = 4U + sizeof(body);

    if (cap < need)
        return 0U;
    out[0] = FOUND_COMMON_DATA;
    out[1] = 0U;
    put_le16(out + 2, (uint16_t)sizeof(body));
    memcpy(out + 4, body, sizeof(body));
    return need;
}

static int validate_bind(const unsigned char *buf, size_t len)
{
    return len >= 5U && buf[0] == FOUND_BIND;
}

static int validate_cterm_initiate(const unsigned char *buf, size_t len)
{
    uint16_t inner;

    if (len < 5U || buf[0] != FOUND_COMMON_DATA)
        return -1;
    inner = get_le16(buf + 2);
    if ((size_t)inner + 4U > len || inner < 1U)
        return -1;
    return buf[4] == CTERM_INITIATE ? 0 : -1;
}

static int selftest(void)
{
    unsigned char bind[17];
    unsigned char init[64];
    unsigned char peer_bind[] = { FOUND_BIND, 2, 4, 0, 7 };
    unsigned char peer_init[] = { FOUND_COMMON_DATA, 0, 1, 0, CTERM_INITIATE };
    uint16_t addr;

    if (parse_node("31.70", &addr) || addr != (uint16_t)((31U << 10) | 70U))
        return 1;
    if (!parse_node("64.1", &addr) || !parse_node("31.0", &addr))
        return 1;
    if (make_bind_accept(bind) != sizeof(bind) || bind[0] != FOUND_BIND_ACCEPT ||
        get_le16(bind + 4) != 193U)
        return 1;
    if (!make_cterm_initiate(init, sizeof(init)) ||
        init[0] != FOUND_COMMON_DATA || get_le16(init + 2) != 28U ||
        init[4] != CTERM_INITIATE)
        return 1;
    if (!validate_bind(peer_bind, sizeof(peer_bind)) ||
        validate_cterm_initiate(peer_init, sizeof(peer_init)))
        return 1;
    puts("dnlogin protocol selftest passed");
    return 0;
}

static int probe(const char *node_text)
{
    struct sockaddr_dn peer;
    struct timeval tv = { 15, 0 };
    unsigned char buf[1024];
    unsigned char out[64];
    uint16_t address;
    ssize_t got;
    size_t len;
    int fd;

    if (parse_node(node_text, &address)) {
        fprintf(stderr, "dnlogin: invalid DECnet node %s\n", node_text);
        return 2;
    }
    fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (fd < 0) {
        perror("dnlogin: socket");
        return 1;
    }
    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv)) ||
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv))) {
        perror("dnlogin: timeout");
        close(fd);
        return 1;
    }
    memset(&peer, 0, sizeof(peer));
    peer.sdn_family = AF_DECnet;
    peer.sdn_objnum = DNLOGIN_CTERM_OBJECT;
    peer.sdn_nodeaddrl = (__le16)2U;
    peer.sdn_nodeaddr[0] = (unsigned char)(address & 0xffU);
    peer.sdn_nodeaddr[1] = (unsigned char)(address >> 8);
    if (connect(fd, (struct sockaddr *)&peer, sizeof(peer))) {
        perror("dnlogin: connect");
        close(fd);
        return 1;
    }
    got = recv(fd, buf, sizeof(buf), 0);
    if (got <= 0 || !validate_bind(buf, (size_t)got)) {
        fprintf(stderr, "dnlogin: invalid Foundation bind\n");
        close(fd);
        return 1;
    }
    len = make_bind_accept(out);
    if (send(fd, out, len, MSG_EOR | MSG_NOSIGNAL) != (ssize_t)len) {
        perror("dnlogin: bind accept");
        close(fd);
        return 1;
    }
    got = recv(fd, buf, sizeof(buf), 0);
    if (got <= 0 || validate_cterm_initiate(buf, (size_t)got)) {
        fprintf(stderr, "dnlogin: missing CTERM initiate\n");
        close(fd);
        return 1;
    }
    len = make_cterm_initiate(out, sizeof(out));
    if (!len || send(fd, out, len, MSG_EOR | MSG_NOSIGNAL) != (ssize_t)len) {
        perror("dnlogin: CTERM initiate");
        close(fd);
        return 1;
    }
    printf("dnlogin: CTERM Foundation handshake complete with %s\n", node_text);
    close(fd);
    return 0;
}

int main(int argc, char **argv)
{
    if (argc == 2 && strcmp(argv[1], "--selftest") == 0)
        return selftest();
    if (argc == 3 && strcmp(argv[1], "--probe") == 0)
        return probe(argv[2]);
    fprintf(stderr, "usage: %s --probe AREA.NODE\n       %s --selftest\n",
            argv[0], argv[0]);
    return 2;
}

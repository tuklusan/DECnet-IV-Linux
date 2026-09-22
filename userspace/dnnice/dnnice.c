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

static __le16 cpu_to_le16_u(uint16_t value)
{
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return (__le16)value;
#else
    return (__le16)__builtin_bswap16(value);
#endif
}

static uint16_t le16_to_cpu_u(__le16 value)
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
    static const unsigned char version[] = { 4U, 0U, 0U };
    static const unsigned char request[] = { 0x14U, 0x00U, 0x00U, 0x00U, 0x00U };
    struct dniv_nice_node_reply reply;
    struct sockaddr_dn peer;
    struct optdata_dn conndata;
    struct optdata_dn acceptdata;
    struct timeval timeout = { .tv_sec = 20, .tv_usec = 0 };
    unsigned char response[512];
    socklen_t optlen;
    uint16_t address;
    ssize_t got;
    int fd;

    if (argc != 2 || parse_node(argv[1], &address)) {
        fprintf(stderr, "usage: %s AREA.NODE\n", argv[0]);
        return 2;
    }
    fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (fd < 0) {
        perror("dnnice: socket");
        return 1;
    }
    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) ||
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout))) {
        perror("dnnice: timeout");
        close(fd);
        return 1;
    }
    memset(&conndata, 0, sizeof(conndata));
    conndata.opt_optl = cpu_to_le16_u(sizeof(version));
    memcpy(conndata.opt_data, version, sizeof(version));
    if (setsockopt(fd, DNPROTO_NSP, DSO_CONDATA, &conndata, sizeof(conndata))) {
        perror("dnnice: DSO_CONDATA");
        close(fd);
        return 1;
    }
    memset(&peer, 0, sizeof(peer));
    peer.sdn_family = AF_DECnet;
    peer.sdn_objnum = 19U;
    peer.sdn_nodeaddrl = cpu_to_le16_u(2U);
    peer.sdn_nodeaddr[0] = (unsigned char)(address & 0xffU);
    peer.sdn_nodeaddr[1] = (unsigned char)(address >> 8);
    if (connect(fd, (struct sockaddr *)&peer, sizeof(peer))) {
        perror("dnnice: connect");
        close(fd);
        return 1;
    }
    memset(&acceptdata, 0, sizeof(acceptdata));
    optlen = sizeof(acceptdata);
    if (getsockopt(fd, DNPROTO_NSP, DSO_CONDATA, &acceptdata, &optlen) ||
        optlen != sizeof(acceptdata) ||
        le16_to_cpu_u(acceptdata.opt_optl) != sizeof(version) ||
        memcmp(acceptdata.opt_data, version, sizeof(version))) {
        fprintf(stderr, "dnnice: incompatible NML accept data\n");
        close(fd);
        return 1;
    }
    if (send(fd, request, sizeof(request), MSG_EOR | MSG_NOSIGNAL) !=
        (ssize_t)sizeof(request)) {
        perror("dnnice: send");
        close(fd);
        return 1;
    }
    got = recv(fd, response, sizeof(response), 0);
    if (got <= 0 || dniv_nice_parse_node_reply(response, (size_t)got, &reply)) {
        if (got < 0)
            perror("dnnice: recv");
        else
            fprintf(stderr, "dnnice: malformed READ NODE reply\n");
        close(fd);
        return 1;
    }
    close(fd);
    printf("Executor node = %u.%u (%s)",
           reply.address >> 10, reply.address & 1023U, reply.name);
    if (reply.has_state)
        printf(" state=%u", reply.state);
    if (reply.has_active_links)
        printf(" active-links=%u", reply.active_links);
    putchar('\n');
    return 0;
}

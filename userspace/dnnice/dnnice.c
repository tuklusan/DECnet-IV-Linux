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

static int entity_offset(const unsigned char *buf, size_t length,
                         size_t *offset, uint16_t *address,
                         char *name, size_t name_size)
{
    size_t name_len;
    size_t off;

    if (!buf || !offset || !address || !name || name_size < 2U ||
        length < 7U || buf[0] != DNIV_NICE_RET_SUCCESS ||
        buf[1] != 0xffU || buf[2] != 0xffU || buf[3] != 0U)
        return -1;

    *address = (uint16_t)((uint16_t)buf[4] |
                          ((uint16_t)buf[5] << 8));
    name_len = buf[6] & 0x7fU;
    if (name_len >= name_size || length < 7U + name_len)
        return -1;
    off = 7U;
    if (name_len) {
        memcpy(name, buf + off, name_len);
        name[name_len] = '\0';
        off += name_len;
    } else {
        name[0] = '\0';
    }
    *offset = off;
    return 0;
}

static int print_characteristics(const unsigned char *buf, size_t length)
{
    uint16_t address;
    char name[128];
    size_t off;
    uint16_t param;
    size_t value_len;

    if (entity_offset(buf, length, &off, &address, name, sizeof(name)) ||
        length - off < 4U)
        return -1;
    param = (uint16_t)((uint16_t)buf[off] |
                       ((uint16_t)buf[off + 1U] << 8));
    if (param != DNIV_NICE_PARAM_IDENTIFICATION ||
        buf[off + 2U] != DNIV_NICE_TYPE_ASCII)
        return -1;
    value_len = buf[off + 3U];
    if (length - off < 4U + value_len)
        return -1;

    printf("Executor node = %u.%u (%s) identification=",
           address >> 10, address & 1023U, name);
    fwrite(buf + off + 4U, 1U, value_len, stdout);
    putchar('\n');
    return 0;
}

static int print_counters(const unsigned char *buf, size_t length)
{
    static const uint16_t expected[] = { 608U, 609U, 610U, 611U };
    uint32_t values[4];
    uint16_t address;
    char name[128];
    size_t off;
    size_t i;

    if (entity_offset(buf, length, &off, &address, name, sizeof(name)))
        return -1;
    for (i = 0U; i < 4U; i++) {
        uint16_t encoded;

        if (length - off < 6U)
            return -1;
        encoded = (uint16_t)((uint16_t)buf[off] |
                             ((uint16_t)buf[off + 1U] << 8));
        if (encoded != (uint16_t)(expected[i] | 0xe000U))
            return -1;
        values[i] = (uint32_t)buf[off + 2U] |
                    ((uint32_t)buf[off + 3U] << 8) |
                    ((uint32_t)buf[off + 4U] << 16) |
                    ((uint32_t)buf[off + 5U] << 24);
        off += 6U;
    }

    printf("Executor node = %u.%u (%s) "
           "rx-bytes=%u tx-bytes=%u rx-messages=%u tx-messages=%u\n",
           address >> 10, address & 1023U, name,
           values[0], values[1], values[2], values[3]);
    return 0;
}

int main(int argc, char **argv)
{
    static const unsigned char version[] = { 4U, 0U, 0U };
    struct dniv_nice_node_reply reply;
    struct sockaddr_dn peer;
    struct optdata_dn conndata;
    struct optdata_dn acceptdata;
    struct timeval timeout = { .tv_sec = 20, .tv_usec = 0 };
    unsigned char request[] = { 0x14U, 0x00U, 0x00U, 0x00U, 0x00U };
    unsigned char response[512];
    const char *query = "summary";
    socklen_t optlen;
    uint16_t address;
    ssize_t got;
    int fd;

    if (argc < 2 || argc > 3 || parse_node(argv[1], &address)) {
        fprintf(stderr,
                "usage: %s AREA.NODE [summary|status|characteristics|counters]\n",
                argv[0]);
        return 2;
    }
    if (argc == 3)
        query = argv[2];
    if (strcmp(query, "summary") == 0) {
        request[1] = 0x00U;
    } else if (strcmp(query, "status") == 0) {
        request[1] = 0x10U;
    } else if (strcmp(query, "characteristics") == 0) {
        request[1] = 0x20U;
    } else if (strcmp(query, "counters") == 0) {
        request[1] = 0x30U;
    } else {
        fprintf(stderr,
                "usage: %s AREA.NODE [summary|status|characteristics|counters]\n",
                argv[0]);
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
    if (got <= 0) {
        if (got < 0)
            perror("dnnice: recv");
        else
            fprintf(stderr, "dnnice: empty NICE reply\n");
        close(fd);
        return 1;
    }

    if (strcmp(query, "characteristics") == 0) {
        if (print_characteristics(response, (size_t)got)) {
            fprintf(stderr, "dnnice: malformed characteristics reply\n");
            close(fd);
            return 1;
        }
    } else if (strcmp(query, "counters") == 0) {
        if (print_counters(response, (size_t)got)) {
            fprintf(stderr, "dnnice: malformed counters reply\n");
            close(fd);
            return 1;
        }
    } else {
        if (dniv_nice_parse_node_reply(response, (size_t)got, &reply)) {
            fprintf(stderr, "dnnice: malformed READ NODE reply\n");
            close(fd);
            return 1;
        }
        printf("Executor node = %u.%u (%s)",
               reply.address >> 10, reply.address & 1023U, reply.name);
        if (reply.has_state)
            printf(" state=%u", reply.state);
        if (reply.has_active_links)
            printf(" active-links=%u", reply.active_links);
        putchar('\n');
    }
    close(fd);
    return 0;
}

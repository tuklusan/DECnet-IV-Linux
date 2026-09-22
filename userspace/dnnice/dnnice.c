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

static int reply_offset(const unsigned char *buf, size_t length,
                        size_t *offset)
{
    size_t off;

    if (!buf || !offset || length < 4U ||
        buf[0] != DNIV_NICE_RET_SUCCESS)
        return -1;
    off = 4U + (size_t)buf[3];
    if (off > length)
        return -1;
    *offset = off;
    return 0;
}

static int entity_offset(const unsigned char *buf, size_t length,
                         size_t *offset, uint16_t *address,
                         char *name, size_t name_size)
{
    size_t name_len;
    size_t off;

    if (!address || !name || name_size < 2U ||
        reply_offset(buf, length, &off) || length - off < 3U)
        return -1;

    *address = (uint16_t)((uint16_t)buf[off] |
                          ((uint16_t)buf[off + 1U] << 8));
    off += 2U;
    name_len = buf[off++] & 0x7fU;
    if (name_len >= name_size || length - off < name_len)
        return -1;
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

static int circuit_entity_offset(const unsigned char *buf, size_t length,
                                 size_t *offset, char *name,
                                 size_t name_size)
{
    size_t name_len;
    size_t off;

    if (!offset || !name || name_size < 2U ||
        reply_offset(buf, length, &off) || off >= length)
        return -1;
    name_len = buf[off++] & 0x7fU;
    if (!name_len || name_len >= name_size || length - off < name_len)
        return -1;
    memcpy(name, buf + off, name_len);
    name[name_len] = '\0';
    off += name_len;
    *offset = off;
    return 0;
}

static int nice_value_length(const unsigned char *buf, size_t length,
                             size_t *value_length)
{
    unsigned char type;

    if (!buf || !value_length || !length)
        return -1;
    type = buf[0];
    if (type == 0x20U || type == 0x40U) {
        if (length < 2U || length < 2U + (size_t)buf[1])
            return -1;
        *value_length = 2U + (size_t)buf[1];
        return 0;
    }
    if (type >= 0x01U && type <= 0x3fU && type != 0x20U &&
        type != 0x30U) {
        size_t width = (size_t)(type & 0x0fU);

        if (!width || length < 1U + width)
            return -1;
        *value_length = 1U + width;
        return 0;
    }
    if (type >= 0x81U && type <= 0x9fU) {
        size_t width = (size_t)(type & 0x1fU);

        if (!width || length < 1U + width)
            return -1;
        *value_length = 1U + width;
        return 0;
    }
    if (type >= 0xc1U && type <= 0xdfU) {
        size_t count = (size_t)(type & 0x1fU);
        size_t off = 1U;
        size_t i;

        if (!count)
            return -1;
        for (i = 0U; i < count; i++) {
            size_t component_len;

            if (off >= length ||
                nice_value_length(buf + off, length - off, &component_len))
                return -1;
            off += component_len;
        }
        *value_length = off;
        return 0;
    }
    return -1;
}

static int print_characteristics(const unsigned char *buf, size_t length)
{
    uint16_t address;
    char name[128];
    const unsigned char *ident = NULL;
    size_t ident_len = 0U;
    size_t off;

    if (entity_offset(buf, length, &off, &address, name, sizeof(name)))
        return -1;

    while (length - off >= 3U) {
        uint16_t param = (uint16_t)((uint16_t)buf[off] |
                                    ((uint16_t)buf[off + 1U] << 8));
        size_t encoded_len;

        off += 2U;
        if (nice_value_length(buf + off, length - off, &encoded_len))
            return -1;
        if (param == DNIV_NICE_PARAM_IDENTIFICATION &&
            buf[off] == DNIV_NICE_TYPE_ASCII) {
            ident_len = buf[off + 1U];
            ident = buf + off + 2U;
        }
        off += encoded_len;
    }
    if (off != length || !ident)
        return -1;

    printf("Executor node = %u.%u (%s) identification=",
           address >> 10, address & 1023U, name);
    fwrite(ident, 1U, ident_len, stdout);
    putchar('\n');
    return 0;
}

static int decode_counter_stream(const unsigned char *buf, size_t length,
                                 size_t off, const uint16_t *expected,
                                 size_t expected_count, uint32_t *values)
{
    unsigned int found = 0U;

    if (!buf || !expected || !values || !expected_count ||
        expected_count > 31U)
        return -1;

    while (length - off >= 3U) {
        uint16_t encoded = (uint16_t)((uint16_t)buf[off] |
                                      ((uint16_t)buf[off + 1U] << 8));
        uint16_t param = encoded & 0x0fffU;
        uint16_t kind = encoded & 0xf000U;
        size_t width;
        size_t value_off = off + 2U;
        size_t i;
        uint32_t value = 0U;

        switch (kind) {
        case 0xa000U:
            width = 1U;
            break;
        case 0xc000U:
            width = 2U;
            break;
        case 0xe000U:
            width = 4U;
            break;
        case 0xb000U:
            width = 1U;
            value_off += 2U;
            break;
        case 0xd000U:
            width = 2U;
            value_off += 2U;
            break;
        case 0xf000U:
            width = 4U;
            value_off += 2U;
            break;
        default:
            return -1;
        }
        if (value_off > length || length - value_off < width)
            return -1;
        for (i = 0U; i < width; i++)
            value |= (uint32_t)buf[value_off + i] << (8U * i);
        for (i = 0U; i < expected_count; i++) {
            if (param == expected[i]) {
                values[i] = value;
                found |= 1U << i;
                break;
            }
        }
        off = value_off + width;
    }

    if (off != length ||
        found != ((1U << expected_count) - 1U))
        return -1;
    return 0;
}

static int print_counters(const unsigned char *buf, size_t length)
{
    static const uint16_t expected[] = { 608U, 609U, 610U, 611U };
    uint32_t values[4] = { 0U, 0U, 0U, 0U };
    uint16_t address;
    char name[128];
    size_t off;

    if (entity_offset(buf, length, &off, &address, name, sizeof(name)) ||
        decode_counter_stream(buf, length, off, expected,
                              sizeof(expected) / sizeof(expected[0]), values))
        return -1;

    printf("Executor node = %u.%u (%s) "
           "rx-bytes=%u tx-bytes=%u rx-messages=%u tx-messages=%u\n",
           address >> 10, address & 1023U, name,
           values[0], values[1], values[2], values[3]);
    return 0;
}

static int print_remote_node(const unsigned char *buf, size_t length)
{
    uint16_t address;
    uint16_t cost = 0U;
    uint16_t next_node = 0U;
    unsigned int state = 0U;
    unsigned int node_type = 0U;
    unsigned int hops = 0U;
    unsigned int have_state = 0U;
    unsigned int have_type = 0U;
    unsigned int have_cost = 0U;
    unsigned int have_hops = 0U;
    unsigned int have_circuit = 0U;
    unsigned int have_next = 0U;
    char name[128];
    char circuit[128] = "";
    size_t off;

    if (entity_offset(buf, length, &off, &address, name, sizeof(name)))
        return -1;

    while (length - off >= 3U) {
        uint16_t param = (uint16_t)((uint16_t)buf[off] |
                                    ((uint16_t)buf[off + 1U] << 8));
        const unsigned char *value;
        size_t encoded_len;

        off += 2U;
        value = buf + off;
        if (nice_value_length(value, length - off, &encoded_len))
            return -1;

        if (param == 0U && value[0] == 0x81U && encoded_len >= 2U) {
            state = value[1];
            have_state = 1U;
        } else if (param == 810U && value[0] == 0x81U &&
                   encoded_len >= 2U) {
            node_type = value[1];
            have_type = 1U;
        } else if (param == 820U && value[0] == 0x02U &&
                   encoded_len == 3U) {
            cost = (uint16_t)((uint16_t)value[1] |
                              ((uint16_t)value[2] << 8));
            have_cost = 1U;
        } else if (param == 821U && value[0] == 0x01U &&
                   encoded_len == 2U) {
            hops = value[1];
            have_hops = 1U;
        } else if (param == 822U && value[0] == DNIV_NICE_TYPE_ASCII &&
                   encoded_len >= 2U &&
                   (size_t)value[1] + 2U == encoded_len &&
                   (size_t)value[1] < sizeof(circuit)) {
            memcpy(circuit, value + 2U, value[1]);
            circuit[value[1]] = '\0';
            have_circuit = 1U;
        } else if (param == 830U && value[0] == 0xc1U &&
                   encoded_len == 4U && value[1] == 0x02U) {
            next_node = (uint16_t)((uint16_t)value[2] |
                                   ((uint16_t)value[3] << 8));
            have_next = 1U;
        }
        off += encoded_len;
    }
    if (off != length || !have_state)
        return -1;

    printf("Node = %u.%u", address >> 10, address & 1023U);
    if (name[0] != '\0')
        printf(" (%s)", name);
    printf(" state=%u", state);
    if (have_type)
        printf(" type=%u", node_type);
    if (have_cost)
        printf(" cost=%u", cost);
    if (have_hops)
        printf(" hops=%u", hops);
    if (have_circuit)
        printf(" circuit=%s", circuit);
    if (have_next)
        printf(" next-node=%u.%u", next_node >> 10, next_node & 1023U);
    putchar('\n');
    return 0;
}

static int print_circuit_status(const unsigned char *buf, size_t length)
{
    uint16_t adjacent = 0U;
    uint16_t block_size = 0U;
    unsigned int state = 0U;
    unsigned int have_state = 0U;
    unsigned int have_adjacent = 0U;
    unsigned int have_block = 0U;
    char name[128];
    size_t off;

    if (circuit_entity_offset(buf, length, &off, name, sizeof(name)))
        return -1;

    while (length - off >= 3U) {
        uint16_t param = (uint16_t)((uint16_t)buf[off] |
                                    ((uint16_t)buf[off + 1U] << 8));
        const unsigned char *value;
        size_t encoded_len;

        off += 2U;
        value = buf + off;
        if (nice_value_length(value, length - off, &encoded_len))
            return -1;
        if (param == 0U && value[0] == 0x81U && encoded_len >= 2U) {
            state = value[1];
            have_state = 1U;
        } else if (param == 800U && value[0] == 0xc1U &&
                   encoded_len == 4U && value[1] == 0x02U) {
            adjacent = (uint16_t)((uint16_t)value[2] |
                                  ((uint16_t)value[3] << 8));
            have_adjacent = 1U;
        } else if (param == 810U && value[0] == 0x02U &&
                   encoded_len == 3U) {
            block_size = (uint16_t)((uint16_t)value[1] |
                                    ((uint16_t)value[2] << 8));
            have_block = 1U;
        }
        off += encoded_len;
    }
    if (off != length || !have_state)
        return -1;

    printf("Circuit = %s state=%u", name, state);
    if (have_adjacent)
        printf(" adjacent=%u.%u", adjacent >> 10, adjacent & 1023U);
    if (have_block)
        printf(" block-size=%u", block_size);
    putchar('\n');
    return 0;
}

static int print_circuit_counters(const unsigned char *buf, size_t length)
{
    static const uint16_t expected[] = { 1000U, 1001U, 1010U, 1011U };
    uint32_t values[4] = { 0U, 0U, 0U, 0U };
    char name[128];
    size_t off;

    if (circuit_entity_offset(buf, length, &off, name, sizeof(name)) ||
        decode_counter_stream(buf, length, off, expected,
                              sizeof(expected) / sizeof(expected[0]), values))
        return -1;

    printf("Circuit = %s rx-bytes=%u tx-bytes=%u "
           "rx-blocks=%u tx-blocks=%u\n",
           name, values[0], values[1], values[2], values[3]);
    return 0;
}

enum dnnice_query_entity {
    QUERY_EXECUTOR,
    QUERY_NODE,
    QUERY_CIRCUIT,
    QUERY_NODES,
    QUERY_CIRCUITS
};

static int receive_multiple(int fd, enum dnnice_query_entity entity,
                            unsigned int info)
{
    unsigned char response[512];
    unsigned int saw_header = 0U;

    for (;;) {
        ssize_t got = recv(fd, response, sizeof(response), 0);
        int bad;

        if (got <= 0) {
            if (got < 0)
                perror("dnnice: recv");
            else
                fprintf(stderr, "dnnice: truncated multiple NICE reply\n");
            return -1;
        }
        if (!saw_header) {
            if (got == 1 && response[0] == 2U) {
                saw_header = 1U;
                continue;
            }
            if ((int8_t)response[0] < 0) {
                fprintf(stderr, "dnnice: NICE error %d\n",
                        (int8_t)response[0]);
                return -1;
            }
            if (response[0] == DNIV_NICE_RET_SUCCESS) {
                if (entity == QUERY_NODES)
                    bad = print_remote_node(response, (size_t)got);
                else if (info == DNIV_NICE_INFO_STATUS)
                    bad = print_circuit_status(response, (size_t)got);
                else
                    bad = print_circuit_counters(response, (size_t)got);
                return bad ? -1 : 0;
            }
            fprintf(stderr, "dnnice: missing multiple-items header\n");
            return -1;
        }
        if (got == 1 && response[0] == 0x80U)
            return 0;
        if ((int8_t)response[0] < 0) {
            fprintf(stderr, "dnnice: NICE error %d\n",
                    (int8_t)response[0]);
            return -1;
        }

        if (entity == QUERY_NODES)
            bad = print_remote_node(response, (size_t)got);
        else if (info == DNIV_NICE_INFO_STATUS)
            bad = print_circuit_status(response, (size_t)got);
        else
            bad = print_circuit_counters(response, (size_t)got);
        if (bad) {
            fprintf(stderr, "dnnice: malformed multiple-item reply\n");
            return -1;
        }
    }
}

int main(int argc, char **argv)
{
    static const unsigned char version[] = { 4U, 0U, 0U };
    struct dniv_nice_node_reply reply;
    struct sockaddr_dn peer;
    struct optdata_dn conndata;
    struct optdata_dn acceptdata;
    struct timeval timeout = { .tv_sec = 20, .tv_usec = 0 };
    unsigned char request[256];
    unsigned char response[512];
    enum dnnice_query_entity entity = QUERY_EXECUTOR;
    const char *query = "summary";
    const char *circuit_name = NULL;
    size_t request_len = 0U;
    socklen_t optlen;
    uint16_t address;
    uint16_t target_node = 0U;
    unsigned int info = DNIV_NICE_INFO_SUMMARY;
    ssize_t got;
    int fd;

    if (argc < 2 || argc > 5 || parse_node(argv[1], &address)) {
        fprintf(stderr,
                "usage: %s AREA.NODE [summary|status|characteristics|counters]\n"
                "       %s AREA.NODE node AREA.NODE [summary|status]\n"
                "       %s AREA.NODE circuit NAME [status|counters]\n"
                "       %s AREA.NODE nodes known|active|adjacent [summary|status]\n"
                "       %s AREA.NODE circuits known|active [status|counters]\n",
                argv[0], argv[0], argv[0], argv[0], argv[0]);
        return 2;
    }

    if (argc >= 4 && strcmp(argv[2], "node") == 0) {
        entity = QUERY_NODE;
        if (parse_node(argv[3], &target_node)) {
            fprintf(stderr, "dnnice: invalid target node %s\n", argv[3]);
            return 2;
        }
        query = argc == 5 ? argv[4] : "status";
        if (strcmp(query, "summary") == 0)
            info = DNIV_NICE_INFO_SUMMARY;
        else if (strcmp(query, "status") == 0)
            info = DNIV_NICE_INFO_STATUS;
        else {
            fprintf(stderr, "dnnice: node query must be summary or status\n");
            return 2;
        }
    } else if (argc >= 4 && strcmp(argv[2], "circuit") == 0) {
        size_t name_len = strlen(argv[3]);

        entity = QUERY_CIRCUIT;
        circuit_name = argv[3];
        if (!name_len || name_len > 127U) {
            fprintf(stderr, "dnnice: invalid circuit name\n");
            return 2;
        }
        query = argc == 5 ? argv[4] : "status";
        if (strcmp(query, "status") == 0)
            info = DNIV_NICE_INFO_STATUS;
        else if (strcmp(query, "counters") == 0)
            info = DNIV_NICE_INFO_COUNTERS;
        else {
            fprintf(stderr, "dnnice: circuit query must be status or counters\n");
            return 2;
        }
    } else if (argc >= 4 && strcmp(argv[2], "nodes") == 0) {
        entity = QUERY_NODES;
        if (strcmp(argv[3], "known") == 0)
            request[2] = 0xffU;
        else if (strcmp(argv[3], "active") == 0)
            request[2] = 0xfeU;
        else if (strcmp(argv[3], "adjacent") == 0)
            request[2] = 0xfcU;
        else {
            fprintf(stderr,
                    "dnnice: nodes selector must be known, active, or adjacent\n");
            return 2;
        }
        query = argc == 5 ? argv[4] : "status";
        if (strcmp(query, "summary") == 0)
            info = DNIV_NICE_INFO_SUMMARY;
        else if (strcmp(query, "status") == 0)
            info = DNIV_NICE_INFO_STATUS;
        else {
            fprintf(stderr, "dnnice: nodes query must be summary or status\n");
            return 2;
        }
    } else if (argc >= 4 && strcmp(argv[2], "circuits") == 0) {
        entity = QUERY_CIRCUITS;
        if (strcmp(argv[3], "known") == 0)
            request[2] = 0xffU;
        else if (strcmp(argv[3], "active") == 0)
            request[2] = 0xfeU;
        else {
            fprintf(stderr,
                    "dnnice: circuits selector must be known or active\n");
            return 2;
        }
        query = argc == 5 ? argv[4] : "status";
        if (strcmp(query, "status") == 0)
            info = DNIV_NICE_INFO_STATUS;
        else if (strcmp(query, "counters") == 0)
            info = DNIV_NICE_INFO_COUNTERS;
        else {
            fprintf(stderr, "dnnice: circuits query must be status or counters\n");
            return 2;
        }
    } else {
        if (argc > 3) {
            fprintf(stderr,
                    "usage: %s AREA.NODE [summary|status|characteristics|counters]\n",
                    argv[0]);
            return 2;
        }
        if (argc == 3)
            query = argv[2];
        if (strcmp(query, "summary") == 0)
            info = DNIV_NICE_INFO_SUMMARY;
        else if (strcmp(query, "status") == 0)
            info = DNIV_NICE_INFO_STATUS;
        else if (strcmp(query, "characteristics") == 0)
            info = DNIV_NICE_INFO_CHARACTERISTICS;
        else if (strcmp(query, "counters") == 0)
            info = DNIV_NICE_INFO_COUNTERS;
        else {
            fprintf(stderr,
                    "usage: %s AREA.NODE [summary|status|characteristics|counters]\n",
                    argv[0]);
            return 2;
        }
    }

    request[0] = DNIV_NICE_FUNC_READ_INFO;
    if (entity == QUERY_CIRCUIT) {
        size_t name_len = strlen(circuit_name);

        request[1] = (unsigned char)((info << 4) | DNIV_NICE_ENTITY_CIRCUIT);
        request[2] = (unsigned char)name_len;
        memcpy(request + 3U, circuit_name, name_len);
        request_len = 3U + name_len;
    } else if (entity == QUERY_NODES) {
        request[1] = (unsigned char)(info << 4);
        request_len = 3U;
    } else if (entity == QUERY_CIRCUITS) {
        request[1] = (unsigned char)((info << 4) | DNIV_NICE_ENTITY_CIRCUIT);
        request_len = 3U;
    } else {
        uint16_t requested = entity == QUERY_NODE ? target_node : 0U;

        request[1] = (unsigned char)(info << 4);
        request[2] = 0U;
        request[3] = (unsigned char)(requested & 0xffU);
        request[4] = (unsigned char)(requested >> 8);
        request_len = 5U;
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
    if (send(fd, request, request_len, MSG_EOR | MSG_NOSIGNAL) !=
        (ssize_t)request_len) {
        perror("dnnice: send");
        close(fd);
        return 1;
    }
    if (entity == QUERY_NODES || entity == QUERY_CIRCUITS) {
        int bad = receive_multiple(fd, entity, info);

        close(fd);
        return bad ? 1 : 0;
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
    if ((int8_t)response[0] < 0) {
        fprintf(stderr, "dnnice: NICE error %d\n", (int8_t)response[0]);
        close(fd);
        return 1;
    }

    if (entity == QUERY_NODE) {
        if (print_remote_node(response, (size_t)got)) {
            fprintf(stderr, "dnnice: malformed remote-node reply\n");
            close(fd);
            return 1;
        }
    } else if (entity == QUERY_CIRCUIT) {
        int bad;

        if (info == DNIV_NICE_INFO_STATUS)
            bad = print_circuit_status(response, (size_t)got);
        else
            bad = print_circuit_counters(response, (size_t)got);
        if (bad) {
            fprintf(stderr, "dnnice: malformed circuit %s reply\n", query);
            close(fd);
            return 1;
        }
    } else if (strcmp(query, "characteristics") == 0) {
        if (print_characteristics(response, (size_t)got)) {
            size_t i;

            fprintf(stderr, "dnnice: malformed characteristics reply:");
            for (i = 0U; i < (size_t)got; i++)
                fprintf(stderr, " %02x", response[i]);
            fputc('\n', stderr);
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

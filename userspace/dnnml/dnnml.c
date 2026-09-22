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
#include <fcntl.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <sys/time.h>
#include <unistd.h>

#include <linux/decnet_iv.h>
#include <linux/dn.h>
#include <decnet_iv_nice.h>

#define DNIV_DEVICE "/dev/decnet_iv"
#define DNIV_NML_OBJECT 19U
#define DNIV_NML_BACKLOG 8
#define DNIV_NML_IDENT "DECnet-IV-Linux"

static __le16 cpu_to_le16_u(uint16_t value)
{
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return (__le16)value;
#else
    return (__le16)__builtin_bswap16(value);
#endif
}

static int read_identity(struct dniv_identity *identity)
{
    int fd = open(DNIV_DEVICE, O_RDONLY);

    if (fd < 0)
        return -1;
    memset(identity, 0, sizeof(*identity));
    if (ioctl(fd, DNIV_IOC_GET_IDENTITY, identity) < 0) {
        close(fd);
        return -1;
    }
    close(fd);
    if (identity->uapi_version != DNIV_UAPI_VERSION ||
        !identity->address || !identity->name[0])
        return -1;
    return 0;
}

static int make_listener(void)
{
    const unsigned char version[] = { 4U, 0U, 0U };
    struct optdata_dn conndata;
    struct sockaddr_dn local;
    int fd;

    fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (fd < 0)
        return -1;

    memset(&conndata, 0, sizeof(conndata));
    conndata.opt_optl = cpu_to_le16_u(sizeof(version));
    memcpy(conndata.opt_data, version, sizeof(version));
    if (setsockopt(fd, DNPROTO_NSP, DSO_CONDATA,
                   &conndata, sizeof(conndata)) < 0)
        goto fail;

    memset(&local, 0, sizeof(local));
    local.sdn_family = AF_DECnet;
    local.sdn_objnum = DNIV_NML_OBJECT;
    if (bind(fd, (struct sockaddr *)&local, sizeof(local)) < 0 ||
        listen(fd, DNIV_NML_BACKLOG) < 0)
        goto fail;
    return fd;

fail:
    close(fd);
    return -1;
}

static int read_traffic_stats(int ifindex, struct dniv_traffic_stats *stats)
{
    int fd;

    if (!stats || ifindex < 0)
        return -1;
    fd = open(DNIV_DEVICE, O_RDONLY);
    if (fd < 0)
        return -1;
    memset(stats, 0, sizeof(*stats));
    stats->uapi_version = DNIV_UAPI_VERSION;
    stats->ifindex = ifindex;
    if (ioctl(fd, DNIV_IOC_GET_TRAFFIC_STATS, stats) < 0) {
        close(fd);
        return -1;
    }
    close(fd);
    return stats->uapi_version == DNIV_UAPI_VERSION &&
           stats->ifindex == ifindex ? 0 : -1;
}

static int count_active_links(__u16 *active)
{
    struct dniv_link link;
    __u32 index;
    __u16 count = 0U;
    int fd;

    if (!active)
        return -1;
    fd = open(DNIV_DEVICE, O_RDONLY);
    if (fd < 0)
        return -1;
    for (index = 0U;; index++) {
        memset(&link, 0, sizeof(link));
        link.uapi_version = DNIV_UAPI_VERSION;
        link.index = index;
        if (ioctl(fd, DNIV_IOC_GET_LINK, &link) < 0) {
            if (errno == ENOENT)
                break;
            close(fd);
            return -1;
        }
        if (link.state != DNIV_LINK_STATE_CLOSED && count != UINT16_MAX)
            count++;
    }
    close(fd);
    *active = count;
    return 0;
}

static int read_circuit_state(const char *name, int *ifindex,
                              __u16 *block_size, __u16 *adjacent_node)
{
    struct dniv_adjacency adjacency;
    int ifindices[32];
    unsigned long wanted;
    char *end;
    __u32 index;
    size_t circuits = 0U;
    int target_ifindex = 0;
    __u16 target_block = 0U;
    __u16 target_node = 0U;
    int fd;

    if (!name || !ifindex || !block_size || !adjacent_node ||
        strncmp(name, "ETH-", 4U) != 0)
        return -1;
    errno = 0;
    wanted = strtoul(name + 4U, &end, 10);
    if (errno || end == name + 4U || *end != '\0' || wanted >= 32U)
        return -1;

    fd = open(DNIV_DEVICE, O_RDONLY);
    if (fd < 0)
        return -1;
    for (index = 0U;; index++) {
        size_t i;
        int known = 0;

        memset(&adjacency, 0, sizeof(adjacency));
        adjacency.uapi_version = DNIV_UAPI_VERSION;
        adjacency.index = index;
        if (ioctl(fd, DNIV_IOC_GET_ADJACENCY, &adjacency) < 0) {
            if (errno == ENOENT)
                break;
            close(fd);
            return -1;
        }
        if (adjacency.uapi_version != DNIV_UAPI_VERSION) {
            close(fd);
            return -1;
        }
        for (i = 0U; i < circuits; i++) {
            if (ifindices[i] == adjacency.ifindex) {
                known = 1;
                break;
            }
        }
        if (!known) {
            if (circuits >= sizeof(ifindices) / sizeof(ifindices[0])) {
                close(fd);
                return -1;
            }
            ifindices[circuits] = adjacency.ifindex;
            if (circuits == wanted)
                target_ifindex = adjacency.ifindex;
            circuits++;
        }
        if (target_ifindex == adjacency.ifindex &&
            adjacency.state == DNIV_ADJ_STATE_UP &&
            adjacency.block_size != 0U && target_node == 0U) {
            target_block = adjacency.block_size;
            target_node = adjacency.address;
        }
    }
    close(fd);
    if (!target_ifindex || !target_block || !target_node)
        return -1;
    *ifindex = target_ifindex;
    *block_size = target_block;
    *adjacent_node = target_node;
    return 0;
}

static int read_node_state(__u16 address, __u8 *node_type,
                           __u16 *cost, __u8 *hops, char *circuit,
                           size_t circuit_size, __u16 *next_node)
{
    struct dniv_adjacency adjacency;
    struct dniv_route route;
    int ifindices[32];
    size_t circuits = 0U;
    size_t target_circuit = 0U;
    int target_ifindex = 0;
    __u8 target_type = 0U;
    __u32 index;
    int fd;

    if (!address || !node_type || !cost || !hops || !circuit ||
        circuit_size < 6U || !next_node)
        return -1;
    fd = open(DNIV_DEVICE, O_RDONLY);
    if (fd < 0)
        return -1;

    for (index = 0U;; index++) {
        size_t i;
        int known = 0;

        memset(&adjacency, 0, sizeof(adjacency));
        adjacency.uapi_version = DNIV_UAPI_VERSION;
        adjacency.index = index;
        if (ioctl(fd, DNIV_IOC_GET_ADJACENCY, &adjacency) < 0) {
            if (errno == ENOENT)
                break;
            close(fd);
            return -1;
        }
        for (i = 0U; i < circuits; i++) {
            if (ifindices[i] == adjacency.ifindex) {
                known = 1;
                break;
            }
        }
        if (!known) {
            if (circuits >= sizeof(ifindices) / sizeof(ifindices[0])) {
                close(fd);
                return -1;
            }
            ifindices[circuits++] = adjacency.ifindex;
        }
        if (adjacency.address == address &&
            adjacency.state == DNIV_ADJ_STATE_UP) {
            for (i = 0U; i < circuits; i++) {
                if (ifindices[i] == adjacency.ifindex) {
                    target_circuit = i;
                    break;
                }
            }
            target_ifindex = adjacency.ifindex;
            target_type = adjacency.node_type == DNIV_NODE_TYPE_ENDNODE ?
                          5U : 4U;
        }
    }
    if (!target_ifindex) {
        close(fd);
        return -1;
    }

    for (index = 0U;; index++) {
        memset(&route, 0, sizeof(route));
        route.uapi_version = DNIV_UAPI_VERSION;
        route.index = index;
        if (ioctl(fd, DNIV_IOC_GET_ROUTE, &route) < 0) {
            if (errno == ENOENT)
                break;
            close(fd);
            return -1;
        }
        if (route.ifindex == target_ifindex &&
            ((route.level == 1U &&
              route.destination == DNIV_ADDR_NODE(address) &&
              DNIV_ADDR_AREA(route.next_hop) == DNIV_ADDR_AREA(address)) ||
             (route.level == 2U &&
              route.destination == DNIV_ADDR_AREA(address)))) {
            int written = snprintf(circuit, circuit_size, "ETH-%zu",
                                   target_circuit);

            if (written < 0 || (size_t)written >= circuit_size) {
                close(fd);
                return -1;
            }
            *node_type = target_type;
            *cost = route.cost;
            *hops = route.hops;
            *next_node = route.next_hop;
            close(fd);
            return 0;
        }
    }
    close(fd);
    return -1;
}

struct dniv_nml_node_status {
    __u16 address;
    __u16 cost;
    __u16 next_node;
    __u8 node_type;
    __u8 hops;
    char circuit[16];
};

static int node_status_find(struct dniv_nml_node_status *nodes, size_t count,
                            __u16 address)
{
    size_t i;

    for (i = 0U; i < count; i++) {
        if (nodes[i].address == address)
            return (int)i;
    }
    return -1;
}

static int collect_node_status(__s8 entity_code,
                               struct dniv_nml_node_status *nodes,
                               size_t capacity, size_t *count)
{
    __u16 addresses[256];
    size_t address_count = 0U;
    __u32 index;
    int fd;

    if (!nodes || !count || !capacity ||
        (entity_code != -1 && entity_code != -2 && entity_code != -4))
        return -1;

    fd = open(DNIV_DEVICE, O_RDONLY);
    if (fd < 0)
        return -1;

    if (entity_code == -4) {
        for (index = 0U;; index++) {
            struct dniv_adjacency adjacency;
            size_t i;
            int duplicate = 0;

            memset(&adjacency, 0, sizeof(adjacency));
            adjacency.uapi_version = DNIV_UAPI_VERSION;
            adjacency.index = index;
            if (ioctl(fd, DNIV_IOC_GET_ADJACENCY, &adjacency) < 0) {
                if (errno == ENOENT)
                    break;
                close(fd);
                return -1;
            }
            if (adjacency.state != DNIV_ADJ_STATE_UP)
                continue;
            for (i = 0U; i < address_count; i++) {
                if (addresses[i] == adjacency.address) {
                    duplicate = 1;
                    break;
                }
            }
            if (!duplicate && address_count <
                sizeof(addresses) / sizeof(addresses[0]))
                addresses[address_count++] = adjacency.address;
        }
    } else {
        for (index = 0U;; index++) {
            struct dniv_route route;
            __u16 address;
            size_t i;
            int duplicate = 0;

            memset(&route, 0, sizeof(route));
            route.uapi_version = DNIV_UAPI_VERSION;
            route.index = index;
            if (ioctl(fd, DNIV_IOC_GET_ROUTE, &route) < 0) {
                if (errno == ENOENT)
                    break;
                close(fd);
                return -1;
            }
            if (route.level != 1U || route.destination == 0U)
                continue;
            address = DNIV_ADDR(DNIV_ADDR_AREA(route.next_hop),
                                route.destination);
            for (i = 0U; i < address_count; i++) {
                if (addresses[i] == address) {
                    duplicate = 1;
                    break;
                }
            }
            if (!duplicate && address_count <
                sizeof(addresses) / sizeof(addresses[0]))
                addresses[address_count++] = address;
        }
    }
    close(fd);

    *count = 0U;
    for (index = 0U; index < address_count; index++) {
        struct dniv_nml_node_status status;

        memset(&status, 0, sizeof(status));
        status.address = addresses[index];
        if (read_node_state(status.address, &status.node_type,
                            &status.cost, &status.hops,
                            status.circuit, sizeof(status.circuit),
                            &status.next_node))
            continue;
        if (node_status_find(nodes, *count, status.address) >= 0)
            continue;
        if (*count >= capacity)
            return -1;
        nodes[(*count)++] = status;
    }

    for (index = 1U; index < *count; index++) {
        struct dniv_nml_node_status value = nodes[index];
        size_t pos = index;

        while (pos > 0U && nodes[pos - 1U].address > value.address) {
            nodes[pos] = nodes[pos - 1U];
            pos--;
        }
        nodes[pos] = value;
    }
    return 0;
}

static int send_nice_code(int fd, signed char code)
{
    return send(fd, &code, sizeof(code), MSG_EOR | MSG_NOSIGNAL) ==
           (ssize_t)sizeof(code) ? 0 : -1;
}

static int serve_multiple_circuits(int fd, __s8 entity_code, __u8 info,
                                   unsigned char *out, size_t out_capacity)
{
    unsigned int index;

    if ((entity_code != -1 && entity_code != -2) ||
        (info != DNIV_NICE_INFO_STATUS &&
         info != DNIV_NICE_INFO_COUNTERS))
        return send_nice_code(fd, -1);
    if (send_nice_code(fd, 2))
        return -1;

    for (index = 0U; index < 32U; index++) {
        struct dniv_traffic_stats traffic;
        char name[16];
        size_t out_len = 0U;
        int ifindex = 0;
        __u16 block_size = 0U;
        __u16 adjacent_node = 0U;
        int written;

        written = snprintf(name, sizeof(name), "ETH-%u", index);
        if (written < 0 || (size_t)written >= sizeof(name))
            return -1;
        if (read_circuit_state(name, &ifindex, &block_size, &adjacent_node))
            continue;
        if (info == DNIV_NICE_INFO_STATUS) {
            if (dniv_nice_build_circuit_status_reply(
                    out, out_capacity, &out_len, name,
                    adjacent_node, block_size))
                return -1;
        } else {
            if (read_traffic_stats(ifindex, &traffic) ||
                dniv_nice_build_circuit_counters_reply(
                    out, out_capacity, &out_len, name,
                    traffic.rx_bytes, traffic.tx_bytes,
                    traffic.rx_frames, traffic.tx_frames))
                return -1;
        }
        if (send(fd, out, out_len, MSG_EOR | MSG_NOSIGNAL) !=
            (ssize_t)out_len)
            return -1;
    }
    return send_nice_code(fd, -128);
}

static int serve_multiple_nodes(int fd, __s8 entity_code, __u8 info,
                                unsigned char *out, size_t out_capacity)
{
    struct dniv_nml_node_status nodes[256];
    size_t count = 0U;
    size_t i;

    if (info != DNIV_NICE_INFO_SUMMARY &&
        info != DNIV_NICE_INFO_STATUS)
        return send_nice_code(fd, -1);
    if (collect_node_status(entity_code, nodes,
                            sizeof(nodes) / sizeof(nodes[0]), &count))
        return send_nice_code(fd, -1);
    if (send_nice_code(fd, 2))
        return -1;

    for (i = 0U; i < count; i++) {
        size_t out_len = 0U;

        if (dniv_nice_build_remote_node_status_reply(
                out, out_capacity, &out_len, nodes[i].address,
                nodes[i].node_type, nodes[i].cost, nodes[i].hops,
                nodes[i].circuit, nodes[i].next_node))
            return -1;
        if (send(fd, out, out_len, MSG_EOR | MSG_NOSIGNAL) !=
            (ssize_t)out_len)
            return -1;
    }
    return send_nice_code(fd, -128);
}

static int serve_connection(int fd)
{
    struct timeval timeout = { .tv_sec = 30, .tv_usec = 0 };
    unsigned char in[256];
    unsigned char out[512];

    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO,
                   &timeout, sizeof(timeout)) < 0 ||
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO,
                   &timeout, sizeof(timeout)) < 0)
        return -1;

    for (;;) {
        struct dniv_nice_read_node request;
        struct dniv_identity identity;
        size_t out_len = 0U;
        __u16 active_links = 0U;
        ssize_t got;

        got = recv(fd, in, sizeof(in), 0);
        if (got == 0)
            return 0;
        if (got < 0)
            return -1;

        if (dniv_nice_parse_read_node(in, (size_t)got, &request) == 0) {
            if (request.permanent || read_identity(&identity)) {
                if (send_nice_code(fd, -1))
                    return -1;
                continue;
            }
            if (request.entity_code < 0) {
                if (request.entity_code != -1 &&
                    request.entity_code != -2 &&
                    request.entity_code != -4) {
                    if (send_nice_code(fd, -1))
                        return -1;
                } else if (serve_multiple_nodes(
                               fd, request.entity_code, request.info,
                               out, sizeof(out))) {
                    return -1;
                }
                continue;
            }
            if (request.node != 0U) {
                char circuit[16];
                __u16 next_node = 0U;
                __u16 cost = 0U;
                __u8 node_type = 0U;
                __u8 hops = 0U;

                if ((request.info != DNIV_NICE_INFO_SUMMARY &&
                     request.info != DNIV_NICE_INFO_STATUS) ||
                    read_node_state(request.node, &node_type, &cost, &hops,
                                    circuit, sizeof(circuit), &next_node) ||
                    dniv_nice_build_remote_node_status_reply(
                        out, sizeof(out), &out_len, request.node, node_type,
                        cost, hops, circuit, next_node)) {
                    if (send_nice_code(fd, -8))
                        return -1;
                    continue;
                }
                if (send(fd, out, out_len, MSG_EOR | MSG_NOSIGNAL) !=
                    (ssize_t)out_len)
                    return -1;
                continue;
            }
        } else {
            struct dniv_nice_read_circuit circuit;
            struct dniv_traffic_stats traffic;
            int ifindex = 0;
            __u16 block_size = 0U;
            __u16 adjacent_node = 0U;
            int build_failed = 0;

            if (dniv_nice_parse_read_circuit(in, (size_t)got, &circuit) ||
                circuit.permanent) {
                build_failed = 1;
            } else if (circuit.entity_code < 0) {
                if (serve_multiple_circuits(fd, circuit.entity_code,
                                            circuit.info,
                                            out, sizeof(out)))
                    return -1;
                continue;
            } else if ((circuit.info != DNIV_NICE_INFO_STATUS &&
                        circuit.info != DNIV_NICE_INFO_COUNTERS) ||
                       read_circuit_state(circuit.name, &ifindex, &block_size,
                                          &adjacent_node)) {
                build_failed = 1;
            } else if (circuit.info == DNIV_NICE_INFO_STATUS) {
                build_failed = dniv_nice_build_circuit_status_reply(
                    out, sizeof(out), &out_len, circuit.name,
                    adjacent_node, block_size);
            } else if (read_traffic_stats(ifindex, &traffic)) {
                build_failed = 1;
            } else {
                build_failed = dniv_nice_build_circuit_counters_reply(
                    out, sizeof(out), &out_len, circuit.name,
                    traffic.rx_bytes, traffic.tx_bytes,
                    traffic.rx_frames, traffic.tx_frames);
            }
            if (build_failed) {
                const signed char error = -1;

                if (send(fd, &error, sizeof(error),
                         MSG_EOR | MSG_NOSIGNAL) != (ssize_t)sizeof(error))
                    return -1;
                continue;
            }
            if (send(fd, out, out_len, MSG_EOR | MSG_NOSIGNAL) !=
                (ssize_t)out_len)
                return -1;
            continue;
        }

        switch (request.info) {
        case DNIV_NICE_INFO_SUMMARY:
        case DNIV_NICE_INFO_STATUS:
            if (count_active_links(&active_links) ||
                dniv_nice_build_node_status_reply(out, sizeof(out), &out_len,
                                                  identity.address,
                                                  identity.name,
                                                  active_links))
                return -1;
            break;
        case DNIV_NICE_INFO_CHARACTERISTICS:
            if (dniv_nice_build_node_reply(out, sizeof(out), &out_len,
                                           identity.address, identity.name,
                                           DNIV_NML_IDENT))
                return -1;
            break;
        case DNIV_NICE_INFO_COUNTERS: {
            struct dniv_traffic_stats traffic;

            if (read_traffic_stats(0, &traffic) ||
                dniv_nice_build_node_counters_reply(
                    out, sizeof(out), &out_len, identity.address,
                    identity.name, traffic.rx_bytes, traffic.tx_bytes,
                    traffic.rx_frames, traffic.tx_frames))
                return -1;
            break;
        }
        default: {
            const signed char error = -1;

            if (send(fd, &error, sizeof(error),
                     MSG_EOR | MSG_NOSIGNAL) != (ssize_t)sizeof(error))
                return -1;
            continue;
        }
        }
        if (send(fd, out, out_len, MSG_EOR | MSG_NOSIGNAL) !=
            (ssize_t)out_len)
            return -1;
    }
}

#define DNIV_NML_MAX_BOUNDED_SESSIONS 32U

static int serve_forked_sessions(int listener, unsigned int limit)
{
    pid_t children[DNIV_NML_MAX_BOUNDED_SESSIONS];
    unsigned int accepted = 0U;
    unsigned int i;
    int failed = 0;

    for (;;) {
        pid_t child;
        int fd;

        if (limit && accepted >= limit)
            break;
        fd = accept(listener, NULL, NULL);
        if (fd < 0) {
            if (errno == EINTR)
                continue;
            perror("dnnml: accept");
            return -1;
        }

        child = fork();
        if (child < 0) {
            perror("dnnml: fork");
            close(fd);
            return -1;
        }
        if (child == 0) {
            int ret;

            close(listener);
            ret = serve_connection(fd);
            close(fd);
            if (!ret)
                puts("dnnml: served NICE management session");
            _exit(ret ? 1 : 0);
        }

        close(fd);
        if (limit)
            children[accepted] = child;
        accepted++;
    }

    for (i = 0U; i < accepted; i++) {
        int status = 0;
        pid_t waited;

        do {
            waited = waitpid(children[i], &status, 0);
        } while (waited < 0 && errno == EINTR);
        if (waited != children[i] || !WIFEXITED(status) ||
            WEXITSTATUS(status) != 0)
            failed = 1;
    }
    return failed ? -1 : 0;
}

int main(int argc, char **argv)
{
    unsigned int sessions = 0U;
    int once = 0;
    int listener;

    if (argc == 2 && strcmp(argv[1], "--once") == 0) {
        once = 1;
    } else if (argc == 3 && strcmp(argv[1], "--sessions") == 0) {
        unsigned long parsed;
        char *end = NULL;

        errno = 0;
        parsed = strtoul(argv[2], &end, 10);
        if (errno || end == argv[2] || *end != '\0' || parsed == 0U ||
            parsed > DNIV_NML_MAX_BOUNDED_SESSIONS) {
            fprintf(stderr, "dnnml: invalid session count\n");
            return 2;
        }
        sessions = (unsigned int)parsed;
    } else if (argc != 1) {
        fprintf(stderr, "usage: %s [--once | --sessions COUNT]\n", argv[0]);
        return 2;
    }

    setvbuf(stdout, NULL, _IONBF, 0);
    listener = make_listener();
    if (listener < 0) {
        perror("dnnml: listener");
        return 1;
    }
    puts("dnnml: ready object=19 version=4.0.0");

    if (!once) {
        int ret;

        if (!sessions && signal(SIGCHLD, SIG_IGN) == SIG_ERR) {
            perror("dnnml: signal");
            close(listener);
            return 1;
        }
        ret = serve_forked_sessions(listener, sessions);
        close(listener);
        return ret ? 1 : 0;
    }

    for (;;) {
        int fd = accept(listener, NULL, NULL);
        int ret;

        if (fd < 0) {
            if (errno == EINTR)
                continue;
            perror("dnnml: accept");
            close(listener);
            return 1;
        }
        ret = serve_connection(fd);
        close(fd);
        if (ret) {
            fprintf(stderr, "dnnml: request failed\n");
            close(listener);
            return 1;
        }
        puts("dnnml: served NICE management session");
        break;
    }

    close(listener);
    return 0;
}

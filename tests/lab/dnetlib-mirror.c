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

#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

#include <netdnet/dnetdb.h>

static int exchange(int fd, const unsigned char *request, size_t request_len,
                    const unsigned char *expected, size_t expected_len)
{
    unsigned char reply[128];
    int got;

    if (send(fd, request, request_len, MSG_EOR | MSG_NOSIGNAL) !=
        (ssize_t)request_len)
        return -1;
    got = dnet_recv(fd, reply, sizeof(reply), MSG_EOR);
    if (got != (ssize_t)expected_len ||
        memcmp(reply, expected, expected_len))
        return -1;
    return 0;
}

int main(int argc, char **argv)
{
    static const unsigned char loop_request[] = "\x00libdnet-dnet_conn";
    static const unsigned char loop_expected[] = "\x01libdnet-dnet_conn";
    static const unsigned char bad_request[] = "\x7fmalformed";
    static const unsigned char bad_expected[] = { 0xffU };
    unsigned char expected_addr[DN_ADDL];
    unsigned char accept_data[DN_MAXOPTL];
    struct dn_naddr *expected;
    struct dn_naddr *executor;
    struct nodeent *node;
    struct nodeent *reverse;
    void *iterator;
    char *iter_name;
    char object_name[DN_MAXOBJL + 1U];
    int accept_len = sizeof(accept_data);
    int entries = 0;
    int peer_seen = 0;
    int fd;

    if (argc != 4) {
        fprintf(stderr, "usage: %s NODE-NAME PEER-AREA.NODE LOCAL-AREA.NODE\n",
                argv[0]);
        return 2;
    }

    expected = dnet_addr(argv[2]);
    if (!expected) {
        fprintf(stderr, "dnetlib-mirror: invalid expected peer address\n");
        return 1;
    }
    memcpy(expected_addr, expected->a_addr, sizeof(expected_addr));

    node = getnodebyname(argv[1]);
    if (!node || node->n_addrtype != AF_DECnet ||
        node->n_length != DN_ADDL ||
        memcmp(node->n_addr, expected_addr, sizeof(expected_addr))) {
        fprintf(stderr, "dnetlib-mirror: node-name lookup failed\n");
        return 1;
    }
    reverse = getnodebyaddr((const char *)expected_addr, DN_ADDL, AF_DECnet);
    if (!reverse || strcmp(reverse->n_name, argv[1])) {
        fprintf(stderr, "dnetlib-mirror: node-address lookup failed\n");
        return 1;
    }
    executor = getnodeadd();
    if (!executor || !dnet_ntoa(executor) ||
        strcmp(dnet_ntoa(executor), argv[3])) {
        fprintf(stderr, "dnetlib-mirror: executor lookup failed\n");
        return 1;
    }
    if (!getexecdev() || !*getexecdev()) {
        fprintf(stderr, "dnetlib-mirror: executor device lookup failed\n");
        return 1;
    }

    iterator = dnet_getnode();
    if (!iterator) {
        fprintf(stderr, "dnetlib-mirror: node iterator open failed\n");
        return 1;
    }
    while ((iter_name = dnet_nextnode(iterator)) != NULL) {
        entries++;
        if (!strcmp(iter_name, argv[1]))
            peer_seen = 1;
    }
    dnet_endnode(iterator);
    if (entries != 2 || !peer_seen) {
        fprintf(stderr, "dnetlib-mirror: node iteration failed\n");
        return 1;
    }

    if (getobjectbyname("mirror") != 25) {
        fprintf(stderr, "dnetlib-mirror: object-name lookup failed\n");
        return 1;
    }
    memset(object_name, 0, sizeof(object_name));
    if (getobjectbynumber(25, object_name, sizeof(object_name)) != 25 ||
        strcmp(object_name, "MIRROR")) {
        fprintf(stderr, "dnetlib-mirror: object-number lookup failed\n");
        return 1;
    }

    fd = dnet_conn(argv[1], "MIRROR", SOCK_SEQPACKET,
                   NULL, 0, accept_data, &accept_len);
    if (fd < 0) {
        perror("dnetlib-mirror: dnet_conn");
        return 1;
    }
    if (dnet_eof(fd)) {
        perror("dnetlib-mirror: dnet_eof");
        close(fd);
        return 1;
    }
    if (accept_len != 2 || accept_data[0] != 0xffU ||
        accept_data[1] != 0xffU) {
        fprintf(stderr, "dnetlib-mirror: invalid MIRROR accept data\n");
        close(fd);
        return 1;
    }

    if (exchange(fd, loop_request, sizeof(loop_request) - 1U,
                 loop_expected, sizeof(loop_expected) - 1U) ||
        exchange(fd, bad_request, sizeof(bad_request) - 1U,
                 bad_expected, sizeof(bad_expected))) {
        fprintf(stderr, "dnetlib-mirror: MIRROR exchange failed\n");
        close(fd);
        return 1;
    }

    close(fd);
    printf("dnetlib-mirror: pass peer=%s address=%s object=MIRROR connect-data=2 records=2 node-db=2\n",
           argv[1], argv[2]);
    return 0;
}

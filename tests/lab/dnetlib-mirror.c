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
    ssize_t got;

    if (send(fd, request, request_len, MSG_EOR | MSG_NOSIGNAL) !=
        (ssize_t)request_len)
        return -1;
    got = recv(fd, reply, sizeof(reply), 0);
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
    unsigned char accept_data[DN_MAXOPTL];
    int accept_len = sizeof(accept_data);
    int fd;

    if (argc != 2) {
        fprintf(stderr, "usage: %s AREA.NODE\n", argv[0]);
        return 2;
    }

    fd = dnet_conn(argv[1], "#25", SOCK_SEQPACKET,
                   NULL, 0, accept_data, &accept_len);
    if (fd < 0) {
        perror("dnetlib-mirror: dnet_conn");
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
    printf("dnetlib-mirror: pass peer=%s object=25 connect-data=2 records=2\n",
           argv[1]);
    return 0;
}

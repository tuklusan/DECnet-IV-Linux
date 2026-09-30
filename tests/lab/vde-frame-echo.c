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

#include <libvdeplug.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/select.h>
#include <unistd.h>

#define FRAME_LEN 60
#define MARK_LEN 7

static const unsigned char server_mac[6] = {0x02, 0x00, 0x00, 0x00, 0x31, 0x77};
static const unsigned char client_mac[6] = {0x02, 0x00, 0x00, 0x00, 0x31, 0x78};
static const unsigned char req_mark[MARK_LEN] = {'D','N','I','V','X','R','Q'};
static const unsigned char rsp_mark[MARK_LEN] = {'D','N','I','V','X','O','K'};

static int wait_readable(VDECONN *conn, int seconds)
{
    fd_set rfds;
    struct timeval tv = {seconds, 0};
    int fd = vde_datafd(conn);

    if (fd < 0)
        return -1;
    FD_ZERO(&rfds);
    FD_SET(fd, &rfds);
    return select(fd + 1, &rfds, NULL, NULL, &tv);
}

static int is_request(const unsigned char *frame, ssize_t len)
{
    return len >= 22 &&
           memcmp(frame, server_mac, sizeof(server_mac)) == 0 &&
           frame[12] == 0x88 && frame[13] == 0xb5 &&
           memcmp(frame + 14, req_mark, MARK_LEN) == 0;
}

static int is_response(const unsigned char *frame, ssize_t len, unsigned char token)
{
    return len >= 22 &&
           memcmp(frame, client_mac, sizeof(client_mac)) == 0 &&
           memcmp(frame + 6, server_mac, sizeof(server_mac)) == 0 &&
           frame[12] == 0x88 && frame[13] == 0xb5 &&
           memcmp(frame + 14, rsp_mark, MARK_LEN) == 0 &&
           frame[21] == token;
}

static int run_server(const char *url)
{
    VDECONN *conn = vde_open((char *)url, (char *)"dniv-cross-vde-server", NULL);
    unsigned char frame[2048];

    if (!conn) {
        perror("vde_open server");
        return 1;
    }

    for (;;) {
        ssize_t n;
        unsigned char reply[FRAME_LEN] = {0};

        if (wait_readable(conn, 60) <= 0)
            continue;
        n = vde_recv(conn, frame, sizeof(frame), 0);
        if (!is_request(frame, n))
            continue;

        memcpy(reply, frame + 6, 6);
        memcpy(reply + 6, server_mac, 6);
        reply[12] = 0x88;
        reply[13] = 0xb5;
        memcpy(reply + 14, rsp_mark, MARK_LEN);
        reply[21] = frame[21];
        if (vde_send(conn, reply, sizeof(reply), 0) != (ssize_t)sizeof(reply)) {
            perror("vde_send server");
            vde_close(conn);
            return 1;
        }
    }
}

static int run_client(const char *url, unsigned char token)
{
    VDECONN *conn = vde_open((char *)url, (char *)"dniv-cross-vde-client", NULL);
    unsigned char frame[FRAME_LEN] = {0};
    unsigned char got[2048];
    int tries;

    if (!conn) {
        perror("vde_open client");
        return 1;
    }

    memcpy(frame, server_mac, 6);
    memcpy(frame + 6, client_mac, 6);
    frame[12] = 0x88;
    frame[13] = 0xb5;
    memcpy(frame + 14, req_mark, MARK_LEN);
    frame[21] = token;

    if (vde_send(conn, frame, sizeof(frame), 0) != (ssize_t)sizeof(frame)) {
        perror("vde_send client");
        vde_close(conn);
        return 1;
    }

    for (tries = 0; tries < 8; tries++) {
        ssize_t n;

        if (wait_readable(conn, 1) <= 0)
            continue;
        n = vde_recv(conn, got, sizeof(got), 0);
        if (is_response(got, n, token)) {
            printf("vde-frame-echo: pass token=%u\n", token);
            vde_close(conn);
            return 0;
        }
    }

    fprintf(stderr, "vde-frame-echo: response timeout\n");
    vde_close(conn);
    return 1;
}

int main(int argc, char **argv)
{
    char *end = NULL;
    unsigned long token;

    if (argc < 3 || argc > 4) {
        fprintf(stderr, "usage: %s server URL | client URL TOKEN\n", argv[0]);
        return 2;
    }
    if (strcmp(argv[1], "server") == 0 && argc == 3)
        return run_server(argv[2]);
    if (strcmp(argv[1], "client") != 0 || argc != 4)
        return 2;

    errno = 0;
    token = strtoul(argv[3], &end, 10);
    if (errno || !end || *end || token > 255)
        return 2;
    return run_client(argv[2], (unsigned char)token);
}

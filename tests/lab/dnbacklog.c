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

#define BACKLOG_OBJECT 241U
#define BACKLOG_COUNT 4U

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

static int make_listener(void)
{
    struct sockaddr_dn local;
    struct timeval timeout = { .tv_sec = 30, .tv_usec = 0 };
    int fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);

    if (fd < 0)
        return -1;
    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)))
        goto fail;
    memset(&local, 0, sizeof(local));
    local.sdn_family = AF_DECnet;
    local.sdn_objnum = BACKLOG_OBJECT;
    if (bind(fd, (struct sockaddr *)&local, sizeof(local)) ||
        listen(fd, (int)BACKLOG_COUNT))
        goto fail;
    return fd;
fail:
    close(fd);
    return -1;
}

int main(int argc, char **argv)
{
    unsigned char buf[128];
    uint16_t expected_node;
    unsigned int i;
    int listener;

    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc != 4 || parse_node(argv[1], &expected_node)) {
        fprintf(stderr, "usage: %s PEER-AREA.NODE SESSION SCENARIO\n", argv[0]);
        return 2;
    }

    listener = make_listener();
    if (listener < 0) {
        perror("backlog listener");
        return 1;
    }
    printf("DNIV-INTEROP-BACKLOG-READY session=%s scenario=%s count=%u\n",
           argv[2], argv[3], BACKLOG_COUNT);

    sleep(3);
    for (i = 0U; i < BACKLOG_COUNT; i++) {
        struct sockaddr_dn peer;
        socklen_t peerlen = sizeof(peer);
        ssize_t got;
        uint16_t node;
        int fd = accept(listener, (struct sockaddr *)&peer, &peerlen);

        if (fd < 0 || peerlen != sizeof(peer) ||
            peer.sdn_family != AF_DECnet ||
            (uint16_t)peer.sdn_nodeaddrl != 2U) {
            if (fd >= 0)
                close(fd);
            close(listener);
            return 1;
        }
        node = (uint16_t)(peer.sdn_nodeaddr[0] |
                          ((uint16_t)peer.sdn_nodeaddr[1] << 8));
        if (node != expected_node) {
            close(fd);
            close(listener);
            return 1;
        }
        got = recv(fd, buf, sizeof(buf), 0);
        if (got <= 0) {
            fprintf(stderr, "backlog recv index=%u got=%zd errno=%d (%s)\\n",
                    i, got, errno, strerror(errno));
            close(fd);
            close(listener);
            return 1;
        }
        {
            ssize_t sent = send(fd, buf, (size_t)got,
                                MSG_EOR | MSG_NOSIGNAL);

            if (sent != got) {
                fprintf(stderr,
                        "backlog send index=%u got=%zd sent=%zd errno=%d (%s)\\n",
                        i, got, sent, errno, strerror(errno));
                close(fd);
                close(listener);
                return 1;
            }
        }
        close(fd);
    }

    close(listener);
    printf("DNIV-INTEROP-BACKLOG-SERVER-PASS session=%s scenario=%s count=%u\n",
           argv[2], argv[3], BACKLOG_COUNT);
    return 0;
}

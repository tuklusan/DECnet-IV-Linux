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

#define TERM_OBJECT 246U
#define TERM_COUNT 4U
#define ABORT_REASON 9U
#define RECOVER_NAME "RECOVER"
#define RECOVER_PAYLOAD "term-recover"
#define RECOVER_DONE "recover-done"

static uint16_t dniv_le16_to_cpu(__le16 value)
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
    local.sdn_objnum = TERM_OBJECT;
    if (bind(fd, (struct sockaddr *)&local, sizeof(local)) ||
        listen(fd, TERM_COUNT))
        goto fail;
    return fd;
fail:
    close(fd);
    return -1;
}

static int peer_name(const struct sockaddr_dn *peer, char *name, size_t size)
{
    uint16_t length = dniv_le16_to_cpu(peer->sdn_objnamel);

    if (!length || length >= size || peer->sdn_objnum)
        return -1;
    memcpy(name, peer->sdn_objname, length);
    name[length] = '\0';
    return 0;
}

static int disconnect_data(int fd, uint16_t reason, const char *data)
{
    struct optdata_dn discdata;
    socklen_t optlen = sizeof(discdata);
    size_t length = strlen(data);

    memset(&discdata, 0, sizeof(discdata));
    if (getsockopt(fd, DNPROTO_NSP, DSO_DISDATA, &discdata, &optlen) ||
        optlen != sizeof(discdata) ||
        dniv_le16_to_cpu(discdata.opt_status) != reason ||
        dniv_le16_to_cpu(discdata.opt_optl) != length ||
        memcmp(discdata.opt_data, data, length))
        return -1;
    return 0;
}

static int verify_terminated(int fd, const char *name)
{
    unsigned char byte;
    char expected[32];
    uint16_t reason;
    ssize_t got;

    got = recv(fd, &byte, sizeof(byte), 0);
    if (got != 0)
        return -1;
    if (!strncmp(name, "ABORT", 5)) {
        reason = ABORT_REASON;
        if (snprintf(expected, sizeof(expected), "abort-%c", name[5]) < 0)
            return -1;
    } else if (!strncmp(name, "DISC", 4)) {
        reason = 0U;
        if (snprintf(expected, sizeof(expected), "disconnect-%c", name[4]) < 0)
            return -1;
    } else {
        return -1;
    }
    return disconnect_data(fd, reason, expected);
}

static int verify_peer(struct sockaddr_dn *peer, socklen_t peerlen,
                       uint16_t expected_node)
{
    uint16_t node;

    if (peerlen != sizeof(*peer) || peer->sdn_family != AF_DECnet ||
        dniv_le16_to_cpu(peer->sdn_nodeaddrl) != 2U)
        return -1;
    node = (uint16_t)(peer->sdn_nodeaddr[0] |
                      ((uint16_t)peer->sdn_nodeaddr[1] << 8));
    return node == expected_node ? 0 : -1;
}

int main(int argc, char **argv)
{
    int fds[TERM_COUNT] = { -1, -1, -1, -1 };
    char names[TERM_COUNT][DN_MAXOBJL + 1U];
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
        perror("termination listener");
        return 1;
    }

    printf("DNIV-INTEROP-TERM-RACE-READY session=%s scenario=%s count=%u\n",
           argv[2], argv[3], TERM_COUNT);

    for (i = 0U; i < TERM_COUNT; i++) {
        struct sockaddr_dn peer;
        socklen_t peerlen = sizeof(peer);

        memset(&peer, 0, sizeof(peer));
        fds[i] = accept(listener, (struct sockaddr *)&peer, &peerlen);
        if (fds[i] < 0 || verify_peer(&peer, peerlen, expected_node) ||
            peer_name(&peer, names[i], sizeof(names[i]))) {
            fprintf(stderr, "term-race accept=%u failed errno=%d\n", i, errno);
            goto fail;
        }
    }

    for (i = 0U; i < TERM_COUNT; i++) {
        if (verify_terminated(fds[i], names[i])) {
            fprintf(stderr,
                    "term-race child=%u name=%s termination failed errno=%d (%s)\n",
                    i, names[i], errno, strerror(errno));
            goto fail;
        }
        close(fds[i]);
        fds[i] = -1;
    }

    {
        struct sockaddr_dn peer;
        socklen_t peerlen = sizeof(peer);
        char name[DN_MAXOBJL + 1U];
        ssize_t got;
        int fd;

        memset(&peer, 0, sizeof(peer));
        fd = accept(listener, (struct sockaddr *)&peer, &peerlen);
        if (fd < 0 || verify_peer(&peer, peerlen, expected_node) ||
            peer_name(&peer, name, sizeof(name)) ||
            strcmp(name, RECOVER_NAME)) {
            if (fd >= 0)
                close(fd);
            fprintf(stderr, "term-race recovery accept failed errno=%d\n", errno);
            goto fail;
        }
        got = recv(fd, buf, sizeof(buf), 0);
        if (got != (ssize_t)(sizeof(RECOVER_PAYLOAD) - 1U) ||
            memcmp(buf, RECOVER_PAYLOAD, sizeof(RECOVER_PAYLOAD) - 1U) ||
            send(fd, buf, (size_t)got, MSG_EOR | MSG_NOSIGNAL) != got) {
            fprintf(stderr, "term-race recovery echo failed errno=%d\n", errno);
            close(fd);
            goto fail;
        }
        got = recv(fd, buf, sizeof(buf), 0);
        if (got != 0 || disconnect_data(fd, 0U, RECOVER_DONE)) {
            fprintf(stderr, "term-race recovery disconnect failed errno=%d\n", errno);
            close(fd);
            goto fail;
        }
        close(fd);
    }

    close(listener);
    printf("DNIV-INTEROP-TERM-RACE-SERVER-PASS session=%s scenario=%s count=%u\n",
           argv[2], argv[3], TERM_COUNT);
    return 0;

fail:
    for (i = 0U; i < TERM_COUNT; i++)
        if (fds[i] >= 0)
            close(fds[i]);
    close(listener);
    return 1;
}

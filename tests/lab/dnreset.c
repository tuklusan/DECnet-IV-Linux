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

#define RESET_OBJECT 244U
#define RESET_ROUNDS 8U
#define ABORT_NAME "ABORTER"
#define SURVIVOR_NAME "SURVIVOR"
#define ABORT_DATA "py-abort"
#define SURVIVOR_DONE "py-survivor-done"
#define ABORT_REASON 9U

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
    local.sdn_objnum = RESET_OBJECT;
    if (bind(fd, (struct sockaddr *)&local, sizeof(local)) || listen(fd, 4))
        goto fail;
    return fd;
fail:
    close(fd);
    return -1;
}

static int peer_name_is(const struct sockaddr_dn *peer, const char *name)
{
    size_t length = strlen(name);

    return peer->sdn_objnum == 0U &&
           dniv_le16_to_cpu(peer->sdn_objnamel) == length &&
           !memcmp(peer->sdn_objname, name, length);
}

static int check_disconnect_data(int fd, uint16_t reason, const char *data)
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

static int accept_pair(int listener, uint16_t expected_node,
                       int *abort_fd, int *survivor_fd)
{
    unsigned int i;

    *abort_fd = -1;
    *survivor_fd = -1;
    for (i = 0U; i < 2U; i++) {
        struct sockaddr_dn peer;
        socklen_t peerlen = sizeof(peer);
        uint16_t node;
        int fd = accept(listener, (struct sockaddr *)&peer, &peerlen);

        if (fd < 0 || peerlen != sizeof(peer) ||
            peer.sdn_family != AF_DECnet ||
            dniv_le16_to_cpu(peer.sdn_nodeaddrl) != 2U) {
            if (fd >= 0)
                close(fd);
            return -1;
        }
        node = (uint16_t)(peer.sdn_nodeaddr[0] |
                          ((uint16_t)peer.sdn_nodeaddr[1] << 8));
        if (node != expected_node) {
            close(fd);
            return -1;
        }
        if (peer_name_is(&peer, ABORT_NAME) && *abort_fd < 0)
            *abort_fd = fd;
        else if (peer_name_is(&peer, SURVIVOR_NAME) && *survivor_fd < 0)
            *survivor_fd = fd;
        else {
            close(fd);
            return -1;
        }
    }
    return *abort_fd >= 0 && *survivor_fd >= 0 ? 0 : -1;
}

int main(int argc, char **argv)
{
    unsigned char buf[128];
    uint16_t expected_node;
    unsigned int round;
    int listener;

    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc != 4 || parse_node(argv[1], &expected_node)) {
        fprintf(stderr, "usage: %s PEER-AREA.NODE SESSION SCENARIO\n", argv[0]);
        return 2;
    }

    listener = make_listener();
    if (listener < 0) {
        perror("reset listener");
        return 1;
    }
    printf("DNIV-INTEROP-RESET-READY session=%s scenario=%s rounds=%u\n",
           argv[2], argv[3], RESET_ROUNDS);

    for (round = 0U; round < RESET_ROUNDS; round++) {
        char expected[64];
        ssize_t got;
        int abort_fd;
        int survivor_fd;

        if (accept_pair(listener, expected_node, &abort_fd, &survivor_fd)) {
            fprintf(stderr, "reset round=%u accept pair failed errno=%d\n",
                    round, errno);
            close(listener);
            return 1;
        }

        got = recv(abort_fd, buf, sizeof(buf), 0);
        if (got != 0 || check_disconnect_data(abort_fd, ABORT_REASON, ABORT_DATA)) {
            fprintf(stderr,
                    "reset round=%u abort child failed got=%zd errno=%d (%s)\n",
                    round, got, errno, strerror(errno));
            close(abort_fd);
            close(survivor_fd);
            close(listener);
            return 1;
        }

        if (snprintf(expected, sizeof(expected), "reset-survivor-%u", round) < 0) {
            close(abort_fd);
            close(survivor_fd);
            close(listener);
            return 1;
        }
        got = recv(survivor_fd, buf, sizeof(buf), 0);
        if (got != (ssize_t)strlen(expected) ||
            memcmp(buf, expected, (size_t)got) ||
            send(survivor_fd, buf, (size_t)got, MSG_EOR | MSG_NOSIGNAL) != got) {
            fprintf(stderr,
                    "reset round=%u survivor echo failed got=%zd errno=%d (%s)\n",
                    round, got, errno, strerror(errno));
            close(abort_fd);
            close(survivor_fd);
            close(listener);
            return 1;
        }

        got = recv(survivor_fd, buf, sizeof(buf), 0);
        if (got != 0 ||
            check_disconnect_data(survivor_fd, 0U, SURVIVOR_DONE)) {
            fprintf(stderr,
                    "reset round=%u survivor disconnect failed got=%zd errno=%d (%s)\n",
                    round, got, errno, strerror(errno));
            close(abort_fd);
            close(survivor_fd);
            close(listener);
            return 1;
        }

        close(abort_fd);
        close(survivor_fd);
    }

    close(listener);
    printf("DNIV-INTEROP-RESET-SERVER-PASS session=%s scenario=%s rounds=%u\n",
           argv[2], argv[3], RESET_ROUNDS);
    return 0;
}

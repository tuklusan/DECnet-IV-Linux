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
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

#include <linux/sockios.h>

#include <linux/dn.h>

#define TEST_OBJECT 240U
#define TEST_NAME "DNIVTEST"
#define SOURCE_NAME "PYDNIV"
#define OOB_ONE "py-oob-one"
#define OOB_TWO "py-oob-two"
#define OOB_REPLY "linux-oob"
#define AFTER_OOB "after-oob"
#define CONNECT_DATA "py-connect"
#define ACCEPT_DATA "linux-accept"
#define ACCESS_USER "PYUSER"
#define ACCESS_PASS "PYPASS"
#define ACCESS_ACCOUNT "PYACCT"

static uint16_t dniv_le16_to_cpu(__le16 value)
{
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return (uint16_t)value;
#else
    return __builtin_bswap16((uint16_t)value);
#endif
}

static __le16 dniv_cpu_to_le16(uint16_t value)
{
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return (__le16)value;
#else
    return (__le16)__builtin_bswap16(value);
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
    if (errno || end == text || *end || node < 1U || node > 1023U)
        return -1;
    *address = (uint16_t)((area << 10) | node);
    return 0;
}

static int make_listener(int named)
{
    struct sockaddr_dn local;
    struct optdata_dn acceptdata;
    int acceptmode = named ? ACC_DEFER : ACC_IMMED;
    struct timeval timeout = { .tv_sec = 30, .tv_usec = 0 };
    int fd;

    fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (fd < 0)
        return -1;
    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)))
        goto fail;

    memset(&acceptdata, 0, sizeof(acceptdata));
    acceptdata.opt_optl = dniv_cpu_to_le16(sizeof(ACCEPT_DATA) - 1U);
    memcpy(acceptdata.opt_data, ACCEPT_DATA, sizeof(ACCEPT_DATA) - 1U);
    if (setsockopt(fd, DNPROTO_NSP, DSO_CONDATA,
                   &acceptdata, sizeof(acceptdata)) ||
        setsockopt(fd, DNPROTO_NSP, DSO_ACCEPTMODE,
                   &acceptmode, sizeof(acceptmode)))
        goto fail;

    memset(&local, 0, sizeof(local));
    local.sdn_family = AF_DECnet;
    if (named) {
        local.sdn_objnamel = dniv_cpu_to_le16(sizeof(TEST_NAME) - 1U);
        memcpy(local.sdn_objname, TEST_NAME, sizeof(TEST_NAME) - 1U);
    } else {
        local.sdn_objnum = TEST_OBJECT;
    }
    if (bind(fd, (struct sockaddr *)&local, sizeof(local)) || listen(fd, 2))
        goto fail;
    return fd;

fail:
    close(fd);
    return -1;
}

static int recv_oob(int fd, const char *expected)
{
    struct pollfd pfd = { .fd = fd, .events = POLLPRI };
    unsigned char buf[DN_MAXOPTL];
    size_t length = strlen(expected);
    ssize_t got;
    int atmark = 0;
    int ready;

    ready = poll(&pfd, 1, 30000);
    if (ready != 1 || !(pfd.revents & POLLPRI))
        return -1;
    if (ioctl(fd, SIOCATMARK, &atmark) || atmark != 1)
        return -1;

    got = recv(fd, buf, sizeof(buf), MSG_OOB);
    if (got != (ssize_t)length || memcmp(buf, expected, length))
        return -1;
    return 0;
}

static int serve_one(int listener, uint16_t expected_node,
                     const char *payload, int deferred)
{
    struct sockaddr_dn peer;
    socklen_t peer_len = sizeof(peer);
    struct timeval timeout = { .tv_sec = 30, .tv_usec = 0 };
    unsigned char buf[128];
    struct optdata_dn conndata;
    struct accessdata_dn access;
    socklen_t optlen;
    uint16_t node;
    size_t expected = strlen(payload);
    ssize_t got;
    int fd;

    fd = accept(listener, NULL, NULL);
    if (fd < 0)
        return -1;
    if (deferred) {
        unsigned char mode = 0xffU;
        socklen_t modelen = sizeof(mode);

        if (getsockopt(fd, DNPROTO_NSP, DSO_ACCEPTMODE, &mode, &modelen) ||
            modelen != sizeof(mode) || mode != ACC_DEFER ||
            setsockopt(fd, DNPROTO_NSP, DSO_CONACCEPT, NULL, 0))
            goto fail;
    }
    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) ||
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout)))
        goto fail;

    memset(&peer, 0, sizeof(peer));
    if (getpeername(fd, (struct sockaddr *)&peer, &peer_len) ||
        peer_len != sizeof(peer) || peer.sdn_family != AF_DECnet ||
        dniv_le16_to_cpu(peer.sdn_nodeaddrl) != 2U)
        goto fail;
    node = (uint16_t)(peer.sdn_nodeaddr[0] |
                      ((uint16_t)peer.sdn_nodeaddr[1] << 8));
    if (node != expected_node || peer.sdn_objnum ||
        dniv_le16_to_cpu(peer.sdn_objnamel) != sizeof(SOURCE_NAME) - 1U ||
        memcmp(peer.sdn_objname, SOURCE_NAME, sizeof(SOURCE_NAME) - 1U))
        goto fail;

    memset(&conndata, 0, sizeof(conndata));
    optlen = sizeof(conndata);
    if (getsockopt(fd, DNPROTO_NSP, DSO_CONDATA, &conndata, &optlen) ||
        optlen != sizeof(conndata) ||
        dniv_le16_to_cpu(conndata.opt_optl) != sizeof(CONNECT_DATA) - 1U ||
        memcmp(conndata.opt_data, CONNECT_DATA, sizeof(CONNECT_DATA) - 1U))
        goto fail;

    memset(&access, 0, sizeof(access));
    optlen = sizeof(access);
    if (getsockopt(fd, DNPROTO_NSP, DSO_CONACCESS, &access, &optlen) ||
        optlen != sizeof(access) ||
        access.acc_userl != sizeof(ACCESS_USER) - 1U ||
        access.acc_passl != sizeof(ACCESS_PASS) - 1U ||
        access.acc_accl != sizeof(ACCESS_ACCOUNT) - 1U ||
        memcmp(access.acc_user, ACCESS_USER, sizeof(ACCESS_USER) - 1U) ||
        memcmp(access.acc_pass, ACCESS_PASS, sizeof(ACCESS_PASS) - 1U) ||
        memcmp(access.acc_acc, ACCESS_ACCOUNT, sizeof(ACCESS_ACCOUNT) - 1U))
        goto fail;

    got = recv(fd, buf, sizeof(buf), 0);
    if (got != (ssize_t)expected || memcmp(buf, payload, expected))
        goto fail;
    if (send(fd, buf, expected, MSG_EOR | MSG_NOSIGNAL) != (ssize_t)expected)
        goto fail;

    if (recv_oob(fd, OOB_ONE))
        goto fail;
    if (send(fd, OOB_REPLY, sizeof(OOB_REPLY) - 1U,
             MSG_OOB | MSG_NOSIGNAL) != (ssize_t)(sizeof(OOB_REPLY) - 1U))
        goto fail;
    if (recv_oob(fd, OOB_TWO))
        goto fail;

    got = recv(fd, buf, sizeof(buf), 0);
    if (got != (ssize_t)(sizeof(AFTER_OOB) - 1U) ||
        memcmp(buf, AFTER_OOB, sizeof(AFTER_OOB) - 1U))
        goto fail;
    if (send(fd, buf, (size_t)got, MSG_EOR | MSG_NOSIGNAL) != got)
        goto fail;

    got = recv(fd, buf, sizeof(buf), 0);
    if (got != 0)
        goto fail;
    close(fd);
    return 0;

fail:
    close(fd);
    return -1;
}

int main(int argc, char **argv)
{
    uint16_t expected_node;
    int numeric;
    int named;

    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc != 4 || parse_node(argv[1], &expected_node)) {
        fprintf(stderr, "usage: %s PEER-AREA.NODE SESSION SCENARIO\n", argv[0]);
        return 2;
    }

    numeric = make_listener(0);
    if (numeric < 0) {
        perror("numeric listener");
        return 1;
    }
    named = make_listener(1);
    if (named < 0) {
        perror("named listener");
        close(numeric);
        return 1;
    }

    printf("DNIV-INTEROP-LISTEN-READY session=%s scenario=%s\n",
           argv[2], argv[3]);
    if (serve_one(numeric, expected_node, "numeric-inbound", 0) ||
        serve_one(named, expected_node, "named-inbound", 1)) {
        fprintf(stderr, "dnaccept: inbound listener exchange failed\n");
        close(named);
        close(numeric);
        return 1;
    }

    close(named);
    close(numeric);
    printf("DNIV-INTEROP-LISTEN-SERVER-PASS session=%s scenario=%s options=access+condata+defer\n",
           argv[2], argv[3]);
    return 0;
}

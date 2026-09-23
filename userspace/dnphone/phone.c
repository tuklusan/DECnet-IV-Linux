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
#include <linux/dn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

#define PHONE_OBJECT 29U
#define PHONE_REPLYOK 0x01U
#define PHONE_CONNECT 0x07U
#define PHONE_DIAL 0x08U
#define PHONE_DATA 0x0eU

static int parse_target(const char *text, uint16_t *addr, const char **user)
{
    char node[16];
    const char *sep = strstr(text, "::");
    char *end;
    unsigned long area;
    unsigned long n;
    size_t len;

    if (!sep || !sep[2])
        return -1;
    len = (size_t)(sep - text);
    if (!len || len >= sizeof(node))
        return -1;
    memcpy(node, text, len);
    node[len] = '\0';
    errno = 0;
    area = strtoul(node, &end, 10);
    if (errno || end == node || *end != '.' || area > 63U)
        return -1;
    n = strtoul(end + 1, &end, 10);
    if (errno || *end || n == 0U || n > 1023U)
        return -1;
    *addr = (uint16_t)((area << 10) | n);
    *user = sep + 2;
    return strlen(*user) <= 40U ? 0 : -1;
}

static int connect_phone(uint16_t addr)
{
    struct sockaddr_dn peer;
    struct timeval timeout = { .tv_sec = 30, .tv_usec = 0 };
    int fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);

    if (fd < 0)
        return -1;
    if (setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout)) ||
        setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)))
        goto fail;
    memset(&peer, 0, sizeof(peer));
    peer.sdn_family = AF_DECnet;
    peer.sdn_objnum = PHONE_OBJECT;
    peer.sdn_add.a_len = 2;
    peer.sdn_add.a_addr[0] = (unsigned char)(addr & 0xffU);
    peer.sdn_add.a_addr[1] = (unsigned char)(addr >> 8);
    if (connect(fd, (struct sockaddr *)&peer, sizeof(peer)))
        goto fail;
    return fd;
fail:
    close(fd);
    return -1;
}

static int send_packet(int fd, unsigned char code, const char *source,
                       const char *tail, size_t tail_len)
{
    unsigned char buf[2048];
    size_t source_len = strlen(source);
    size_t total = 1U + source_len + 1U + tail_len;

    if (total > sizeof(buf))
        return -1;
    buf[0] = code;
    memcpy(buf + 1U, source, source_len + 1U);
    if (tail_len)
        memcpy(buf + 1U + source_len + 1U, tail, tail_len);
    return send(fd, buf, total, MSG_EOR | MSG_NOSIGNAL) == (ssize_t)total ? 0 : -1;
}

static int selftest(void)
{
    uint16_t addr;
    const char *user;

    if (parse_target("1.23::ALICE", &addr, &user) ||
        addr != 1047U || strcmp(user, "ALICE") ||
        !parse_target("1.0::ALICE", &addr, &user) ||
        !parse_target("1.23", &addr, &user))
        return 1;
    puts("phone selftest passed");
    return 0;
}

int main(int argc, char **argv)
{
    const char *source = "LINUX::USER";
    const char *target;
    const char *user;
    const char *message;
    uint16_t addr;
    unsigned char reply;
    char remote[96];
    int fd;
    int arg = 1;

    if (argc == 2 && !strcmp(argv[1], "--selftest"))
        return selftest();
    if (arg + 1 < argc && !strcmp(argv[arg], "-s")) {
        source = argv[arg + 1];
        arg += 2;
    }
    if (arg + 2 != argc) {
        fprintf(stderr, "usage: %s [-s NODE::USER] AREA.NODE::USER MESSAGE\n",
                argv[0]);
        return 2;
    }
    target = argv[arg];
    message = argv[arg + 1];
    if (strlen(source) > 80U || strlen(message) > 1800U ||
        parse_target(target, &addr, &user)) {
        fprintf(stderr, "phone: invalid arguments\n");
        return 2;
    }
    if (snprintf(remote, sizeof(remote), "%.*s::%s",
                 (int)(strstr(target, "::") - target), target, user) >=
        (int)sizeof(remote))
        return 2;

    fd = connect_phone(addr);
    if (fd < 0) {
        perror("phone: connect");
        return 1;
    }
    {
        unsigned char buf[256];
        size_t sl = strlen(source), rl = strlen(remote);
        size_t total = 1U + sl + 1U + rl + 1U;

        if (total > sizeof(buf)) {
            close(fd);
            return 2;
        }
        buf[0] = PHONE_CONNECT;
        memcpy(buf + 1U, source, sl + 1U);
        memcpy(buf + 1U + sl + 1U, remote, rl + 1U);
        if (send(fd, buf, total, MSG_EOR | MSG_NOSIGNAL) != (ssize_t)total)
            goto fail;
    }
    if (recv(fd, &reply, 1U, 0) != 1 || reply != PHONE_REPLYOK)
        goto fail;
    {
        unsigned char dial[128];
        size_t sl = strlen(source);
        size_t total = 1U + sl + 1U + 1U;

        if (total > sizeof(dial))
            goto fail;
        dial[0] = PHONE_DIAL;
        memcpy(dial + 1U, source, sl + 1U);
        dial[total - 1U] = 1U;
        if (send(fd, dial, total, MSG_EOR | MSG_NOSIGNAL) != (ssize_t)total)
            goto fail;
    }
    if (recv(fd, &reply, 1U, 0) != 1 || reply != PHONE_REPLYOK)
        goto fail;
    if (send_packet(fd, PHONE_DATA, source, message, strlen(message)))
        goto fail;
    close(fd);
    return 0;

fail:
    fprintf(stderr, "phone: protocol failure\n");
    close(fd);
    return 1;
}

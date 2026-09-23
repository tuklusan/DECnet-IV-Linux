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

#define MAIL_OBJECT 27U

static int parse_target(const char *text, uint16_t *addr, const char **user)
{
    char node[16];
    const char *sep = strstr(text, "::");
    char *end;
    unsigned long area, n;
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
    return strlen(*user) < 256U ? 0 : -1;
}

static int connect_mail(uint16_t addr)
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
    peer.sdn_objnum = MAIL_OBJECT;
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

static int send_record(int fd, const void *data, size_t len)
{
    return send(fd, data, len, MSG_EOR | MSG_NOSIGNAL) == (ssize_t)len ? 0 : -1;
}

static int recv_ack(int fd)
{
    unsigned char ack[8];
    ssize_t got = recv(fd, ack, sizeof(ack), 0);

    return got == 4 && ack[0] == 1U && ack[1] == 0U &&
        ack[2] == 0U && ack[3] == 0U ? 0 : -1;
}

static int send_recipients(int fd, const char *users)
{
    char list[256];
    char *part;
    char *save = NULL;
    const unsigned char zero = 0U;

    if (strlen(users) >= sizeof(list))
        return -1;
    strcpy(list, users);
    part = strtok_r(list, ",", &save);
    if (!part)
        return -1;
    while (part) {
        if (!*part || send_record(fd, part, strlen(part)) || recv_ack(fd))
            return -1;
        part = strtok_r(NULL, ",", &save);
    }
    return send_record(fd, &zero, 1U);
}

static int selftest(void)
{
    uint16_t addr;
    const char *user;

    if (parse_target("1.23::ALICE,BOB", &addr, &user) ||
        addr != 1047U || strcmp(user, "ALICE,BOB") ||
        !parse_target("1.0::ALICE", &addr, &user))
        return 1;
    puts("dnmail selftest passed");
    return 0;
}

int main(int argc, char **argv)
{
    const char *from = "LINUX";
    const char *subject = "No subject";
    const char *target;
    const char *user;
    const char *message;
    uint16_t addr;
    int fd;
    int arg = 1;
    const unsigned char zero = 0U;

    if (argc == 2 && !strcmp(argv[1], "--selftest"))
        return selftest();
    while (arg + 1 < argc) {
        if (!strcmp(argv[arg], "-f")) {
            from = argv[arg + 1];
            arg += 2;
            continue;
        }
        if (!strcmp(argv[arg], "-s")) {
            subject = argv[arg + 1];
            arg += 2;
            continue;
        }
        break;
    }
    if (arg + 2 != argc) {
        fprintf(stderr,
                "usage: %s [-f FROM] [-s SUBJECT] AREA.NODE::USER[,USER...] MESSAGE\n",
                argv[0]);
        return 2;
    }
    target = argv[arg];
    message = argv[arg + 1];
    if (!*from || strlen(from) >= 256U || strlen(subject) >= 256U ||
        strlen(message) > 4095U || parse_target(target, &addr, &user)) {
        fprintf(stderr, "dnmail: invalid arguments\n");
        return 2;
    }

    fd = connect_mail(addr);
    if (fd < 0) {
        perror("dnmail: connect");
        return 1;
    }
    if (send_record(fd, from, strlen(from)) ||
        send_recipients(fd, user) ||
        send_record(fd, target, strlen(target)) ||
        send_record(fd, subject, strlen(subject)) ||
        send_record(fd, message, strlen(message)) ||
        send_record(fd, &zero, 1U) ||
        recv_ack(fd)) {
        fprintf(stderr, "dnmail: MAIL-11 protocol failure\n");
        close(fd);
        return 1;
    }
    close(fd);
    return 0;
}

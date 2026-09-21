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

static int send_record(int fd, const char *tag, int flags)
{
    unsigned char buf[128];
    size_t n = strlen(tag);

    if (n + 1U > sizeof(buf))
        return -1;
    buf[0] = 0U;
    memcpy(buf + 1U, tag, n);
    return send(fd, buf, n + 1U, MSG_EOR | MSG_NOSIGNAL | flags) ==
           (ssize_t)(n + 1U) ? 0 : -1;
}

int main(int argc, char **argv)
{
    struct sockaddr_dn peer;
    struct timeval timeout = { .tv_sec = 12, .tv_usec = 0 };
    uint16_t address;
    int fd;

    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc != 4 || parse_node(argv[1], &address)) {
        fprintf(stderr, "usage: %s AREA.NODE SESSION SCENARIO\n", argv[0]);
        return 2;
    }

    fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (fd < 0) {
        perror("socket(AF_DECnet)");
        return 1;
    }
    if (setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout))) {
        perror("setsockopt(SO_SNDTIMEO)");
        close(fd);
        return 1;
    }

    memset(&peer, 0, sizeof(peer));
    peer.sdn_family = AF_DECnet;
    peer.sdn_objnum = 25U;
    peer.sdn_nodeaddrl = (__le16)2U;
    peer.sdn_nodeaddr[0] = (unsigned char)(address & 0xffU);
    peer.sdn_nodeaddr[1] = (unsigned char)(address >> 8);
    if (connect(fd, (struct sockaddr *)&peer, sizeof(peer))) {
        perror("connect(MIRROR flow probe)");
        close(fd);
        return 1;
    }

    if (send_record(fd, "DNIV-FLOW-FIRST", 0)) {
        perror("send(flow first)");
        close(fd);
        return 1;
    }
    sleep(2);

    errno = 0;
    if (!send_record(fd, "DNIV-FLOW-BLOCKED", MSG_DONTWAIT) ||
        (errno != EAGAIN && errno != EWOULDBLOCK)) {
        fprintf(stderr, "flow XOFF did not block normal data: errno=%d\n", errno);
        close(fd);
        return 1;
    }
    printf("DNIV-INTEROP-FLOW-XOFF session=%s scenario=%s peer=%s\n",
           argv[2], argv[3], argv[1]);

    if (send_record(fd, "DNIV-FLOW-XON", 0)) {
        perror("send(flow XON)");
        close(fd);
        return 1;
    }
    printf("DNIV-INTEROP-FLOW-XON session=%s scenario=%s peer=%s\n",
           argv[2], argv[3], argv[1]);

    close(fd);
    return 0;
}

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

#define WINDOW_COUNT 8U

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

static int send_tag(int fd, unsigned int tag, int flags)
{
    unsigned char buf[32];
    int len = snprintf((char *)buf + 1, sizeof(buf) - 1, "DNIV-WINDOW-%u", tag);
    size_t total;

    if (len < 0 || (size_t)len >= sizeof(buf) - 1U) {
        errno = EINVAL;
        return -1;
    }
    buf[0] = 0U;
    total = (size_t)len + 1U;
    if (send(fd, buf, total, flags | MSG_EOR | MSG_NOSIGNAL) != (ssize_t)total)
        return -1;
    return 0;
}

int main(int argc, char **argv)
{
    struct sockaddr_dn peer;
    struct timeval timeout = { .tv_sec = 30, .tv_usec = 0 };
    uint16_t address;
    unsigned int i;
    int fd = -1;

    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc != 4 || parse_node(argv[1], &address)) {
        fprintf(stderr, "usage: %s AREA.NODE SESSION SCENARIO\n", argv[0]);
        return 2;
    }
    fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (fd < 0)
        goto fail;
    if (setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout)) ||
        setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)))
        goto fail;
    memset(&peer, 0, sizeof(peer));
    peer.sdn_family = AF_DECnet;
    peer.sdn_objnum = 25U;
    peer.sdn_nodeaddrl = (__le16)2U;
    peer.sdn_nodeaddr[0] = (unsigned char)(address & 0xffU);
    peer.sdn_nodeaddr[1] = (unsigned char)(address >> 8);
    if (connect(fd, (struct sockaddr *)&peer, sizeof(peer)))
        goto fail;

    printf("DNIV-INTEROP-WINDOW-READY session=%s scenario=%s peer=%s\n",
           argv[2], argv[3], argv[1]);
    sleep(3);
    for (i = 0U; i < WINDOW_COUNT; i++)
        if (send_tag(fd, i + 1U, MSG_DONTWAIT))
            goto fail;

    errno = 0;
    if (!send_tag(fd, WINDOW_COUNT + 1U, MSG_DONTWAIT) ||
        (errno != EAGAIN && errno != EWOULDBLOCK)) {
        fprintf(stderr, "window did not stop ninth segment: errno=%d\n", errno);
        goto fail;
    }
    printf("DNIV-INTEROP-WINDOW-FULL session=%s scenario=%s peer=%s count=%u\n",
           argv[2], argv[3], argv[1], WINDOW_COUNT);

    if (send_tag(fd, WINDOW_COUNT + 1U, 0))
        goto fail;
    printf("DNIV-INTEROP-WINDOW-RESUMED session=%s scenario=%s peer=%s\n",
           argv[2], argv[3], argv[1]);
    close(fd);
    printf("dnwindow: pass peer=%s full=%u blocked=1 resumed=1\n",
           argv[1], WINDOW_COUNT);
    return 0;

fail:
    fprintf(stderr, "dnwindow: failed errno=%d (%s)\n", errno, strerror(errno));
    if (fd >= 0)
        close(fd);
    return 1;
}

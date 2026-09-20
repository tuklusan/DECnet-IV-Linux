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
#include <sys/epoll.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <sys/wait.h>
#include <unistd.h>

#include <linux/dn.h>

#define CONCURRENT 8U
#define PAYLOAD 128U

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

static void fill_peer(struct sockaddr_dn *peer, uint16_t address)
{
    memset(peer, 0, sizeof(*peer));
    peer->sdn_family = AF_DECnet;
    peer->sdn_objnum = 25U;
    peer->sdn_nodeaddrl = (__le16)2U;
    peer->sdn_nodeaddr[0] = (unsigned char)(address & 0xffU);
    peer->sdn_nodeaddr[1] = (unsigned char)(address >> 8);
}

static int open_mirror(const struct sockaddr_dn *peer)
{
    struct timeval timeout = { .tv_sec = 20, .tv_usec = 0 };
    int fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);

    if (fd < 0)
        return -1;
    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) ||
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout)) ||
        connect(fd, (const struct sockaddr *)peer, sizeof(*peer))) {
        close(fd);
        return -1;
    }
    return fd;
}

static void make_payload(unsigned char *buf, size_t len, unsigned int tag)
{
    size_t i;

    buf[0] = 0U;
    for (i = 1U; i < len; i++)
        buf[i] = (unsigned char)((i * 31U + tag * 7U) & 0xffU);
}

static int exchange(int fd, unsigned int tag)
{
    unsigned char tx[PAYLOAD], rx[PAYLOAD];
    ssize_t got;

    make_payload(tx, sizeof(tx), tag);
    if (send(fd, tx, sizeof(tx), MSG_EOR | MSG_NOSIGNAL) !=
        (ssize_t)sizeof(tx))
        return -1;
    got = recv(fd, rx, sizeof(rx), 0);
    if (got != (ssize_t)sizeof(rx) || rx[0] != 1U ||
        memcmp(rx + 1U, tx + 1U, sizeof(tx) - 1U))
        return -1;
    return 0;
}

static int readiness_test(const struct sockaddr_dn *peer)
{
    struct pollfd pfd;
    struct epoll_event event;
    int epfd = -1;
    int fd = open_mirror(peer);

    if (fd < 0)
        return -1;
    memset(&pfd, 0, sizeof(pfd));
    pfd.fd = fd;
    pfd.events = POLLOUT;
    if (poll(&pfd, 1, 1000) != 1 || !(pfd.revents & POLLOUT))
        goto fail;

    epfd = epoll_create1(EPOLL_CLOEXEC);
    if (epfd < 0)
        goto fail;
    memset(&event, 0, sizeof(event));
    event.events = EPOLLOUT;
    event.data.fd = fd;
    if (epoll_ctl(epfd, EPOLL_CTL_ADD, fd, &event))
        goto fail;
    memset(&event, 0, sizeof(event));
    if (epoll_wait(epfd, &event, 1, 1000) != 1 ||
        !(event.events & EPOLLOUT))
        goto fail;
    if (exchange(fd, 1U))
        goto fail;
    close(epfd);
    close(fd);
    return 0;

fail:
    if (epfd >= 0)
        close(epfd);
    close(fd);
    return -1;
}

static int dup_test(const struct sockaddr_dn *peer)
{
    int fd = open_mirror(peer);
    int copy;

    if (fd < 0)
        return -1;
    copy = dup(fd);
    if (copy < 0) {
        close(fd);
        return -1;
    }
    close(fd);
    if (exchange(copy, 2U)) {
        close(copy);
        return -1;
    }
    close(copy);
    return 0;
}

static int fork_test(const struct sockaddr_dn *peer)
{
    int status;
    int fd = open_mirror(peer);
    pid_t pid;

    if (fd < 0)
        return -1;
    pid = fork();
    if (pid < 0) {
        close(fd);
        return -1;
    }
    if (pid == 0) {
        int rc = exchange(fd, 3U);
        close(fd);
        _exit(rc ? 1 : 0);
    }
    close(fd);
    if (waitpid(pid, &status, 0) != pid || !WIFEXITED(status) ||
        WEXITSTATUS(status) != 0)
        return -1;
    return 0;
}

static int exit_cleanup_test(const struct sockaddr_dn *peer)
{
    int status;
    pid_t pid = fork();

    if (pid < 0)
        return -1;
    if (pid == 0) {
        int fd = open_mirror(peer);
        if (fd < 0)
            _exit(1);
        if (exchange(fd, 4U))
            _exit(1);
        _exit(0);
    }
    if (waitpid(pid, &status, 0) != pid || !WIFEXITED(status) ||
        WEXITSTATUS(status) != 0)
        return -1;

    {
        int fd = open_mirror(peer);
        int rc;
        if (fd < 0)
            return -1;
        rc = exchange(fd, 5U);
        close(fd);
        return rc;
    }
}

static int concurrent_test(const struct sockaddr_dn *peer)
{
    int fds[CONCURRENT];
    unsigned int i;

    for (i = 0U; i < CONCURRENT; i++)
        fds[i] = -1;
    for (i = 0U; i < CONCURRENT; i++) {
        fds[i] = open_mirror(peer);
        if (fds[i] < 0)
            goto fail;
    }
    for (i = 0U; i < CONCURRENT; i++) {
        unsigned char tx[PAYLOAD];
        make_payload(tx, sizeof(tx), 100U + i);
        if (send(fds[i], tx, sizeof(tx), MSG_EOR | MSG_NOSIGNAL) !=
            (ssize_t)sizeof(tx))
            goto fail;
    }
    for (i = 0U; i < CONCURRENT; i++) {
        unsigned char tx[PAYLOAD], rx[PAYLOAD];
        ssize_t got;
        make_payload(tx, sizeof(tx), 100U + i);
        got = recv(fds[i], rx, sizeof(rx), 0);
        if (got != (ssize_t)sizeof(rx) || rx[0] != 1U ||
            memcmp(rx + 1U, tx + 1U, sizeof(tx) - 1U))
            goto fail;
    }
    for (i = 0U; i < CONCURRENT; i++)
        close(fds[i]);
    return 0;

fail:
    for (i = 0U; i < CONCURRENT; i++)
        if (fds[i] >= 0)
            close(fds[i]);
    return -1;
}

int main(int argc, char **argv)
{
    struct sockaddr_dn peer;
    uint16_t address;

    if (argc != 2 || parse_node(argv[1], &address)) {
        fprintf(stderr, "usage: %s AREA.NODE\n", argv[0]);
        return 2;
    }
    fill_peer(&peer, address);

    if (readiness_test(&peer) || dup_test(&peer) || fork_test(&peer) ||
        exit_cleanup_test(&peer) || concurrent_test(&peer)) {
        fprintf(stderr, "dnsockstress: failed errno=%d\n", errno);
        return 1;
    }
    printf("dnsockstress: pass peer=%s concurrent=%u poll=1 epoll=1 dup=1 fork=1 exit=1\n",
           argv[1], CONCURRENT);
    return 0;
}

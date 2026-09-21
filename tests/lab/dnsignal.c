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

#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

#include <linux/dn.h>

#define SIGNAL_OBJECT 247U
#define PAYLOAD 64U

static volatile sig_atomic_t got_alarm;

static void alarm_handler(int signo)
{
    (void)signo;
    got_alarm = 1;
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

static void fill_peer(struct sockaddr_dn *peer, uint16_t address)
{
    memset(peer, 0, sizeof(*peer));
    peer->sdn_family = AF_DECnet;
    peer->sdn_objnum = 25U;
    peer->sdn_nodeaddrl = (__le16)2U;
    peer->sdn_nodeaddr[0] = (unsigned char)(address & 0xffU);
    peer->sdn_nodeaddr[1] = (unsigned char)(address >> 8);
}

static int accept_eintr(void)
{
    struct sockaddr_dn local;
    int listener;
    int rc;

    listener = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (listener < 0)
        return -1;
    memset(&local, 0, sizeof(local));
    local.sdn_family = AF_DECnet;
    local.sdn_objnum = SIGNAL_OBJECT;
    if (bind(listener, (struct sockaddr *)&local, sizeof(local)) ||
        listen(listener, 1)) {
        close(listener);
        return -1;
    }

    got_alarm = 0;
    alarm(1);
    errno = 0;
    rc = accept(listener, NULL, NULL);
    alarm(0);
    if (rc >= 0) {
        close(rc);
        close(listener);
        errno = EPROTO;
        return -1;
    }
    if (errno != EINTR || !got_alarm) {
        close(listener);
        return -1;
    }
    close(listener);
    return 0;
}

static int recv_eintr_and_recover(const struct sockaddr_dn *peer)
{
    unsigned char tx[PAYLOAD], rx[PAYLOAD];
    size_t i;
    ssize_t got;
    int fd;

    fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (fd < 0)
        return -1;
    if (connect(fd, (const struct sockaddr *)peer, sizeof(*peer))) {
        close(fd);
        return -1;
    }

    got_alarm = 0;
    alarm(1);
    errno = 0;
    got = recv(fd, rx, sizeof(rx), 0);
    alarm(0);
    if (got >= 0 || errno != EINTR || !got_alarm) {
        close(fd);
        if (got >= 0)
            errno = EPROTO;
        return -1;
    }

    tx[0] = 0U;
    for (i = 1U; i < sizeof(tx); i++)
        tx[i] = (unsigned char)(i * 13U + 7U);
    if (send(fd, tx, sizeof(tx), MSG_EOR | MSG_NOSIGNAL) !=
        (ssize_t)sizeof(tx)) {
        close(fd);
        return -1;
    }
    got = recv(fd, rx, sizeof(rx), 0);
    if (got != (ssize_t)sizeof(rx) || rx[0] != 1U ||
        memcmp(rx + 1U, tx + 1U, sizeof(tx) - 1U)) {
        close(fd);
        return -1;
    }
    close(fd);
    return 0;
}

int main(int argc, char **argv)
{
    struct sigaction sa;
    struct sockaddr_dn peer;
    uint16_t address;

    if (argc != 2 || parse_node(argv[1], &address)) {
        fprintf(stderr, "usage: %s AREA.NODE\n", argv[0]);
        return 2;
    }
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = alarm_handler;
    sigemptyset(&sa.sa_mask);
    if (sigaction(SIGALRM, &sa, NULL)) {
        perror("sigaction");
        return 1;
    }
    fill_peer(&peer, address);

    if (accept_eintr() || recv_eintr_and_recover(&peer)) {
        fprintf(stderr, "dnsignal: failed errno=%d (%s)\n", errno, strerror(errno));
        return 1;
    }
    printf("dnsignal: pass peer=%s accept_eintr=1 recv_eintr=1 recover=1\n", argv[1]);
    return 0;
}

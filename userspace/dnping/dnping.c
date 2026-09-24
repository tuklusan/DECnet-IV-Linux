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
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

#include <netdnet/dnetdb.h>

#define DNPING_DEFAULT_COUNT 10
#define DNPING_DEFAULT_SIZE 40
#define DNPING_MAX_SIZE 65023

static void usage(const char *prog)
{
    fprintf(stderr,
            "usage: %s [-qv] [-c count] [-i usec] [-s bytes] [-w seconds] node\n",
            prog);
}

static long elapsed_us(const struct timeval *start, const struct timeval *end)
{
    return (end->tv_sec - start->tv_sec) * 1000000L +
           (end->tv_usec - start->tv_usec);
}

static int parse_positive(const char *text, long max, long *out)
{
    char *end;
    long value;

    errno = 0;
    value = strtol(text, &end, 10);
    if (errno || end == text || *end || value <= 0 || value > max)
        return -1;
    *out = value;
    return 0;
}

static int run_selftest(void)
{
    long value = 0;

    if (parse_positive("3", 10, &value) || value != 3)
        return 1;
    if (!parse_positive("0", 10, &value))
        return 1;
    if (!parse_positive("11", 10, &value))
        return 1;
    puts("dnping selftest passed");
    return 0;
}

int main(int argc, char **argv)
{
    unsigned char *tx;
    unsigned char *rx;
    const char *node = NULL;
    int count = DNPING_DEFAULT_COUNT;
    int size = DNPING_DEFAULT_SIZE;
    int interval_us = 0;
    int timeout_sec = 10;
    int quiet = 0;
    int verbose = 0;
    int sent = 0;
    int received = 0;
    long min_us = 0;
    long max_us = 0;
    long total_us = 0;
    int fd;
    int i;

    if (argc == 2 && !strcmp(argv[1], "--selftest"))
        return run_selftest();

    for (i = 1; i < argc; i++) {
        long value;

        if (!strcmp(argv[i], "-q")) {
            quiet = 1;
        } else if (!strcmp(argv[i], "-v")) {
            verbose = 1;
        } else if ((!strcmp(argv[i], "-c") || !strcmp(argv[i], "-i") ||
                    !strcmp(argv[i], "-s") || !strcmp(argv[i], "-w")) &&
                   i + 1 < argc) {
            const char *opt = argv[i++];
            if (!strcmp(opt, "-c")) {
                if (parse_positive(argv[i], 1000000L, &value))
                    goto bad_usage;
                count = (int)value;
            } else if (!strcmp(opt, "-i")) {
                if (parse_positive(argv[i], 60000000L, &value))
                    goto bad_usage;
                interval_us = (int)value;
            } else if (!strcmp(opt, "-s")) {
                if (parse_positive(argv[i], DNPING_MAX_SIZE, &value))
                    goto bad_usage;
                size = (int)value;
            } else {
                if (parse_positive(argv[i], 3600L, &value))
                    goto bad_usage;
                timeout_sec = (int)value;
            }
        } else if (argv[i][0] == '-') {
            goto bad_usage;
        } else if (!node) {
            node = argv[i];
        } else {
            goto bad_usage;
        }
    }

    if (!node)
        goto bad_usage;

    tx = malloc((size_t)size);
    rx = malloc((size_t)size);
    if (!tx || !rx) {
        perror("dnping: malloc");
        free(tx);
        free(rx);
        return 1;
    }
    memset(tx, 0x85, (size_t)size);
    tx[0] = 0U;

    fd = dnet_conn((char *)node, "MIRROR", SOCK_SEQPACKET,
                   NULL, 0, NULL, NULL);
    if (fd < 0) {
        if (!quiet)
            perror("dnping: connect");
        free(tx);
        free(rx);
        return 1;
    }

    {
        struct timeval timeout = { timeout_sec, 0 };
        if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO,
                       &timeout, sizeof(timeout))) {
            if (!quiet)
                perror("dnping: timeout");
            close(fd);
            free(tx);
            free(rx);
            return 1;
        }
    }

    for (i = 0; i < count; i++) {
        struct timeval start;
        struct timeval end;
        int got;
        long rtt;

        tx[size > 1 ? 1 : 0] = (unsigned char)(i & 0xff);
        if (gettimeofday(&start, NULL)) {
            if (!quiet)
                perror("dnping: gettimeofday");
            break;
        }
        if (send(fd, tx, (size_t)size, MSG_EOR | MSG_NOSIGNAL) != size) {
            if (!quiet)
                perror("dnping: send");
            break;
        }
        sent++;
        got = dnet_recv(fd, rx, size, MSG_EOR);
        if (got != size || rx[0] != 1U ||
            (size > 1 && memcmp(tx + 1, rx + 1, (size_t)size - 1U))) {
            if (!quiet)
                fprintf(stderr, "dnping: loopback mismatch on packet %d\n", i + 1);
            break;
        }
        if (gettimeofday(&end, NULL)) {
            if (!quiet)
                perror("dnping: gettimeofday");
            break;
        }
        received++;
        rtt = elapsed_us(&start, &end);
        total_us += rtt;
        if (received == 1 || rtt < min_us)
            min_us = rtt;
        if (received == 1 || rtt > max_us)
            max_us = rtt;
        if (verbose)
            printf("packet %d: %d bytes time=%ld.%03ld ms\n",
                   i + 1, size, rtt / 1000L, rtt % 1000L);

        if (interval_us > 0 && i + 1 < count) {
            struct timeval delay;
            delay.tv_sec = interval_us / 1000000;
            delay.tv_usec = interval_us % 1000000;
            (void)select(0, NULL, NULL, NULL, &delay);
        }
    }

    close(fd);
    free(tx);
    free(rx);

    if (!quiet) {
        printf("Sent %d packets, Received %d packets\n", sent, received);
        if (received)
            printf("round-trip min/avg/max = %ld.%03ld/%ld.%03ld/%ld.%03ld ms\n",
                   min_us / 1000L, min_us % 1000L,
                   (total_us / received) / 1000L,
                   (total_us / received) % 1000L,
                   max_us / 1000L, max_us % 1000L);
    }
    return sent == count && received == count ? 0 : 1;

bad_usage:
    usage(argv[0]);
    return 2;
}

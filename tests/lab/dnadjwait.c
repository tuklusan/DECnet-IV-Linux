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
#include <fcntl.h>
#include <linux/decnet_iv.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>

#define DNIV_DEVICE "/dev/decnet_iv"
#define DNIV_MAX_SCAN 64U

static int parse_address(const char *text, __u16 *address)
{
    char copy[32];
    char *dot;
    char *end;
    unsigned long area;
    unsigned long node;

    if (strlen(text) >= sizeof(copy))
        return -1;
    strcpy(copy, text);
    dot = strchr(copy, '.');
    if (!dot || strchr(dot + 1, '.'))
        return -1;
    *dot++ = '\0';

    errno = 0;
    area = strtoul(copy, &end, 10);
    if (errno || *copy == '\0' || *end != '\0' || area < 1 || area > 63)
        return -1;

    errno = 0;
    node = strtoul(dot, &end, 10);
    if (errno || *dot == '\0' || *end != '\0' || node < 1 || node > 1023)
        return -1;

    *address = DNIV_ADDR(area, node);
    return 0;
}

static uint64_t monotonic_ms(void)
{
    struct timespec ts;

    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0)
        return 0;
    return (uint64_t)ts.tv_sec * 1000U + (uint64_t)ts.tv_nsec / 1000000U;
}

static int adjacency_state(int fd, __u16 address, int *present, int *up)
{
    __u32 index;

    *present = 0;
    *up = 0;
    for (index = 0; index < DNIV_MAX_SCAN; index++) {
        struct dniv_adjacency adjacency;

        memset(&adjacency, 0, sizeof(adjacency));
        adjacency.uapi_version = DNIV_UAPI_VERSION;
        adjacency.index = index;
        if (ioctl(fd, DNIV_IOC_GET_ADJACENCY, &adjacency) < 0) {
            if (errno == ENOENT)
                return 0;
            perror("DNIV_IOC_GET_ADJACENCY");
            return -1;
        }
        if (adjacency.address == address) {
            *present = 1;
            *up = adjacency.state == DNIV_ADJ_STATE_UP;
            return 0;
        }
    }
    return 0;
}

int main(int argc, char **argv)
{
    const struct timespec pause = { .tv_sec = 0, .tv_nsec = 10000000L };
    __u16 address;
    uint64_t deadline;
    unsigned long timeout_ms;
    char *end;
    int want_up;
    int fd;

    if (argc != 4 || (strcmp(argv[1], "gone") != 0 &&
                      strcmp(argv[1], "up") != 0)) {
        fprintf(stderr, "usage: %s gone|up AREA.NODE TIMEOUT_MS\n", argv[0]);
        return 2;
    }
    if (parse_address(argv[2], &address) != 0) {
        fprintf(stderr, "dnadjwait: invalid DECnet address\n");
        return 2;
    }

    errno = 0;
    timeout_ms = strtoul(argv[3], &end, 10);
    if (errno || *argv[3] == '\0' || *end != '\0' ||
        timeout_ms < 1 || timeout_ms > 600000) {
        fprintf(stderr, "dnadjwait: invalid timeout\n");
        return 2;
    }

    fd = open(DNIV_DEVICE, O_RDONLY);
    if (fd < 0) {
        perror(DNIV_DEVICE);
        return 2;
    }

    want_up = strcmp(argv[1], "up") == 0;
    deadline = monotonic_ms() + timeout_ms;
    for (;;) {
        int present;
        int up;

        if (adjacency_state(fd, address, &present, &up) != 0) {
            close(fd);
            return 2;
        }
        if ((!want_up && !present) || (want_up && present && up)) {
            close(fd);
            return 0;
        }
        if (monotonic_ms() >= deadline)
            break;
        nanosleep(&pause, NULL);
    }

    close(fd);
    return 1;
}

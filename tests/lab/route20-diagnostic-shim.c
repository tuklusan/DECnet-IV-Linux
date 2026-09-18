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

#define _GNU_SOURCE
#include <execinfo.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

static void dniv_route20_crash(int sig, siginfo_t *info, void *context)
{
    void *frames[64];
    int fd;
    int count;
    (void)context;

    fd = open("/run/reference/route20-backtrace.log",
              O_WRONLY | O_CREAT | O_TRUNC, 0600);
    if (fd >= 0) {
        dprintf(fd, "DNIV-ROUTE20-SIGNAL sig=%d addr=%p\n", sig, info->si_addr);
        count = backtrace(frames, (int)(sizeof(frames) / sizeof(frames[0])));
        backtrace_symbols_fd(frames, count, fd);
        fsync(fd);
        close(fd);
    }
    _exit(128 + sig);
}

__attribute__((constructor))
static void dniv_route20_install_crash_handler(void)
{
    struct sigaction action;
    sigemptyset(&action.sa_mask);
    action.sa_sigaction = dniv_route20_crash;
    action.sa_flags = SA_SIGINFO | SA_RESETHAND;
    sigaction(SIGSEGV, &action, NULL);
    sigaction(SIGBUS, &action, NULL);
    sigaction(SIGILL, &action, NULL);
}

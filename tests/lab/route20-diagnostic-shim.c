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
#include <dlfcn.h>
#include <execinfo.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <ucontext.h>
#include <unistd.h>

#include "route20.h"

static void dniv_log_site(int fd, uintptr_t site)
{
    Dl_info symbol;
    const char *name = "?";
    uintptr_t offset = 0;

    if (site != 0 && dladdr((void *)site, &symbol) != 0) {
        if (symbol.dli_sname != NULL)
            name = symbol.dli_sname;
        if (symbol.dli_saddr != NULL)
            offset = site - (uintptr_t)symbol.dli_saddr;
    }
    dprintf(fd, "DNIV-ROUTE20-CALLSITE address=%p symbol=%s offset=0x%lx\n",
            (void *)site, name, (unsigned long)offset);
}

static void dniv_log_event_handlers(int fd)
{
    int i;

    dprintf(fd, "DNIV-ROUTE20-EVENTS count=%d changed=%d\n",
            numEventHandlers, eventHandlersChanged);
    for (i = 0; i < numEventHandlers; i++) {
        dprintf(fd,
                "DNIV-ROUTE20-EVENT index=%d handle=%u context=%p handler=%p name=%s\n",
                i,
                eventHandlers[i].waitHandle,
                eventHandlers[i].context,
                (void *)eventHandlers[i].eventHandler,
                eventHandlers[i].name != NULL ? eventHandlers[i].name : "?");
    }
}

static void dniv_route20_crash(int sig, siginfo_t *info, void *context)
{
    ucontext_t *uc = (ucontext_t *)context;
    void *frames[64];
    uintptr_t site = 0;
    int fd;
    int count;

#if defined(__x86_64__)
    uintptr_t sp = (uintptr_t)uc->uc_mcontext.gregs[REG_RSP];
    if (sp != 0)
        site = *(uintptr_t *)sp;
#elif defined(__aarch64__)
    site = (uintptr_t)uc->uc_mcontext.regs[30];
#endif

    fd = open("/run/reference/route20-backtrace.log",
              O_WRONLY | O_CREAT | O_TRUNC, 0600);
    if (fd >= 0) {
        dprintf(fd, "DNIV-ROUTE20-SIGNAL sig=%d addr=%p\n", sig, info->si_addr);
        dniv_log_site(fd, site);
        dniv_log_event_handlers(fd);
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

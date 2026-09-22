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
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#define NCP_MAX_WORDS 16
#define NCP_MAX_ARGS 8
#define DNIV_DEVICE "/dev/decnet_iv"

struct ncp_plan {
    char local_target[16];
    char *argv[NCP_MAX_ARGS];
    int argc;
};

static void usage(FILE *stream)
{
    fputs("usage:\n"
          "  ncp show executor [summary|status|characteristics|counters]\n"
          "  ncp show node AREA.NODE [summary|status]\n"
          "  ncp show known|active|adjacent nodes [summary|status]\n"
          "  ncp show circuit NAME [status|counters]\n"
          "  ncp show known|active circuits [status|counters]\n"
          "  ncp tell AREA.NODE <show-command>\n"
          "  ncp set executor name NAME\n"
          "  ncp zero executor\n"
          "  ncp\n", stream);
}

static int local_target(char out[16])
{
    struct dniv_identity identity;
    int fd = open(DNIV_DEVICE, O_RDONLY);

    if (fd < 0) {
        perror(DNIV_DEVICE);
        return -1;
    }
    memset(&identity, 0, sizeof(identity));
    if (ioctl(fd, DNIV_IOC_GET_IDENTITY, &identity) < 0) {
        perror("DNIV_IOC_GET_IDENTITY");
        close(fd);
        return -1;
    }
    close(fd);
    if (identity.uapi_version != DNIV_UAPI_VERSION) {
        fprintf(stderr, "ncp: unsupported kernel UAPI version %u\n",
                identity.uapi_version);
        return -1;
    }
    snprintf(out, 16, "%u.%u", DNIV_ADDR_AREA(identity.address),
             DNIV_ADDR_NODE(identity.address));
    return 0;
}

static int info_ok(const char *s, int executor, int circuit)
{
    if (circuit)
        return strcmp(s, "status") == 0 || strcmp(s, "counters") == 0;
    if (executor)
        return strcmp(s, "summary") == 0 || strcmp(s, "status") == 0 ||
               strcmp(s, "characteristics") == 0 ||
               strcmp(s, "counters") == 0;
    return strcmp(s, "summary") == 0 || strcmp(s, "status") == 0;
}

static int build_plan(char **word, int nword, const char *local,
                      struct ncp_plan *plan)
{
    const char *target = local;
    int off = 0;
    int n;

    memset(plan, 0, sizeof(*plan));
    if (nword >= 2 && strcmp(word[0], "tell") == 0) {
        target = word[1];
        off = 2;
    }
    if (!target || !*target || off >= nword)
        return -1;
    if (strcmp(word[off], "show") != 0 && strcmp(word[off], "list") != 0)
        return -1;
    n = nword - off;
    plan->argv[0] = "dnnice";
    plan->argv[1] = (char *)target;

    if (n >= 2 && strcmp(word[off + 1], "executor") == 0) {
        const char *info = n == 2 ? "summary" : word[off + 2];

        if (n > 3 || !info_ok(info, 1, 0))
            return -1;
        plan->argv[2] = (char *)info;
        plan->argc = 3;
    } else if (n >= 3 && strcmp(word[off + 1], "node") == 0) {
        const char *info = n == 3 ? "status" : word[off + 3];

        if (n > 4 || !info_ok(info, 0, 0))
            return -1;
        plan->argv[2] = "node";
        plan->argv[3] = word[off + 2];
        plan->argv[4] = (char *)info;
        plan->argc = 5;
    } else if (n >= 3 &&
               (strcmp(word[off + 1], "known") == 0 ||
                strcmp(word[off + 1], "active") == 0 ||
                strcmp(word[off + 1], "adjacent") == 0) &&
               strcmp(word[off + 2], "nodes") == 0) {
        const char *info = n == 3 ? "summary" : word[off + 3];

        if (n > 4 || !info_ok(info, 0, 0))
            return -1;
        plan->argv[2] = "nodes";
        plan->argv[3] = word[off + 1];
        plan->argv[4] = (char *)info;
        plan->argc = 5;
    } else if (n >= 3 && strcmp(word[off + 1], "circuit") == 0) {
        const char *info = n == 3 ? "status" : word[off + 3];

        if (n > 4 || !info_ok(info, 0, 1))
            return -1;
        plan->argv[2] = "circuit";
        plan->argv[3] = word[off + 2];
        plan->argv[4] = (char *)info;
        plan->argc = 5;
    } else if (n >= 3 &&
               (strcmp(word[off + 1], "known") == 0 ||
                strcmp(word[off + 1], "active") == 0) &&
               strcmp(word[off + 2], "circuits") == 0) {
        const char *info = n == 3 ? "status" : word[off + 3];

        if (n > 4 || !info_ok(info, 0, 1))
            return -1;
        plan->argv[2] = "circuits";
        plan->argv[3] = word[off + 1];
        plan->argv[4] = (char *)info;
        plan->argc = 5;
    } else {
        return -1;
    }
    plan->argv[plan->argc] = NULL;
    return 0;
}

static int run_tool(const char *envname, const char *path,
                    const char *name, char **argv)
{
    const char *tool = getenv(envname);
    pid_t pid = fork();
    int status;

    if (pid < 0) {
        perror("ncp: fork");
        return 1;
    }
    if (pid == 0) {
        if (tool && *tool)
            execv(tool, argv);
        execv(path, argv);
        execvp(name, argv);
        perror(name);
        _exit(127);
    }
    while (waitpid(pid, &status, 0) < 0) {
        if (errno != EINTR) {
            perror("ncp: waitpid");
            return 1;
        }
    }
    if (WIFEXITED(status))
        return WEXITSTATUS(status);
    return 1;
}

static int run_plan(struct ncp_plan *plan)
{
    return run_tool("DNIV_DNNICE", "/usr/local/sbin/dnnice",
                    "dnnice", plan->argv);
}

static int split_line(char *line, char **word)
{
    char *save = NULL;
    char *tok;
    int n = 0;

    for (tok = strtok_r(line, " \t\r\n", &save); tok;
         tok = strtok_r(NULL, " \t\r\n", &save)) {
        if (n == NCP_MAX_WORDS)
            return -1;
        word[n++] = tok;
    }
    return n;
}

static int selftest(void)
{
    struct ncp_plan p;
    char *a1[] = { "show", "executor" };
    char *a2[] = { "tell", "31.71", "show", "node", "31.70", "status" };
    char *a3[] = { "show", "adjacent", "nodes" };
    char *a4[] = { "show", "active", "circuits", "counters" };
    char *bad[] = { "show", "adjacent", "circuits" };

    if (build_plan(a1, 2, "31.70", &p) || p.argc != 3 ||
        strcmp(p.argv[1], "31.70") || strcmp(p.argv[2], "summary"))
        return 1;
    if (build_plan(a2, 6, "31.70", &p) || p.argc != 5 ||
        strcmp(p.argv[1], "31.71") || strcmp(p.argv[2], "node") ||
        strcmp(p.argv[3], "31.70"))
        return 1;
    if (build_plan(a3, 3, "31.70", &p) || strcmp(p.argv[2], "nodes") ||
        strcmp(p.argv[3], "adjacent") || strcmp(p.argv[4], "summary"))
        return 1;
    if (build_plan(a4, 4, "31.70", &p) || strcmp(p.argv[2], "circuits") ||
        strcmp(p.argv[4], "counters"))
        return 1;
    if (!build_plan(bad, 3, "31.70", &p))
        return 1;
    puts("ncp parser selftest passed");
    return 0;
}

static int one_command(char **word, int nword)
{
    struct ncp_plan plan;
    char target[16];

    if (nword == 1 &&
        (strcmp(word[0], "help") == 0 || strcmp(word[0], "?") == 0)) {
        usage(stdout);
        return 0;
    }
    if (local_target(target))
        return 1;
    if (nword == 2 && strcmp(word[0], "zero") == 0 &&
        strcmp(word[1], "executor") == 0) {
        char *argv[] = { "dnctl", "reset-stats", NULL };

        return run_tool("DNIV_DNCTL", "/usr/local/sbin/dnctl",
                        "dnctl", argv);
    }
    if (nword == 4 && strcmp(word[0], "set") == 0 &&
        strcmp(word[1], "executor") == 0 &&
        strcmp(word[2], "name") == 0) {
        char *argv[] = { "dnctl", "set", target, word[3], NULL };

        return run_tool("DNIV_DNCTL", "/usr/local/sbin/dnctl",
                        "dnctl", argv);
    }
    if (build_plan(word, nword, target, &plan)) {
        usage(stderr);
        return 2;
    }
    return run_plan(&plan);
}

int main(int argc, char **argv)
{
    if (argc == 2 && strcmp(argv[1], "--selftest") == 0)
        return selftest();
    if (argc > 1)
        return one_command(argv + 1, argc - 1);

    for (;;) {
        char *word[NCP_MAX_WORDS];
        char *line = NULL;
        size_t cap = 0;
        ssize_t got;
        int nword;
        int rc;

        if (isatty(STDIN_FILENO)) {
            fputs("NCP> ", stdout);
            fflush(stdout);
        }
        got = getline(&line, &cap, stdin);
        if (got < 0) {
            free(line);
            break;
        }
        nword = split_line(line, word);
        if (nword < 0) {
            fprintf(stderr, "ncp: too many words\n");
            free(line);
            continue;
        }
        if (!nword) {
            free(line);
            continue;
        }
        if (strcmp(word[0], "quit") == 0 || strcmp(word[0], "exit") == 0) {
            free(line);
            break;
        }
        rc = one_command(word, nword);
        free(line);
        if (rc && !isatty(STDIN_FILENO))
            return rc;
    }
    return 0;
}

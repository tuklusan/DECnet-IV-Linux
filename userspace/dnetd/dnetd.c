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

#include <errno.h>
#include <fcntl.h>
#include <grp.h>
#include <limits.h>
#include <poll.h>
#include <pwd.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#include <linux/dn.h>

#define DNETD_MAX_SERVICES 32
#define DNETD_MAX_ARGS 16
#define DNETD_ARG_LEN 128
#define DNETD_USER_LEN 64
#define DNETD_BACKLOG 8

struct service {
    char name[DN_MAXOBJL + 1U];
    unsigned int number;
    int auto_mode;
    char user[DNETD_USER_LEN];
    char argv_store[DNETD_MAX_ARGS][DNETD_ARG_LEN];
    int argc;
    int listener;
};

static __le16 cpu_to_le16_u(uint16_t value)
{
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return (__le16)value;
#else
    return (__le16)__builtin_bswap16(value);
#endif
}

static int parse_unsigned(const char *text, unsigned long max,
                          unsigned long *value)
{
    char *end;
    unsigned long parsed;

    errno = 0;
    parsed = strtoul(text, &end, 10);
    if (errno || end == text || *end || parsed > max)
        return -1;
    *value = parsed;
    return 0;
}

static int parse_options(const char *text, int *auto_mode)
{
    const char *comma;

    if (!text || !*text || !auto_mode)
        return -1;
    if (text[0] != 'N' && text[0] != 'n') {
        errno = EOPNOTSUPP;
        return -1;
    }
    *auto_mode = 0;
    comma = strchr(text, ',');
    if (!comma)
        return 0;
    if (!comma[1] || comma[2]) {
        errno = EINVAL;
        return -1;
    }
    switch (comma[1]) {
    case 'A':
    case 'a':
    case 'Y':
    case 'y':
        *auto_mode = 1;
        return 0;
    case 'N':
    case 'n':
        *auto_mode = 0;
        return 0;
    case 'R':
    case 'r':
        *auto_mode = -1;
        return 0;
    default:
        errno = EINVAL;
        return -1;
    }
}

static int parse_line(char *line, const char *program_dir,
                      struct service *service)
{
    char *tokens[4 + DNETD_MAX_ARGS];
    int count = 0;
    char *token;
    unsigned long number;
    size_t len;

    for (token = strtok(line, " \t\r\n");
         token && count < (int)(sizeof(tokens) / sizeof(tokens[0]));
         token = strtok(NULL, " \t\r\n"))
        tokens[count++] = token;

    if (!count || tokens[0][0] == '#')
        return 0;
    if (count < 5) {
        errno = EINVAL;
        return -1;
    }
    if (strchr(tokens[0], '#')) {
        errno = EINVAL;
        return -1;
    }

    memset(service, 0, sizeof(*service));
    service->listener = -1;
    len = strlen(tokens[0]);
    if (!len || len > DN_MAXOBJL || !strcmp(tokens[0], "*")) {
        errno = EOPNOTSUPP;
        return -1;
    }
    memcpy(service->name, tokens[0], len + 1U);

    if (parse_unsigned(tokens[1], 255U, &number)) {
        errno = EINVAL;
        return -1;
    }
    service->number = (unsigned int)number;
    if (!service->number && !service->name[0]) {
        errno = EINVAL;
        return -1;
    }
    if (parse_options(tokens[2], &service->auto_mode))
        return -1;

    len = strlen(tokens[3]);
    if (!len || len >= sizeof(service->user)) {
        errno = EINVAL;
        return -1;
    }
    memcpy(service->user, tokens[3], len + 1U);

    service->argc = count - 4;
    if (service->argc > DNETD_MAX_ARGS) {
        errno = E2BIG;
        return -1;
    }
    for (int i = 0; i < service->argc; i++) {
        const char *src = tokens[4 + i];

        if (i == 0 && src[0] != '/') {
            int written = snprintf(service->argv_store[i],
                                   sizeof(service->argv_store[i]),
                                   "%s/%s", program_dir, src);
            if (written < 0 ||
                (size_t)written >= sizeof(service->argv_store[i])) {
                errno = ENAMETOOLONG;
                return -1;
            }
        } else {
            len = strlen(src);
            if (!len || len >= sizeof(service->argv_store[i])) {
                errno = ENAMETOOLONG;
                return -1;
            }
            memcpy(service->argv_store[i], src, len + 1U);
        }
    }
    return 1;
}

static int duplicate_service(const struct service *services, int count,
                             const struct service *candidate)
{
    for (int i = 0; i < count; i++) {
        if (candidate->number && services[i].number == candidate->number)
            return 1;
        if (!candidate->number && !services[i].number &&
            !strcmp(services[i].name, candidate->name))
            return 1;
    }
    return 0;
}

static int load_config(const char *path, const char *program_dir,
                       struct service *services, int *count_out)
{
    FILE *file;
    char line[2048];
    int count = 0;
    unsigned int lineno = 0U;

    file = fopen(path, "r");
    if (!file)
        return -1;

    while (fgets(line, sizeof(line), file)) {
        char *start = line;
        struct service service;
        int parsed;

        lineno++;
        while (*start == ' ' || *start == '\t')
            start++;
        if (!*start || *start == '\n' || *start == '#')
            continue;
        {
            char *comment = strchr(start, '#');
            if (comment)
                *comment = '\0';
        }

        parsed = parse_line(start, program_dir, &service);
        if (parsed < 0) {
            fprintf(stderr, "dnetd: invalid config line %u: %s\n",
                    lineno, strerror(errno));
            fclose(file);
            return -1;
        }
        if (!parsed)
            continue;
        if (count >= DNETD_MAX_SERVICES) {
            errno = E2BIG;
            fclose(file);
            return -1;
        }
        if (duplicate_service(services, count, &service)) {
            errno = EEXIST;
            fclose(file);
            return -1;
        }
        services[count++] = service;
    }
    if (ferror(file)) {
        fclose(file);
        errno = EIO;
        return -1;
    }
    fclose(file);
    if (!count) {
        errno = ENOENT;
        return -1;
    }
    *count_out = count;
    return 0;
}

static int make_listener(const struct service *service)
{
    struct sockaddr_dn local;
    int mode = ACC_DEFER;
    int fd;

    fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (fd < 0)
        return -1;
    if (setsockopt(fd, DNPROTO_NSP, DSO_ACCEPTMODE, &mode, sizeof(mode)))
        goto fail;

    memset(&local, 0, sizeof(local));
    local.sdn_family = AF_DECnet;
    if (service->number) {
        local.sdn_objnum = (unsigned char)service->number;
    } else {
        size_t len = strlen(service->name);
        local.sdn_objnamel = cpu_to_le16_u((uint16_t)len);
        memcpy(local.sdn_objname, service->name, len);
    }
    if (bind(fd, (struct sockaddr *)&local, sizeof(local)) ||
        listen(fd, DNETD_BACKLOG))
        goto fail;
    return fd;

fail:
    {
        int saved_errno = errno;
        close(fd);
        errno = saved_errno;
        return -1;
    }
}

static int apply_identity(const char *name)
{
    struct passwd *pw;

    if (!strcmp(name, "-") || !strcmp(name, "none"))
        return 0;
    pw = getpwnam(name);
    if (!pw) {
        errno = ENOENT;
        return -1;
    }
    if (geteuid() != 0) {
        if (geteuid() == pw->pw_uid)
            return 0;
        errno = EPERM;
        return -1;
    }
    if (initgroups(pw->pw_name, pw->pw_gid) ||
        setgid(pw->pw_gid) ||
        setuid(pw->pw_uid))
        return -1;
    if (chdir(pw->pw_dir))
        return chdir("/");
    return 0;
}

static int child_exec(const struct service *service, int fd)
{
    char *argv[DNETD_MAX_ARGS + 1];

    if (dup2(fd, STDIN_FILENO) < 0 || dup2(fd, STDOUT_FILENO) < 0)
        return -1;
    if (fd != STDIN_FILENO && fd != STDOUT_FILENO)
        close(fd);
    if (apply_identity(service->user))
        return -1;

    for (int i = 0; i < service->argc; i++)
        argv[i] = (char *)service->argv_store[i];
    argv[service->argc] = NULL;
    execv(argv[0], argv);
    return -1;
}

static int accept_policy(const struct service *service, int fd)
{
    if (service->auto_mode > 0)
        return setsockopt(fd, DNPROTO_NSP, DSO_CONACCEPT, NULL, 0);
    if (service->auto_mode < 0) {
        struct optdata_dn reject;
        memset(&reject, 0, sizeof(reject));
        reject.opt_status = cpu_to_le16_u(DNSTAT_REJECTED);
        (void)setsockopt(fd, DNPROTO_NSP, DSO_DISDATA,
                         &reject, sizeof(reject));
        (void)setsockopt(fd, DNPROTO_NSP, DSO_CONREJECT, NULL, 0);
        close(fd);
        return 1;
    }
    return 0;
}

static void close_listeners(struct service *services, int count)
{
    for (int i = 0; i < count; i++) {
        if (services[i].listener >= 0)
            close(services[i].listener);
        services[i].listener = -1;
    }
}

static int run_selftest(void)
{
    struct service service;
    char good[] = "TEST 0 N,N root /bin/cat arg";
    char bad_auth[] = "TEST 0 Y,N root /bin/cat";
    char bad_wild[] = "* 0 N,N root /bin/cat";
    int rc;

    rc = parse_line(good, "/usr/local/sbin", &service);
    if (rc != 1 || strcmp(service.name, "TEST") || service.number ||
        service.auto_mode || strcmp(service.user, "root") ||
        service.argc != 2 || strcmp(service.argv_store[0], "/bin/cat") ||
        strcmp(service.argv_store[1], "arg"))
        return 1;
    errno = 0;
    if (parse_line(bad_auth, "/usr/local/sbin", &service) >= 0 ||
        errno != EOPNOTSUPP)
        return 1;
    errno = 0;
    if (parse_line(bad_wild, "/usr/local/sbin", &service) >= 0 ||
        errno != EOPNOTSUPP)
        return 1;
    puts("dnetd selftest passed");
    return 0;
}

static int daemonize_process(void)
{
    int nullfd;
    pid_t pid = fork();

    if (pid < 0)
        return -1;
    if (pid > 0)
        _exit(0);
    if (setsid() < 0 || chdir("/"))
        return -1;
    nullfd = open("/dev/null", O_RDWR);
    if (nullfd < 0)
        return -1;
    if (dup2(nullfd, STDIN_FILENO) < 0 ||
        dup2(nullfd, STDOUT_FILENO) < 0 ||
        dup2(nullfd, STDERR_FILENO) < 0) {
        close(nullfd);
        return -1;
    }
    if (nullfd > STDERR_FILENO)
        close(nullfd);
    return 0;
}

int main(int argc, char **argv)
{
    const char *config = "/etc/dnetd.conf";
    const char *program_dir = "/usr/local/sbin";
    struct service services[DNETD_MAX_SERVICES];
    struct pollfd polls[DNETD_MAX_SERVICES];
    int service_count = 0;
    int foreground = 0;
    int once = 0;

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--selftest")) {
            return run_selftest();
        } else if (!strcmp(argv[i], "-d") || !strcmp(argv[i], "--foreground")) {
            foreground = 1;
        } else if (!strcmp(argv[i], "--once")) {
            once = 1;
        } else if ((!strcmp(argv[i], "-c") || !strcmp(argv[i], "--config")) &&
                   i + 1 < argc) {
            config = argv[++i];
        } else if ((!strcmp(argv[i], "-p") || !strcmp(argv[i], "--program-dir")) &&
                   i + 1 < argc) {
            program_dir = argv[++i];
        } else {
            fprintf(stderr,
                    "usage: %s [-d|--foreground] [--once] "
                    "[-c|--config FILE] [-p|--program-dir DIR]\n",
                    argv[0]);
            return 2;
        }
    }

    memset(services, 0, sizeof(services));
    for (int i = 0; i < DNETD_MAX_SERVICES; i++)
        services[i].listener = -1;

    if (load_config(config, program_dir, services, &service_count)) {
        perror("dnetd: config");
        return 1;
    }
    for (int i = 0; i < service_count; i++) {
        services[i].listener = make_listener(&services[i]);
        if (services[i].listener < 0) {
            perror("dnetd: listen");
            close_listeners(services, service_count);
            return 1;
        }
        polls[i].fd = services[i].listener;
        polls[i].events = POLLIN;
        polls[i].revents = 0;
    }

    if (!foreground && daemonize_process()) {
        perror("dnetd: daemonize");
        close_listeners(services, service_count);
        return 1;
    }
    setvbuf(stdout, NULL, _IONBF, 0);
    if (foreground)
        printf("dnetd: ready services=%d\n", service_count);

    for (;;) {
        int ready;

        do {
            ready = poll(polls, (nfds_t)service_count, -1);
        } while (ready < 0 && errno == EINTR);
        if (ready < 0) {
            perror("dnetd: poll");
            close_listeners(services, service_count);
            return 1;
        }

        for (int i = 0; i < service_count; i++) {
            int fd;
            int policy;
            pid_t pid;

            if (!(polls[i].revents & POLLIN))
                continue;
            do {
                fd = accept(services[i].listener, NULL, NULL);
            } while (fd < 0 && errno == EINTR);
            if (fd < 0) {
                perror("dnetd: accept");
                close_listeners(services, service_count);
                return 1;
            }

            policy = accept_policy(&services[i], fd);
            if (policy < 0) {
                perror("dnetd: accept policy");
                close(fd);
                close_listeners(services, service_count);
                return 1;
            }
            if (policy > 0) {
                if (once) {
                    close_listeners(services, service_count);
                    return 0;
                }
                continue;
            }

            pid = fork();
            if (pid < 0) {
                perror("dnetd: fork");
                close(fd);
                close_listeners(services, service_count);
                return 1;
            }
            if (!pid) {
                close_listeners(services, service_count);
                if (child_exec(&services[i], fd))
                    _exit(126);
                _exit(127);
            }
            close(fd);

            if (once) {
                int status;
                close_listeners(services, service_count);
                do {
                    ready = waitpid(pid, &status, 0);
                } while (ready < 0 && errno == EINTR);
                if (ready < 0)
                    return 1;
                return WIFEXITED(status) && WEXITSTATUS(status) == 0 ? 0 : 1;
            }
            while (waitpid(-1, NULL, WNOHANG) > 0)
                ;
        }
    }
}

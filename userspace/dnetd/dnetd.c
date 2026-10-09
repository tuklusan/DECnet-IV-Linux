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
    if (text[1] != '\0' && text[1] != ',') {
        errno = EINVAL;
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

    if (token) {
        errno = E2BIG;
        return -1;
    }
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

/* Read a whole physical line without silently discarding bytes after NUL.
 * Reject oversized lines, including unterminated exact-buffer-sized input.
 * Returns 1 for a line, 0 at clean EOF, and -1 for invalid/failed input.
 */
static int read_config_line(FILE *file, char *line, size_t cap)
{
    size_t len = 0U;
    int ch = EOF;

    if (!file || !line || cap < 2U) {
        errno = EINVAL;
        return -1;
    }
    while ((ch = fgetc(file)) != EOF) {
        if (ch == 0) {
            errno = EILSEQ;
            return -1;
        }
        if (len + 1U >= cap) {
            errno = E2BIG;
            return -1;
        }
        line[len++] = (char)ch;
        if (ch == '\n')
            break;
    }
    if (ch == EOF && ferror(file)) {
        if (!errno)
            errno = EIO;
        return -1;
    }
    if (!len)
        return 0;
    if (len == cap - 1U && line[len - 1U] != '\n') {
        errno = E2BIG;
        return -1;
    }
    line[len] = '\0';
    return 1;
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

    for (;;) {
        char *start = line;
        struct service service;
        int parsed;
        int line_rc = read_config_line(file, line, sizeof(line));

        if (line_rc < 0) {
            int saved_errno = errno;

            fprintf(stderr, "dnetd: invalid config line %u: %s\n",
                    lineno + 1U, strerror(saved_errno));
            fclose(file);
            errno = saved_errno;
            return -1;
        }
        if (!line_rc)
            break;
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

static void reap_children(int signo)
{
    int saved_errno = errno;

    (void)signo;
    while (waitpid(-1, NULL, WNOHANG) > 0)
        ;
    errno = saved_errno;
}

static int install_child_reaper(void)
{
    struct sigaction action;

    memset(&action, 0, sizeof(action));
    action.sa_handler = reap_children;
    action.sa_flags = SA_RESTART | SA_NOCLDSTOP;
    if (sigemptyset(&action.sa_mask))
        return -1;
    return sigaction(SIGCHLD, &action, NULL);
}

static int selftest_reaper(void)
{
    sigset_t blocked;
    sigset_t previous;
    pid_t child;
    int rc = -1;

    if (sigemptyset(&blocked) || sigaddset(&blocked, SIGCHLD) ||
        sigprocmask(SIG_BLOCK, &blocked, &previous))
        return -1;
    child = fork();
    if (child < 0)
        goto out;
    if (!child)
        _exit(0);
    while (sigwaitinfo(&blocked, NULL) < 0) {
        if (errno != EINTR)
            goto kill_child;
    }
    reap_children(SIGCHLD);
    errno = 0;
    if (waitpid(child, NULL, WNOHANG) != -1 || errno != ECHILD)
        goto kill_child;
    rc = 0;
    goto out;

kill_child:
    (void)kill(child, SIGKILL);
    while (waitpid(child, NULL, 0) < 0 && errno == EINTR)
        ;
out:
    if (sigprocmask(SIG_SETMASK, &previous, NULL))
        return -1;
    return rc;
}

static int selftest_config_line_bound(void)
{
    char path[] = "/tmp/dnetd-config-selftest.XXXXXX";
    char overlong[2200];
    static const char prefix[] = "TEST 0 N,N root /bin/cat";
    struct service services[DNETD_MAX_SERVICES];
    int count = 0;
    int fd;
    int rc;

    memset(overlong, ' ', sizeof(overlong));
    memcpy(overlong, prefix, sizeof(prefix) - 1U);
    overlong[sizeof(overlong) - 2U] = '\n';
    overlong[sizeof(overlong) - 1U] = '\0';

    fd = mkstemp(path);
    if (fd < 0)
        return -1;
    if (write(fd, overlong, sizeof(overlong) - 1U) !=
        (ssize_t)(sizeof(overlong) - 1U)) {
        (void)close(fd);
        unlink(path);
        return -1;
    }
    if (close(fd)) {
        unlink(path);
        return -1;
    }

    errno = 0;
    rc = load_config(path, "/usr/local/sbin", services, &count);
    {
        int saved_errno = errno;

        unlink(path);
        return rc < 0 && saved_errno == E2BIG ? 0 : -1;
    }
}

static int selftest_config_nul(void)
{
    char path[] = "/tmp/dnetd-nul-selftest.XXXXXX";
    static const char bad[] = "TEST 0 N,N root /bin/cat\0ignored";
    static const char good[] = "TEST 0 N,N root /bin/cat";
    struct service services[DNETD_MAX_SERVICES];
    int count = 0;
    int fd;
    int rc;
    int saved_errno;

    fd = mkstemp(path);
    if (fd < 0)
        return -1;
    if (write(fd, bad, sizeof(bad) - 1U) !=
        (ssize_t)(sizeof(bad) - 1U)) {
        (void)close(fd);
        (void)unlink(path);
        return -1;
    }
    if (close(fd)) {
        (void)unlink(path);
        return -1;
    }
    errno = 0;
    rc = load_config(path, "/usr/local/sbin", services, &count);
    saved_errno = errno;
    if (rc >= 0 || saved_errno != EILSEQ) {
        unlink(path);
        return -1;
    }
    fd = open(path, O_WRONLY | O_TRUNC | O_CLOEXEC);
    if (fd < 0)
        goto fail;
    if (write(fd, good, sizeof(good) - 1U) !=
        (ssize_t)(sizeof(good) - 1U)) {
        close(fd);
        goto fail;
    }
    if (close(fd))
        goto fail;
    count = 0;
    rc = load_config(path, "/usr/local/sbin", services, &count);
    unlink(path);
    return rc == 0 && count == 1 ? 0 : -1;
fail:
    unlink(path);
    return -1;
}

static int run_selftest(void)
{
    struct service service;
    char good[] = "TEST 0 N,N root /bin/cat arg";
    char bad_auth[] = "TEST 0 Y,N root /bin/cat";
    char bad_option[] = "TEST 0 Nextra root /bin/cat";
    char bad_wild[] = "* 0 N,N root /bin/cat";
    char too_many[] =
        "TEST 0 N,N root /bin/cat "
        "1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16";
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
    errno = 0;
    if (parse_line(bad_option, "/usr/local/sbin", &service) >= 0 ||
        errno != EINVAL)
        return 1;
    errno = 0;
    if (parse_line(too_many, "/usr/local/sbin", &service) >= 0 ||
        errno != E2BIG)
        return 1;
    if (selftest_reaper() || selftest_config_line_bound() ||
        selftest_config_nul())
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
    if (!once && install_child_reaper()) {
        perror("dnetd: SIGCHLD");
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
                if (once) {
                    close_listeners(services, service_count);
                    return 1;
                }
                continue;
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
        }
    }
}

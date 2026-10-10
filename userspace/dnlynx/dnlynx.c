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
#include <getopt.h>
#include <linux/dn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <sys/wait.h>
#include <unistd.h>

#include "../common/record_io.h"

#define DNLYNX_OBJECT "HTTP"
#define DNLYNX_HEADER_MAX 8192U

struct access_options { const char *user; const char *password; const char *account; };

static __le16 cpu_to_le16_u(uint16_t value)
{
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return (__le16)value;
#else
    return (__le16)__builtin_bswap16(value);
#endif
}

static int parse_node(const char *text, uint16_t *address)
{
    char *end; unsigned long area, node;
    errno = 0; area = strtoul(text, &end, 10);
    if (errno || end == text || *end != '.' || area < 1U || area > 63U) return -1;
    errno = 0; node = strtoul(end + 1, &end, 10);
    if (errno || *end || node == 0U || node > 1023U) return -1;
    *address = (uint16_t)((area << 10) | node);
    return 0;
}

static int normalize_path(const char *text, char *path, size_t cap)
{
    size_t n;
    if (!text || !text[0]) text = "/";
    n = strlen(text);
    if (text[0] != '/' || n >= cap || strchr(text, '\r') || strchr(text, '\n')) return -1;
    memcpy(path, text, n + 1U);
    return 0;
}

static int set_access_field(unsigned char *dst, size_t cap, __u8 *len, const char *text)
{
    size_t n = text ? strlen(text) : 0U;
    if (n > cap) return -1;
    if (n) memcpy(dst, text, n);
    *len = (__u8)n;
    return 0;
}

static int valid_object(const char *object)
{
    size_t i, n;
    if (!object) return 0;
    n = strlen(object);
    if (n < 1U || n > DN_MAXOBJL) return 0;
    if (!((object[0] >= 'A' && object[0] <= 'Z') ||
          (object[0] >= 'a' && object[0] <= 'z'))) return 0;
    for (i = 1U; i < n; i++)
        if (!((object[i] >= 'A' && object[i] <= 'Z') ||
              (object[i] >= 'a' && object[i] <= 'z') ||
              (object[i] >= '0' && object[i] <= '9'))) return 0;
    return 1;
}

static int connect_http(const char *node_text, const char *object,
                        const struct access_options *options)
{
    struct sockaddr_dn peer; struct accessdata_dn access;
    struct timeval timeout = { .tv_sec = 15, .tv_usec = 0 };
    uint16_t address; size_t object_len = strlen(object); int fd;
    if (parse_node(node_text, &address)) { fprintf(stderr, "dnlynx: invalid DECnet node %s\n", node_text); return -1; }
    if (!valid_object(object)) { fprintf(stderr, "dnlynx: invalid DECnet object\n"); return -1; }
    fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (fd < 0) { perror("dnlynx: socket"); return -1; }
    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) ||
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout))) {
        perror("dnlynx: timeout"); close(fd); return -1;
    }
    if (options && (options->user || options->password || options->account)) {
        memset(&access, 0, sizeof(access));
        if (set_access_field(access.acc_user, sizeof(access.acc_user), &access.acc_userl, options->user) ||
            set_access_field(access.acc_pass, sizeof(access.acc_pass), &access.acc_passl, options->password) ||
            set_access_field(access.acc_acc, sizeof(access.acc_acc), &access.acc_accl, options->account)) {
            fprintf(stderr, "dnlynx: access field exceeds %u bytes\n", DN_MAXACCL); close(fd); return -1;
        }
        if (setsockopt(fd, DNPROTO_NSP, SO_CONACCESS, &access, sizeof(access))) {
            perror("dnlynx: access data"); close(fd); return -1;
        }
    }
    memset(&peer, 0, sizeof(peer));
    peer.sdn_family = AF_DECnet;
    peer.sdn_objnamel = cpu_to_le16_u((uint16_t)object_len);
    memcpy(peer.sdn_objname, object, object_len);
    peer.sdn_add.a_len = cpu_to_le16_u(2U);
    peer.sdn_add.a_addr[0] = (unsigned char)(address & 0xffU);
    peer.sdn_add.a_addr[1] = (unsigned char)(address >> 8);
    if (connect(fd, (struct sockaddr *)&peer, sizeof(peer))) { perror("dnlynx: connect HTTP"); close(fd); return -1; }
    return fd;
}

static ssize_t header_end(const unsigned char *buf, size_t len)
{
    size_t i;
    for (i = 3U; i < len; i++)
        if (buf[i-3U]=='\r' && buf[i-2U]=='\n' && buf[i-1U]=='\r' && buf[i]=='\n')
            return (ssize_t)(i + 1U);
    return -1;
}

static int append_header_record(unsigned char *header, size_t cap,
                                size_t *used,
                                const unsigned char *record, size_t got,
                                ssize_t *end, size_t *copied)
{
    size_t available;
    size_t take;

    if (!header || !cap || !used || !record || !end || !copied ||
        *used > cap)
        return -1;
    available = cap - *used;
    take = got < available ? got : available;
    if (take)
        memcpy(header + *used, record, take);
    *used += take;
    *copied = take;
    *end = header_end(header, *used);
    if (*end < 0 && (take < got || *used == cap))
        return -1;
    return 0;
}

static int status_code(const unsigned char *buf, size_t len)
{
    size_t i;

    if (!buf || len < 16U ||
        (memcmp(buf, "HTTP/1.0 ", 9U) && memcmp(buf, "HTTP/1.1 ", 9U)) ||
        buf[9] < '0' || buf[9] > '9' ||
        buf[10] < '0' || buf[10] > '9' ||
        buf[11] < '0' || buf[11] > '9' || buf[12] != ' ')
        return -1;
    /* An HTTP status is a complete CRLF-terminated line, not just a
     * three-digit prefix. Reject embedded controls and truncated lines.
     */
    for (i = 13U; i + 1U < len; i++) {
        if (buf[i] == '\r' && buf[i + 1U] == '\n')
            return (buf[9] - '0') * 100 + (buf[10] - '0') * 10 +
                   (buf[11] - '0');
        if (buf[i] < 0x20U || buf[i] == 0x7fU)
            return -1;
    }
    return -1;
}

/* A successful HTTP status does not imply that all declared body bytes
 * arrived. Enforce an unambiguous decimal Content-Length when present, and
 * fail closed on unsupported transfer codings instead of printing chunks. */
static int header_name_is(const unsigned char *name, size_t len,
                          const char *wanted)
{
    size_t i;

    if (strlen(wanted) != len)
        return 0;
    for (i = 0U; i < len; i++) {
        unsigned char a = name[i];
        unsigned char b = (unsigned char)wanted[i];

        if (a >= 'A' && a <= 'Z')
            a = (unsigned char)(a + ('a' - 'A'));
        if (b >= 'A' && b <= 'Z')
            b = (unsigned char)(b + ('a' - 'A'));
        if (a != b)
            return 0;
    }
    return 1;
}

static int valid_header_name_byte(unsigned char c)
{
    if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
        (c >= '0' && c <= '9'))
        return 1;
    return c && strchr("!#$%&'*+-.^_`|~", c) != NULL;
}

static int parse_response_headers(const unsigned char *header, size_t end,
                                  int *has_length, size_t *content_length)
{
    size_t pos = 0U;

    if (!header || !has_length || !content_length || end < 4U ||
        end > DNLYNX_HEADER_MAX)
        return -1;
    *has_length = 0;
    *content_length = 0U;
    /* Skip the validated HTTP status line. */
    while (pos + 1U < end &&
           !(header[pos] == '\r' && header[pos + 1U] == '\n'))
        pos++;
    if (pos + 1U >= end)
        return -1;
    pos += 2U;
    while (pos + 1U < end) {
        size_t line_end = pos;
        size_t colon = pos;
        size_t i;

        while (line_end + 1U < end &&
               !(header[line_end] == '\r' && header[line_end + 1U] == '\n'))
            line_end++;
        if (line_end + 1U >= end)
            return -1;
        if (line_end == pos)
            return line_end + 2U == end ? 0 : -1;
        while (colon < line_end && header[colon] != ':')
            colon++;
        if (colon == pos || colon == line_end)
            return -1;
        for (i = pos; i < colon; i++)
            if (!valid_header_name_byte(header[i]))
                return -1;
        for (i = colon + 1U; i < line_end; i++)
            if ((header[i] < 0x20U && header[i] != '\t') ||
                header[i] == 0x7fU)
                return -1;
        if (header_name_is(header + pos, colon - pos, "Transfer-Encoding"))
            return -1; /* Chunk framing is not implemented by this client. */
        if (header_name_is(header + pos, colon - pos, "Content-Length")) {
            size_t number = 0U;
            size_t digit_count = 0U;

            if (*has_length)
                return -1; /* Duplicates are ambiguous even if identical. */
            i = colon + 1U;
            while (i < line_end && (header[i] == ' ' || header[i] == '\t'))
                i++;
            while (i < line_end && header[i] >= '0' && header[i] <= '9') {
                size_t digit = (size_t)(header[i] - '0');

                if (number > (SIZE_MAX - digit) / 10U)
                    return -1;
                number = number * 10U + digit;
                i++;
                digit_count++;
            }
            while (i < line_end && (header[i] == ' ' || header[i] == '\t'))
                i++;
            if (!digit_count || i != line_end)
                return -1;
            *content_length = number;
            *has_length = 1;
        }
        pos = line_end + 2U;
    }
    return -1;
}

static int write_http_body(const unsigned char *body, size_t count,
                           int has_length, size_t content_length,
                           size_t *written)
{
    if (!written || *written > SIZE_MAX - count ||
        (has_length && (*written > content_length ||
                        count > content_length - *written)))
        return -1;
    if (count && fwrite(body, 1, count, stdout) != count)
        return -1;
    *written += count;
    return 0;
}

static int run_http(int fd, const char *node, const char *path, int include_headers)
{
    unsigned char header[DNLYNX_HEADER_MAX], record[DNBUFSIZE];
    char request[1536]; size_t used=0U, body_written=0U, content_length=0U;
    int code=-1, have_header=0, has_length=0; int n;
    n=snprintf(request,sizeof(request),
        "GET %s HTTP/1.0\r\nHost: %s\r\nUser-Agent: dnlynx/1\r\nConnection: close\r\n\r\n",path,node);
    if (n<0 || (size_t)n>=sizeof(request)) {
        fputs("dnlynx: HTTP stage=request-format\n", stderr);
        return -1;
    }
    if (dniv_send_record(fd, request, (size_t)n, 0)) {
        fprintf(stderr,"dnlynx: HTTP stage=request-send errno=%d\n",errno);
        return -1;
    }
    for (;;) {
        ssize_t got=dniv_recv_record(fd,record,sizeof(record),0);
        if (got==0) break;
        if (got<0) {
            fprintf(stderr,"dnlynx: HTTP stage=response-recv errno=%d\n",errno);
            return -1;
        }
        if (!have_header) {
            ssize_t end;
            size_t copied = 0U;

            if (append_header_record(header, sizeof(header), &used,
                                     record, (size_t)got,
                                     &end, &copied)) {
                fputs("dnlynx: HTTP stage=header-limit\n",stderr);
                return -1;
            }
            if (end<0) continue;
            code=status_code(header,used);
            if (code<0) {
                fputs("dnlynx: HTTP stage=status-line\n",stderr);
                return -1;
            }
            if (parse_response_headers(header, (size_t)end, &has_length,
                                       &content_length)) {
                fputs("dnlynx: HTTP stage=invalid-headers\n", stderr);
                return -1;
            }
            have_header=1;
            if (include_headers && fwrite(header,1,(size_t)end,stdout)!=(size_t)end) {
                fputs("dnlynx: HTTP stage=header-output\n",stderr);
                return -1;
            }
            if (write_http_body(header + end, used - (size_t)end,
                                has_length, content_length, &body_written) ||
                write_http_body(record + copied, (size_t)got - copied,
                                has_length, content_length, &body_written)) {
                fputs("dnlynx: HTTP stage=body-length-or-output\n",stderr);
                return -1;
            }
            continue;
        }
        if (write_http_body(record, (size_t)got, has_length,
                            content_length, &body_written)) {
            fputs("dnlynx: HTTP stage=body-length-or-output\n",stderr);
            return -1;
        }
    }
    if (!have_header) {
        fputs("dnlynx: HTTP stage=no-header\n",stderr);
        return -1;
    }
    if (has_length && body_written != content_length) {
        fprintf(stderr, "dnlynx: HTTP stage=truncated-body received=%zu expected=%zu\n",
                body_written, content_length);
        return -1;
    }
    if (fflush(stdout)) {
        fputs("dnlynx: HTTP stage=flush\n",stderr);
        return -1;
    }
    return code>=200 && code<300 ? 0 : 1;
}

/* Real SOCK_SEQPACKET end-of-stream proof with a local fake HTTP peer.
 * Never requires a DECnet listener, external network or writable document. */
static int selftest_response(const char *response, int expected_rc,
                             const char *expected_body)
{
    int pair[2] = { -1, -1 };
    int capture[2] = { -1, -1 };
    int saved_out;
    int rc;
    int status;
    pid_t child;
    ssize_t got;
    unsigned char output[128];
    size_t expected = strlen(expected_body);

    if (socketpair(AF_UNIX, SOCK_SEQPACKET, 0, pair))
        return -1;
    if (pipe(capture)) {
        close(pair[0]);
        close(pair[1]);
        return -1;
    }
    child = fork();
    if (child < 0) {
        close(pair[0]);
        close(pair[1]);
        close(capture[0]);
        close(capture[1]);
        return -1;
    }
    if (!child) {
        unsigned char request[2048];

        alarm(5U);
        close(pair[0]);
        close(capture[0]);
        close(capture[1]);
        if (dniv_recv_record(pair[1], request, sizeof(request), 0) <= 0 ||
            dniv_send_record(pair[1], response, strlen(response), 0))
            _exit(1);
        close(pair[1]);
        _exit(0);
    }
    close(pair[1]);
    saved_out = dup(STDOUT_FILENO);
    if (saved_out < 0 || fflush(stdout) ||
        dup2(capture[1], STDOUT_FILENO) < 0) {
        close(pair[0]);
        close(capture[0]);
        close(capture[1]);
        if (saved_out >= 0)
            close(saved_out);
        (void)waitpid(child, &status, 0);
        return -1;
    }
    close(capture[1]);
    rc = run_http(pair[0], "31.71", "/", 0);
    close(pair[0]);
    if (fflush(stdout) || dup2(saved_out, STDOUT_FILENO) < 0) {
        close(capture[0]);
        close(saved_out);
        (void)waitpid(child, &status, 0);
        return -1;
    }
    close(saved_out);
    got = read(capture[0], output, sizeof(output));
    close(capture[0]);
    if (waitpid(child, &status, 0) != child ||
        !WIFEXITED(status) || WEXITSTATUS(status) ||
        rc != expected_rc || got != (ssize_t)expected ||
        memcmp(output, expected_body, expected))
        return -1;
    return 0;
}

static int selftest(void)
{
    uint16_t address; char path[64];
    unsigned char header[DNLYNX_HEADER_MAX];
    unsigned char large[DNLYNX_HEADER_MAX + 16U];
    static const unsigned char ok[]="HTTP/1.0 200 OK\r\nContent-Length: 2\r\n\r\nOK";
    size_t used = 0U;
    size_t copied = 0U;
    ssize_t end = -1;

    memset(large, 'X', sizeof(large));
    memcpy(large, ok, sizeof(ok) - 1U);
    if (parse_node("31.71",&address) || address != ((31U<<10)|71U) ||
        !parse_node("0.1",&address) || !parse_node("31.0",&address) ||
        !parse_node("64.1",&address) ||
        normalize_path("/",path,sizeof(path)) || strcmp(path,"/") ||
        normalize_path("/index.html",path,sizeof(path)) || strcmp(path,"/index.html") ||
        !normalize_path("index.html",path,sizeof(path)) ||
        !normalize_path("/bad\nheader",path,sizeof(path)) ||
        !valid_object("HTTP") || !valid_object("DNIVHT") ||
        valid_object("") || valid_object("1HTTP") || valid_object("BAD-NAME") ||
        header_end(ok,sizeof(ok)-1U)!=38 || status_code(ok,sizeof(ok)-1U)!=200 ||
        status_code((const unsigned char *)"HTTP/1.1 204 No Content\r\n\r\n",
                    sizeof("HTTP/1.1 204 No Content\r\n\r\n") - 1U)!=204 ||
        status_code((const unsigned char *)"HTTP/1.0 200Bad\r\n\r\n",
                    sizeof("HTTP/1.0 200Bad\r\n\r\n") - 1U)>=0 ||
        status_code((const unsigned char *)"HTTP/1.0 200 OK\n\n",
                    sizeof("HTTP/1.0 200 OK\n\n") - 1U)>=0 ||
        status_code((const unsigned char *)"HTTP/1.0 200 \r\n\r\n",
                    sizeof("HTTP/1.0 200 \r\n\r\n") - 1U)!=200 ||
        append_header_record(header, sizeof(header), &used,
                             large, sizeof(large), &end, &copied) ||
        end != 38 || used != sizeof(header) ||
        copied != sizeof(header) ||
        selftest_response("HTTP/1.0 200 OK\r\nContent-Length: 5\r\n\r\nhello", 0, "hello") ||
        selftest_response("HTTP/1.1 200 OK\r\ncOnTeNt-LeNgTh: 5\r\n\r\nhello", 0, "hello") ||
        selftest_response("HTTP/1.0 200 OK\r\n\r\nhello", 0, "hello") ||
        selftest_response("HTTP/1.0 200 OK\r\nContent-Length: 10\r\n\r\nhello", -1, "hello") ||
        selftest_response("HTTP/1.0 200 OK\r\nContent-Length: 3\r\n\r\nhello", -1, "") ||
        selftest_response("HTTP/1.0 200 OK\r\nContent-Length: five\r\n\r\nhello", -1, "") ||
        selftest_response("HTTP/1.0 200 OK\r\nContent-Length: 5\r\nContent-Length: 5\r\n\r\nhello", -1, "") ||
        selftest_response("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\nhello", -1, ""))
        return 1;
    used = 0U;
    copied = 0U;
    end = -1;
    memset(large, 'X', sizeof(large));
    if (!append_header_record(header, sizeof(header), &used,
                              large, sizeof(large), &end, &copied))
        return 1;
    puts("dnlynx selftest passed"); return 0;
}

int main(int argc, char **argv)
{
    struct access_options options={getenv("DNACCESS_USER"),getenv("DNACCESS_PASSWORD"),getenv("DNACCESS_ACCOUNT")};
    char path[1024]; const char *node; const char *object=DNLYNX_OBJECT;
    int include_headers=0,opt,fd,rc;
    if (argc==2 && !strcmp(argv[1],"--selftest")) return selftest();
    if (options.user && !options.user[0]) options.user=NULL;
    if (options.password && !options.password[0]) options.password=NULL;
    if (options.account && !options.account[0]) options.account=NULL;
    opterr=0;
    while ((opt=getopt(argc,argv,"io:u:p:a:"))!=-1) {
        switch(opt) {
        case 'i': include_headers=1; break;
        case 'o': object=optarg; break;
        case 'u': options.user=optarg; break;
        case 'p': options.password=optarg; break;
        case 'a': options.account=optarg; break;
        default: fprintf(stderr,"dnlynx: invalid option\n"); return 2;
        }
    }
    if (optind>=argc || optind+2<argc) {
        fprintf(stderr,"usage: %s [-i] [-o OBJECT] [-u USER] [-p PASSWORD] [-a ACCOUNT] AREA.NODE [PATH]\n"
                       "       %s --selftest\n"
                       "DNACCESS_USER, DNACCESS_PASSWORD and DNACCESS_ACCOUNT provide non-command-line access defaults.\n",
                       argv[0],argv[0]); return 2;
    }
    node=argv[optind++];
    if (normalize_path(optind<argc?argv[optind]:"/",path,sizeof(path))) {
        fprintf(stderr,"dnlynx: invalid HTTP path\n"); return 2;
    }
    fd=connect_http(node,object,&options); if (fd<0) return 1;
    rc=run_http(fd,node,path,include_headers); close(fd);
    if (rc<0) { fprintf(stderr,"dnlynx: HTTP exchange failed\n"); return 1; }
    return rc;
}

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
#include <unistd.h>

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
    if (errno || end == text || *end != '.' || area > 63U) return -1;
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

static int status_code(const unsigned char *buf, size_t len)
{
    if (len < 12U || (memcmp(buf,"HTTP/1.0 ",9U) && memcmp(buf,"HTTP/1.1 ",9U))) return -1;
    if (buf[9]<'0'||buf[9]>'9'||buf[10]<'0'||buf[10]>'9'||buf[11]<'0'||buf[11]>'9') return -1;
    return (buf[9]-'0')*100 + (buf[10]-'0')*10 + (buf[11]-'0');
}

static int run_http(int fd, const char *node, const char *path, int include_headers)
{
    unsigned char header[DNLYNX_HEADER_MAX], record[DNBUFSIZE];
    char request[1536]; size_t used=0U; int code=-1, have_header=0; int n;
    n=snprintf(request,sizeof(request),
        "GET %s HTTP/1.0\r\nHost: %s\r\nUser-Agent: dnlynx/1\r\nConnection: close\r\n\r\n",path,node);
    if (n<0 || (size_t)n>=sizeof(request)) {
        fputs("dnlynx: HTTP stage=request-format\n", stderr);
        return -1;
    }
    if (send(fd,request,(size_t)n,MSG_EOR|MSG_NOSIGNAL)!=n) {
        fprintf(stderr,"dnlynx: HTTP stage=request-send errno=%d\n",errno);
        return -1;
    }
    for (;;) {
        ssize_t got=recv(fd,record,sizeof(record),0);
        if (got==0) break;
        if (got<0) {
            fprintf(stderr,"dnlynx: HTTP stage=response-recv errno=%d\n",errno);
            return -1;
        }
        if (!have_header) {
            ssize_t end;
            if (used+(size_t)got>sizeof(header)) {
                fputs("dnlynx: HTTP stage=header-limit\n",stderr);
                return -1;
            }
            memcpy(header+used,record,(size_t)got); used+=(size_t)got;
            end=header_end(header,used); if (end<0) continue;
            code=status_code(header,used);
            if (code<0) {
                fputs("dnlynx: HTTP stage=status-line\n",stderr);
                return -1;
            }
            have_header=1;
            if (include_headers && fwrite(header,1,(size_t)end,stdout)!=(size_t)end) {
                fputs("dnlynx: HTTP stage=header-output\n",stderr);
                return -1;
            }
            if (used>(size_t)end && fwrite(header+end,1,used-(size_t)end,stdout)!=used-(size_t)end) {
                fputs("dnlynx: HTTP stage=body-output\n",stderr);
                return -1;
            }
            continue;
        }
        if (fwrite(record,1,(size_t)got,stdout)!=(size_t)got) {
            fputs("dnlynx: HTTP stage=body-output\n",stderr);
            return -1;
        }
    }
    if (!have_header) {
        fputs("dnlynx: HTTP stage=no-header\n",stderr);
        return -1;
    }
    if (fflush(stdout)) {
        fputs("dnlynx: HTTP stage=flush\n",stderr);
        return -1;
    }
    return code>=200 && code<300 ? 0 : 1;
}

static int selftest(void)
{
    uint16_t address; char path[64];
    static const unsigned char ok[]="HTTP/1.0 200 OK\r\nContent-Length: 2\r\n\r\nOK";
    if (parse_node("31.71",&address) || address != ((31U<<10)|71U) ||
        !parse_node("31.0",&address) || !parse_node("64.1",&address) ||
        normalize_path("/",path,sizeof(path)) || strcmp(path,"/") ||
        normalize_path("/index.html",path,sizeof(path)) || strcmp(path,"/index.html") ||
        !normalize_path("index.html",path,sizeof(path)) ||
        !normalize_path("/bad\nheader",path,sizeof(path)) ||
        !valid_object("HTTP") || !valid_object("DNIVHT") ||
        valid_object("") || valid_object("1HTTP") || valid_object("BAD-NAME") ||
        header_end(ok,sizeof(ok)-1U)!=38 || status_code(ok,sizeof(ok)-1U)!=200) return 1;
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

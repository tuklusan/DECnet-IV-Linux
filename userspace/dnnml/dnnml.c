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
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

#include <linux/decnet_iv.h>
#include <linux/dn.h>
#include <decnet_iv_nice.h>

#define DNIV_DEVICE "/dev/decnet_iv"
#define DNIV_NML_OBJECT 19U
#define DNIV_NML_BACKLOG 8
#define DNIV_NML_IDENT "DECnet-IV-Linux"

static __le16 cpu_to_le16_u(uint16_t value)
{
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return (__le16)value;
#else
    return (__le16)__builtin_bswap16(value);
#endif
}

static int read_identity(struct dniv_identity *identity)
{
    int fd = open(DNIV_DEVICE, O_RDONLY);

    if (fd < 0)
        return -1;
    memset(identity, 0, sizeof(*identity));
    if (ioctl(fd, DNIV_IOC_GET_IDENTITY, identity) < 0) {
        close(fd);
        return -1;
    }
    close(fd);
    if (identity->uapi_version != DNIV_UAPI_VERSION ||
        !identity->address || !identity->name[0])
        return -1;
    return 0;
}

static int make_listener(void)
{
    const unsigned char version[] = { 4U, 0U, 0U };
    struct optdata_dn conndata;
    struct sockaddr_dn local;
    int fd;

    fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (fd < 0)
        return -1;

    memset(&conndata, 0, sizeof(conndata));
    conndata.opt_optl = cpu_to_le16_u(sizeof(version));
    memcpy(conndata.opt_data, version, sizeof(version));
    if (setsockopt(fd, DNPROTO_NSP, DSO_CONDATA,
                   &conndata, sizeof(conndata)) < 0)
        goto fail;

    memset(&local, 0, sizeof(local));
    local.sdn_family = AF_DECnet;
    local.sdn_objnum = DNIV_NML_OBJECT;
    if (bind(fd, (struct sockaddr *)&local, sizeof(local)) < 0 ||
        listen(fd, DNIV_NML_BACKLOG) < 0)
        goto fail;
    return fd;

fail:
    close(fd);
    return -1;
}

static int count_active_links(__u16 *active)
{
    struct dniv_link link;
    __u32 index;
    __u16 count = 0U;
    int fd;

    if (!active)
        return -1;
    fd = open(DNIV_DEVICE, O_RDONLY);
    if (fd < 0)
        return -1;
    for (index = 0U;; index++) {
        memset(&link, 0, sizeof(link));
        link.uapi_version = DNIV_UAPI_VERSION;
        link.index = index;
        if (ioctl(fd, DNIV_IOC_GET_LINK, &link) < 0) {
            if (errno == ENOENT)
                break;
            close(fd);
            return -1;
        }
        if (link.state != DNIV_LINK_STATE_CLOSED && count != UINT16_MAX)
            count++;
    }
    close(fd);
    *active = count;
    return 0;
}

static int serve_connection(int fd)
{
    struct timeval timeout = { .tv_sec = 30, .tv_usec = 0 };
    struct dniv_nice_read_node request;
    struct dniv_identity identity;
    unsigned char in[256];
    unsigned char out[512];
    size_t out_len = 0U;
    __u16 active_links = 0U;
    ssize_t got;

    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO,
                   &timeout, sizeof(timeout)) < 0 ||
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO,
                   &timeout, sizeof(timeout)) < 0)
        return -1;

    got = recv(fd, in, sizeof(in), 0);
    if (got <= 0)
        return -1;

    if (dniv_nice_parse_read_node(in, (size_t)got, &request) ||
        request.permanent || request.node != 0U ||
        read_identity(&identity)) {
        const signed char error = -1;
        return send(fd, &error, sizeof(error), MSG_EOR | MSG_NOSIGNAL) ==
               (ssize_t)sizeof(error) ? 0 : -1;
    }

    switch (request.info) {
    case DNIV_NICE_INFO_SUMMARY:
    case DNIV_NICE_INFO_STATUS:
        if (count_active_links(&active_links) ||
            dniv_nice_build_node_status_reply(out, sizeof(out), &out_len,
                                              identity.address,
                                              identity.name, active_links))
            return -1;
        break;
    case DNIV_NICE_INFO_CHARACTERISTICS:
        if (dniv_nice_build_node_reply(out, sizeof(out), &out_len,
                                       identity.address, identity.name,
                                       DNIV_NML_IDENT))
            return -1;
        break;
    default: {
        const signed char error = -1;
        return send(fd, &error, sizeof(error), MSG_EOR | MSG_NOSIGNAL) ==
               (ssize_t)sizeof(error) ? 0 : -1;
    }
    }
    if (send(fd, out, out_len, MSG_EOR | MSG_NOSIGNAL) != (ssize_t)out_len)
        return -1;
    return 0;
}

int main(int argc, char **argv)
{
    int once = 0;
    int listener;

    if (argc == 2 && strcmp(argv[1], "--once") == 0)
        once = 1;
    else if (argc != 1) {
        fprintf(stderr, "usage: %s [--once]\n", argv[0]);
        return 2;
    }

    setvbuf(stdout, NULL, _IONBF, 0);
    listener = make_listener();
    if (listener < 0) {
        perror("dnnml: listener");
        return 1;
    }
    puts("dnnml: ready object=19 version=4.0.0");

    for (;;) {
        int fd = accept(listener, NULL, NULL);
        int ret;

        if (fd < 0) {
            if (errno == EINTR)
                continue;
            perror("dnnml: accept");
            close(listener);
            return 1;
        }
        ret = serve_connection(fd);
        close(fd);
        if (ret) {
            fprintf(stderr, "dnnml: request failed\n");
            close(listener);
            return 1;
        }
        puts("dnnml: served READ NODE executor");
        if (once)
            break;
    }

    close(listener);
    return 0;
}

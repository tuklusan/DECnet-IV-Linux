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
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

#include <netdnet/dnetdb.h>

int main(void)
{
    static char accept_data[] = { (char)0xff, (char)0xff };
    unsigned char in[2048];
    unsigned char out[2048];
    int fd;

    fd = dnet_daemon(0, "LIBMIRROR", 0, 0);
    if (fd < 0) {
        perror("dnetlib-daemon: dnet_daemon");
        return 1;
    }
    dnet_accept(fd, 0, accept_data, sizeof(accept_data));
    if (dnet_eof(fd)) {
        perror("dnetlib-daemon: accept");
        close(fd);
        return 1;
    }

    for (;;) {
        int got = dnet_recv(fd, in, sizeof(in), MSG_EOR);

        if (got == 0)
            break;
        if (got < 0) {
            if (errno == ENOTCONN)
                break;
            perror("dnetlib-daemon: recv");
            close(fd);
            return 1;
        }
        if (in[0] == 0U) {
            out[0] = 1U;
            if (got > 1)
                memcpy(out + 1, in + 1, (size_t)got - 1U);
            if (send(fd, out, (size_t)got, MSG_EOR | MSG_NOSIGNAL) != got) {
                perror("dnetlib-daemon: send");
                close(fd);
                return 1;
            }
        } else {
            out[0] = 0xffU;
            if (send(fd, out, 1U, MSG_EOR | MSG_NOSIGNAL) != 1) {
                perror("dnetlib-daemon: send");
                close(fd);
                return 1;
            }
        }
    }
    close(fd);
    puts("dnetlib-daemon: pass object=LIBMIRROR");
    return 0;
}

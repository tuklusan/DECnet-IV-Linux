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

    dnet_accept(STDIN_FILENO, 0, accept_data, sizeof(accept_data));
    if (dnet_eof(STDIN_FILENO)) {
        perror("dnetd-mirror: accept");
        return 1;
    }

    for (;;) {
        int got = dnet_recv(STDIN_FILENO, in, sizeof(in), MSG_EOR);

        if (got == 0)
            return 0;
        if (got < 0) {
            if (errno == ENOTCONN)
                return 0;
            perror("dnetd-mirror: recv");
            return 1;
        }
        if (in[0] == 0U) {
            out[0] = 1U;
            if (got > 1)
                memcpy(out + 1, in + 1, (size_t)got - 1U);
            if (send(STDOUT_FILENO, out, (size_t)got,
                     MSG_EOR | MSG_NOSIGNAL) != got)
                return 1;
        } else {
            out[0] = 0xffU;
            if (send(STDOUT_FILENO, out, 1U,
                     MSG_EOR | MSG_NOSIGNAL) != 1)
                return 1;
        }
    }
}

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

#include <netdnet/dnetdb.h>

int main(void)
{
    struct dn_naddr addr;
    char text[DNET_ADDRSTRLEN];
    char object_name[DN_MAXOBJL + 1U];
    struct dn_naddr *compat;
    struct nodeent *node;

    memset(&addr, 0, sizeof(addr));
    if (dnet_pton(AF_DECnet, "31.71", &addr) != 1 ||
        !dnet_ntop(AF_DECnet, &addr, text, sizeof(text)) ||
        strcmp(text, "31.71"))
        return 1;
    compat = dnet_addr("1.1023");
    if (!compat || !dnet_ntoa(compat) || strcmp(dnet_ntoa(compat), "1.1023"))
        return 1;
    errno = 0;
    if (dnet_pton(AF_DECnet, "64.1", &addr) != 0 || errno != EINVAL)
        return 1;
    errno = 0;
    if (dnet_pton(AF_INET, "31.71", &addr) != -1 ||
        errno != EAFNOSUPPORT)
        return 1;
    node = getnodebyname("31.71");
    if (!node || node->n_addrtype != AF_DECnet || node->n_length != DN_ADDL ||
        node->n_addr[0] != 71U || node->n_addr[1] != 124U)
        return 1;
    if (getobjectbyname("mirror") != 25 ||
        getobjectbyname("NICE") != 19)
        return 1;
    memset(object_name, 0, sizeof(object_name));
    if (getobjectbynumber(25, object_name, sizeof(object_name)) != 25 ||
        strcmp(object_name, "MIRROR"))
        return 1;
    if (dnet_setobjhinum_handling(DNOBJHINUM_ERROR, 0))
        return 1;
    errno = 0;
    if (dnet_checkobjectnumber(256) != -1 || errno != EINVAL)
        return 1;
    errno = 0;
    if (dnet_conn(NULL, "#25", SOCK_SEQPACKET, NULL, 0, NULL, NULL) != -1 ||
        errno != EINVAL)
        return 1;
    errno = 0;
    if (dnet_conn("31.71", "#25", SOCK_DGRAM, NULL, 0, NULL, NULL) != -1 ||
        errno != EPROTONOSUPPORT)
        return 1;
    errno = 0;
    if (dnet_conn("31.71/USER/PASS", "#25", SOCK_SEQPACKET,
                  NULL, 0, NULL, NULL) != -1 || errno != EINVAL)
        return 1;
    errno = 0;
    if (dnet_conn("31.71", "OBJECT-NAME-TOO-LONG", SOCK_SEQPACKET,
                  NULL, 0, NULL, NULL) != -1 || errno != ENAMETOOLONG)
        return 1;
    puts("libdnet selftest passed");
    return 0;
}

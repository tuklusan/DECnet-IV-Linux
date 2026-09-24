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
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>

#include <netdnet/dnetdb.h>

#define DNIV_NODE_DB "/etc/decnet.conf"

struct node_record {
    char kind[16];
    char address[16];
    char name_tag[16];
    char name[DN_MAXNODEL + 1U];
    char line_tag[16];
    char device[64];
    struct dn_naddr dnaddr;
    int fields;
};

struct node_iterator {
    FILE *file;
    char name[DN_MAXNODEL + 1U];
};

struct object_entry {
    int number;
    const char *name;
};

static const struct object_entry object_db[] = {
    { 17, "FAL" },
    { 18, "HLD" },
    { 19, "NML" },
    { 19, "NICE" },
    { 23, "DTERM" },
    { 23, "REMACP" },
    { 25, "MIRROR" },
    { 26, "EVR" },
    { 27, "MAIL11" },
    { 27, "MAIL" },
    { 29, "PHONE" },
    { 42, "CTERM" },
    { 51, "VPM" },
    { 63, "DTR" },
    { -1, NULL }
};

static struct nodeent static_node;
static unsigned char static_node_addr[DN_ADDL];
static char static_node_name[DN_MAXNODEL + 1U];
static struct dn_naddr static_executor_addr;
static char static_exec_device[64];
static int object_high_mode = DNOBJHINUM_ERROR;
static int object_high_ready;

static unsigned char ascii_lower(unsigned char ch)
{
    if (ch >= 'A' && ch <= 'Z')
        return (unsigned char)(ch + ('a' - 'A'));
    return ch;
}

static int ascii_case_equal(const char *left, const char *right)
{
    if (!left || !right)
        return 0;
    while (*left && *right) {
        if (ascii_lower((unsigned char)*left) !=
            ascii_lower((unsigned char)*right))
            return 0;
        left++;
        right++;
    }
    return *left == '\0' && *right == '\0';
}

static int uppercase_copy(char *dst, size_t cap, const char *src)
{
    size_t used = 0;

    if (!dst || !cap || !src) {
        errno = EINVAL;
        return -1;
    }
    while (src[used]) {
        unsigned char ch;

        if (used + 1U >= cap) {
            errno = ENAMETOOLONG;
            return -1;
        }
        ch = (unsigned char)src[used];
        if (ch >= 'a' && ch <= 'z')
            ch = (unsigned char)(ch - ('a' - 'A'));
        dst[used++] = (char)ch;
    }
    dst[used] = '\0';
    return 0;
}

static int read_node_record(FILE *file, struct node_record *record)
{
    char line[512];

    while (fgets(line, sizeof(line), file)) {
        char *start = line;

        while (*start == ' ' || *start == '\t' || *start == '\r' ||
               *start == '\n')
            start++;
        if (!*start || *start == '#')
            continue;

        memset(record, 0, sizeof(*record));
        record->fields = sscanf(start, "%15s %15s %15s %256s %15s %63s",
                                record->kind, record->address,
                                record->name_tag, record->name,
                                record->line_tag, record->device);
        if (record->fields != 4 && record->fields != 6) {
            errno = EINVAL;
            return -1;
        }
        if ((!ascii_case_equal(record->kind, "executor") &&
             !ascii_case_equal(record->kind, "node")) ||
            !ascii_case_equal(record->name_tag, "name")) {
            errno = EINVAL;
            return -1;
        }
        if (record->fields == 6 &&
            (!ascii_case_equal(record->kind, "executor") ||
             !ascii_case_equal(record->line_tag, "line"))) {
            errno = EINVAL;
            return -1;
        }
        if (dnet_pton(AF_DECnet, record->address, &record->dnaddr) != 1) {
            errno = EINVAL;
            return -1;
        }
        return 1;
    }

    if (ferror(file)) {
        errno = EIO;
        return -1;
    }
    return 0;
}

static struct nodeent *fill_node(const char *name,
                                 const unsigned char addr[DN_ADDL])
{
    if (uppercase_copy(static_node_name, sizeof(static_node_name), name))
        return NULL;
    memcpy(static_node_addr, addr, DN_ADDL);
    memset(&static_node, 0, sizeof(static_node));
    static_node.n_name = static_node_name;
    static_node.n_addrtype = AF_DECnet;
    static_node.n_length = DN_ADDL;
    static_node.n_addr = static_node_addr;
    errno = 0;
    return &static_node;
}

struct nodeent *getnodebyname(const char *name)
{
    struct dn_naddr numeric;
    struct node_record record;
    FILE *file;
    int rc;

    if (!name || !*name) {
        errno = EINVAL;
        return NULL;
    }

    if (dnet_pton(AF_DECnet, name, &numeric) == 1)
        return fill_node(name, numeric.a_addr);

    file = fopen(DNIV_NODE_DB, "r");
    if (!file)
        return NULL;
    while ((rc = read_node_record(file, &record)) > 0) {
        if (ascii_case_equal(record.name, name)) {
            fclose(file);
            return fill_node(record.name, record.dnaddr.a_addr);
        }
    }
    fclose(file);
    if (rc == 0)
        errno = ENOENT;
    return NULL;
}

struct nodeent *getnodebyaddr(const char *addr, int len, int type)
{
    struct node_record record;
    FILE *file;
    int rc;

    if (!addr || len != DN_ADDL) {
        errno = EINVAL;
        return NULL;
    }
    if (type != AF_DECnet) {
        errno = EAFNOSUPPORT;
        return NULL;
    }

    file = fopen(DNIV_NODE_DB, "r");
    if (!file)
        return NULL;
    while ((rc = read_node_record(file, &record)) > 0) {
        if (!memcmp(record.dnaddr.a_addr, addr, DN_ADDL)) {
            fclose(file);
            return fill_node(record.name, record.dnaddr.a_addr);
        }
    }
    fclose(file);
    if (rc == 0)
        errno = ENOENT;
    return NULL;
}

struct dn_naddr *getnodeadd(void)
{
    struct node_record record;
    FILE *file;
    int rc;

    file = fopen(DNIV_NODE_DB, "r");
    if (!file)
        return NULL;
    while ((rc = read_node_record(file, &record)) > 0) {
        if (ascii_case_equal(record.kind, "executor")) {
            static_executor_addr = record.dnaddr;
            fclose(file);
            errno = 0;
            return &static_executor_addr;
        }
    }
    fclose(file);
    if (rc == 0)
        errno = ENOENT;
    return NULL;
}

char *getexecdev(void)
{
    struct node_record record;
    FILE *file;
    int rc;

    file = fopen(DNIV_NODE_DB, "r");
    if (!file)
        return NULL;
    while ((rc = read_node_record(file, &record)) > 0) {
        if (ascii_case_equal(record.kind, "executor") &&
            record.fields == 6) {
            size_t len = strlen(record.device);

            if (len >= sizeof(static_exec_device)) {
                fclose(file);
                errno = ENAMETOOLONG;
                return NULL;
            }
            memcpy(static_exec_device, record.device, len + 1U);
            fclose(file);
            errno = 0;
            return static_exec_device;
        }
    }
    fclose(file);
    if (rc == 0)
        errno = ENOENT;
    return NULL;
}

void setnodeent(int stayopen)
{
    (void)stayopen;
}

void *dnet_getnode(void)
{
    struct node_iterator *iterator;
    FILE *file = fopen(DNIV_NODE_DB, "r");

    if (!file)
        return NULL;
    iterator = calloc(1U, sizeof(*iterator));
    if (!iterator) {
        fclose(file);
        return NULL;
    }
    iterator->file = file;
    return iterator;
}

char *dnet_nextnode(void *handle)
{
    struct node_iterator *iterator = handle;
    struct node_record record;
    int rc;

    if (!iterator || !iterator->file) {
        errno = EINVAL;
        return NULL;
    }
    while ((rc = read_node_record(iterator->file, &record)) > 0) {
        if (uppercase_copy(iterator->name, sizeof(iterator->name),
                           record.name))
            return NULL;
        errno = 0;
        return iterator->name;
    }
    return NULL;
}

void dnet_endnode(void *handle)
{
    struct node_iterator *iterator = handle;

    if (!iterator)
        return;
    if (iterator->file)
        fclose(iterator->file);
    free(iterator);
}

static void init_object_high_mode(void)
{
    const char *mode;

    if (object_high_ready)
        return;
    object_high_mode = DNOBJHINUM_ERROR;
    mode = getenv(DNOBJ_HINUM_ENV);
    if (mode && *mode) {
        if (ascii_case_equal(mode, "zero"))
            object_high_mode = DNOBJHINUM_ZERO;
        else if (ascii_case_equal(mode, "return"))
            object_high_mode = DNOBJHINUM_RETURN;
        else if (ascii_case_equal(mode, "alwayszero"))
            object_high_mode = DNOBJHINUM_ALWAYSZERO;
    }
    object_high_ready = 1;
}

int dnet_setobjhinum_handling(int handling, int min)
{
    if (handling == DNOBJHINUM_RESET) {
        object_high_ready = 0;
        init_object_high_mode();
        return 0;
    }
    if (handling != DNOBJHINUM_ERROR &&
        handling != DNOBJHINUM_RETURN &&
        handling != DNOBJHINUM_ZERO &&
        handling != DNOBJHINUM_ALWAYSZERO) {
        errno = EINVAL;
        return -1;
    }

    init_object_high_mode();
    if (min && object_high_mode > handling)
        return 1;
    object_high_mode = handling;
    object_high_ready = 1;
    return 0;
}

int dnet_checkobjectnumber(int number)
{
    init_object_high_mode();

    if (object_high_mode == DNOBJHINUM_ALWAYSZERO && number != -1)
        return 0;
    if (number < 256)
        return number;

    switch (object_high_mode) {
    case DNOBJHINUM_ERROR:
        errno = EINVAL;
        return -1;
    case DNOBJHINUM_ZERO:
        return 0;
    case DNOBJHINUM_RETURN:
        return number;
    default:
        errno = ENOSYS;
        return -1;
    }
}

int getobjectbyname(const char *name)
{
    size_t i;

    if (!name || !*name) {
        errno = EINVAL;
        return -1;
    }
    for (i = 0; object_db[i].name; i++) {
        if (ascii_case_equal(name, object_db[i].name)) {
            int number = dnet_checkobjectnumber(object_db[i].number);

            if (number >= 0)
                errno = 0;
            return number;
        }
    }
    errno = ENOENT;
    return -1;
}

int getobjectbynumber(int number, char *name, size_t name_len)
{
    int checked;
    size_t i;

    if (!name || name_len < 2U) {
        errno = EINVAL;
        return -1;
    }
    checked = dnet_checkobjectnumber(number);
    if (checked < 0)
        return -1;

    for (i = 0; object_db[i].name; i++) {
        if (object_db[i].number == number) {
            size_t len = strlen(object_db[i].name);

            if (len >= name_len)
                len = name_len - 1U;
            memcpy(name, object_db[i].name, len);
            name[len] = '\0';
            errno = 0;
            return checked;
        }
    }
    errno = ENOENT;
    return -1;
}

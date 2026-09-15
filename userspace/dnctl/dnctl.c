// SPDX-License-Identifier: GPL-2.0
#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/decnet_iv.h>
#include <net/if.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#define DNIV_DEVICE "/dev/decnet_iv"

static void usage(FILE *stream, const char *prog)
{
    fprintf(stream,
            "usage:\n"
            "  %s show\n"
            "  %s set AREA.NODE NAME\n"
            "  %s stats\n"
            "  %s adjacencies\n"
            "  %s reset-stats\n",
            prog, prog, prog, prog, prog);
}

static int parse_address(const char *text, __u16 *address)
{
    char *dot;
    char *end;
    unsigned long area;
    unsigned long node;
    char copy[32];

    if (strlen(text) >= sizeof(copy))
        return -1;
    strcpy(copy, text);
    dot = strchr(copy, '.');
    if (!dot || strchr(dot + 1, '.'))
        return -1;
    *dot++ = '\0';

    errno = 0;
    area = strtoul(copy, &end, 10);
    if (errno || *copy == '\0' || *end != '\0' || area < 1 || area > 63)
        return -1;

    errno = 0;
    node = strtoul(dot, &end, 10);
    if (errno || *dot == '\0' || *end != '\0' || node < 1 || node > 1023)
        return -1;

    *address = DNIV_ADDR(area, node);
    return 0;
}

static int normalize_name(const char *input, char output[DNIV_NODE_NAME_BUFSZ])
{
    size_t len = strlen(input);
    size_t i;

    if (len == 0 || len > DNIV_NODE_NAME_MAX)
        return -1;
    memset(output, 0, DNIV_NODE_NAME_BUFSZ);
    for (i = 0; i < len; i++) {
        if (!isalnum((unsigned char)input[i]))
            return -1;
        output[i] = (char)toupper((unsigned char)input[i]);
    }
    return 0;
}

static int open_device(int writable)
{
    int fd = open(DNIV_DEVICE, writable ? O_RDWR : O_RDONLY);

    if (fd < 0)
        perror(DNIV_DEVICE);
    return fd;
}

static int show_identity(void)
{
    struct dniv_identity identity;
    int fd = open_device(0);

    if (fd < 0)
        return 1;
    memset(&identity, 0, sizeof(identity));
    if (ioctl(fd, DNIV_IOC_GET_IDENTITY, &identity) < 0) {
        perror("DNIV_IOC_GET_IDENTITY");
        close(fd);
        return 1;
    }
    close(fd);

    if (identity.uapi_version != DNIV_UAPI_VERSION) {
        fprintf(stderr, "dnctl: unsupported kernel UAPI version %u\n",
                identity.uapi_version);
        return 1;
    }

    printf("Executor node = %u.%u (%s)\n",
           DNIV_ADDR_AREA(identity.address),
           DNIV_ADDR_NODE(identity.address), identity.name);
    return 0;
}

static int set_identity(const char *address_text, const char *name)
{
    struct dniv_identity identity;
    int fd;

    memset(&identity, 0, sizeof(identity));
    identity.uapi_version = DNIV_UAPI_VERSION;
    if (parse_address(address_text, &identity.address) < 0 ||
        normalize_name(name, identity.name) < 0) {
        fprintf(stderr, "dnctl: invalid DECnet identity\n");
        return 2;
    }

    fd = open_device(1);
    if (fd < 0)
        return 1;
    if (ioctl(fd, DNIV_IOC_SET_IDENTITY, &identity) < 0) {
        perror("DNIV_IOC_SET_IDENTITY");
        close(fd);
        return 1;
    }
    close(fd);
    return show_identity();
}

static int show_stats(void)
{
    struct dniv_stats stats;
    int fd = open_device(0);

    if (fd < 0)
        return 1;
    memset(&stats, 0, sizeof(stats));
    if (ioctl(fd, DNIV_IOC_GET_STATS, &stats) < 0) {
        perror("DNIV_IOC_GET_STATS");
        close(fd);
        return 1;
    }
    close(fd);

    if (stats.uapi_version != DNIV_UAPI_VERSION) {
        fprintf(stderr, "dnctl: unsupported kernel UAPI version %u\n",
                stats.uapi_version);
        return 1;
    }

    printf("Routing frames received = %llu\n",
           (unsigned long long)stats.rx_frames);
    printf("Routing bytes received  = %llu\n",
           (unsigned long long)stats.rx_bytes);
    printf("Hello frames received   = %llu\n",
           (unsigned long long)stats.hello_rx);
    printf("Hello frames sent       = %llu\n",
           (unsigned long long)stats.hello_tx);
    printf("Hello errors            = %llu\n",
           (unsigned long long)stats.hello_errors);
    printf("Adjacencies up          = %llu\n",
           (unsigned long long)stats.adjacency_up);
    printf("Adjacencies down        = %llu\n",
           (unsigned long long)stats.adjacency_down);
    return 0;
}

static const char *node_type_name(__u8 type)
{
    switch (type) {
    case DNIV_NODE_TYPE_L2_ROUTER:
        return "L2 router";
    case DNIV_NODE_TYPE_L1_ROUTER:
        return "L1 router";
    case DNIV_NODE_TYPE_ENDNODE:
        return "endnode";
    default:
        return "unknown";
    }
}

static const char *state_name(__u8 state)
{
    switch (state) {
    case DNIV_ADJ_STATE_INIT:
        return "INIT";
    case DNIV_ADJ_STATE_UP:
        return "UP";
    default:
        return "UNKNOWN";
    }
}

static int show_adjacencies(void)
{
    struct dniv_adjacency adjacency;
    __u32 index;
    int fd = open_device(0);

    if (fd < 0)
        return 1;

    for (index = 0;; index++) {
        char ifname[IF_NAMESIZE];
        const char *display_ifname;

        memset(&adjacency, 0, sizeof(adjacency));
        adjacency.uapi_version = DNIV_UAPI_VERSION;
        adjacency.index = index;
        if (ioctl(fd, DNIV_IOC_GET_ADJACENCY, &adjacency) < 0) {
            if (errno == ENOENT)
                break;
            perror("DNIV_IOC_GET_ADJACENCY");
            close(fd);
            return 1;
        }
        if (adjacency.uapi_version != DNIV_UAPI_VERSION) {
            fprintf(stderr, "dnctl: unsupported kernel UAPI version %u\n",
                    adjacency.uapi_version);
            close(fd);
            return 1;
        }
        display_ifname = if_indextoname(adjacency.ifindex, ifname);
        if (!display_ifname)
            display_ifname = "?";
        printf("%u.%u via %s: %s %s block=%u hello=%us priority=%u "
               "expires=%ums mac=%02x:%02x:%02x:%02x:%02x:%02x\n",
               DNIV_ADDR_AREA(adjacency.address),
               DNIV_ADDR_NODE(adjacency.address), display_ifname,
               node_type_name(adjacency.node_type), state_name(adjacency.state),
               adjacency.block_size, adjacency.hello_timer,
               adjacency.priority, adjacency.expires_ms,
               adjacency.mac[0], adjacency.mac[1], adjacency.mac[2],
               adjacency.mac[3], adjacency.mac[4], adjacency.mac[5]);
    }
    close(fd);
    return 0;
}

static int reset_stats(void)
{
    int fd = open_device(1);

    if (fd < 0)
        return 1;
    if (ioctl(fd, DNIV_IOC_RESET_STATS) < 0) {
        perror("DNIV_IOC_RESET_STATS");
        close(fd);
        return 1;
    }
    close(fd);
    return 0;
}

int main(int argc, char **argv)
{
    if (argc == 1 || (argc == 2 && strcmp(argv[1], "show") == 0))
        return show_identity();
    if (argc == 4 && strcmp(argv[1], "set") == 0)
        return set_identity(argv[2], argv[3]);
    if (argc == 2 && strcmp(argv[1], "stats") == 0)
        return show_stats();
    if (argc == 2 && strcmp(argv[1], "adjacencies") == 0)
        return show_adjacencies();
    if (argc == 2 && strcmp(argv[1], "reset-stats") == 0)
        return reset_stats();

    usage(stderr, argv[0]);
    return 2;
}

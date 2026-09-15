// SPDX-License-Identifier: GPL-2.0
#include <arpa/inet.h>
#include <errno.h>
#include <linux/if_ether.h>
#include <net/if.h>
#include <netpacket/packet.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <unistd.h>

#define DNIV_ETHERTYPE 0x6003
#define DNIV_PAYLOAD_MAX 256

static int parse_mac(const char *text, unsigned char mac[ETH_ALEN])
{
    unsigned int b[ETH_ALEN];
    int i;

    if (sscanf(text, "%x:%x:%x:%x:%x:%x",
               &b[0], &b[1], &b[2], &b[3], &b[4], &b[5]) != ETH_ALEN)
        return -1;
    for (i = 0; i < ETH_ALEN; i++) {
        if (b[i] > 0xff)
            return -1;
        mac[i] = (unsigned char)b[i];
    }
    return 0;
}

int main(int argc, char **argv)
{
    unsigned char dst[ETH_ALEN];
    unsigned char frame[ETH_HLEN + DNIV_PAYLOAD_MAX];
    struct sockaddr_ll sa;
    struct ifreq ifr;
    const char *iface;
    const char *payload;
    size_t payload_len;
    int fd;
    int ifindex;
    ssize_t sent;

    if (argc != 4) {
        fprintf(stderr, "usage: %s IFACE DEST-MAC PAYLOAD\n", argv[0]);
        return 2;
    }
    iface = argv[1];
    payload = argv[3];
    payload_len = strlen(payload);
    if (payload_len == 0 || payload_len > DNIV_PAYLOAD_MAX) {
        fprintf(stderr, "dnraw: payload must be 1..%d bytes\n", DNIV_PAYLOAD_MAX);
        return 2;
    }
    if (parse_mac(argv[2], dst) < 0) {
        fprintf(stderr, "dnraw: invalid destination MAC\n");
        return 2;
    }

    ifindex = (int)if_nametoindex(iface);
    if (ifindex == 0) {
        perror("if_nametoindex");
        return 1;
    }

    fd = socket(AF_PACKET, SOCK_RAW, htons(DNIV_ETHERTYPE));
    if (fd < 0) {
        perror("socket");
        return 1;
    }

    memset(&ifr, 0, sizeof(ifr));
    if (strlen(iface) >= sizeof(ifr.ifr_name)) {
        fprintf(stderr, "dnraw: interface name too long\n");
        close(fd);
        return 2;
    }
    strcpy(ifr.ifr_name, iface);
    if (ioctl(fd, SIOCGIFHWADDR, &ifr) < 0) {
        perror("SIOCGIFHWADDR");
        close(fd);
        return 1;
    }

    memcpy(frame, dst, ETH_ALEN);
    memcpy(frame + ETH_ALEN, ifr.ifr_hwaddr.sa_data, ETH_ALEN);
    frame[12] = (unsigned char)(DNIV_ETHERTYPE >> 8);
    frame[13] = (unsigned char)(DNIV_ETHERTYPE & 0xff);
    memcpy(frame + ETH_HLEN, payload, payload_len);

    memset(&sa, 0, sizeof(sa));
    sa.sll_family = AF_PACKET;
    sa.sll_protocol = htons(DNIV_ETHERTYPE);
    sa.sll_ifindex = ifindex;
    sa.sll_halen = ETH_ALEN;
    memcpy(sa.sll_addr, dst, ETH_ALEN);

    sent = sendto(fd, frame, ETH_HLEN + payload_len, 0,
                  (struct sockaddr *)&sa, sizeof(sa));
    if (sent < 0) {
        perror("sendto");
        close(fd);
        return 1;
    }
    close(fd);
    return sent == (ssize_t)(ETH_HLEN + payload_len) ? 0 : 1;
}

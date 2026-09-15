// SPDX-License-Identifier: GPL-2.0
#include <arpa/inet.h>
#include <linux/if_packet.h>
#include <net/ethernet.h>
#include <net/if.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <unistd.h>

#define DNIV_ETHERTYPE 0x6003

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
    unsigned char frame[ETH_FRAME_LEN];
    struct sockaddr_ll dst;
    struct ifreq ifr;
    size_t payload_len;
    int fd, ifindex;
    ssize_t sent;

    if (argc != 4) {
        fprintf(stderr, "usage: %s INTERFACE DEST-MAC PAYLOAD\n", argv[0]);
        return 2;
    }
    payload_len = strlen(argv[3]);
    if (payload_len > sizeof(frame) - ETH_HLEN) {
        fprintf(stderr, "dnraw: payload too large\n");
        return 2;
    }

    fd = socket(AF_PACKET, SOCK_RAW, htons(DNIV_ETHERTYPE));
    if (fd < 0) {
        perror("socket");
        return 1;
    }

    memset(&ifr, 0, sizeof(ifr));
    snprintf(ifr.ifr_name, sizeof(ifr.ifr_name), "%s", argv[1]);
    if (ioctl(fd, SIOCGIFINDEX, &ifr) < 0) {
        perror("SIOCGIFINDEX");
        close(fd);
        return 1;
    }
    ifindex = ifr.ifr_ifindex;
    if (ioctl(fd, SIOCGIFHWADDR, &ifr) < 0) {
        perror("SIOCGIFHWADDR");
        close(fd);
        return 1;
    }

    if (parse_mac(argv[2], frame) < 0) {
        fprintf(stderr, "dnraw: invalid destination MAC\n");
        close(fd);
        return 2;
    }
    memcpy(frame + ETH_ALEN, ifr.ifr_hwaddr.sa_data, ETH_ALEN);
    frame[12] = (unsigned char)(DNIV_ETHERTYPE >> 8);
    frame[13] = (unsigned char)(DNIV_ETHERTYPE & 0xff);
    memcpy(frame + ETH_HLEN, argv[3], payload_len);

    memset(&dst, 0, sizeof(dst));
    dst.sll_family = AF_PACKET;
    dst.sll_protocol = htons(DNIV_ETHERTYPE);
    dst.sll_ifindex = ifindex;
    dst.sll_halen = ETH_ALEN;
    memcpy(dst.sll_addr, frame, ETH_ALEN);

    sent = sendto(fd, frame, ETH_HLEN + payload_len, 0,
                  (struct sockaddr *)&dst, sizeof(dst));
    if (sent < 0) {
        perror("sendto");
        close(fd);
        return 1;
    }
    printf("sent %zd-byte DECnet routing frame on %s\n", sent, argv[1]);
    close(fd);
    return 0;
}

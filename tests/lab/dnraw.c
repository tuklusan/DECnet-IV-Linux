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

#define _DEFAULT_SOURCE
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
#define DNIV_LENGTH_LEN 2
#define DNIV_PAYLOAD_MAX 256
#define DNIV_SHORT_HEADER_LEN 6

static int parse_decnet(const char *text, unsigned short *address)
{
    unsigned int area;
    unsigned int node;
    char tail;

    if (sscanf(text, "%u.%u%c", &area, &node, &tail) != 2 ||
        area < 1 || area > 63 || node < 1 || node > 1023)
        return -1;
    *address = (unsigned short)((area << 10) | node);
    return 0;
}

static int parse_mac(const char *text, unsigned char mac[ETH_ALEN])
{
    unsigned int b[ETH_ALEN];
    char tail;
    int i;

    if (sscanf(text, "%x:%x:%x:%x:%x:%x%c",
               &b[0], &b[1], &b[2], &b[3], &b[4], &b[5], &tail) != ETH_ALEN)
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
    unsigned char frame[ETH_HLEN + DNIV_LENGTH_LEN + DNIV_PAYLOAD_MAX];
    struct sockaddr_ll sa;
    struct ifreq ifr;
    const char *iface;
    const char *payload;
    unsigned short src_addr = 0;
    unsigned short dst_addr = 0;
    unsigned int visit = 0;
    int short_mode = 0;
    size_t payload_len;
    size_t frame_len;
    int fd;
    int ifindex;
    ssize_t sent;

    if (argc == 8 && strcmp(argv[1], "--short") == 0) {
        short_mode = 1;
        iface = argv[2];
        if (parse_mac(argv[3], dst) < 0 ||
            parse_decnet(argv[4], &src_addr) < 0 ||
            parse_decnet(argv[5], &dst_addr) < 0 ||
            sscanf(argv[6], "%u", &visit) != 1 || visit > 63U) {
            fprintf(stderr, "dnraw: invalid short-data argument\n");
            return 2;
        }
        payload = argv[7];
    } else if (argc == 4) {
        iface = argv[1];
        payload = argv[3];
        if (parse_mac(argv[2], dst) < 0) {
            fprintf(stderr, "dnraw: invalid destination MAC\n");
            return 2;
        }
    } else {
        fprintf(stderr, "usage: %s IFACE DEST-MAC PAYLOAD\n", argv[0]);
        fprintf(stderr, "       %s --short IFACE LINK-DEST SRC DST VISIT PAYLOAD\n", argv[0]);
        return 2;
    }
    payload_len = strlen(payload);
    if (payload_len == 0 || payload_len > DNIV_PAYLOAD_MAX) {
        fprintf(stderr, "dnraw: payload must be 1..%d bytes\n", DNIV_PAYLOAD_MAX);
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
    if (short_mode) {
        size_t route_len = DNIV_SHORT_HEADER_LEN + payload_len;
        unsigned char *route = frame + ETH_HLEN + DNIV_LENGTH_LEN;

        if (route_len > DNIV_PAYLOAD_MAX) {
            fprintf(stderr, "dnraw: short data packet too large\n");
            close(fd);
            return 2;
        }
        frame[14] = (unsigned char)(route_len & 0xffU);
        frame[15] = (unsigned char)(route_len >> 8);
        route[0] = 0x02;
        route[1] = (unsigned char)(dst_addr & 0xffU);
        route[2] = (unsigned char)(dst_addr >> 8);
        route[3] = (unsigned char)(src_addr & 0xffU);
        route[4] = (unsigned char)(src_addr >> 8);
        route[5] = (unsigned char)visit;
        memcpy(route + DNIV_SHORT_HEADER_LEN, payload, payload_len);
        frame_len = ETH_HLEN + DNIV_LENGTH_LEN + route_len;
    } else {
        frame[14] = (unsigned char)(payload_len & 0xffU);
        frame[15] = (unsigned char)(payload_len >> 8);
        memcpy(frame + ETH_HLEN + DNIV_LENGTH_LEN, payload, payload_len);
        frame_len = ETH_HLEN + DNIV_LENGTH_LEN + payload_len;
    }

    memset(&sa, 0, sizeof(sa));
    sa.sll_family = AF_PACKET;
    sa.sll_protocol = htons(DNIV_ETHERTYPE);
    sa.sll_ifindex = ifindex;
    sa.sll_halen = ETH_ALEN;
    memcpy(sa.sll_addr, dst, ETH_ALEN);

    sent = sendto(fd, frame, frame_len, 0,
                  (struct sockaddr *)&sa, sizeof(sa));
    if (sent < 0) {
        perror("sendto");
        close(fd);
        return 1;
    }
    close(fd);
    return sent == (ssize_t)frame_len ? 0 : 1;
}

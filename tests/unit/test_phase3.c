// SPDX-License-Identifier: GPL-2.0
#include <assert.h>
#include <decnet_iv_wire.h>
#include <stdio.h>
#include <string.h>

static void test_mac(void)
{
    __u8 mac[6];
    __u16 address = 0;
    const __u8 expected[6] = {0xaa, 0x00, 0x04, 0x00, 0x46, 0x7c};

    dniv_wire_mac_from_address(DNIV_ADDR(31, 70), mac);
    assert(memcmp(mac, expected, sizeof(mac)) == 0);
    assert(dniv_wire_address_from_mac(mac, &address) == 0);
    assert(dniv_wire_address_from_mac(NULL, &address) < 0);
    assert(dniv_wire_address_from_mac(mac, NULL) < 0);
    assert(address == DNIV_ADDR(31, 70));

    mac[0] = 0xab;
    assert(dniv_wire_address_from_mac(mac, &address) < 0);
}

static void test_router_vector(void)
{
    __u8 buf[128];
    struct dniv_wire_hello hello;
    struct dniv_wire_rs_entry entry;
    __u8 priority = 0;
    __u8 twoway = 0;
    __u8 state = 0;
    int len;
    const __u8 empty_expected[] = {
        0x0b, 0x02, 0x00, 0x00, 0xaa, 0x00, 0x04, 0x00,
        0x46, 0x7c, 0x02, 0xda, 0x05, 0x40, 0x00, 0x0a,
        0x00, 0x00, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00
    };

    len = dniv_wire_build_router_hello(buf, sizeof(buf), DNIV_ADDR(31, 70),
                                       DNIV_NODE_TYPE_L1_ROUTER, 64, 10,
                                       NULL, 0);
    assert(len == (int)sizeof(empty_expected));
    assert(memcmp(buf, empty_expected, sizeof(empty_expected)) == 0);
    assert(dniv_wire_parse_hello(buf, len, &hello) == DNIV_WIRE_OK);
    assert(hello.is_router == 1);
    assert(hello.address == DNIV_ADDR(31, 70));
    assert(hello.node_type == DNIV_NODE_TYPE_L1_ROUTER);
    assert(hello.block_size == 1498);
    assert(hello.priority == 64);
    assert(hello.timer == 10);
    assert(hello.rs_count == 0);
    assert(dniv_wire_router_adjacency_state(&hello, DNIV_ADDR(31, 71),
                                             32, &state) == 0);
    assert(state == DNIV_ADJ_STATE_INIT);
    assert(dniv_wire_listen_msecs(10, 30) == 31000U);
    assert(dniv_wire_listen_msecs(0, 10) == 31000U);

    assert(dniv_wire_build_router_hello(buf, sizeof(buf), DNIV_ADDR(31, 70),
                                         DNIV_NODE_TYPE_L1_ROUTER, 64, 10,
                                         NULL, 1) == 0);

    entry.address = DNIV_ADDR(31, 71);
    entry.priority = 32;
    entry.twoway = 1;
    len = dniv_wire_build_router_hello(buf, sizeof(buf), DNIV_ADDR(31, 70),
                                       DNIV_NODE_TYPE_L1_ROUTER, 64, 10,
                                       &entry, 1);
    assert(len == 34);
    assert(buf[18] == 15);
    assert(buf[26] == 7);
    assert(memcmp(buf + 27,
                  (const __u8[]){0xaa, 0x00, 0x04, 0x00, 0x47, 0x7c, 0xa0},
                  7) == 0);
    assert(dniv_wire_parse_hello(buf, len, &hello) == DNIV_WIRE_OK);
    assert(hello.rs_count == 1);
    assert(dniv_wire_router_lists(&hello, DNIV_ADDR(31, 71),
                                  &priority, &twoway) == 1);
    assert(priority == 32);
    assert(twoway == 1);
    assert(dniv_wire_router_adjacency_state(&hello, DNIV_ADDR(31, 71),
                                             32, &state) == 0);
    assert(state == DNIV_ADJ_STATE_UP);
    assert(dniv_wire_router_adjacency_state(&hello, DNIV_ADDR(31, 71),
                                             31, &state) < 0);
}

static void test_endnode_vector(void)
{
    __u8 buf[128];
    __u8 neighbor[6];
    struct dniv_wire_hello hello;
    int len;
    unsigned int i;

    dniv_wire_mac_from_address(DNIV_ADDR(31, 70), neighbor);
    len = dniv_wire_build_endnode_hello(buf, sizeof(buf), DNIV_ADDR(31, 71),
                                        10, neighbor);
    assert(len == 82);
    assert(memcmp(buf,
                  (const __u8[]){0x0d, 0x02, 0x00, 0x00,
                                 0xaa, 0x00, 0x04, 0x00, 0x47, 0x7c,
                                 0x03, 0xda, 0x05},
                  13) == 0);
    assert(memcmp(buf + 22, neighbor, 6) == 0);
    assert(buf[28] == 10 && buf[29] == 0);
    assert(buf[31] == 50);
    for (i = 32; i < 82; i++)
        assert(buf[i] == 0xaa);
    assert(dniv_wire_parse_hello(buf, len, &hello) == DNIV_WIRE_OK);
    assert(hello.is_router == 0);
    assert(hello.address == DNIV_ADDR(31, 71));
    assert(hello.node_type == DNIV_NODE_TYPE_ENDNODE);
    assert(hello.timer == 10);
    assert(dniv_wire_endnode_test_valid(&hello));
}

static void test_malformed_and_padding(void)
{
    __u8 buf[128];
    __u8 padded[128];
    struct dniv_wire_hello hello;
    int len;

    len = dniv_wire_build_router_hello(buf, sizeof(buf), DNIV_ADDR(31, 70),
                                       DNIV_NODE_TYPE_L1_ROUTER, 64, 10,
                                       NULL, 0);
    assert(len == 27);

    memcpy(padded + 3, buf, (size_t)len);
    padded[0] = 0x83;
    padded[1] = 0;
    padded[2] = 0;
    assert(dniv_wire_parse_hello(padded, (__u32)len + 3, &hello) ==
           DNIV_WIRE_OK);

    buf[18] = 7;
    assert(dniv_wire_parse_hello(buf, len, &hello) == DNIV_WIRE_MALFORMED);
    buf[18] = 8;
    buf[4] = 0xab;
    assert(dniv_wire_parse_hello(buf, len, &hello) == DNIV_WIRE_MALFORMED);

    assert(dniv_wire_parse_hello((const __u8 *)"x", 1, &hello) ==
           DNIV_WIRE_NOT_HELLO);
}

int main(void)
{
    test_mac();
    test_router_vector();
    test_endnode_vector();
    test_malformed_and_padding();
    puts("Phase 3 Ethernet vector tests passed");
    return 0;
}

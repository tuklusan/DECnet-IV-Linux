// License: GPL-2.0
#include <assert.h>
#include <linux/decnet_iv.h>
#include <stdio.h>

_Static_assert(sizeof(struct dniv_identity) == 16, "dniv_identity UAPI size changed");
_Static_assert(sizeof(struct dniv_stats) == 64, "dniv_stats UAPI size changed");
_Static_assert(sizeof(struct dniv_adjacency) == 32, "dniv_adjacency UAPI size changed");

int main(void)
{
    __u16 first = DNIV_ADDR(31, 70);
    __u16 last = DNIV_ADDR(31, 79);

    assert(DNIV_UAPI_VERSION == 2U);
    assert(first == 0x7c46);
    assert(last == 0x7c4f);
    assert(DNIV_ADDR_AREA(first) == 31);
    assert(DNIV_ADDR_NODE(first) == 70);
    assert(DNIV_ADDR_AREA(last) == 31);
    assert(DNIV_ADDR_NODE(last) == 79);
    puts("UAPI address tests passed");
    return 0;
}

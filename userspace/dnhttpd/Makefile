# ============================================================================
# Copyright (c) 2026 Supratim Sanyal of SANYALnet Labs.
# Proprietary rights reserved except as expressly licensed herein.
# ============================================================================

CC ?= cc
CPPFLAGS ?= -I../../include/uapi
CFLAGS ?= -O2 -Wall -Wextra -Werror -std=c11

.PHONY: all check clean
all: dnhttpd check

dnhttpd: dnhttpd.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $<

check: dnhttpd
	./dnhttpd --selftest

clean:
	rm -f dnhttpd

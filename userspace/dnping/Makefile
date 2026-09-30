# ============================================================================
# Copyright (c) 2026 Supratim Sanyal of SANYALnet Labs.
# Proprietary rights reserved except as expressly licensed herein.
#
# DECnet-IV-Linux
# This file is governed by the SANYALnet Labs Non-Commercial License in the
# root LICENSE file. Non-Commercial use is permitted; Commercial Use and use
# for AI/ML model training are prohibited unless separately authorized.
#
# Attribution is required: "Based on original work by Supratim Sanyal of
# SANYALnet Labs." See LICENSE for full terms, warranty disclaimer, termination,
# patent, trademark, and governing-law provisions.
# ============================================================================

CC ?= cc
CFLAGS ?= -O2 -Wall -Wextra -Werror -std=c11
CPPFLAGS += -I../libdnet/include -I../../include/uapi
LDLIBS = ../libdnet/libdnet.a

.PHONY: all clean test

all: dnping

dnping: dnping.c ../libdnet/libdnet.a
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ dnping.c $(LDLIBS)

test: all
	./dnping --selftest

clean:
	rm -f dnping

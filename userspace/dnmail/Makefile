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
CPPFLAGS ?= -I../../include/uapi
CFLAGS ?= -O2 -Wall -Wextra -Werror -std=c11

.PHONY: all check clean
all: dnmail dnmaild check

dnmail: dnmail.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $<

dnmaild: dnmaild.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $<

check: dnmail dnmaild
	./dnmail --selftest
	./dnmaild --selftest

clean:
	rm -f dnmail dnmaild

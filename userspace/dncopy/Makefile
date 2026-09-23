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
CFLAGS ?= -O2 -Wall -Wextra -Werror

.PHONY: all check clean
all: dncopy dntype dndir check

dncopy: dncopy.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $<

dntype dndir: dncopy
	ln -sf dncopy $@

check: dncopy dntype dndir
	./dncopy --selftest

clean:
	rm -f dncopy dntype dndir

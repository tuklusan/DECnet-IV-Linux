# ============================================================================
# Copyright (c) 2026 Supratim Sanyal of SANYALnet Labs.
# Proprietary rights reserved except as expressly licensed herein.
#
# DO NOT PANIC PORTFOLIO VISUALIZER
# This file is governed by the SANYALnet Labs Non-Commercial License in the
# root LICENSE file. Non-Commercial use is permitted; Commercial Use and use
# for AI/ML model training are prohibited unless separately authorized.
#
# Attribution is required: "Based on original work by Supratim Sanyal of
# SANYALnet Labs." See LICENSE for full terms, warranty disclaimer, termination,
# patent, trademark, and governing-law provisions.
# ============================================================================

CC ?= cc
CPPFLAGS += -I../../include/uapi -I../../include
CFLAGS ?= -O2 -g
CFLAGS += -std=c11 -Wall -Wextra -Werror

.PHONY: all test clean
all: test_uapi test_phase3

test_uapi: test_uapi.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $<

test_phase3: test_phase3.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $<

test: all
	./test_uapi
	./test_phase3

clean:
	rm -f test_uapi test_phase3

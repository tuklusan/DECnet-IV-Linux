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
CPPFLAGS += -I../../include/uapi -I../../include
CFLAGS ?= -O2 -g
CFLAGS += -std=c11 -Wall -Wextra -Werror

.PHONY: all test clean
all: test_uapi test_dn_uapi test_phase3 test_endnode_bounds test_phase4_routing test_phase4_route_metric test_phase4_data test_phase5_nsp test_phase6_nice test_phase6_nice

test_uapi: test_uapi.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $<

test_dn_uapi: test_dn_uapi.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $<

test_phase3: test_phase3.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $<

test_endnode_bounds: test_endnode_bounds.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $<

test_phase4_routing: test_phase4_routing.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $<

test_phase4_route_metric: test_phase4_route_metric.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $<

test_phase4_data: test_phase4_data.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $<

test_phase5_nsp: test_phase5_nsp.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $<

test_phase6_nice: test_phase6_nice.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $<

test: all
	./test_uapi
	./test_dn_uapi
	./test_phase3
	./test_endnode_bounds
	./test_phase4_routing
	./test_phase4_route_metric
	./test_phase4_data
	./test_phase5_nsp
	./test_phase6_nice

clean:
	rm -f test_uapi test_dn_uapi test_phase3 test_endnode_bounds test_phase4_routing test_phase4_route_metric test_phase4_data test_phase5_nsp

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
AR ?= ar
CFLAGS ?= -O2 -Wall -Wextra -Werror -std=c11
CPPFLAGS += -Iinclude -I../../include/uapi
LIB = libdnet.a
SHARED = libdnet.so.1.0
SONAME = libdnet.so.1
OBJ = libdnet.o dnetdb.o compat.o
PICFLAGS ?= -fPIC

.PHONY: all clean test

all: $(LIB) $(SHARED) dnetlib-selftest

$(LIB): $(OBJ)
	$(AR) rcs $@ $^

libdnet.o: libdnet.c include/netdnet/dnetdb.h include/netdnet/dn.h
	$(CC) $(CPPFLAGS) $(CFLAGS) $(PICFLAGS) -c -o $@ libdnet.c

dnetdb.o: dnetdb.c include/netdnet/dnetdb.h include/netdnet/dn.h
	$(CC) $(CPPFLAGS) $(CFLAGS) $(PICFLAGS) -c -o $@ dnetdb.c

compat.o: compat.c include/netdnet/dnetdb.h include/netdnet/dn.h
	$(CC) $(CPPFLAGS) $(CFLAGS) $(PICFLAGS) -c -o $@ compat.c

$(SHARED): $(OBJ)
	$(CC) -shared -Wl,-soname,$(SONAME) -o $@ $(OBJ)
	ln -sf $(SHARED) $(SONAME)
	ln -sf $(SONAME) libdnet.so

dnetlib-selftest: selftest.c $(LIB)
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ selftest.c $(LIB)

test: all
	./dnetlib-selftest

clean:
	rm -f $(OBJ) $(LIB) $(SHARED) $(SONAME) libdnet.so dnetlib-selftest

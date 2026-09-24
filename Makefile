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

.PHONY: all userspace unit kernel clean

all: userspace unit

userspace:
	$(MAKE) -C userspace/dnctl
	$(MAKE) -C userspace/ncp
	$(MAKE) -C userspace/dnlogin
	$(MAKE) -C userspace/dncopy
	$(MAKE) -C userspace/dntask
	$(MAKE) -C userspace/dnfald
	$(MAKE) -C userspace/dnnml
	$(MAKE) -C userspace/dnnice
	$(MAKE) -C userspace/dnmirror
	$(MAKE) -C userspace/dnobject
	$(MAKE) -C userspace/dnhttpd
	$(MAKE) -C userspace/dnphone
	$(MAKE) -C userspace/dnmail
	$(MAKE) -C userspace/dnmultinet
	$(MAKE) -C userspace/libdnet test

unit:
	$(MAKE) -C tests/unit test

kernel:
	$(MAKE) -C kernel/decnet KDIR="$(KDIR)"

clean:
	$(MAKE) -C userspace/dnctl clean
	$(MAKE) -C userspace/ncp clean
	$(MAKE) -C userspace/dnlogin clean
	$(MAKE) -C userspace/dncopy clean
	$(MAKE) -C userspace/dntask clean
	$(MAKE) -C userspace/dnfald clean
	$(MAKE) -C userspace/dnnml clean
	$(MAKE) -C userspace/dnnice clean
	$(MAKE) -C userspace/dnmirror clean
	$(MAKE) -C userspace/dnobject clean
	$(MAKE) -C userspace/dnhttpd clean
	$(MAKE) -C userspace/dnphone clean
	$(MAKE) -C userspace/dnmail clean
	$(MAKE) -C userspace/dnmultinet clean
	$(MAKE) -C userspace/libdnet clean
	$(MAKE) -C tests/unit clean
	@if [ -n "$(KDIR)" ]; then $(MAKE) -C kernel/decnet KDIR="$(KDIR)" clean; fi

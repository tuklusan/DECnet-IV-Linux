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

.PHONY: all userspace unit kernel clean

all: userspace unit

userspace:
	$(MAKE) -C userspace/dnctl

unit:
	$(MAKE) -C tests/unit test

kernel:
	$(MAKE) -C kernel/decnet KDIR="$(KDIR)"

clean:
	$(MAKE) -C userspace/dnctl clean
	$(MAKE) -C tests/unit clean
	@if [ -n "$(KDIR)" ]; then $(MAKE) -C kernel/decnet KDIR="$(KDIR)" clean; fi

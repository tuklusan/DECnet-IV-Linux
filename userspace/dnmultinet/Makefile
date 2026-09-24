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

PYTHON ?= python3

.PHONY: all test clean
all: test

test:
	$(PYTHON) -m py_compile dnmultinet.py
	$(PYTHON) dnmultinet.py --node 31.80 --name MNET80 --type l2router \
		--vde vde:///tmp/dn31.ctl --mode connect \
		--peer-host 127.0.0.1 --peer-port 700 --dry-run | \
		grep -Fqx 'logging console --events 4.8,4.10,4.15,4.16'
	$(PYTHON) dnmultinet.py --node 31.80 --name MNET80 --type l2router \
		--vde vde:///tmp/dn31.ctl --mode listen --local-port 700 \
		--dry-run | \
		grep -Fqx 'logging console --events 4.8,4.10,4.15,4.16'

clean:
	rm -rf __pycache__

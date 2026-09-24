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
		--api-socket /tmp/dniv-api.sock --dry-run | \
		grep -Fqx 'api /tmp/dniv-api.sock --mode 600'
	MULTINET_REMOTE_HOST=127.0.0.1 MULTINET_REMOTE_PORT=700 \
		$(PYTHON) dnmultinet.py --node 31.80 --name MNET80 --type l2router \
		--vde vde:///tmp/dn31.ctl --mode connect --runtime-peer-env \
		--validate-only | grep -Fqx 'dnmultinet: configuration valid'
	$(PYTHON) -m py_compile ../../tests/lab/area31-nice.py
	$(CC) -std=c11 -Wall -Wextra -Werror -I../../include/uapi -I../../include \
		-I../libdnet/include -fsyntax-only ../../tests/lab/area31-native.c
	bash -n ../../tests/lab/prove-area31.sh
	sh -n ../../tests/lab/dniv-area31-smoke.sh
	MULTINET_REMOTE_HOST=127.0.0.1 MULTINET_REMOTE_PORT=700 \
		VAX_ADDR=31.99 VAX_USERNAME=TESTUSR VAX_PASSWORD=TESTPASS \
		DNIV_AREA31_GATEWAY_NODE=31.80 DNIV_AREA31_GATEWAY_NAME=MNET80 \
		DNIV_AREA31_LINUX_NODE=31.81 DNIV_AREA31_LINUX_NAME=DNIV81 \
		../../tests/lab/prove-area31.sh --preflight-only | \
		grep -Fqx 'area31-proof: preflight pass'
	@if out=$$(MULTINET_REMOTE_HOST=127.0.0.1 MULTINET_REMOTE_PORT=700 \
		VAX_ADDR=31.99 VAX_USERNAME=TESTUSR VAX_PASSWORD= \
		DNIV_AREA31_GATEWAY_NODE=31.80 DNIV_AREA31_GATEWAY_NAME=MNET80 \
		DNIV_AREA31_LINUX_NODE=31.81 DNIV_AREA31_LINUX_NAME=DNIV81 \
		../../tests/lab/prove-area31.sh --preflight-only 2>&1); then \
		echo 'area31 preflight unexpectedly accepted missing password' >&2; exit 1; \
	else \
		printf '%s\n' "$$out" | grep -Fqx 'area31-proof: missing required secret: VAX_PASSWORD'; \
	fi
	@if out=$$(MULTINET_REMOTE_HOST=127.0.0.1 MULTINET_REMOTE_PORT=700 \
		$(PYTHON) dnmultinet.py --node 31.80 --name MNET80 --type l2router \
		--vde vde:///tmp/dn31.ctl --mode connect --runtime-peer-env --dry-run 2>&1); then \
		echo 'runtime peer dry-run unexpectedly succeeded' >&2; exit 1; \
	else \
		printf '%s\n' "$$out" | grep -Fqx 'dry-run refuses runtime peer environment'; \
		! printf '%s\n' "$$out" | grep -Fq '127.0.0.1'; \
	fi

	bash -n ../../tests/lab/prove-vde2-cross-runner.sh
	VDE_SSH_HOST=bastion.invalid VDE_SSH_PORT=22 VDE_SSH_USER=TEST \
		VDE_SSH_KEY=TESTKEY VDE_SSH_KNOWN_HOSTS=TESTHOSTKEY \
		DNIV_VDE_REVERSE_PORT=22022 \
		../../tests/lab/prove-vde2-cross-runner.sh --preflight-only | \
		grep -Fqx 'vde2-cross: preflight pass'
	VDE_SSH_HOST=bastion.invalid VDE_SSH_PORT=22 VDE_SSH_USER=TEST \
		VDE_SSH_KEY=TESTKEY VDE_SSH_KNOWN_HOSTS=TESTHOSTKEY \
		DNIV_VDE_REVERSE_PORT=22022 \
		../../tests/lab/prove-vde2-cross-runner.sh --wrapper-selftest | \
		grep -Fqx 'vde2-cross: wrapper selftest pass'
	@if out=$$(VDE_SSH_HOST=bastion.invalid VDE_SSH_PORT=22 VDE_SSH_USER=TEST \
		VDE_SSH_KEY= VDE_SSH_KNOWN_HOSTS=TESTHOSTKEY DNIV_VDE_REVERSE_PORT=22022 \
		../../tests/lab/prove-vde2-cross-runner.sh --preflight-only 2>&1); then \
		echo 'cross-runner preflight unexpectedly accepted missing key' >&2; exit 1; \
	else \
		printf '%s\n' "$$out" | grep -Fqx 'vde2-cross: missing required secret/input: VDE_SSH_KEY'; \
	fi

clean:
	rm -rf __pycache__

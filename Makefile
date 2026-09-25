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
	$(MAKE) -C userspace/dnlynx
	$(MAKE) -C userspace/dnphone
	$(MAKE) -C userspace/dnmail
	$(MAKE) -C userspace/dnmultinet
	$(MAKE) -C userspace/libdnet test
	$(MAKE) -C userspace/dnping test
	$(MAKE) -C userspace/dnetd test

unit:
	$(MAKE) -C tests/unit test
	python3 tests/lab/vax/make-http-com.py --selftest
	python3 tests/lab/vax/make-task-com.py --selftest
	python3 -m py_compile tests/lab/area31-find-node.py
	python3 -m py_compile tests/lab/area31-nice.py
	cc -Iuserspace/libdnet/include -Iinclude/uapi -Iinclude -std=c11 -Wall -Wextra -Werror -fsyntax-only tests/lab/area31-native.c
	python3 tests/lab/area31-parse-known.py --selftest
	tests/lab/prove-vde2-cross-runner.sh --classifier-selftest
	bash -n tests/lab/prove-area31.sh
	env MULTINET_REMOTE_HOST=example.invalid MULTINET_REMOTE_PORT=60001 \
		VAX_ADDR=31.91 VAX_USERNAME=TEST VAX_PASSWORD=TEST \
		DNIV_AREA31_GATEWAY_NODE=31.92 DNIV_AREA31_GATEWAY_NAME=DNIV31 \
		DNIV_AREA31_LINUX_NODE=31.93 DNIV_AREA31_LINUX_NAME=DNIV32 \
		DNIV_QCOCAL_NODE=31.94 DNIV_AREA31_ARCH=amd64 \
		tests/lab/prove-area31.sh --preflight-only >/dev/null
	env MULTINET_REMOTE_HOST=example.invalid MULTINET_REMOTE_PORT=60001 \
		VAX_ADDR=31.91 VAX_USERNAME=TEST VAX_PASSWORD=TEST \
		DNIV_AREA31_GATEWAY_NODE=31.92 DNIV_AREA31_GATEWAY_NAME=DNIV31 \
		DNIV_AREA31_LINUX_NODE=31.93 DNIV_AREA31_LINUX_NAME=DNIV32 \
		DNIV_QCOCAL_NODE=31.94 DNIV_AREA31_ARCH=arm64 \
		tests/lab/prove-area31.sh --preflight-only >/dev/null

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
	$(MAKE) -C userspace/dnlynx clean
	$(MAKE) -C userspace/dnphone clean
	$(MAKE) -C userspace/dnmail clean
	$(MAKE) -C userspace/dnmultinet clean
	$(MAKE) -C userspace/dnping clean
	$(MAKE) -C userspace/dnetd clean
	$(MAKE) -C userspace/libdnet clean
	$(MAKE) -C tests/unit clean
	@if [ -n "$(KDIR)" ]; then $(MAKE) -C kernel/decnet KDIR="$(KDIR)" clean; fi

#!/usr/bin/env bash
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


# Static allowlist of the exact installed component names. Both lifecycle
# scripts use this function when trusting any existing manifest.
# Prefix containment alone must not authorize deleting another app.
dniv_manifest_prefix_member() {
    local path=$1 prefix=$2
    case "$path" in
        "$prefix"/sbin/dnctl|\
        "$prefix"/sbin/dnetd|\
        "$prefix"/sbin/dnfald|\
        "$prefix"/sbin/dnnml|\
        "$prefix"/sbin/dnphoned|\
        "$prefix"/sbin/dnmaild|\
        "$prefix"/sbin/dnhttpd|\
        "$prefix"/sbin/dnmultinet|\
        "$prefix"/bin/ncp|\
        "$prefix"/bin/dnlogin|\
        "$prefix"/bin/sethost|\
        "$prefix"/bin/dncopy|\
        "$prefix"/bin/dntype|\
        "$prefix"/bin/dndir|\
        "$prefix"/bin/dndel|\
        "$prefix"/bin/dnrename|\
        "$prefix"/bin/dnsubmit|\
        "$prefix"/bin/dnprint|\
        "$prefix"/bin/dntask|\
        "$prefix"/bin/dnnice|\
        "$prefix"/bin/dnmirror|\
        "$prefix"/bin/dnobject|\
        "$prefix"/bin/phone|\
        "$prefix"/bin/dnmail|\
        "$prefix"/bin/dnlynx|\
        "$prefix"/bin/dnping|\
        "$prefix"/lib/libdnet.a|\
        "$prefix"/lib/libdnet.so.1.0|\
        "$prefix"/lib/libdnet.so.1|\
        "$prefix"/lib/libdnet.so|\
        "$prefix"/lib/libdnet_daemon.a|\
        "$prefix"/lib/libdnet_daemon.so.1.0|\
        "$prefix"/lib/libdnet_daemon.so.1|\
        "$prefix"/lib/libdnet_daemon.so|\
        "$prefix"/include/netdnet/dn.h|\
        "$prefix"/include/netdnet/dnetdb.h|\
        "$prefix"/include/linux/dn.h|\
        "$prefix"/include/linux/decnet_iv.h|\
        "$prefix"/share/doc/decnet-iv-linux/README.md|\
        "$prefix"/share/doc/decnet-iv-linux/INSTALL.md|\
        "$prefix"/share/doc/decnet-iv-linux/LICENSE|\
        "$prefix"/share/doc/decnet-iv-linux/DELIVERY.md|\
        "$prefix"/share/doc/decnet-iv-linux/FEATURES.md|\
        "$prefix"/share/doc/decnet-iv-linux/COMPONENTS.md|\
        "$prefix"/share/doc/decnet-iv-linux/ARCHITECTURE.md|\
        "$prefix"/share/doc/decnet-iv-linux/SOURCE-METADATA)
            return 0 ;;
    esac
    return 1
}

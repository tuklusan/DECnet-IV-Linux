#!/bin/sh
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

set -eu

fail() {
    echo "DNIV-AREA31-NATIVE-FAIL reason=$1"
    poweroff -f || true
    exit 1
}

parse_node() {
    case "$1" in
        31.*) ;;
        *) return 1 ;;
    esac
    node=${1#31.}
    case "$node" in
        ''|*[!0-9]*) return 1 ;;
    esac
    [ "$node" -ge 1 ] && [ "$node" -le 1023 ]
}

parse_name() {
    case "$1" in
        [A-Za-z][A-Za-z0-9]|[A-Za-z][A-Za-z0-9][A-Za-z0-9]|[A-Za-z][A-Za-z0-9][A-Za-z0-9][A-Za-z0-9]|[A-Za-z][A-Za-z0-9][A-Za-z0-9][A-Za-z0-9][A-Za-z0-9]|[A-Za-z][A-Za-z0-9][A-Za-z0-9][A-Za-z0-9][A-Za-z0-9][A-Za-z0-9]|[A-Za-z]) return 0 ;;
        *) return 1 ;;
    esac
}

read_field() {
    key=$1
    sed -n "s/^${key}=//p" "$config" | tail -1
}

mkdir -p /run/dniv-area31
device=
for _ in $(seq 1 100); do
    device=$(blkid -L DNIVCTL 2>/dev/null || true)
    [ -n "$device" ] && break
    sleep 0.1
done
[ -n "$device" ] || fail no-control-disk
mount -o ro "$device" /run/dniv-area31 || fail mount-control
config=/run/dniv-area31/dniv-area31.env
[ -r "$config" ] || fail no-control-config

linux_node=$(read_field DNIV_LINUX_NODE)
linux_name=$(read_field DNIV_LINUX_NAME)
gateway_node=$(read_field DNIV_GATEWAY_NODE)
target=$(read_field DNIV_VAX_ADDR)
qcocal=$(read_field DNIV_QCOCAL_ADDR)
user_file=/run/dniv-area31/vax-user
password_file=/run/dniv-area31/vax-password
survey_manifest=/run/dniv-area31/area31-manifest.tsv
[ -r "$survey_manifest" ] || fail no-survey-manifest
[ -r "$user_file" ] || fail no-vax-user
[ -r "$password_file" ] || fail no-vax-password
vax_user=$(cat "$user_file")
vax_password=$(cat "$password_file")
[ -n "$vax_user" ] || fail empty-vax-user
[ -n "$vax_password" ] || fail empty-vax-password

parse_node "$linux_node" || fail bad-linux-node
parse_node "$gateway_node" || fail bad-gateway-node
parse_node "$target" || fail bad-target
parse_name "$linux_name" || fail bad-linux-name
[ "$linux_node" != "$gateway_node" ] || fail duplicate-node
[ "$linux_node" != "$target" ] || fail duplicate-node
[ "$gateway_node" != "$target" ] || fail duplicate-node
if [ -n "$qcocal" ]; then
    parse_node "$qcocal" || fail bad-qcocal-node
    [ "$qcocal" != "$linux_node" ] || fail duplicate-qcocal-node
    [ "$qcocal" != "$gateway_node" ] || fail duplicate-qcocal-node
    [ "$qcocal" != "$target" ] || fail duplicate-qcocal-node
    [ -r /run/dniv-area31/DNIVHT.COM ] || fail no-qcocal-http
    [ -r /run/dniv-area31/DNIVTK.COM ] || fail no-qcocal-task
fi

iface=
for _ in $(seq 1 100); do
    for path in /sys/class/net/*; do
        candidate=${path##*/}
        if [ "$candidate" != lo ]; then
            iface=$candidate
            break
        fi
    done
    [ -n "$iface" ] && break
    sleep 0.1
done
[ -n "$iface" ] || fail no-interface

area=31
node=${linux_node#31.}
modprobe decnet_iv default_area="$area" default_node="$node" default_name="$linux_name" \
    default_node_type=3 hello_interval=2 || fail module
/usr/local/sbin/dnctl set "$linux_node" "$linux_name" >/dev/null || fail identity
ip link set "$iface" up || fail link

ready=0
for _ in $(seq 1 320); do
    output=$(/usr/local/sbin/dnctl adjacencies 2>/dev/null || true)
    if printf '%s\n' "$output" | grep -F "$gateway_node via " | grep -Fq ' UP '; then
        ready=1
        break
    fi
    sleep 0.25
done
[ "$ready" -eq 1 ] || fail gateway-adjacency

route_ready=0
for _ in $(seq 1 320); do
    output=$(/usr/local/sbin/dnctl routes 2>/dev/null || true)
    if printf '%s\n' "$output" | grep -F "L1 $target via $gateway_node " >/dev/null; then
        route_ready=1
        break
    fi
    sleep 0.25
done
[ "$route_ready" -eq 1 ] || fail vax-route

remote_log=/tmp/dniv-area31-native.err
remote_ready=0
for _ in $(seq 1 120); do
    : >"$remote_log"
    if DNIV_AREA31_TARGET="$target" /usr/local/sbin/dniv-area31-native \
        >/dev/null 2>"$remote_log"; then
        remote_ready=1
        break
    fi
    sleep 0.5
done
if [ "$remote_ready" -ne 1 ]; then
    cat "$remote_log" >&2 || true
    rm -f "$remote_log"
    fail remote-protocol
fi
rm -f "$remote_log"

DNACCESS_USER="$vax_user" DNACCESS_PASSWORD="$vax_password" \
    /usr/local/sbin/dnlogin --probe "$target" >/dev/null 2>&1 ||
    fail cterm-access
DNACCESS_USER="$vax_user" DNACCESS_PASSWORD="$vax_password" \
    /usr/local/bin/dncopy --probe "$target" >/dev/null 2>&1 ||
    fail fal-access
DNACCESS_USER="$vax_user" DNACCESS_PASSWORD="$vax_password" \
    /usr/local/bin/dncopy --dir "$target" '*.*;*' >/dev/null 2>&1 ||
    fail fal-directory

if [ -n "$qcocal" ]; then
    qcocal_route_ready=0
    for _ in $(seq 1 320); do
        output=$(/usr/local/sbin/dnctl routes 2>/dev/null || true)
        if printf '%s\n' "$output" | grep -F "L1 $qcocal via $gateway_node " >/dev/null; then
            qcocal_route_ready=1
            break
        fi
        sleep 0.25
    done
    [ "$qcocal_route_ready" -eq 1 ] || fail qcocal-route
    DNACCESS_USER="$vax_user" DNACCESS_PASSWORD="$vax_password" \
        /usr/local/bin/dncopy --probe "$qcocal" >/dev/null 2>&1 ||
        fail qcocal-fal-access

    qcocal_listing=
    if ! qcocal_listing=$(DNACCESS_USER="$vax_user" DNACCESS_PASSWORD="$vax_password" \
        /usr/local/bin/dncopy --dir "$qcocal" '*.*;*' 2>/dev/null); then
        fail qcocal-http-preflight
    fi
    if printf '%s\n' "$qcocal_listing" | grep -Eiq 'DNIV(HT|TK)\.COM'; then
        unset qcocal_listing
        fail qcocal-object-existing
    fi
    unset qcocal_listing
    DNACCESS_USER="$vax_user" DNACCESS_PASSWORD="$vax_password" \
        /usr/local/bin/dncopy --put-text /run/dniv-area31/DNIVHT.COM "$qcocal" DNIVHT.COM \
        >/dev/null 2>&1 || fail qcocal-http-install
    http_out=/tmp/dniv-qcocal-http.out
    http_err=/tmp/dniv-qcocal-http.err
    if ! DNACCESS_USER="$vax_user" DNACCESS_PASSWORD="$vax_password" \
        /usr/local/bin/dnlynx -i -o DNIVHT "$qcocal" / >"$http_out" 2>"$http_err"; then
        sed -n '1p' "$http_err" >&2 || true
        sed -n '1{s/\r$//;/^HTTP\/1\.[01] [0-9][0-9][0-9] /p;}' "$http_out" >&2 || true
        DNACCESS_USER="$vax_user" DNACCESS_PASSWORD="$vax_password" \
            /usr/local/bin/dndel "$qcocal" DNIVHT.COM >/dev/null 2>&1 || true
        rm -f "$http_out" "$http_err"
        fail qcocal-http-client
    fi
    if ! grep -Fq 'QCOCAL-DECNET-HTTP-PASS' "$http_out"; then
        sed -n '1{s/\r$//;/^HTTP\/1\.[01] [0-9][0-9][0-9] /p;}' "$http_out" >&2 || true
        DNACCESS_USER="$vax_user" DNACCESS_PASSWORD="$vax_password" \
            /usr/local/bin/dndel "$qcocal" DNIVHT.COM >/dev/null 2>&1 || true
        rm -f "$http_out" "$http_err"
        fail qcocal-http-client
    fi
    rm -f "$http_out" "$http_err"
    DNACCESS_USER="$vax_user" DNACCESS_PASSWORD="$vax_password" \
        /usr/local/bin/dndel "$qcocal" DNIVHT.COM >/dev/null 2>&1 ||
        fail qcocal-http-cleanup
    echo "DNIV-AREA31-QCOCAL-HTTP-PASS"

    DNACCESS_USER="$vax_user" DNACCESS_PASSWORD="$vax_password" \
        /usr/local/bin/dncopy --put-text /run/dniv-area31/DNIVTK.COM "$qcocal" DNIVTK.COM \
        >/dev/null 2>&1 || fail qcocal-task-install
    if ! DNACCESS_USER="$vax_user" DNACCESS_PASSWORD="$vax_password" \
        /usr/local/bin/dntask "$qcocal::DNIVTK" 2>/dev/null | \
        grep -Fq 'QCOCAL-DECNET-TASK-PASS'; then
        DNACCESS_USER="$vax_user" DNACCESS_PASSWORD="$vax_password" \
            /usr/local/bin/dndel "$qcocal" DNIVTK.COM >/dev/null 2>&1 || true
        fail qcocal-task-client
    fi
    DNACCESS_USER="$vax_user" DNACCESS_PASSWORD="$vax_password" \
        /usr/local/bin/dndel "$qcocal" DNIVTK.COM >/dev/null 2>&1 ||
        fail qcocal-task-cleanup
    echo "DNIV-AREA31-QCOCAL-TASK-PASS"
fi

survey_live=0
survey_nice=0
survey_mirror=0
tab=$(printf '\t')
while IFS="$tab" read -r survey_node survey_name survey_state; do
    [ -n "$survey_node" ] || continue
    parse_node "$survey_node" || fail survey-bad-node
    [ "$survey_state" != "Unreachable" ] || continue
    [ "$survey_node" != "$linux_node" ] || continue
    [ "$survey_node" != "$gateway_node" ] || continue
    survey_live=$((survey_live + 1))
    nice_result=unavailable
    mirror_result=skipped
    if timeout 6 /usr/local/sbin/dniv-area31-native --nice-summary "$survey_node"         >/dev/null 2>/dev/null; then
        nice_result=pass
        survey_nice=$((survey_nice + 1))
        if timeout 6 /usr/local/sbin/dniv-area31-native --mirror-once "$survey_node"             >/dev/null 2>/dev/null; then
            mirror_result=pass
            survey_mirror=$((survey_mirror + 1))
        else
            rc=$?
            if [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ]; then
                mirror_result=timeout
            else
                mirror_result=unavailable
            fi
        fi
    else
        rc=$?
        if [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ]; then
            nice_result=timeout
        fi
    fi
    echo "DNIV-AREA31-SURVEY node=$survey_node name=$survey_name state=$survey_state nice=$nice_result mirror=$mirror_result"
done <"$survey_manifest"
[ "$survey_live" -gt 0 ] || fail survey-empty
[ "$survey_nice" -gt 0 ] || fail survey-no-nice
echo "DNIV-AREA31-SURVEY-PASS live=$survey_live nice=$survey_nice mirror=$survey_mirror"

unset vax_user vax_password
echo "DNIV-AREA31-NATIVE-PASS"
sync
poweroff -f || true

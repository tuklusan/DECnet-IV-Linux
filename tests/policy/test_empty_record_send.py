#!/usr/bin/env python3
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

"""Exercise exact native socket sendmsg against the empty MSG_EOR record."""
import os
import shlex
import subprocess
import tempfile
from pathlib import Path
from test_zero_send_connected import C_PREFIX, SOCKET_SOURCE

MOCK_ORIGINAL = 'static int dniv_nsp_send_data(int link,const void *data,__u16 n,__u8 bom,__u8 eom){(void)link;(void)data;(void)n;(void)bom;(void)eom;return 0;}'
MOCK_OBSERVED = '''static int data_calls;
static int enqueue_error;
static unsigned data_length, data_bom, data_eom;
static int dniv_nsp_send_data(int link,const void *data,__u16 n,__u8 bom,__u8 eom){
 (void)link;
 if(!data)return -EINVAL;
 if(enqueue_error)return enqueue_error;
 data_calls++;
 data_length=n;
 data_bom=bom;
 data_eom=eom;
 return 0;
}'''
C_CASES = r'''
int main(void) {
    struct dniv_sock dsk={0};
    struct socket sock={.sk=&dsk.sk,.type=SOCK_SEQPACKET,.state=SS_CONNECTED};
    struct msghdr msg={0};
    int rc;
    dsk.local_link=91;
    msg.msg_flags=MSG_EOR;
    rc=dniv_sock_sendmsg(&sock,&msg,0);
    if(rc || data_calls!=1 || data_length!=0 || data_bom!=1 || data_eom!=1)
        return 1;
    dsk.tx_record_open=true;
    dsk.tx_record_len=6;
    rc=dniv_sock_sendmsg(&sock,&msg,0);
    if(rc || data_calls!=2 || data_bom!=0 || data_eom!=1 ||
       dsk.tx_record_open || dsk.tx_record_len)
        return 2;
    dsk.tx_record_open=true;
    dsk.tx_record_len=7;
    msg.msg_flags=0;
    rc=dniv_sock_sendmsg(&sock,&msg,0);
    if(rc || data_calls!=2 || !dsk.tx_record_open || dsk.tx_record_len!=7)
        return 3;
    dsk.tx_record_open=true;
    dsk.tx_record_len=7;
    enqueue_error=-EAGAIN;
    msg.msg_flags=MSG_EOR | MSG_DONTWAIT;
    rc=dniv_sock_sendmsg(&sock,&msg,0);
    if(rc!=-EAGAIN || data_calls!=2 || !dsk.tx_record_open ||
       dsk.tx_record_len!=7)
        return 6;
    enqueue_error=0;
    sock.type=SOCK_STREAM;
    msg.msg_flags=MSG_EOR;
    if(dniv_sock_sendmsg(&sock,&msg,0)!=-EINVAL || data_calls!=2)
        return 4;
    sock.type=SOCK_SEQPACKET;
    sock.state=0;
    if(dniv_sock_sendmsg(&sock,&msg,0)!=-ENOTCONN || data_calls!=2)
        return 5;
    puts("empty record send and MSG_EOR completion passed");
    return 0;
}
'''

def main():
    source = SOCKET_SOURCE.read_text(encoding='utf-8')
    beginning = source.index('static int dniv_sock_sendmsg(')
    opening = source.index('{', beginning)
    depth = 1
    end = opening + 1
    while depth:
        if source[end] == '{': depth += 1
        elif source[end] == '}': depth -= 1
        end += 1
    actual = source[beginning:end]
    prefix = C_PREFIX.replace(MOCK_ORIGINAL, MOCK_OBSERVED)
    if prefix == C_PREFIX: raise SystemExit('fixture no longer matches source')
    with tempfile.TemporaryDirectory(prefix='dniv-empty-eor-') as directory:
        file = Path(directory) / 'test.c'
        exe = Path(directory) / 'test'
        file.write_text(prefix + actual + C_CASES, encoding='utf-8')
        subprocess.run(shlex.split(os.environ.get('CC','cc')) +
                       ['-std=gnu11','-Wall','-Wextra','-Werror','-O2',
                        str(file),'-o',str(exe)],check=True,timeout=60)
        subprocess.run([str(exe)],check=True,timeout=20)
    nsp = (SOCKET_SOURCE.parent/'decnet_iv_nsp.c').read_text(encoding='utf-8')
    nsp_send = nsp.split('int dniv_nsp_send_data(',1)[1].split('\nint ',1)[0]
    if 'if (!payload || !payload_len)' in nsp_send or 'if (!payload)' not in nsp_send:
        raise SystemExit('NSP send_data still rejects zero length')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

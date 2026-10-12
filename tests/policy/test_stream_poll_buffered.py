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

"""Compiled source-derived stream poll regression for buffered partial reads."""
import os
import shlex
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOCKET = ROOT / 'kernel/decnet/decnet_iv_socket.c'

PREFIX = r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stdint.h>
#include <sys/socket.h>
#include <sys/epoll.h>
#include <poll.h>
#include <unistd.h>
#define READ_ONCE(x) (x)
#define DNIV_NSP_ST_RUN 3
#define DNIV_NSP_ST_DI 4
#define DNIV_NSP_ST_CLOSED 5
#define DNIV_NSP_REASON_NODE_UNREACHABLE 39
#define DNIV_NSP_MAX_WINDOW 16
#define DNIV_NSP_MAX_RETRANSMIT 16
#define __poll_t unsigned int
struct sock { int dummy; };
struct dniv_sock {
 struct sock sk;
 int listening;
 unsigned int pending_count;
 int local_link;
 unsigned int stream_rx_len,stream_rx_off;
};
struct socket { struct sock* sk; int type; };
struct file { int dummy; };
typedef int poll_table;
static int dniv_sock_waitq;
struct dniv_nsp_conn_snapshot {
 int state;
 int shutdown_pending;
 int data_xon,data_retransmit_count,retransmit_count;
 int disconnect_reason;
};
static struct dniv_nsp_conn_snapshot scenario;
static int normal_ready,interrupt_ready;
static struct dniv_sock *dniv_sk(struct sock*s) { return (struct dniv_sock*)s; }
static void poll_wait(struct file*f,void*q,poll_table*t) {(void)f;(void)q;(void)t;}
static int dniv_nsp_conn_snapshot(int link,struct dniv_nsp_conn_snapshot*out){
 (void)link;*out=scenario;return 0;
}
static int dniv_nsp_data_send_allowed(int a,int b,int c,int d,int e) {
 (void)a;(void)b;(void)c;(void)d;(void)e;return 0;
}
static int dniv_nsp_rx_ready(int link,bool*normal,bool*intr) {
 (void)link;*normal=normal_ready;*intr=interrupt_ready;return 0;
}
'''
SUFFIX = r'''
int main(void) {
 struct dniv_sock dsk={0};
 struct socket sock={.sk=&dsk.sk,.type=SOCK_STREAM};
 unsigned int mask;
 int fd[2]; char data[4]="ABC",one;
 struct pollfd pfd;
 dsk.local_link=10;
 dsk.stream_rx_off=1;
 dsk.stream_rx_len=4;
 scenario.state=DNIV_NSP_ST_RUN;
 mask=dniv_sock_poll(NULL,&sock,NULL);
 if(!(mask & EPOLLIN) || !(mask & EPOLLRDNORM))return 1;
 scenario.state=DNIV_NSP_ST_DI;
 mask=dniv_sock_poll(NULL,&sock,NULL);
 if(!(mask & EPOLLIN) || !(mask & EPOLLHUP))return 2;
 scenario.state=DNIV_NSP_ST_CLOSED;
 mask=dniv_sock_poll(NULL,&sock,NULL);
 if(!(mask & EPOLLIN) || !(mask & EPOLLHUP))return 3;
 dsk.stream_rx_off=4;
 mask=dniv_sock_poll(NULL,&sock,NULL);
 if(mask & EPOLLIN)return 4;
 scenario.state=DNIV_NSP_ST_RUN;
 dsk.stream_rx_off=1;
 sock.type=SOCK_SEQPACKET;
 mask=dniv_sock_poll(NULL,&sock,NULL);
 if(mask & EPOLLIN)return 5;
 sock.type=SOCK_STREAM;
 dsk.stream_rx_off=4;
 normal_ready=1;interrupt_ready=1;
 mask=dniv_sock_poll(NULL,&sock,NULL);
 if(!(mask & EPOLLIN) || !(mask & EPOLLPRI))return 6;
 if(socketpair(AF_UNIX,SOCK_STREAM,0,fd))return 7;
 if(send(fd[0],data,3,0)!=3)return 8;
 if(recv(fd[1],&one,1,0)!=1)return 9;
 pfd.fd=fd[1];pfd.events=POLLIN;pfd.revents=0;
 if(poll(&pfd,1,0)!=1 || !(pfd.revents&POLLIN))return 10;
 close(fd[0]);close(fd[1]);
 puts("stream poll reports buffered partial reads");
 return 0;
}
'''

def main() -> int:
    source = SOCKET.read_text(encoding='utf-8')
    begin = source.index('static __poll_t dniv_sock_poll(')
    opening = source.index('{', begin)
    depth = 1
    end = opening + 1
    while depth:
        if source[end] == '{': depth += 1
        elif source[end] == '}': depth -= 1
        end += 1
    actual = source[begin:end]
    with tempfile.TemporaryDirectory(prefix='dniv-poll-buffered-') as tmp:
        filename = Path(tmp)/'case.c'
        exe = Path(tmp)/'case'
        filename.write_text(PREFIX+actual+SUFFIX,encoding='utf-8')
        subprocess.run(shlex.split(os.environ.get('CC','cc'))+['-std=gnu11','-O2',
                       '-Wall','-Wextra','-Werror',str(filename),'-o',str(exe)],
                       check=True,timeout=60)
        subprocess.run([str(exe)],check=True,timeout=20)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

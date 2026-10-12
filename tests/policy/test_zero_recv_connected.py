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

"""Check zero-byte receives do not report success on unconnected DECnet sockets."""

import os
import shlex
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOCKET_SOURCE = ROOT / "kernel/decnet/decnet_iv_socket.c"

C_PREFIX = '\n#include <errno.h>\n#include <stdbool.h>\n#include <stdint.h>\n#include <stdio.h>\n#include <stdlib.h>\n#include <stddef.h>\n#include <string.h>\n#include <sys/socket.h>\n#include <unistd.h>\n#define __u8 uint8_t\n#define __u16 uint16_t\n#define __u32 uint32_t\n#define DNIV_NSP_MAX_INTERRUPT 1024\n#define DNBUFSIZE 65535\n#define SS_CONNECTED 2\n#define GFP_KERNEL 0\n#define msg_iter msg_iov\n#define min_t(type,a,b) ((type)(a)<(type)(b)?(type)(a):(type)(b))\n#define wait_event_interruptible_timeout(w,pred,limit) ((long)0)\nstruct sock {int locked;};\nstruct dniv_sock {struct sock sk;int local_link;char peer[24];};\nstruct socket {struct sock *sk;int type;int state;};\nstatic struct dniv_sock *dniv_sk(struct sock *s){return (struct dniv_sock*)s;}\nstatic void lock_sock(struct sock *s){s->locked++;}\nstatic void release_sock(struct sock *s){s->locked--;}\nstatic int link_status=1;\nstatic int dniv_link_status(struct dniv_sock *s){(void)s;return link_status;}\nstatic void *kmalloc(size_t s,int f){(void)f;return malloc(s);}\nstatic void kfree(void *p){free(p);}\nstatic long sock_rcvtimeo(struct sock *s,int nonblock){(void)s;(void)nonblock;return 0;}\nstatic int dniv_stream_recv_locked(struct socket *s,struct msghdr *m,size_t n,int f,long *t) {\n (void)s;(void)m;(void)n;(void)f;(void)t;return -EAGAIN;\n}\nstatic int dniv_nsp_recv_message(int a,void *p,__u32 cap,__u32 *n){(void)a;(void)p;(void)cap;(void)n;return -EAGAIN;}\nstatic int dniv_nsp_recv_interrupt(int a,void *p,__u16 cap,__u16 *n){(void)a;(void)p;(void)cap;(void)n;return -EAGAIN;}\nstatic int __attribute__((unused)) dniv_nsp_rx_ready(int a,bool *normal,bool *intr){(void)a;(void)normal;(void)intr;return 0;}\nstatic size_t copy_to_iter(const void *p,size_t n,void *i){(void)p;(void)n;(void)i;return 0;}\n'
C_SUFFIX = '\nint main(void){\n struct dniv_sock dsk={0};\n struct socket sock={.sk=&dsk.sk,.type=SOCK_SEQPACKET,.state=0};\n struct msghdr msg={0};\n int rc,fd;\n rc=dniv_sock_recvmsg(&sock,&msg,0,MSG_DONTWAIT);\n printf("unconnected seqpacket recv0=%d expected=%d\\n",rc,-ENOTCONN);\n if(rc!=-ENOTCONN)return 1;\n sock.state=SS_CONNECTED;\n rc=dniv_sock_recvmsg(&sock,&msg,0,MSG_DONTWAIT);\n if(rc!=0)return 2;\n rc=dniv_sock_recvmsg(&sock,&msg,0,MSG_TRUNC|MSG_DONTWAIT);\n if(rc!=-EAGAIN)return 3;\n sock.state=0;\n sock.type=SOCK_STREAM;\n rc=dniv_sock_recvmsg(&sock,&msg,0,MSG_DONTWAIT);\n if(rc!=-ENOTCONN)return 4;\n fd=socket(AF_UNIX,SOCK_SEQPACKET,0);\n if(fd<0)return 5;\n char zero=0;\n errno=0;\n ssize_t got=recv(fd,&zero,0,MSG_DONTWAIT);\n if(got!=-1 || errno!=ENOTCONN)return 6;\n close(fd);\n puts("zero-length recv validates connection state");\n return 0;\n}\n'

def main() -> int:
    text = SOCKET_SOURCE.read_text(encoding="utf-8")
    start = text.index("static int dniv_sock_recvmsg(")
    opening = text.index("{", start)
    depth = 1
    ending = opening + 1
    while depth:
        if ending >= len(text):
            raise SystemExit("socket receive function has unbalanced braces")
        if text[ending] == "{":
            depth += 1
        elif text[ending] == "}":
            depth -= 1
        ending += 1
    actual_function = text[start:ending]
    with tempfile.TemporaryDirectory(prefix="dniv-zero-recv-") as directory:
        work = Path(directory)
        source = work / "check.c"
        source.write_text(C_PREFIX + actual_function + C_SUFFIX,
                          encoding="utf-8")
        exe = work / "check"
        subprocess.run(shlex.split(os.environ.get("CC", "cc")) + [
            "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror",
            str(source), "-o", str(exe)], check=True, timeout=60)
        subprocess.run([str(exe)], check=True, timeout=20)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

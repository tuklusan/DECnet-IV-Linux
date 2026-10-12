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

"""Exercise the actual socket sendmsg function on zero-length input and terminal links."""

import os
import shlex
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOCKET_SOURCE = ROOT / "kernel/decnet/decnet_iv_socket.c"

C_PREFIX = '\n#include <stdlib.h>\n#include <stddef.h>\n#include <stdio.h>\n#include <stdint.h>\n#include <errno.h>\n#include <stdbool.h>\n#include <sys/socket.h>\n#include <unistd.h>\n#define __u8 uint8_t\n#define __u16 uint16_t\n#define GFP_KERNEL 0\n#define DNIV_NSP_MAX_INTERRUPT 1024\n#define DNBUFSIZE 65535\n#define SS_CONNECTED 2\n#define min_t(type,a,b) ((type)(a)<(type)(b)?(type)(a):(type)(b))\n#define wait_event_interruptible_timeout(w,condition,timeo) ((long)0)\nstruct sock { int locked; };\nstruct dniv_sock {\n struct sock sk;\n int local_link;\n size_t tx_record_len;\n bool tx_record_open;\n};\nstruct socket {struct sock *sk;int type;int state;};\n#define msg_iter msg_iov\nstruct dniv_nsp_conn_snapshot {unsigned short segment_size;};\nstatic int link_status=1;\nstatic struct dniv_sock *dniv_sk(struct sock *sk){return (struct dniv_sock*)sk;}\nstatic void *kmalloc(size_t s,int flags){(void)flags;return malloc(s);}\nstatic void kfree(void *p){free(p);}\nstatic int copy_from_iter_full(void *dst,size_t n,void *iter){(void)dst;(void)n;(void)iter;return 1;}\nstatic void lock_sock(struct sock *sk){sk->locked++;}\nstatic void release_sock(struct sock *sk){sk->locked--;}\nstatic int dniv_link_status(struct dniv_sock *sk){(void)sk;return link_status;}\nstatic long sock_sndtimeo(struct sock *sk,int nb){(void)sk;(void)nb;return 0;}\nstatic int dniv_nsp_send_interrupt(int link,const void *data,__u16 n){(void)link;(void)data;(void)n;return 0;}\nstatic int dniv_nsp_send_data(int link,const void *data,__u16 n,__u8 bom,__u8 eom){(void)link;(void)data;(void)n;(void)bom;(void)eom;return 0;}\nstatic int dniv_nsp_conn_snapshot(int l,struct dniv_nsp_conn_snapshot *snap){(void)l;snap->segment_size=512;return 0;}\n'
C_SUFFIX = '\nint main(void){\n struct dniv_sock dsk={0};\n struct socket sock={.sk=&dsk.sk,.type=SOCK_STREAM,.state=0};\n struct msghdr msg={0};\n int rc;\n int fd;\n link_status=1;\n rc=dniv_sock_sendmsg(&sock,&msg,0);\n printf("unconnected empty send=%d (expected -%d)\\n",rc,ENOTCONN);\n if(rc!=-ENOTCONN)return 1;\n sock.state=SS_CONNECTED;\n link_status=1;\n rc=dniv_sock_sendmsg(&sock,&msg,0);\n if(rc!=0)return 2;\n link_status=-EHOSTUNREACH;\n rc=dniv_sock_sendmsg(&sock,&msg,0);\n if(rc!=-EHOSTUNREACH)return 3;\n sock.state=0;\n link_status=1;\n msg.msg_flags=MSG_OOB;\n if(dniv_sock_sendmsg(&sock,&msg,0)!=-EINVAL)return 4;\n sock.type=SOCK_SEQPACKET;\n msg.msg_flags=0;\n if(dniv_sock_sendmsg(&sock,&msg,0)!=-ENOTCONN)return 5;\n fd=socket(AF_UNIX,SOCK_SEQPACKET,0);\n if(fd<0)return 6;\n errno=0;\n rc=(int)send(fd,"",0,0);\n if(rc!=-1||errno!=ENOTCONN)return 7;\n close(fd);\n printf("source-extracted empty send socket lifecycle passed\\n");\n return 0;\n}\n'

def main() -> int:
    source = SOCKET_SOURCE.read_text(encoding="utf-8")
    start = source.index("static int dniv_sock_sendmsg(")
    opening = source.index("{", start)
    depth = 1
    ending = opening + 1
    while depth:
        if ending >= len(source):
            raise SystemExit("socket sendmsg source has unbalanced braces")
        if source[ending] == "{":
            depth += 1
        elif source[ending] == "}":
            depth -= 1
        ending += 1
    actual_function = source[start:ending]
    if "dniv_link_status(dsk)" not in actual_function:
        raise SystemExit("socket sendmsg link-state check missing")
    with tempfile.TemporaryDirectory(prefix="dniv-zero-send-") as directory:
        work = Path(directory)
        program = work / "check.c"
        program.write_text(C_PREFIX + actual_function + C_SUFFIX,
                           encoding="utf-8")
        exe = work / "check"
        subprocess.run(shlex.split(os.environ.get("CC", "cc")) + [
            "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror",
            str(program), "-o", str(exe)], check=True, timeout=60)
        subprocess.run([str(exe)], check=True, timeout=20)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

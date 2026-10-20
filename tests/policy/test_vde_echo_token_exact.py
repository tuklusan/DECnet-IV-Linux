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

"""Actually compile VDE echo program, forbid any VDE socket, reject token aliases."""

import subprocess
import tempfile
from pathlib import Path

source = Path(__file__).resolve().parents[1] / 'lab/vde-frame-echo.c'
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    (root / 'libvdeplug.h').write_text('''#ifndef VDE_STUB_H
#define VDE_STUB_H
#include <sys/types.h>
typedef struct VDECONN VDECONN;
VDECONN *vde_open(char *, char *, void *);
int vde_datafd(VDECONN *);
ssize_t vde_send(VDECONN *, const void *, size_t, int);
ssize_t vde_recv(VDECONN *, void *, size_t, int);
void vde_close(VDECONN *);
#endif
'''.replace('#include <sys/types.h>', '#include <sys/types.h>\n#include <stddef.h>'))
    (root / 'stub.c').write_text('''#include "libvdeplug.h"
#include <errno.h>
VDECONN *vde_open(char *a,char *b,void *c) {
    (void)a; (void)b; (void)c; errno=EACCES; return 0;
}
int vde_datafd(VDECONN *c) {(void)c;return -1;}
ssize_t vde_send(VDECONN *c,const void *b,size_t n,int f){(void)c;(void)b;(void)n;(void)f;return -1;}
ssize_t vde_recv(VDECONN *c,void *b,size_t n,int f){(void)c;(void)b;(void)n;(void)f;return -1;}
void vde_close(VDECONN *c){(void)c;}
''')
    binary = root / 'vde-frame-echo'
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I',str(root),str(source),str(root/'stub.c'),'-o',str(binary)],check=True)
    for token, expected in [ ('0',1),('1',1),('255',1),('0001',1),
        ('-18446744073709551615',2),('-1',2),('+1',2),(' 1',2),('1x',2),
        ('256',2),('18446744073709551617',2) ]:
        run = subprocess.run([str(binary),'client','vde://never-connect',token],capture_output=True,text=True,timeout=3)
        assert run.returncode==expected, (token,expected,run.returncode,run.stderr)
print('VDE echo token exact unsigned parser regression passed without VDE/network')

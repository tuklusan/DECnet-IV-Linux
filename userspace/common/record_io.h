// ============================================================================
/* DECnet-IV-Linux bounded sequenced-packet receive helper. */
#ifndef DNIV_RECORD_IO_H
#define DNIV_RECORD_IO_H

#include <errno.h>
#include <stddef.h>
#include <sys/socket.h>
#include <sys/types.h>

static inline ssize_t dniv_recv_record(int fd, void *buf, size_t cap, int flags)
{
    ssize_t got;

    got = recv(fd, buf, cap, flags | MSG_TRUNC);
    if (got < 0)
        return got;
    if ((size_t)got > cap) {
        errno = EMSGSIZE;
        return -1;
    }
    return got;
}

#endif

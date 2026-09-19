// ============================================================================
// Copyright (c) 2026 Supratim Sanyal of SANYALnet Labs.
// Proprietary rights reserved except as expressly licensed herein.
//
// DECnet-IV-Linux
// This file is governed by the SANYALnet Labs Non-Commercial License in the
// root LICENSE file. Non-Commercial use is permitted; Commercial Use and use
// for AI/ML model training are prohibited unless separately authorized.
//
// Attribution is required: "Based on original work by Supratim Sanyal of
// SANYALnet Labs." See LICENSE for full terms, warranty disclaimer, termination,
// patent, trademark, and governing-law provisions.
// ============================================================================

#include <linux/errno.h>
#include <linux/fs.h>
#include <linux/kernel.h>
#include <linux/list.h>
#include <linux/module.h>
#include <linux/net.h>
#include <linux/poll.h>
#include <linux/slab.h>
#include <linux/socket.h>
#include <linux/spinlock.h>
#include <linux/uio.h>
#include <linux/version.h>
#include <linux/wait.h>
#include <net/net_namespace.h>
#include <net/sock.h>

#include <linux/dn.h>
#include <decnet_iv_wire.h>
#include "decnet_iv_ethernet.h"
#include "decnet_iv_nsp.h"
#include "decnet_iv_socket.h"

#define DNIV_SOCK_MAX_BACKLOG 64U

#define DNIV_SC_MENU_ACCESS 0x01U
#define DNIV_SC_MENU_USER   0x02U

#define DNIV_REASON_INVALID_DESTINATION 4U
#define DNIV_REASON_OBJECT_BUSY         6U
#define DNIV_REASON_IMAGE_OVERFLOW      43U

struct dniv_sock {
    struct sock sk;
    struct sockaddr_dn local;
    struct sockaddr_dn peer;
    struct list_head listener_link;
    __u16 pending[DNIV_SOCK_MAX_BACKLOG];
    __u16 local_link;
    __u16 pending_head;
    __u16 pending_tail;
    __u16 pending_count;
    bool bound;
    bool listening;
};

static DECLARE_WAIT_QUEUE_HEAD(dniv_sock_waitq);
static DEFINE_SPINLOCK(dniv_listener_lock);
static LIST_HEAD(dniv_listeners);

static const struct proto_ops dniv_proto_ops;
static struct proto dniv_proto;

static inline struct dniv_sock *dniv_sk(struct sock *sk)
{
    return container_of(sk, struct dniv_sock, sk);
}

static int dniv_enduser_decode(const __u8 *buf, __u16 length,
                               bool destination, struct sockaddr_dn *addr,
                               __u16 *used)
{
    __u16 prefix;
    __u16 namelen;
    __u8 format;

    if (!buf || !addr || !used || length < 2U)
        return -EPROTO;

    memset(addr, 0, sizeof(*addr));
    addr->sdn_family = AF_DECnet;
    format = buf[0];

    if (format == 0U) {
        if (!buf[1])
            return -EPROTO;
        addr->sdn_objnum = buf[1];
        *used = 2U;
        return 0;
    }

    if (destination && format != 1U)
        return -EPROTO;

    switch (format) {
    case 1U:
        prefix = 2U;
        break;
    case 2U:
        prefix = 6U;
        break;
    case 4U:
        prefix = 10U;
        break;
    default:
        return -EPROTO;
    }

    if (length <= prefix)
        return -EPROTO;
    namelen = buf[prefix];
    if (!namelen || namelen > DN_MAXOBJL ||
        length < prefix + 1U + namelen)
        return -EPROTO;
    if (format != 1U && namelen > 12U)
        return -EPROTO;

    addr->sdn_objnamel = cpu_to_le16(namelen);
    memcpy(addr->sdn_objname, buf + prefix + 1U, namelen);
    *used = (__u16)(prefix + 1U + namelen);
    return 0;
}

static int dniv_counted_field_validate(const __u8 *buf, __u16 length,
                                       __u16 maximum, __u16 *used)
{
    __u16 field_len;

    if (!buf || !used || !length)
        return -EPROTO;
    field_len = buf[0];
    if (field_len > maximum || length < field_len + 1U)
        return -EPROTO;
    *used = (__u16)(field_len + 1U);
    return 0;
}

static int dniv_ci_decode(const __u8 *payload, __u16 payload_len,
                          struct sockaddr_dn *target,
                          struct sockaddr_dn *source)
{
    __u16 off = 0U;
    __u16 used;
    __u8 menu;
    unsigned int i;
    int ret;

    ret = dniv_enduser_decode(payload, payload_len, true, target, &used);
    if (ret)
        return ret;
    off += used;

    ret = dniv_enduser_decode(payload + off, payload_len - off, false,
                              source, &used);
    if (ret)
        return ret;
    off += used;
    if (off >= payload_len)
        return -EPROTO;

    menu = payload[off++];
    if (menu & DNIV_SC_MENU_ACCESS) {
        for (i = 0; i < 3U; i++) {
            ret = dniv_counted_field_validate(
                payload + off, payload_len - off, DN_MAXACCL, &used);
            if (ret)
                return ret;
            off += used;
        }
    }
    if (menu & DNIV_SC_MENU_USER) {
        ret = dniv_counted_field_validate(
            payload + off, payload_len - off, DN_MAXOPTL, &used);
        if (ret)
            return ret;
    }
    return 0;
}

static bool dniv_selector_match(const struct sockaddr_dn *listener,
                                const struct sockaddr_dn *target)
{
    __u16 llen;
    __u16 tlen;

    if (listener->sdn_objnum || target->sdn_objnum)
        return listener->sdn_objnum &&
               listener->sdn_objnum == target->sdn_objnum;

    llen = le16_to_cpu(listener->sdn_objnamel);
    tlen = le16_to_cpu(target->sdn_objnamel);
    return llen && llen == tlen &&
           !memcmp(listener->sdn_objname, target->sdn_objname, llen);
}

static bool dniv_listener_contains_locked(const struct dniv_sock *dsk,
                                          __u16 local_link)
{
    __u16 i;

    for (i = 0U; i < dsk->pending_count; i++) {
        __u16 slot = (__u16)((dsk->pending_head + i) %
                             DNIV_SOCK_MAX_BACKLOG);

        if (dsk->pending[slot] == local_link)
            return true;
    }
    return false;
}

static void dniv_sock_notify(__u16 local_link)
{
    struct dniv_nsp_ci_snapshot ci;
    struct sockaddr_dn target;
    struct sockaddr_dn source;
    struct dniv_sock *listener;
    __u8 payload[DNIV_NSP_MAX_CI_PAYLOAD];
    unsigned long flags;
    __u16 reject_reason = 0U;
    bool handled = false;

    if (local_link &&
        !dniv_nsp_ci_snapshot(local_link, &ci, payload, sizeof(payload))) {
        if (dniv_ci_decode(payload, ci.payload_len, &target, &source)) {
            reject_reason = DNIV_REASON_IMAGE_OVERFLOW;
        } else {
            spin_lock_irqsave(&dniv_listener_lock, flags);
            list_for_each_entry(listener, &dniv_listeners, listener_link) {
                unsigned int backlog;

                if (!listener->listening ||
                    !dniv_selector_match(&listener->local, &target))
                    continue;
                handled = true;
                if (dniv_listener_contains_locked(listener, local_link))
                    break;
                backlog = min_t(unsigned int,
                                listener->sk.sk_max_ack_backlog,
                                DNIV_SOCK_MAX_BACKLOG);
                if (!backlog || listener->pending_count >= backlog) {
                    reject_reason = DNIV_REASON_OBJECT_BUSY;
                    break;
                }
                listener->pending[listener->pending_tail] = local_link;
                listener->pending_tail =
                    (__u16)((listener->pending_tail + 1U) %
                            DNIV_SOCK_MAX_BACKLOG);
                listener->pending_count++;
                listener->sk.sk_ack_backlog = listener->pending_count;
                break;
            }
            spin_unlock_irqrestore(&dniv_listener_lock, flags);
            if (!handled)
                reject_reason = DNIV_REASON_INVALID_DESTINATION;
        }

        if (reject_reason)
            dniv_nsp_reject(local_link, reject_reason, NULL, 0U);
    }
    wake_up_interruptible_all(&dniv_sock_waitq);
}

static __u16 dniv_sockaddr_node(const struct sockaddr_dn *addr)
{
    return (__u16)((__u16)addr->sdn_nodeaddr[0] |
                   ((__u16)addr->sdn_nodeaddr[1] << 8));
}

static void dniv_sockaddr_set_node(struct sockaddr_dn *addr, __u16 node)
{
    addr->sdn_nodeaddrl = cpu_to_le16(2U);
    addr->sdn_nodeaddr[0] = (__u8)(node & 0xffU);
    addr->sdn_nodeaddr[1] = (__u8)(node >> 8);
}

static int dniv_sockaddr_validate(const struct sockaddr_dn *addr,
                                  bool remote)
{
    __u16 namelen;
    __u16 addrl;

    if (!addr || addr->sdn_family != AF_DECnet)
        return -EINVAL;
    namelen = le16_to_cpu(addr->sdn_objnamel);
    addrl = le16_to_cpu(addr->sdn_nodeaddrl);
    if (namelen > DN_MAXOBJL || (addrl != 0U && addrl != 2U))
        return -EINVAL;
    if (addr->sdn_flags)
        return -EOPNOTSUPP;
    if (addr->sdn_objnum && namelen)
        return -EINVAL;
    if (addrl == 2U && !dniv_wire_address_valid(dniv_sockaddr_node(addr)))
        return -EINVAL;
    if (remote) {
        if (addrl != 2U)
            return -EINVAL;
        if (!addr->sdn_objnum && !namelen)
            return -EINVAL;
    } else if (addrl == 2U &&
               dniv_sockaddr_node(addr) != dniv_eth_get_address()) {
        return -EADDRNOTAVAIL;
    }
    return 0;
}

static int dniv_enduser_encode(const struct sockaddr_dn *addr, __u8 *buf,
                               size_t capacity, size_t *used)
{
    __u16 namelen = le16_to_cpu(addr->sdn_objnamel);

    if (addr->sdn_objnum) {
        if (capacity < 2U)
            return -EMSGSIZE;
        buf[0] = 0U;
        buf[1] = addr->sdn_objnum;
        *used = 2U;
        return 0;
    }
    if (!namelen || namelen > DN_MAXOBJL || capacity < 3U + namelen)
        return -EINVAL;
    buf[0] = 1U;
    buf[1] = 0U;
    buf[2] = (__u8)namelen;
    memcpy(buf + 3U, addr->sdn_objname, namelen);
    *used = 3U + namelen;
    return 0;
}

static int dniv_connect_payload(const struct dniv_sock *dsk,
                                const struct sockaddr_dn *peer,
                                __u8 *buf, size_t capacity, __u16 *length)
{
    static const __u8 generic[] = { 1U, 0U, 5U, 'L', 'I', 'N', 'U', 'X' };
    size_t off = 0U;
    size_t used;
    int ret;

    ret = dniv_enduser_encode(peer, buf, capacity, &used);
    if (ret)
        return ret;
    off += used;

    if (dsk->bound && (dsk->local.sdn_objnum ||
                       le16_to_cpu(dsk->local.sdn_objnamel))) {
        ret = dniv_enduser_encode(&dsk->local, buf + off, capacity - off,
                                  &used);
        if (ret)
            return ret;
        off += used;
    } else {
        if (capacity - off < sizeof(generic))
            return -EMSGSIZE;
        memcpy(buf + off, generic, sizeof(generic));
        off += sizeof(generic);
    }

    if (off >= capacity)
        return -EMSGSIZE;
    buf[off++] = 0U;
    *length = (__u16)off;
    return 0;
}

static int dniv_link_status(struct dniv_sock *dsk)
{
    struct dniv_nsp_conn_snapshot snapshot;
    int ret;

    if (!dsk->local_link)
        return -ENOTCONN;
    ret = dniv_nsp_conn_snapshot(dsk->local_link, &snapshot);
    if (ret)
        return -ECONNRESET;
    if (snapshot.state == DNIV_NSP_ST_RUN)
        return 1;
    if (snapshot.state == DNIV_NSP_ST_CI ||
        snapshot.state == DNIV_NSP_ST_CD ||
        snapshot.state == DNIV_NSP_ST_CC)
        return 0;
    return -ECONNREFUSED;
}

static int dniv_can_send(struct dniv_sock *dsk)
{
    struct dniv_nsp_conn_snapshot snapshot;

    if (!dsk->local_link ||
        dniv_nsp_conn_snapshot(dsk->local_link, &snapshot))
        return -ENOTCONN;
    if (snapshot.state != DNIV_NSP_ST_RUN)
        return -ENOTCONN;
    if (!snapshot.data_xon ||
        snapshot.retransmit_count >= DNIV_NSP_MAX_WINDOW)
        return 0;
    return 1;
}

static int dniv_wait_running(struct sock *sk, long *timeo)
{
    struct dniv_sock *dsk = dniv_sk(sk);
    int status;
    long ret;

    for (;;) {
        status = dniv_link_status(dsk);
        if (status > 0)
            return 0;
        if (status < 0)
            return status;
        if (!*timeo)
            return -EINPROGRESS;
        ret = wait_event_interruptible_timeout(
            dniv_sock_waitq, dniv_link_status(dsk) != 0, *timeo);
        if (ret < 0)
            return (int)ret;
        if (!ret) {
            *timeo = 0;
            return -ETIMEDOUT;
        }
        *timeo = ret;
    }
}

static void dniv_listener_unregister(struct dniv_sock *dsk)
{
    __u16 pending[DNIV_SOCK_MAX_BACKLOG];
    __u16 count = 0U;
    unsigned long flags;

    spin_lock_irqsave(&dniv_listener_lock, flags);
    if (dsk->listening) {
        list_del_init(&dsk->listener_link);
        while (dsk->pending_count && count < DNIV_SOCK_MAX_BACKLOG) {
            pending[count++] = dsk->pending[dsk->pending_head];
            dsk->pending_head =
                (__u16)((dsk->pending_head + 1U) %
                        DNIV_SOCK_MAX_BACKLOG);
            dsk->pending_count--;
        }
        dsk->pending_head = 0U;
        dsk->pending_tail = 0U;
        dsk->sk.sk_ack_backlog = 0;
        dsk->listening = false;
    }
    spin_unlock_irqrestore(&dniv_listener_lock, flags);

    while (count)
        dniv_nsp_reject(pending[--count], DNIV_REASON_OBJECT_BUSY, NULL, 0U);
}

static int dniv_sock_release(struct socket *sock)
{
    struct sock *sk = sock->sk;

    if (sk) {
        struct dniv_sock *dsk = dniv_sk(sk);
        struct dniv_nsp_conn_snapshot snapshot;

        lock_sock(sk);
        dniv_listener_unregister(dsk);
        if (dsk->local_link) {
            if (!dniv_nsp_conn_snapshot(dsk->local_link, &snapshot) &&
                snapshot.state == DNIV_NSP_ST_RUN) {
                if (dniv_nsp_disconnect(dsk->local_link, 0U, NULL, 0U))
                    dniv_nsp_conn_release(dsk->local_link);
            } else {
                dniv_nsp_conn_release(dsk->local_link);
            }
            dsk->local_link = 0U;
        }
        sock->state = SS_DISCONNECTING;
        release_sock(sk);
        sock_orphan(sk);
        sock->sk = NULL;
        sk->sk_socket = NULL;
        sock_put(sk);
    }
    return 0;
}

static int dniv_sock_bind_impl(struct socket *sock,
                               struct sockaddr_dn *addr, int addrlen)
{
    struct sock *sk = sock->sk;
    struct dniv_sock *dsk = dniv_sk(sk);
    int ret;

    if (addrlen != sizeof(*addr))
        return -EINVAL;
    ret = dniv_sockaddr_validate(addr, false);
    if (ret)
        return ret;

    lock_sock(sk);
    if (dsk->bound || dsk->local_link)
        ret = -EINVAL;
    else {
        dsk->local = *addr;
        if (le16_to_cpu(dsk->local.sdn_nodeaddrl) == 0U)
            dniv_sockaddr_set_node(&dsk->local, dniv_eth_get_address());
        dsk->bound = true;
        ret = 0;
    }
    release_sock(sk);
    return ret;
}

#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 19, 0)
static int dniv_sock_bind(struct socket *sock, struct sockaddr_unsized *addr,
                          int addrlen)
{
    return dniv_sock_bind_impl(sock, (struct sockaddr_dn *)addr, addrlen);
}
#else
static int dniv_sock_bind(struct socket *sock, struct sockaddr *addr,
                          int addrlen)
{
    return dniv_sock_bind_impl(sock, (struct sockaddr_dn *)addr, addrlen);
}
#endif

static int dniv_sock_connect_impl(struct socket *sock,
                                  struct sockaddr_dn *addr, int addrlen,
                                  int flags)
{
    struct sock *sk = sock->sk;
    struct dniv_sock *dsk = dniv_sk(sk);
    __u8 payload[64];
    __u16 payload_len;
    __u16 link;
    long timeo;
    int status;
    int ret;

    if (addrlen != sizeof(*addr))
        return -EINVAL;
    ret = dniv_sockaddr_validate(addr, true);
    if (ret)
        return ret;

    lock_sock(sk);
    if (sock->state == SS_CONNECTED) {
        ret = -EISCONN;
        goto out;
    }
    if (dsk->local_link) {
        status = dniv_link_status(dsk);
        if (status > 0) {
            sock->state = SS_CONNECTED;
            ret = 0;
            goto out;
        }
        if (status < 0) {
            dniv_nsp_conn_release(dsk->local_link);
            dsk->local_link = 0U;
            sock->state = SS_UNCONNECTED;
            ret = status;
            goto out;
        }
    } else {
        ret = dniv_connect_payload(dsk, addr, payload, sizeof(payload),
                                   &payload_len);
        if (ret)
            goto out;
        ret = dniv_nsp_connect(dniv_sockaddr_node(addr), payload,
                               payload_len, &link);
        if (ret)
            goto out;
        dsk->local_link = link;
        dsk->peer = *addr;
        sock->state = SS_CONNECTING;
    }

    timeo = sock_sndtimeo(sk, flags & O_NONBLOCK);
    ret = dniv_wait_running(sk, &timeo);
    if (!ret)
        sock->state = SS_CONNECTED;
    else if (ret != -EINPROGRESS) {
        if (dsk->local_link)
            dniv_nsp_conn_release(dsk->local_link);
        dsk->local_link = 0U;
        sock->state = SS_UNCONNECTED;
    }
out:
    release_sock(sk);
    return ret;
}

#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 19, 0)
static int dniv_sock_connect(struct socket *sock, struct sockaddr_unsized *addr,
                             int addrlen, int flags)
{
    return dniv_sock_connect_impl(sock, (struct sockaddr_dn *)addr,
                                  addrlen, flags);
}
#else
static int dniv_sock_connect(struct socket *sock, struct sockaddr *addr,
                             int addrlen, int flags)
{
    return dniv_sock_connect_impl(sock, (struct sockaddr_dn *)addr,
                                  addrlen, flags);
}
#endif

static int dniv_sock_getname(struct socket *sock, struct sockaddr *addr,
                             int peer)
{
    struct dniv_sock *dsk = dniv_sk(sock->sk);
    struct sockaddr_dn *out = (struct sockaddr_dn *)addr;

    lock_sock(sock->sk);
    memset(out, 0, sizeof(*out));
    if (peer) {
        if (!dsk->local_link) {
            release_sock(sock->sk);
            return -ENOTCONN;
        }
        *out = dsk->peer;
    } else if (dsk->bound) {
        *out = dsk->local;
    } else {
        out->sdn_family = AF_DECnet;
        dniv_sockaddr_set_node(out, dniv_eth_get_address());
    }
    release_sock(sock->sk);
    return sizeof(*out);
}

static int dniv_sock_sendmsg(struct socket *sock, struct msghdr *msg,
                             size_t size)
{
    struct sock *sk = sock->sk;
    struct dniv_sock *dsk = dniv_sk(sk);
    __u8 *data;
    size_t off = 0U;
    long timeo;
    int ret = 0;

    if (msg->msg_name || size > DNBUFSIZE)
        return -EMSGSIZE;
    if (msg->msg_flags & ~(MSG_DONTWAIT | MSG_NOSIGNAL | MSG_EOR))
        return -EOPNOTSUPP;
    if (!size)
        return 0;

    data = kmalloc(size, GFP_KERNEL);
    if (!data)
        return -ENOMEM;
    if (!copy_from_iter_full(data, size, &msg->msg_iter)) {
        kfree(data);
        return -EFAULT;
    }

    lock_sock(sk);
    if (sock->state != SS_CONNECTED || dniv_link_status(dsk) <= 0) {
        ret = -ENOTCONN;
        goto out;
    }
    timeo = sock_sndtimeo(sk, msg->msg_flags & MSG_DONTWAIT);
    while (off < size) {
        __u16 chunk = (__u16)min_t(size_t, DNIV_NSP_MSS, size - off);
        __u8 bom = off == 0U;
        __u8 eom = off + chunk == size;

        ret = dniv_nsp_send_data(dsk->local_link, data + off, chunk,
                                 bom, eom);
        if (!ret) {
            off += chunk;
            continue;
        }
        if (ret != -EAGAIN || !timeo)
            break;
        ret = wait_event_interruptible_timeout(
            dniv_sock_waitq, dniv_can_send(dsk) != 0, timeo);
        if (ret < 0)
            break;
        if (!ret) {
            ret = -EAGAIN;
            break;
        }
        timeo = ret;
        ret = 0;
    }
out:
    release_sock(sk);
    kfree(data);
    if (off)
        return (int)off;
    return ret;
}

static int dniv_sock_recvmsg(struct socket *sock, struct msghdr *msg,
                             size_t size, int flags)
{
    struct sock *sk = sock->sk;
    struct dniv_sock *dsk = dniv_sk(sk);
    __u8 *data;
    __u32 length = 0U;
    size_t copied;
    long timeo;
    int ret;

    if (flags & ~(MSG_DONTWAIT | MSG_TRUNC | MSG_NOSIGNAL))
        return -EOPNOTSUPP;
    if (!size && !(flags & MSG_TRUNC))
        return 0;

    data = kmalloc(DNBUFSIZE, GFP_KERNEL);
    if (!data)
        return -ENOMEM;

    lock_sock(sk);
    if (sock->state != SS_CONNECTED) {
        ret = -ENOTCONN;
        goto out;
    }
    timeo = sock_rcvtimeo(sk, flags & MSG_DONTWAIT);
    for (;;) {
        ret = dniv_nsp_recv_message(dsk->local_link, data, DNBUFSIZE,
                                    &length);
        if (!ret)
            break;
        if (ret != -EAGAIN || !timeo)
            goto out;
        ret = wait_event_interruptible_timeout(
            dniv_sock_waitq,
            ({ bool normal = false, intr = false;
               int ready = dniv_nsp_rx_ready(dsk->local_link, &normal, &intr);
               ready || normal || dniv_link_status(dsk) != 1; }),
            timeo);
        if (ret < 0)
            goto out;
        if (!ret) {
            ret = -EAGAIN;
            goto out;
        }
        timeo = ret;
        if (dniv_link_status(dsk) < 0) {
            ret = 0;
            goto out;
        }
    }

    copied = min_t(size_t, size, length);
    if (copied && copy_to_iter(data, copied, &msg->msg_iter) != copied) {
        ret = -EFAULT;
        goto out;
    }
    if (copied < length)
        msg->msg_flags |= MSG_TRUNC;
    if (msg->msg_name) {
        memcpy(msg->msg_name, &dsk->peer, sizeof(dsk->peer));
        msg->msg_namelen = sizeof(dsk->peer);
    }
    ret = (flags & MSG_TRUNC) ? (int)length : (int)copied;
out:
    release_sock(sk);
    kfree(data);
    return ret;
}

static __poll_t dniv_sock_poll(struct file *file, struct socket *sock,
                               poll_table *wait)
{
    struct dniv_sock *dsk = dniv_sk(sock->sk);
    struct dniv_nsp_conn_snapshot snapshot;
    bool normal = false;
    bool intr = false;
    __poll_t mask = 0;

    poll_wait(file, &dniv_sock_waitq, wait);
    if (READ_ONCE(dsk->listening)) {
        if (READ_ONCE(dsk->pending_count))
            return EPOLLIN | EPOLLRDNORM;
        return 0;
    }
    if (!dsk->local_link)
        return 0;
    if (dniv_nsp_conn_snapshot(dsk->local_link, &snapshot))
        return EPOLLERR | EPOLLHUP;
    if (snapshot.state == DNIV_NSP_ST_RUN) {
        if (snapshot.data_xon &&
            snapshot.retransmit_count < DNIV_NSP_MAX_WINDOW)
            mask |= EPOLLOUT | EPOLLWRNORM;
        if (!dniv_nsp_rx_ready(dsk->local_link, &normal, &intr) && normal)
            mask |= EPOLLIN | EPOLLRDNORM;
        if (intr)
            mask |= EPOLLPRI;
    } else if (snapshot.state == DNIV_NSP_ST_DI ||
               snapshot.state == DNIV_NSP_ST_CLOSED) {
        mask |= EPOLLHUP;
    }
    return mask;
}

static int dniv_sock_shutdown(struct socket *sock, int how)
{
    struct dniv_sock *dsk = dniv_sk(sock->sk);
    int ret;

    if (how != SHUT_RDWR)
        return -EOPNOTSUPP;
    lock_sock(sock->sk);
    if (!dsk->local_link)
        ret = -ENOTCONN;
    else {
        ret = dniv_nsp_disconnect(dsk->local_link, 0U, NULL, 0U);
        if (!ret) {
            sock->state = SS_DISCONNECTING;
            sock->sk->sk_shutdown = SHUTDOWN_MASK;
        }
    }
    release_sock(sock->sk);
    return ret;
}

static int dniv_sock_listen(struct socket *sock, int backlog)
{
    struct sock *sk = sock->sk;
    struct dniv_sock *dsk = dniv_sk(sk);
    struct dniv_sock *other;
    unsigned long flags;
    int ret = 0;

    lock_sock(sk);
    if (!dsk->bound || dsk->local_link ||
        (!dsk->local.sdn_objnum &&
         !le16_to_cpu(dsk->local.sdn_objnamel))) {
        ret = -EINVAL;
        goto out;
    }

    backlog = clamp_t(int, backlog, 1, DNIV_SOCK_MAX_BACKLOG);
    spin_lock_irqsave(&dniv_listener_lock, flags);
    if (!dsk->listening) {
        list_for_each_entry(other, &dniv_listeners, listener_link) {
            if (other->listening &&
                dniv_selector_match(&other->local, &dsk->local)) {
                ret = -EADDRINUSE;
                break;
            }
        }
        if (!ret) {
            list_add_tail(&dsk->listener_link, &dniv_listeners);
            dsk->listening = true;
            dsk->pending_head = 0U;
            dsk->pending_tail = 0U;
            dsk->pending_count = 0U;
        }
    }
    if (!ret) {
        sk->sk_max_ack_backlog = backlog;
        sk->sk_ack_backlog = dsk->pending_count;
    }
    spin_unlock_irqrestore(&dniv_listener_lock, flags);
out:
    release_sock(sk);
    return ret;
}

static int dniv_listener_dequeue(struct dniv_sock *dsk, __u16 *local_link)
{
    unsigned long flags;
    int ret = -EAGAIN;

    spin_lock_irqsave(&dniv_listener_lock, flags);
    if (!dsk->listening)
        ret = -EINVAL;
    else if (dsk->pending_count) {
        *local_link = dsk->pending[dsk->pending_head];
        dsk->pending_head =
            (__u16)((dsk->pending_head + 1U) % DNIV_SOCK_MAX_BACKLOG);
        dsk->pending_count--;
        dsk->sk.sk_ack_backlog = dsk->pending_count;
        ret = 0;
    }
    spin_unlock_irqrestore(&dniv_listener_lock, flags);
    return ret;
}

static void dniv_accept_child_discard(struct socket *newsock,
                                      struct sock *newsk, __u16 local_link)
{
    if (local_link)
        dniv_nsp_conn_release(local_link);
    sock_orphan(newsk);
    newsock->sk = NULL;
    newsk->sk_socket = NULL;
    sock_put(newsk);
}

static int dniv_sock_accept_impl(struct socket *sock, struct socket *newsock,
                                 int flags, bool kern)
{
    struct sock *sk = sock->sk;
    struct dniv_sock *dsk = dniv_sk(sk);
    struct dniv_nsp_ci_snapshot ci;
    struct sockaddr_dn target;
    struct sockaddr_dn source;
    struct sock *newsk;
    struct dniv_sock *newdsk;
    __u8 payload[DNIV_NSP_MAX_CI_PAYLOAD];
    __u16 link;
    long timeo;
    int ret;

    lock_sock(sk);
    timeo = sock_rcvtimeo(sk, flags & O_NONBLOCK);
    for (;;) {
        ret = dniv_listener_dequeue(dsk, &link);
        if (!ret) {
            ret = dniv_nsp_ci_snapshot(link, &ci, payload,
                                       sizeof(payload));
            if (ret)
                continue;
            ret = dniv_ci_decode(payload, ci.payload_len, &target, &source);
            if (ret || !dniv_selector_match(&dsk->local, &target)) {
                dniv_nsp_reject(link, DNIV_REASON_INVALID_DESTINATION,
                                NULL, 0U);
                continue;
            }
            break;
        }
        if (ret != -EAGAIN || !timeo)
            goto out;
        ret = wait_event_interruptible_timeout(
            dniv_sock_waitq,
            READ_ONCE(dsk->pending_count) || !READ_ONCE(dsk->listening),
            timeo);
        if (ret < 0)
            goto out;
        if (!ret) {
            ret = -EAGAIN;
            goto out;
        }
        timeo = ret;
    }

    newsk = sk_alloc(sock_net(sk), PF_DECnet, GFP_KERNEL, &dniv_proto, kern);
    if (!newsk) {
        dniv_nsp_reject(link, DNIV_REASON_OBJECT_BUSY, NULL, 0U);
        ret = -ENOMEM;
        goto out;
    }
    sock_init_data(newsock, newsk);
    newsock->ops = &dniv_proto_ops;
    newsk->sk_family = PF_DECnet;
    newsk->sk_protocol = DNPROTO_NSP;

    newdsk = dniv_sk(newsk);
    memset(&newdsk->local, 0, sizeof(newdsk->local));
    memset(&newdsk->peer, 0, sizeof(newdsk->peer));
    INIT_LIST_HEAD(&newdsk->listener_link);
    memset(newdsk->pending, 0, sizeof(newdsk->pending));
    newdsk->local = dsk->local;
    newdsk->peer = source;
    dniv_sockaddr_set_node(&newdsk->peer, ci.remote_node);
    newdsk->local_link = link;
    newdsk->pending_head = 0U;
    newdsk->pending_tail = 0U;
    newdsk->pending_count = 0U;
    newdsk->bound = true;
    newdsk->listening = false;
    newsock->state = SS_CONNECTING;

    ret = dniv_nsp_accept(link, NULL, 0U);
    if (ret) {
        dniv_accept_child_discard(newsock, newsk, link);
        goto out;
    }

    ret = dniv_wait_running(newsk, &timeo);
    if (ret) {
        dniv_accept_child_discard(newsock, newsk, link);
        goto out;
    }
    newsock->state = SS_CONNECTED;
out:
    release_sock(sk);
    return ret;
}

#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 10, 0)
static int dniv_sock_accept(struct socket *sock, struct socket *newsock,
                            struct proto_accept_arg *arg)
{
    int ret = dniv_sock_accept_impl(sock, newsock, arg->flags, arg->kern);

    arg->err = ret;
    return ret;
}
#else
static int dniv_sock_accept(struct socket *sock, struct socket *newsock,
                            int flags, bool kern)
{
    return dniv_sock_accept_impl(sock, newsock, flags, kern);
}
#endif

static int dniv_sock_setsockopt(struct socket *sock, int level, int optname,
                                sockptr_t optval, unsigned int optlen)
{
    (void)sock;
    (void)level;
    (void)optname;
    (void)optval;
    (void)optlen;
    return -ENOPROTOOPT;
}

static int dniv_sock_getsockopt(struct socket *sock, int level, int optname,
                                char __user *optval, int __user *optlen)
{
    (void)sock;
    (void)level;
    (void)optname;
    (void)optval;
    (void)optlen;
    return -ENOPROTOOPT;
}

static const struct proto_ops dniv_proto_ops = {
    .family = PF_DECnet,
    .owner = THIS_MODULE,
    .release = dniv_sock_release,
    .bind = dniv_sock_bind,
    .connect = dniv_sock_connect,
    .socketpair = sock_no_socketpair,
    .accept = dniv_sock_accept,
    .getname = dniv_sock_getname,
    .poll = dniv_sock_poll,
    .ioctl = sock_no_ioctl,
    .listen = dniv_sock_listen,
    .shutdown = dniv_sock_shutdown,
    .setsockopt = dniv_sock_setsockopt,
    .getsockopt = dniv_sock_getsockopt,
    .sendmsg = dniv_sock_sendmsg,
    .recvmsg = dniv_sock_recvmsg,
    .mmap = sock_no_mmap,
#if LINUX_VERSION_CODE < KERNEL_VERSION(6, 5, 0)
    .sendpage = sock_no_sendpage,
#endif
};

static struct proto dniv_proto = {
    .name = "DECnet-IV",
    .owner = THIS_MODULE,
    .obj_size = sizeof(struct dniv_sock),
};

static int dniv_sock_create(struct net *net, struct socket *sock,
                            int protocol, int kern)
{
    struct sock *sk;
    struct dniv_sock *dsk;

    if (!net_eq(net, &init_net))
        return -EAFNOSUPPORT;
    if (sock->type != SOCK_SEQPACKET)
        return -ESOCKTNOSUPPORT;
    if (protocol != 0 && protocol != DNPROTO_NSP)
        return -EPROTONOSUPPORT;

    sk = sk_alloc(net, PF_DECnet, GFP_KERNEL, &dniv_proto, kern);
    if (!sk)
        return -ENOMEM;
    sock_init_data(sock, sk);
    sock->ops = &dniv_proto_ops;
    sk->sk_family = PF_DECnet;
    sk->sk_protocol = protocol ? protocol : DNPROTO_NSP;
    dsk = dniv_sk(sk);
    memset(&dsk->local, 0, sizeof(dsk->local));
    memset(&dsk->peer, 0, sizeof(dsk->peer));
    dsk->local.sdn_family = AF_DECnet;
    dsk->peer.sdn_family = AF_DECnet;
    INIT_LIST_HEAD(&dsk->listener_link);
    memset(dsk->pending, 0, sizeof(dsk->pending));
    dsk->local_link = 0U;
    dsk->pending_head = 0U;
    dsk->pending_tail = 0U;
    dsk->pending_count = 0U;
    dsk->bound = false;
    dsk->listening = false;
    return 0;
}

static const struct net_proto_family dniv_family_ops = {
    .family = PF_DECnet,
    .create = dniv_sock_create,
    .owner = THIS_MODULE,
};

int dniv_sock_init(void)
{
    int ret;

    ret = proto_register(&dniv_proto, 1);
    if (ret)
        return ret;
    dniv_nsp_set_notify(dniv_sock_notify);
    ret = sock_register(&dniv_family_ops);
    if (ret) {
        dniv_nsp_set_notify(NULL);
        proto_unregister(&dniv_proto);
        return ret;
    }
    return 0;
}

void dniv_sock_exit(void)
{
    sock_unregister(PF_DECnet);
    dniv_nsp_set_notify(NULL);
    proto_unregister(&dniv_proto);
}

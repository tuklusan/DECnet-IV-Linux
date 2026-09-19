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
#include <linux/module.h>
#include <linux/net.h>
#include <linux/poll.h>
#include <linux/slab.h>
#include <linux/socket.h>
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

struct dniv_sock {
    struct sock sk;
    struct sockaddr_dn local;
    struct sockaddr_dn peer;
    __u16 local_link;
    bool bound;
};

static DECLARE_WAIT_QUEUE_HEAD(dniv_sock_waitq);

static inline struct dniv_sock *dniv_sk(struct sock *sk)
{
    return container_of(sk, struct dniv_sock, sk);
}

static void dniv_sock_notify(__u16 local_link)
{
    (void)local_link;
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

static int dniv_sock_release(struct socket *sock)
{
    struct sock *sk = sock->sk;

    if (sk) {
        struct dniv_sock *dsk = dniv_sk(sk);
        struct dniv_nsp_conn_snapshot snapshot;

        lock_sock(sk);
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

#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 10, 0)
static int dniv_sock_accept(struct socket *sock, struct socket *newsock,
                            struct proto_accept_arg *arg)
#else
static int dniv_sock_accept(struct socket *sock, struct socket *newsock,
                            int flags, bool kern)
#endif
{
    (void)sock;
    (void)newsock;
#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 10, 0)
    (void)arg;
#else
    (void)flags;
    (void)kern;
#endif
    return -EOPNOTSUPP;
}

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
    .listen = sock_no_listen,
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
    dsk->local_link = 0U;
    dsk->bound = false;
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

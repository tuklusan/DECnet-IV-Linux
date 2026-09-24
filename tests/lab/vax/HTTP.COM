$! ============================================================================
$! Copyright (c) 2026 Supratim Sanyal of SANYALnet Labs.
$! Proprietary rights reserved except as expressly licensed herein.
$!
$! DECnet-IV-Linux
$! This file is governed by the SANYALnet Labs Non-Commercial License in the
$! root LICENSE file. Non-Commercial use is permitted; Commercial Use and use
$! for AI/ML model training are prohibited unless separately authorized.
$!
$! Attribution is required: "Based on original work by Supratim Sanyal of
$! SANYALnet Labs." See LICENSE for full terms, warranty disclaimer, termination,
$! patent, trademark, and governing-law provisions.
$! ============================================================================
$!
$! Single-request HTTP/1.0 object for an OpenVMS DECnet zero object named HTTP.
$! Place this as SYS$LOGIN:HTTP.COM in the account used by the incoming
$! DECnet access-control credentials.  NETACP supplies SYS$NET on activation.
$!
$ set noon
$ open/read/write net sys$net
$ read/end=done net request
$ cr = f$char(13)
$ lf = f$char(10)
$ body = "QCOCAL-DECNET-HTTP-PASS" + lf
$ reply = "HTTP/1.0 200 OK" + cr + lf + -
          "Content-Length: 24" + cr + lf + -
          "Content-Type: text/plain" + cr + lf + -
          "Connection: close" + cr + lf + cr + lf + body
$ write net reply
$done:
$ close net
$ exit

DECnet-IV-Linux: build a complete DECnet Phase IV stack for Linux in https://github.com/tuklusan/DECnet-IV-Linux. Use an out-of-tree kernel module for native Ethernet, endnode/L1/L2 routing, NSP, sockets/UAPI, Session Control, NICE/NML and DDCMP. Provide DECnet/Linux userspace: ncp, sethost/dnlogin, DAP/FAL tools, PHONE, mail, task/object access, daemons, libraries and admin tools.

Prefer tuklusan/Route20, tuklusan/pydecnet, tuklusan/LinuxDECnet and tuklusan/simh; pin SHAs, upstreams only for comparison; respect licenses.

Repository state is authoritative: follow PROJECT_STATE, HANDOVER and ROADMAP; use feature branches; promote only exact green commits. Test x86_64/aarch64, 2→16 independent VMs, routed/mixed-media networks, real DEC peers, faults and stress.

SoP: (1) read the complete latest disk copy byte-for-byte, line-by-line, untruncated; find/fix defects/gaps. (2) Any fix resets to Step 1. (3) Require 3 consecutive clean Step-1 passes. (4) Any later change resets Step 1.

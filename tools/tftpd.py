#!/usr/bin/env python3
"""tftpd.py <dir> [port] - minimal read-only TFTP server (octet, blksize option) for U-Boot."""
import socket, sys, os, struct
root = os.path.realpath(sys.argv[1]); port = int(sys.argv[2]) if len(sys.argv) > 2 else 6969
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(("0.0.0.0", port))
print("serving", root, "on udp", port, flush=True)
while True:
    pkt, peer = s.recvfrom(2048)
    if struct.unpack("!H", pkt[:2])[0] != 1: continue
    parts = pkt[2:].split(b"\0"); name = parts[0].decode(); opts = dict(zip(parts[2::2], parts[3::2]))
    path = os.path.realpath(os.path.join(root, os.path.basename(name)))
    t = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); t.settimeout(2)
    if not os.path.isfile(path):
        t.sendto(struct.pack("!HH", 5, 1) + b"not found\0", peer); continue
    data = open(path, "rb").read(); bs = 512
    if b"blksize" in opts:
        bs = min(int(opts[b"blksize"]), 1468)
        oack = struct.pack("!H", 6) + b"blksize\0" + str(bs).encode() + b"\0"
        if b"tsize" in opts: oack += b"tsize\0" + str(len(data)).encode() + b"\0"
        ok = False
        for _ in range(5):
            t.sendto(oack, peer)
            try:
                r, _p = t.recvfrom(64)
                if struct.unpack("!HH", r[:4]) == (4, 0): ok = True; break
            except socket.timeout: pass
        if not ok: continue
    n = 1; off = 0; done = False
    while not done:
        chunk = data[off:off + bs]; pkt = struct.pack("!HH", 3, n & 0xffff) + chunk
        for _ in range(10):
            t.sendto(pkt, peer)
            try:
                r, _p = t.recvfrom(64)
                if struct.unpack("!HH", r[:4]) == (4, n & 0xffff): break
            except socket.timeout: pass
        else:
            print("gave up at block", n, flush=True); break
        off += bs; n += 1; done = len(chunk) < bs
    print("sent", name, len(data), "bytes to", peer, flush=True)

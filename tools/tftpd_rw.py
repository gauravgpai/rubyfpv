#!/usr/bin/env python3
"""tftpd_rw.py <dir> [port] - minimal TFTP server for U-Boot: reads (RRQ) and
uploads (WRQ, for `tftp <addr> <name> <size>` flash backups). Octet mode,
blksize/tsize options. An upload never overwrites: an existing name gets a
numeric suffix. Prints one line per transfer with size and CRC32."""
import socket, sys, os, struct, zlib

root = os.path.realpath(sys.argv[1]); port = int(sys.argv[2]) if len(sys.argv) > 2 else 6969
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(("0.0.0.0", port))
print("serving", root, "on udp", port, flush=True)


def options(parts):
    return dict(zip(parts[2::2], parts[3::2]))


def send(t, peer, name, opts):
    path = os.path.realpath(os.path.join(root, os.path.basename(name)))
    if not os.path.isfile(path):
        t.sendto(struct.pack("!HH", 5, 1) + b"not found\0", peer); return
    data = open(path, "rb").read(); bs = 512
    if b"blksize" in opts:
        bs = min(int(opts[b"blksize"]), 1468)
        oack = struct.pack("!H", 6) + b"blksize\0" + str(bs).encode() + b"\0"
        if b"tsize" in opts: oack += b"tsize\0" + str(len(data)).encode() + b"\0"
        for _ in range(5):
            t.sendto(oack, peer)
            try:
                r, _p = t.recvfrom(64)
                if struct.unpack("!HH", r[:4]) == (4, 0): break
            except socket.timeout: pass
        else: return
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
            print("gave up at block", n, flush=True); return
        off += bs; n += 1; done = len(chunk) < bs
    print("sent", name, len(data), "bytes crc32 %08x" % zlib.crc32(data), flush=True)


def receive(t, peer, name, opts):
    base = os.path.basename(name) or "upload.bin"
    path = os.path.join(root, base); k = 1
    while os.path.exists(path):
        path = os.path.join(root, f"{base}.{k}"); k += 1
    bs = 512
    if b"blksize" in opts:
        bs = min(int(opts[b"blksize"]), 1468)
        first = struct.pack("!H", 6) + b"blksize\0" + str(bs).encode() + b"\0"
        if b"tsize" in opts: first += b"tsize\0" + opts[b"tsize"] + b"\0"
    else:
        first = struct.pack("!HH", 4, 0)
    buf = bytearray(); want = 1; last = first; t.settimeout(3); tries = 0
    t.sendto(last, peer)
    while True:
        try:
            r, _p = t.recvfrom(bs + 16)
        except socket.timeout:
            tries += 1
            if tries > 10:
                print("upload of", name, "stalled at", len(buf), "bytes", flush=True); return
            t.sendto(last, peer); continue
        tries = 0
        op, blk = struct.unpack("!HH", r[:4])
        if op != 3: continue
        if blk == (want & 0xffff):
            buf += r[4:]; last = struct.pack("!HH", 4, blk); t.sendto(last, peer); want += 1
            if len(r) - 4 < bs: break
        else:
            t.sendto(last, peer)
    open(path, "wb").write(buf)
    print("received", path, len(buf), "bytes crc32 %08x" % zlib.crc32(bytes(buf)), flush=True)


while True:
    pkt, peer = s.recvfrom(2048)
    op = struct.unpack("!H", pkt[:2])[0]
    if op not in (1, 2): continue
    parts = pkt[2:].split(b"\0"); name = parts[0].decode(errors="replace")
    t = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); t.settimeout(2)
    try:
        (send if op == 1 else receive)(t, peer, name, options(parts))
    except Exception as e:
        print("error", name, e, flush=True)
    t.close()

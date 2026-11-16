#!/usr/bin/env python3
"""ymsend.py <file> - send one file with YMODEM-1K over /dev/ttyUSB0 at 115200 (U-Boot loady must be waiting)."""
import sys, os, time, serial
SOH, STX, EOT, ACK, NAK, CAN, C = 1, 2, 4, 6, 0x15, 0x18, ord("C")
def crc16(d):
    c = 0
    for b in d:
        c ^= b << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) & 0xffff if c & 0x8000 else (c << 1) & 0xffff
    return c
path = sys.argv[1]; data = open(path, "rb").read()
s = serial.Serial("/dev/ttyUSB0", 115200, timeout=10)
def wait(wanted):
    t = time.time()
    while time.time() - t < 30:
        b = s.read(1)
        if b and b[0] in wanted: return b[0]
    sys.exit("timeout waiting for %s" % wanted)
def block(seq, payload, size):
    payload = payload.ljust(size, b"\x1a" if seq else b"\0")
    pkt = bytes([STX if size == 1024 else SOH, seq & 0xff, 0xff - (seq & 0xff)]) + payload
    c = crc16(payload); pkt += bytes([c >> 8, c & 0xff])
    for _ in range(10):
        s.write(pkt); r = wait((ACK, NAK, CAN))
        if r == ACK: return
        if r == CAN: sys.exit("cancelled by receiver")
    sys.exit("too many NAKs at block %d" % seq)
wait((C,))
block(0, os.path.basename(path).encode() + b"\0" + str(len(data)).encode() + b"\0", 128)
wait((C,))
t0 = time.time(); n = 0
for i in range(0, len(data), 1024):
    n += 1; block(n, data[i:i+1024], 1024)
    if n % 256 == 0: print("%d KiB  %.0f s" % (n, time.time() - t0), flush=True)
s.write(bytes([EOT]))
if wait((ACK, NAK)) == NAK: s.write(bytes([EOT])); wait((ACK,))
wait((C,)); block(0, b"", 128)
print("sent %d bytes in %.0f s" % (len(data), time.time() - t0))

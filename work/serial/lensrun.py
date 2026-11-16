#!/usr/bin/env python3
"""lensrun.py - right after serstop.py caught the U-Boot prompt: fetch and run
lens.scr in one typed line, then only listen (the lens board blocks typed input)."""
import serial, time, sys
s = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.3)
s.write(b"setenv serverip 192.168.1.107;setenv tftpdstp 6969;tftpboot 0x42000000 lens.scr;source 0x42000000\r")
t0 = time.time(); end = t0 + float(sys.argv[1]) if len(sys.argv) > 1 else t0 + 110
buf = b""
while time.time() < end:
    d = s.read(4096)
    if d:
        buf += d
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            t = line.replace(b"\r", b"")
            txt = t.decode("latin1")
            if "LENSPROBE" in txt or "Bytes transferred" in txt or "nknown" in txt or "rror" in txt or "11040024" in txt or "TFTP" in txt:
                print(f"+{time.time()-t0:5.1f}s {txt[-90:]}", flush=True)
            elif any(c > 0x7e or (c < 0x20 and c != 9) for c in t):
                print(f"+{time.time()-t0:5.1f}s raw {t[-40:].hex(chr(32))}", flush=True)
print("end; left in buffer:", buf[-60:].hex(" "))

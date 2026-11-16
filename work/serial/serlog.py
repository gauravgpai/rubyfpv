#!/usr/bin/env python3
"""serlog.py <seconds> [logfile] - log /dev/ttyUSB0 at 115200 8N1 (Rust stty can't set 115200)."""
import sys, time, serial
secs = float(sys.argv[1]); out = sys.argv[2] if len(sys.argv) > 2 else "/home/hwt/cv610-boot.log"
s = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.2)
end = time.time() + secs
with open(out, "wb") as f:
    while time.time() < end:
        d = s.read(4096)
        if d:
            f.write(d); f.flush()

#!/usr/bin/env python3
"""lenslog.py <out prefix> [seconds] [baud] - passive log of /dev/ttyUSB0
(sends nothing): one line per burst with seconds since start, length and hex;
raw bytes go to <prefix>.bin."""
import sys, time, serial

pre = sys.argv[1]
secs = float(sys.argv[2]) if len(sys.argv) > 2 else 1800
baud = int(sys.argv[3]) if len(sys.argv) > 3 else 57600
s = serial.Serial("/dev/ttyUSB0", baud, timeout=0.03)
raw = open(pre + ".bin", "wb"); log = open(pre + ".log", "w")
t0 = time.time(); burst = b""; tb = 0.0
log.write("# start %s at %d baud\n" % (time.strftime("%H:%M:%S"), baud)); log.flush()
while time.time() - t0 < secs:
    d = s.read(4096); now = time.time() - t0
    if d:
        if not burst: tb = now
        burst += d; raw.write(d); raw.flush()
    elif burst:
        log.write("%9.3f %4d  %s\n" % (tb, len(burst), burst.hex(" "))); log.flush(); burst = b""

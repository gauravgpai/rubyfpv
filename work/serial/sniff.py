#!/usr/bin/env python3
"""sniff.py <outprefix> [wait_s] [boot_s] [sniff_s] - passive capture on
/dev/ttyUSB0. Sends nothing.

Waits up to wait_s for the first byte (a power-on), records boot_s seconds at
115200 (the boot text) to <outprefix>.boot.txt, then switches to 57600 and
records sniff_s seconds with a timestamp per burst to <outprefix>.57600.log
(hex) and <outprefix>.57600.bin (raw)."""
import sys, time, serial

pre = sys.argv[1]
wait_s, boot_s, sniff_s = (float(a) for a in (sys.argv[2:5] + ["900", "45", "300"][len(sys.argv) - 2:]))
s = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.05)
s.reset_input_buffer()
end = time.time() + wait_s; first = b""
while time.time() < end and not first:
    first = s.read(4096)
if not first:
    sys.exit("nothing received: no power-on seen")
t0 = time.time(); buf = first
while time.time() - t0 < boot_s:
    buf += s.read(4096)
open(pre + ".boot.txt", "wb").write(buf)
txt = buf.decode("latin1")
print("boot capture:", len(buf), "bytes;", "U-Boot" in txt and "U-Boot seen" or "no U-Boot banner",
      ";", "Starting kernel" in txt and "kernel started" or "no kernel start", flush=True)

s.baudrate = 57600; s.reset_input_buffer()
raw = open(pre + ".57600.bin", "wb"); log = open(pre + ".57600.log", "w")
t1 = time.time(); total = 0; burst = b""; tb = 0.0
while time.time() - t1 < sniff_s:
    d = s.read(4096)
    now = time.time() - t1
    if d:
        if not burst: tb = now
        burst += d; raw.write(d); total += len(d)
    elif burst:
        log.write(f"{tb:8.3f} {len(burst):4d}  {burst.hex(' ')}\n"); log.flush(); burst = b""
if burst:
    log.write(f"{tb:8.3f} {len(burst):4d}  {burst.hex(' ')}\n")
print("57600 capture:", total, "bytes in", int(sniff_s), "s")

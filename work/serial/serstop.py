#!/usr/bin/env python3
"""serstop.py <seconds> - spam Ctrl-C on /dev/ttyUSB0 until U-Boot shows a prompt; logs to ~/cv610-uboot.log."""
import sys, time, re, serial
s = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.05)
end = time.time() + float(sys.argv[1]); buf = b""; seen_boot = False
while time.time() < end:
    s.write(b"\x03"); buf += s.read(4096)
    if b"autoboot" in buf or b"U-Boot" in buf: seen_boot = True
    if seen_boot and re.search(rb"\n[\w-]+ ?# ?$", buf.replace(b"\r", b"")):
        time.sleep(0.3); buf += s.read(4096); break
open("/home/hwt/cv610-uboot.log", "wb").write(buf)
print(buf.decode("utf-8", "replace").replace("\r", "")[-1500:])
print("PROMPT" if seen_boot and b"#" in buf[-40:] else "NO_PROMPT")

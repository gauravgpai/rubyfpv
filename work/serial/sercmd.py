#!/usr/bin/env python3
"""sercmd.py <wait-seconds> [text|--break-sysrq X] - send to /dev/ttyUSB0 at 115200 and print the reply."""
import sys, time, serial
wait = float(sys.argv[1])
s = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.2)
if len(sys.argv) > 3 and sys.argv[2] == "--break-sysrq":
    s.send_break(0.3); time.sleep(0.1); s.write(sys.argv[3].encode())
elif len(sys.argv) > 2:
    s.write(sys.argv[2].encode().decode("unicode_escape").encode())
end = time.time() + wait; buf = b""
while time.time() < end:
    buf += s.read(4096)
sys.stdout.write(buf.decode("utf-8", "replace").replace("\r", ""))

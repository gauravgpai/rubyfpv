#!/usr/bin/env python3
"""serpush.py <local file> <remote path> - copy a file to the camera shell over /dev/ttyUSB0 (base64, md5-checked)."""
import sys, time, base64, hashlib, serial
src, dst = sys.argv[1], sys.argv[2]
data = open(src, "rb").read()
s = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.1)
def run(cmd, wait=1.0):
    s.reset_input_buffer(); s.write(cmd.encode() + b"\r"); time.sleep(wait)
    return s.read(65536).decode("utf-8", "replace")
run("stty -echo; rm -f /tmp/push.b64")
b64 = base64.b64encode(data).decode()
s.write(b"cat > /tmp/push.b64\r"); time.sleep(0.3)
for i in range(0, len(b64), 76):
    s.write(b64[i:i+76].encode() + b"\n"); s.flush(); time.sleep(0.008)
time.sleep(0.5); s.write(b"\x04"); time.sleep(0.5)
out = run(f"base64 -d /tmp/push.b64 > {dst} && rm /tmp/push.b64; md5sum {dst}; stty echo", 2)
want = hashlib.md5(data).hexdigest()
print(out.strip()); print("OK" if want in out else f"MISMATCH want {want}")

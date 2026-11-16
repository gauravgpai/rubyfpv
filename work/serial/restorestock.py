#!/usr/bin/env python3
"""restorestock.py <file in the TFTP folder> <crc32 hex> - from a stopped
OpenIPC U-Boot on /dev/ttyUSB0: load a 16 MB flash dump over TFTP, and only if
its CRC32 in the camera's RAM matches, erase the whole flash, write the dump
and read it back. Stops at the first step that does not check out. Does not
reset the camera."""
import sys, re, time, serial

name, want = sys.argv[1], sys.argv[2].lower()
SIZE = 0x1000000
s = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.3)


def cmd(text, wait, until=b"OpenIPC # "):
    s.reset_input_buffer(); s.write(text.encode() + b"\r")
    end = time.time() + wait; buf = b""
    while time.time() < end:
        buf += s.read(4096)
        if buf.rstrip(b" ").endswith(until.rstrip(b" ")) and len(buf) > len(text) + 4:
            break
    return buf.decode("latin1").replace("\r", "")


def crc(out):
    m = re.findall(r"==> ([0-9a-f]{8})", out)
    return m[-1] if m else None


def step(title, text, wait):
    out = cmd(text, wait)
    print(f"--- {title}\n{out.strip()[-300:]}", flush=True)
    return out


if "OpenIPC" not in cmd("", 2):
    sys.exit("no U-Boot prompt")
step("network", "setenv serverip 192.168.1.107; setenv tftpdstp 6969", 3)
out = step("load", f"tftpboot 0x42000000 {name}", 60)
if f"Bytes transferred = {SIZE}" not in out:
    sys.exit("STOP: the dump did not load completely; nothing was erased")
got = crc(step("crc in RAM", f"crc32 0x42000000 {SIZE:#x}", 20))
if got != want:
    sys.exit(f"STOP: RAM crc {got} is not {want}; nothing was erased")
step("probe", "sf probe 0", 5)
out = step("erase", f"sf erase 0 {SIZE:#x}", 240)
if "Erased: OK" not in out:
    sys.exit("STOP: erase did not report OK")
out = step("write", f"sf write 0x42000000 0 {SIZE:#x}", 240)
if "Written: OK" not in out:
    sys.exit("STOP: write did not report OK")
got = crc(step("read back", f"sf read 0x44000000 0 {SIZE:#x}; crc32 0x44000000 {SIZE:#x}", 60))
print("RESULT:", "flash matches the dump" if got == want else f"MISMATCH: flash crc {got}, wanted {want}")

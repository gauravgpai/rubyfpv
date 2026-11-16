#!/usr/bin/env python3
"""lenstest2.py - second lens probe from a stopped U-Boot on /dev/ttyUSB0.

Tries, at 115200, 57600 and 9600 baud, three ways of talking to the lens
board (frames and wake-up bytes as in OpenIPC's majestic-af driver source):
  xm        XiongMai near-Pelco frames (C5 .. 5C), no wake-up
  xm+wake   the XiongMai wake-up bytes first, then the same frames
  d+wake    the Pelco-D wake-up bytes and presets 0x53/0x52, then Pelco-D frames
Each try is: zoom in 2.5 s, stop, zoom out 2.5 s, stop. Bytes go out by
writing them to the UART data register. Whatever comes back on the console
(U-Boot echoes what the lens board sends to the camera) is logged in hex.
Nothing is saved; the console ends at 115200."""
import time, serial

DR = 0x11040000
s = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.2)
t0 = time.time()


def rd(wait):
    end = time.time() + wait; buf = b""
    while time.time() < end:
        buf += s.read(4096)
    return buf


def cmd(text, wait=0.6):
    s.reset_input_buffer(); s.write(text.encode() + b"\r"); return rd(wait)


def alive():
    return b"OpenIPC" in cmd("", 0.8)


def put(name, data, hold=0.0):
    line = ";".join(f"mw.b {DR:#x} {b:#04x}" for b in data)
    out = cmd(line, 0.5)
    i = out.find(b"\n")
    after = out[i + 1:] if i >= 0 else out
    after = after.replace(bytes(data), b"").replace(b"OpenIPC # ", b"")
    extra = rd(hold) if hold else b""
    got = (after + extra).replace(b"OpenIPC # ", b"")
    print(f"  +{time.time()-t0:5.1f}s {name:12s} {bytes(data).hex(' ')}"
          + (f"   <- {got.hex(' ')}" if got.strip(b'\r\n') else ""), flush=True)


def frame(sync, c1, c2, term=None, d2=0):
    f = [sync, 1, c1, c2, 0, d2]; f.append(sum(f[1:]) & 0xFF)
    if term is not None: f.append(term)
    return f


XM = {"in": frame(0xC5, 0, 0x20, 0x5C), "out": frame(0xC5, 0, 0x40, 0x5C), "stop": frame(0xC5, 0, 0, 0x5C)}
PD = {"in": frame(0xFF, 0, 0x20), "out": frame(0xFF, 0, 0x40), "stop": frame(0xFF, 0, 0)}
WAKE_XM = [0xa5, 0x7b, 0x9e, 0xf0, 0xef, 0xee, 0xe0, 0xf4]
WAKE_D = [0x51, 0x01, 0x04, 0x79, 0x01, 0x0d, 0x0a, 0x2e, 0x02, 0x7e, 0x00, 0x00, 0x00, 0x95]


def moves(fr):
    put("zoom in", fr["in"], 2.5); put("stop", fr["stop"], 1.0)
    put("zoom out", fr["out"], 2.5); put("stop", fr["stop"], 1.0)


def setbaud(b):
    s.write(f"setenv baudrate {b}\r".encode()); time.sleep(1.0); s.read(4096)
    s.baudrate = b; time.sleep(0.2)
    ok = alive()
    print(f"== {b} baud, console {'ok' if ok else 'NOT answering'}  (+{time.time()-t0:.1f}s)", flush=True)
    return ok


print("start", time.strftime("%H:%M:%S"), "console", "ok" if alive() else "NOT answering", flush=True)
for n, baud in enumerate((115200, 57600, 9600)):
    if baud != 115200 or n:
        if not setbaud(baud):
            break
    else:
        print(f"== {baud} baud  (+{time.time()-t0:.1f}s)", flush=True)
    print(f" try {3*n+1}: xm"); moves(XM)
    print(f" try {3*n+2}: xm+wake"); put("wake xm", WAKE_XM, 1.5); moves(XM)
    print(f" try {3*n+3}: d+wake"); put("wake d", WAKE_D, 0.5)
    put("preset 53", frame(0xFF, 0, 0x07, None, 0x53), 0.5); put("preset 52", frame(0xFF, 0, 0x07, None, 0x52), 3.0)
    moves(PD)
    if not alive():
        print("console stopped answering", flush=True); break
setbaud(115200)
print("end", time.strftime("%H:%M:%S"))

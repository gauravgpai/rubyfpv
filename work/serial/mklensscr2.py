#!/usr/bin/env python3
"""mklensscr2.py <out.scr> - U-Boot script that drives the lens board from the
camera's own UART (the adapter is soldered to the camera pads, so only the
camera's TX reaches the lens input).

Timeline: marker at 115200, WAIT seconds for the lens to be plugged in and to
finish its power-on run, then everything at 57600 with no console text (the PC
identifies each step from the bytes on the wire), then back to 115200.

Only frames whose meaning is known are sent: the stock firmware's handshake
(ff 01 9a 00 00 00 9b), its version query (EXVER), its 30 Hz sharpness frame,
and zoom/focus moves in Pelco-D, VISCA and 0x51-framed VISCA numbers."""
import sys, struct, zlib, time

U = 0x11040000
WAIT = 50


def cs(b):
    return list(b) + [sum(b) & 0xFF]


def baud(i, f):
    return [f"mw.l {U+0x24:#x} {i:#x}", f"mw.l {U+0x28:#x} {f:#x}", f"mw.l {U+0x2c:#x} 0x70"]


def tx(data):
    return [f"mw.b {U:#x} {b:#04x}" for b in data]


FEED = cs([0x51, 0x01, 0x04, 0x78, 0x01, 0x0d, 0x0b, 0xc9, 0x0b, 0xc9, 0x1f, 0, 0, 0, 0])
PD = lambda c1, c2: [0xFF] + cs([1, c1, c2, 0, 0])
MOVES = {
    "pelco-d": dict(zi=PD(0, 0x20), zo=PD(0, 0x40), ff=PD(0, 0x80), fn=PD(1, 0), st=PD(0, 0), st2=PD(0, 0)),
    "visca": dict(zi=[0x81, 1, 4, 7, 2, 0xFF], zo=[0x81, 1, 4, 7, 3, 0xFF], st=[0x81, 1, 4, 7, 0, 0xFF],
                  ff=[0x81, 1, 4, 8, 2, 0xFF], fn=[0x81, 1, 4, 8, 3, 0xFF], st2=[0x81, 1, 4, 8, 0, 0xFF]),
    "51-visca": dict(zi=cs([0x51, 1, 4, 7, 2]), zo=cs([0x51, 1, 4, 7, 3]), st=cs([0x51, 1, 4, 7, 0]),
                     ff=cs([0x51, 1, 4, 8, 2]), fn=cs([0x51, 1, 4, 8, 3]), st2=cs([0x51, 1, 4, 8, 0])),
}

L = ["setenv F '" + ";".join(tx(FEED)) + "'",
     f"echo LENSPROBE start, wait {WAIT}", f"sleep {WAIT}", "echo LENSPROBE go", "sleep 1"]
L += baud(26, 3) + ["sleep 1"]


def hold(sec, feed):
    if not feed:
        return [f"sleep {sec}"]
    return ["run F", "sleep 0.04"] * int(sec * 20)


def moves(m, feed):
    out = []
    for a, b, t in (("zi", "st", 2.5), ("zo", "st", 2.5), ("ff", "st2", 1.5), ("fn", "st2", 1.5)):
        out += tx(m[a]) + hold(t, feed) + tx(m[b]) + hold(1, feed)
    return out


L += tx(PD(0x9a, 0)) + ["sleep 1"] + tx(cs(b"EXVER")) + ["sleep 1"]
L += moves(MOVES["pelco-d"], False)
L += hold(2, True) + tx(PD(0x9a, 0)) + hold(1, True)
for k in ("pelco-d", "visca", "51-visca"):
    L += moves(MOVES[k], True)
L += ["sleep 1"] + baud(13, 1) + ["sleep 1", "echo LENSPROBE done"]

body = ("\n".join(L) + "\n").encode()
data = struct.pack(">II", len(body), 0) + body
hdr = struct.pack(">IIIIIIIBBBB32s", 0x27051956, 0, int(time.time()), len(data), 0, 0,
                  zlib.crc32(data) & 0xFFFFFFFF, 5, 2, 6, 0, b"lensprobe2")
hdr = hdr[:4] + struct.pack(">I", zlib.crc32(hdr) & 0xFFFFFFFF) + hdr[8:]
open(sys.argv[1], "wb").write(hdr + data)
open(sys.argv[1] + ".txt", "wb").write(body)
print(len(L), "lines,", len(hdr + data), "bytes")

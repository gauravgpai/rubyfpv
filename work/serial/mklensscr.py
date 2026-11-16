#!/usr/bin/env python3
"""mklensscr.py <out.txt> - write a U-Boot script that probes the lens board
by itself, so nothing has to be typed while it runs (the lens board shares the
camera's receive line with the serial adapter and blocks typed input).

The script reprograms the PL011 baud divisors directly (UARTCLK 24 MHz) and
writes frame bytes to the data register. Between tries it goes back to 115200
and prints a marker, which the PC logs. Frames and wake-up bytes are the ones
in OpenIPC's majestic-af driver source."""
import sys

U = 0x11040000
DIV = {115200: (13, 1), 57600: (26, 3), 9600: (156, 16), 38400: (39, 4), 19200: (78, 8)}


def baud(b):
    i, f = DIV[b]
    return [f"mw.l {U+0x24:#x} {i:#x}", f"mw.l {U+0x28:#x} {f:#x}", f"mw.l {U+0x2c:#x} 0x70"]


def tx(data):
    return [f"mw.b {U:#x} {b:#04x}" for b in data]


def frame(sync, c1, c2, term=None, d2=0):
    f = [sync, 1, c1, c2, 0, d2]; f.append(sum(f[1:]) & 0xFF)
    if term is not None: f.append(term)
    return f


XM = dict(i=frame(0xC5, 0, 0x20, 0x5C), o=frame(0xC5, 0, 0x40, 0x5C), s=frame(0xC5, 0, 0, 0x5C))
PD = dict(i=frame(0xFF, 0, 0x20), o=frame(0xFF, 0, 0x40), s=frame(0xFF, 0, 0))
WAKE_XM = [0xa5, 0x7b, 0x9e, 0xf0, 0xef, 0xee, 0xe0, 0xf4]
WAKE_D = [0x51, 0x01, 0x04, 0x79, 0x01, 0x0d, 0x0a, 0x2e, 0x02, 0x7e, 0x00, 0x00, 0x00, 0x95]

L = ["echo LENSPROBE start", f"md.l {U+0x24:#x} 2", "sleep 2"]
PRESET107 = frame(0xFF, 0, 0x07, None, 107)   # stock config: LensReset=0,0,107,...
TRIES = [("pelco-d", 57600, PD, []),
         ("pelco-d after lens reset (preset 107)", 57600, PD, [PRESET107, "wait8"]),
         ("xm", 57600, XM, [WAKE_XM]),
         ("pelco-d", 115200, PD, []),
         ("pelco-d", 9600, PD, [])]
n = 0
for name, b, fr, pre in TRIES:
    n += 1
    L += [f"echo LENSPROBE try {n}: {name} at {b}", "sleep 1"]
    L += baud(b) + ["sleep 1"]
    for w in pre:
        L += ["sleep 8"] if w == "wait8" else tx(w) + ["sleep 1"]
    L += tx(fr["i"]) + ["sleep 3"] + tx(fr["s"]) + ["sleep 2"]
    L += tx(fr["o"]) + ["sleep 3"] + tx(fr["s"]) + ["sleep 2"]
    L += baud(115200) + ["sleep 1"]
L += ["echo LENSPROBE done"]
open(sys.argv[1], "w").write("\n".join(L) + "\n")
print(len(L), "lines,", n, "tries")

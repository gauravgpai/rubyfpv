#!/usr/bin/env python3
"""lensdirect.py [baud ...] - talk to the lens board straight from the serial
adapter (adapter TX -> lens RX, adapter RX <- lens TX, common ground).

For each speed: listen for anything the board sends by itself, then send
Pelco-D and near-Pelco (C5..5C) zoom moves and the stock firmware's lens reset
(preset 107), printing every byte that comes back. Default speeds: 57600,
115200, 9600, 38400, 19200."""
import sys, time, serial

bauds = [int(a) for a in sys.argv[1:]] or [57600, 115200, 9600, 38400, 19200]


def frame(sync, c1, c2, term=None, d2=0):
    f = [sync, 1, c1, c2, 0, d2]; f.append(sum(f[1:]) & 0xFF)
    if term is not None: f.append(term)
    return bytes(f)


PD = dict(tele=frame(0xFF, 0, 0x20), wide=frame(0xFF, 0, 0x40), stop=frame(0xFF, 0, 0),
          near=frame(0xFF, 1, 0), far=frame(0xFF, 0, 0x80), reset107=frame(0xFF, 0, 0x07, None, 107))
XM = dict(tele=frame(0xC5, 0, 0x20, 0x5C), wide=frame(0xC5, 0, 0x40, 0x5C), stop=frame(0xC5, 0, 0, 0x5C))

t0 = time.time()
for b in bauds:
    s = serial.Serial("/dev/ttyUSB0", b, timeout=0.1)

    def listen(sec):
        end = time.time() + sec; buf = b""
        while time.time() < end:
            buf += s.read(4096)
        return buf

    def say(name, data, hold):
        s.write(data); s.flush()
        got = listen(hold)
        print(f"  +{time.time()-t0:5.1f}s {name:22s} {data.hex(' ')}" + (f"   <- {len(got)} bytes: {got[:48].hex(' ')}" if got else ""), flush=True)

    idle = listen(2.0)
    print(f"== {b} baud: {len(idle)} bytes while idle" + (f": {idle[:64].hex(' ')}" if idle else ""), flush=True)
    say("pelco-d zoom in", PD["tele"], 2.5); say("pelco-d stop", PD["stop"], 1.0)
    say("pelco-d zoom out", PD["wide"], 2.5); say("pelco-d stop", PD["stop"], 1.0)
    say("pelco-d focus near", PD["near"], 1.5); say("pelco-d stop", PD["stop"], 0.8)
    say("pelco-d focus far", PD["far"], 1.5); say("pelco-d stop", PD["stop"], 0.8)
    say("near-pelco zoom in", XM["tele"], 2.5); say("near-pelco stop", XM["stop"], 1.0)
    say("near-pelco zoom out", XM["wide"], 2.5); say("near-pelco stop", XM["stop"], 1.0)
    if b == bauds[0]:
        say("lens reset (preset 107)", PD["reset107"], 8.0)
        say("pelco-d zoom in", PD["tele"], 2.5); say("pelco-d stop", PD["stop"], 1.0)
        say("pelco-d zoom out", PD["wide"], 2.5); say("pelco-d stop", PD["stop"], 1.0)
    s.close()
print("end")

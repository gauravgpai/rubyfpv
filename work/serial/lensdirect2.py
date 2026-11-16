#!/usr/bin/env python3
"""lensdirect2.py [baud] - talk to the lens board straight from the serial
adapter (adapter TX -> lens RX, adapter RX <- lens TX, common ground; the
lens's two data wires must be OFF the camera).

1. Version query exactly as the stock firmware sends it ("EXVER" + checksum).
   An answer proves wiring and speed.
2. While sending the stock firmware's 16-byte status frame 30 times a second
   (as the camera does), try zoom in / stop / zoom out / stop in three
   command sets: standard VISCA (81 01 04 07 ..FF), the board's own 0x51
   framing with VISCA command numbers, and Pelco-D. Then the 0x51 templates
   found in the stock program.
Everything the board sends back is printed in hex with a timestamp."""
import sys, time, threading, serial

baud = int(sys.argv[1]) if len(sys.argv) > 1 else 57600
s = serial.Serial("/dev/ttyUSB0", baud, timeout=0.02)
t0 = time.time()
lock = threading.Lock()
feed = True
rx_total = 0


def cs(b):
    return bytes(b) + bytes([sum(b) & 0xFF])


def tx(data):
    with lock:
        s.write(data); s.flush()


def reader():
    global rx_total
    burst = b""; tb = 0.0
    while feed is not None:
        d = s.read(256)
        if d:
            if not burst: tb = time.time() - t0
            burst += d; rx_total += len(d)
        elif burst:
            print(f"   <- +{tb:6.2f}s {len(burst):3d} bytes: {burst.hex(' ')}"
                  + (f"   '{burst.decode('latin1')}'" if all(32 <= c < 127 for c in burst) else ""), flush=True)
            burst = b""


def feeder():
    # the frame the stock firmware sends ~30x/s; value 0x0bc9 as captured
    f = cs([0x51, 0x01, 0x04, 0x78, 0x01, 0x0d, 0x0b, 0xc9, 0x0b, 0xc9, 0x1f, 0, 0, 0, 0])
    while feed is not None:
        if feed: tx(f)
        time.sleep(1 / 30)


def say(name, data, hold):
    print(f"+{time.time()-t0:6.2f}s {name:26s} {bytes(data).hex(' ')}", flush=True)
    tx(bytes(data)); time.sleep(hold)


threading.Thread(target=reader, daemon=True).start()
print(f"== {baud} baud; listening 2 s"); feed = False
ft = threading.Thread(target=feeder, daemon=True); ft.start()
time.sleep(2)
for i in range(3):
    say("version query EXVER", cs(b"EXVER"), 1.5)
print(f"   bytes received so far: {rx_total}")

feed = True
print("== status frames on (30/s)"); time.sleep(2)
say("version query EXVER", cs(b"EXVER"), 1.5)

sets = [
    ("VISCA", [("zoom in", bytes.fromhex("8101040702ff")), ("stop", bytes.fromhex("8101040700ff")),
               ("zoom out", bytes.fromhex("8101040703ff")), ("stop", bytes.fromhex("8101040700ff")),
               ("focus far", bytes.fromhex("8101040802ff")), ("stop", bytes.fromhex("8101040800ff")),
               ("focus near", bytes.fromhex("8101040803ff")), ("stop", bytes.fromhex("8101040800ff"))]),
    ("0x51 + VISCA numbers", [("zoom in", cs([0x51, 1, 4, 0x07, 0x02])), ("stop", cs([0x51, 1, 4, 0x07, 0x00])),
                              ("zoom out", cs([0x51, 1, 4, 0x07, 0x03])), ("stop", cs([0x51, 1, 4, 0x07, 0x00])),
                              ("focus far", cs([0x51, 1, 4, 0x08, 0x02])), ("stop", cs([0x51, 1, 4, 0x08, 0x00])),
                              ("focus near", cs([0x51, 1, 4, 0x08, 0x03])), ("stop", cs([0x51, 1, 4, 0x08, 0x00]))]),
    ("Pelco-D", [("zoom in", cs([0xFF, 1, 0, 0x20, 0, 0])[0:1] + cs([1, 0, 0x20, 0, 0])),
                 ("stop", b"\xff" + cs([1, 0, 0, 0, 0])),
                 ("zoom out", b"\xff" + cs([1, 0, 0x40, 0, 0])), ("stop", b"\xff" + cs([1, 0, 0, 0, 0])),
                 ("focus far", b"\xff" + cs([1, 0, 0x80, 0, 0])), ("stop", b"\xff" + cs([1, 0, 0, 0, 0])),
                 ("focus near", b"\xff" + cs([1, 1, 0, 0, 0])), ("stop", b"\xff" + cs([1, 0, 0, 0, 0]))]),
]
n = 0
for title, cmds in sets:
    n += 1
    print(f"== try {n}: {title}")
    for name, data in cmds:
        say(name, data, 1.0 if name == "stop" else 2.5)

print("== templates from the stock program")
for name, body in (("51 01 04 78 89 02", [0x51, 1, 4, 0x78, 0x89, 0x02]), ("51 01 04 a6 ff 02", [0x51, 1, 4, 0xa6, 0xff, 0x02]),
                   ("51 01 04 a7 ff 02", [0x51, 1, 4, 0xa7, 0xff, 0x02])):
    say(name, cs(body), 1.5)
for name, body in (("ff 01 8c 01", [1, 0x8c, 0x01, 0, 0]), ("ff 01 8c 02", [1, 0x8c, 0x02, 0, 0]),
                   ("ff 01 8c 03", [1, 0x8c, 0x03, 0, 0]), ("ff 01 9a 00", [1, 0x9a, 0, 0, 0]), ("ff 01 c0 00", [1, 0xc0, 0, 0, 0])):
    say(name, b"\xff" + cs(body), 1.5)
feed = None; time.sleep(0.3)
print(f"end; {rx_total} bytes received in all")

#!/usr/bin/env python3
"""test_lenscam.py <camera ip> - the PC stands in for the server camera:
receives the lens camera's RTP on UDP 5604 and sends camlink commands."""
import socket, sys, time

cam = sys.argv[1]
rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); rx.bind(("0.0.0.0", 5604)); rx.settimeout(0.2)
tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def send(msg):
    tx.sendto(msg.encode(), (cam, 5610))


def nal(d):
    return (d[12] >> 1) & 0x3F if len(d) > 13 else -1


def measure(sec, keepalive=None):
    """returns (packets, kbit/s, parameter-set packets, seconds to first parameter set)"""
    n = b = ps = 0; first = None; t0 = time.time(); last = 0
    while time.time() - t0 < sec:
        if keepalive and time.time() - last > 0.3: send(keepalive); last = time.time()
        try: d = rx.recv(4000)
        except socket.timeout: continue
        n += 1; b += len(d)
        if nal(d) in (32, 33, 34):
            ps += 1
            if first is None: first = time.time() - t0
    return n, round(b * 8 / sec / 1000), ps, first


def drain():
    rx.settimeout(0.0)
    try:
        while True: rx.recv(4000)
    except (BlockingIOError, socket.error): pass
    rx.settimeout(0.2)


print("stream        :", measure(3))
# keyframe on request: several tries, time from the request to the first parameter set
ts = []
for i in range(5):
    time.sleep(0.12); drain(); send("idr"); r = measure(0.33)
    ts.append(None if r[3] is None else round(r[3] * 1000))
print("idr -> ms     :", ts)
send("cfg video0.bitrate=4000;video0.codec=h265;"); time.sleep(6); drain()
print("cfg 4000 kbit :", measure(4))
send("api /api/v1/set?video0.bitrate=7000"); time.sleep(3); drain()
print("api 7000 kbit :", measure(4))
send("cfg video0.bitrate=4000;"); time.sleep(1); drain()
print("cfg unchanged (no reload expected):", measure(3))
print("zoom 300 for 5 s, then 0 for 5 s")
measure(5, "zoom 300"); measure(5, "zoom 0")

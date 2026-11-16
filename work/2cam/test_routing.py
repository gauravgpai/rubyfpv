#!/usr/bin/env python3
"""test_routing.py <camswitch binary> - picture controls go to the camera
being shown; encoder changes always go to the second camera. Uses
CAMSWITCH_CONF to point the "second camera" at the loopback."""
import os, socket, struct, subprocess, sys, tempfile, time, threading

conf = tempfile.NamedTemporaryFile("w", suffix=".conf", delete=False)
conf.write("CLIENT_IP=127.0.0.1\nSELECT_CH=7\nZOOM_CH=8\n"); conf.close()
p = subprocess.Popen([sys.argv[1]], env=dict(os.environ, CAMSWITCH_CONF=conf.name))
time.sleep(0.3)
client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); client.bind(("127.0.0.1", 5610)); client.settimeout(0.05)
ruby = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); ruby.bind(("127.0.0.1", 5600))
tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
msgs = []; stop = False


def rx():
    while not stop:
        try: msgs.append(client.recv(2000).decode())
        except socket.timeout: pass


def stream(port, tag):
    seq = 0; i = 0
    while not stop:
        nal = 32 if i % 30 == 0 else 1
        tx.sendto(struct.pack(">BBHII", 0x80, 96, seq & 0xFFFF, 0, 1) + bytes([nal << 1, 1]) + tag, ("127.0.0.1", port))
        seq += 1; i += 1; time.sleep(0.005)


for t in (rx,): threading.Thread(target=t, daemon=True).start()
threading.Thread(target=stream, args=(5602, b"L"), daemon=True).start()
threading.Thread(target=stream, args=(5604, b"R"), daemon=True).start()


def rc(ch7, sec, ch8=1500):
    end = time.time() + sec
    while time.time() < end:
        v = [1500] * 16; v[6] = ch7; v[7] = ch8
        tx.sendto(struct.pack("<16H", *v), ("127.0.0.1", 5607)); time.sleep(0.1)


def api(path):
    tx.sendto(path.encode(), ("127.0.0.1", 5606)); time.sleep(0.2)


ok = True
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name); ok = ok and cond


FLAG = "/tmp/camswitch.remote"
rc(1000, 1.0)
check("no remote flag while the local camera is shown", not os.path.exists(FLAG))
msgs.clear(); api("/api/v1/set?image.luminance=61"); api("/api/v1/set?video0.bitrate=5000")
check("picture control NOT passed on while local is shown", not any("image.luminance=61" in m for m in msgs))
check("encoder change passed on while local is shown", any(m == "api /api/v1/set?video0.bitrate=5000" for m in msgs))
rc(2000, 1.5)
check("remote flag present while the second camera is shown", os.path.exists(FLAG))
msgs.clear(); api("/api/v1/set?image.contrast=44"); api("/api/v1/set?isp.exposure=5"); api("/api/v1/set?video0.bitrate=6000")
check("picture control passed on while remote is shown", any(m == "api /api/v1/set?image.contrast=44" for m in msgs))
check("exposure passed on while remote is shown", any(m == "api /api/v1/set?isp.exposure=5" for m in msgs))
check("encoder change passed on while remote is shown", any(m == "api /api/v1/set?video0.bitrate=6000" for m in msgs))
check("zoom target sent", any(m == "zoom 500" for m in msgs))
check("shared settings do not include exposure", not any(m.startswith("cfg ") and "isp.exposure" in m for m in msgs))
rc(1000, 1.5)
check("flag removed after switching back", not os.path.exists(FLAG))
stop = True; time.sleep(0.2); p.terminate(); p.wait(); time.sleep(0.1)
check("flag removed when the switch stops", not os.path.exists(FLAG))
os.unlink(conf.name)
sys.exit(0 if ok else 1)

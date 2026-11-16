#!/usr/bin/env python3
"""test_camswitch.py <camswitch binary> - feed two fake RTP streams and RC
channels on the loopback and check switching, keyframe gating, sequence
continuity and the fallback when the remote stream stops."""
import socket, struct, subprocess, sys, time, threading

p = subprocess.Popen([sys.argv[1]])
time.sleep(0.3)
out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); out.bind(("127.0.0.1", 5600)); out.settimeout(0.05)
tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
got = []          # (time, source tag, nal type, seq)
stop = False


def rx():
    while not stop:
        try:
            d = out.recv(2000)
        except socket.timeout:
            continue
        got.append((time.time(), chr(d[14]), (d[12] >> 1) & 0x3F, (d[2] << 8) | d[3]))


def rtp(seq, nal, tag):       # H.265: first payload byte carries the NAL type
    return struct.pack(">BBHII", 0x80, 96, seq & 0xFFFF, 0, 1) + bytes([nal << 1, 1]) + tag


def stream(port, tag, alive):
    seq = 1000 if tag == b"L" else 50000
    i = 0
    while not stop:
        if alive():
            nal = 32 if i % 30 == 0 else 1          # a keyframe (VPS first) every 30 packets
            tx.sendto(rtp(seq, nal, tag), ("127.0.0.1", port)); seq += 1; i += 1
        time.sleep(0.005)


remote_on = True
threading.Thread(target=rx, daemon=True).start()
threading.Thread(target=stream, args=(5602, b"L", lambda: True), daemon=True).start()
threading.Thread(target=stream, args=(5604, b"R", lambda: remote_on), daemon=True).start()


def rc(ch7, ch8=1500):
    v = [1500] * 16; v[6] = ch7; v[7] = ch8
    tx.sendto(struct.pack("<16H", *v), ("127.0.0.1", 5607))


def phase(sec, ch7):
    end = time.time() + sec
    while time.time() < end:
        rc(ch7); time.sleep(0.1)


ok = True
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name); ok = ok and cond


t0 = time.time(); phase(1.0, 1000); a = len(got)
check("local stream passed while select is low", a > 100 and all(g[1] == "L" for g in got))
phase(1.5, 2000); b = len(got)
seg = got[a:b]
first_r = next((i for i, g in enumerate(seg) if g[1] == "R"), None)
check("switched to remote", first_r is not None)
check("switch happened on a parameter set", first_r is not None and seg[first_r][2] == 32)
check("no local packets after the switch", first_r is not None and all(g[1] == "R" for g in seg[first_r:]))
remote_on = False; phase(1.5, 2000); c = len(got)
check("fell back to local when the remote stopped", got[c - 1][1] == "L")
remote_on = True; phase(1.5, 2000); d = len(got)
check("returned to remote when it came back", got[d - 1][1] == "R")
phase(1.0, 1000); e = len(got)
check("back to local on select low", got[e - 1][1] == "L")
seqs = [g[3] for g in got]
gaps = sum(1 for x, y in zip(seqs, seqs[1:]) if (y - x) & 0xFFFF != 1)
check(f"output sequence numbers continuous ({gaps} gaps in {len(seqs)})", gaps == 0)
stop = True; time.sleep(0.2)
print(open("/tmp/camswitch.status").read().strip())
p.terminate()
sys.exit(0 if ok else 1)

#!/bin/bash
# lensprobe2.sh - lens test through the camera's boot loader (nothing is flashed).
# defib loads the OpenIPC boot loader into RAM at the next power-on (lens
# unplugged), one typed line fetches and runs lens2.scr, the PC then only listens.
cd ~/cv610-fpv/work/camera2 || exit 1
python3 ../serial/mklensscr2.py lens2.scr || exit 1
ps -eo args | grep -q "tools/tftpd_r[w].py work/camera2" || (cd ~/cv610-fpv && nohup python3 tools/tftpd_rw.py work/camera2 6969 > work/camera2/tftpd5.log 2>&1 &)
echo "== defib: waiting for power-on $(date +%T)"
COLUMNS=140 timeout 1500 ../defib-venv/bin/defib burn -c hi3516cv610:20s -p /dev/ttyUSB0 -b > defib-burn3.log 2>&1
echo "defib exit=$? $(date +%T)"; tail -2 defib-burn3.log | cut -c1-120
grep -q "U-Boot console ready\|Done!" defib-burn3.log || { echo "STOP: bootloader did not start"; exit 1; }
python3 - <<'EOF'
import serial, time
s = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.05)
t0 = time.time()
def T(): return f"+{time.time()-t0:6.2f}s"
s.reset_input_buffer(); s.write(b"\r"); time.sleep(0.3)
s.write(b"setenv serverip 192.168.1.107;setenv tftpdstp 6969;tftpboot 0x42000000 lens2.scr;source 0x42000000\r")
buf = b""; go = False
while time.time() - t0 < 90:
    buf += s.read(4096)
    if b"LENSPROBE go" in buf: go = True; break
txt = buf.decode("latin1").replace("\r", "")
for l in txt.split("\n"):
    if any(k in l for k in ("Bytes transferred", "LENSPROBE", "rror", "nknown", "Bad", "Abort")): print(T(), l[-100:])
if not go: print("STOP: script did not reach 'go'"); raise SystemExit(1)
time.sleep(0.5); s.baudrate = 57600; s.reset_input_buffer()
print(T(), "listening at 57600", flush=True)
FEED = bytes.fromhex("51010478010d0bc90bc91f00000000a3")
raw = b""; pend = b""; last = time.time(); nfeed = 0; tb = None
end = time.time() + 100
log = open("lensprobe2.bin", "wb")
while time.time() < end:
    d = s.read(4096)
    if d:
        log.write(d); raw += d
        if not pend: tb = T()
        pend += d; last = time.time()
    elif pend and time.time() - last > 0.02:
        n = pend.count(FEED); rest = pend.replace(FEED, b"")
        nfeed += n
        if rest:
            if nfeed: print(f"           ({nfeed} sharpness frames)"); nfeed = 0
            print(tb, rest.hex(" "), flush=True)
        pend = b""
    if raw.endswith(b"\x00") and time.time() - last > 6: break
    if time.time() - last > 8 and len(raw) > 100: break
if nfeed: print(f"           ({nfeed} sharpness frames)")
s.baudrate = 115200; time.sleep(3)
print(T(), "tail:", s.read(4096).decode("latin1").replace("\r", "").strip()[-60:])
EOF

#!/bin/bash
# recover_lenscam.sh <crc32> - camera 2 has no network address: load the boot
# loader into RAM at the next power-on (lens unplugged) and rewrite only the
# firmware area (0x50000, 0xa50000 bytes). Boot loader, environment and the
# settings partition (ssh key) are left alone. Resets only if the readback
# matches.
cd ~/cv610-fpv/work/camera2 || exit 1
CRC=$1
ps -eo args | grep -q "tools/tftpd_r[w].py work/camera2" || (cd ~/cv610-fpv && nohup python3 tools/tftpd_rw.py work/camera2 6969 > work/camera2/tftpd6.log 2>&1 &)
echo "== defib: waiting for power-on $(date +%T)"
COLUMNS=140 timeout 1700 ../defib-venv/bin/defib burn -c hi3516cv610:20s -p /dev/ttyUSB0 -b > defib-burn4.log 2>&1
echo "defib exit=$? $(date +%T)"
grep -q "U-Boot console ready\|Done!" defib-burn4.log || { echo "STOP: bootloader did not start"; exit 1; }
python3 - "$CRC" <<'EOF'
import serial, time, re, sys
want = sys.argv[1]
s = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.5)
def run(cmd, tmo, endre):
    s.reset_input_buffer(); s.write(cmd.encode() + b"\r"); buf = b""; t = time.time()
    while time.time() - t < tmo:
        buf += s.read(4096)
        body = buf.split(b"\n", 1)[1] if b"\n" in buf else b""
        if re.search(endre, body): break
    return buf.decode("latin1").replace("\r", "")
s.write(b"\r"); time.sleep(0.5)
t = run("setenv serverip 192.168.1.107;setenv tftpdstp 6969;tftpboot 0x43000000 firmware-lenscam.bin && crc32 0x43000000 0xa50000; echo STEP1-END", 120, rb"STEP1-END")
c = re.findall(r"==> ([0-9a-f]{8})", t); print("in RAM", c, re.findall(r"Bytes transferred = \d+", t))
if c != [want]: sys.exit("STOP: image in RAM does not match; nothing written")
t = run("sf probe 0 && sf erase 0x50000 0xa50000 && sf write 0x43000000 0x50000 0xa50000 && sf read 0x45000000 0x50000 0xa50000 && crc32 0x45000000 0xa50000; echo STEP2-END", 300, rb"STEP2-END")
r = re.findall(r"==> ([0-9a-f]{8})", t); print("readback", r, re.findall(r"Erased: \w+|Written: \w+|rror[^\n]*", t))
if r != [want]: sys.exit("STOP: readback mismatch; camera left at the prompt")
s.write(b"reset\r"); print("verified, reset sent")
EOF

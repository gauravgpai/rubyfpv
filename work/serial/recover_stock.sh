#!/bin/bash
# recover_stock.sh - camera 2 does not boot (flash erased, write unconfirmed).
# 1. defib loads the OpenIPC bootloader into RAM at the next power-on.
# 2. One command line, sent at once (the lens board later blocks typed input):
#    load the stock dump over TFTP, erase, write, read back, verify the CRC,
#    and reset only if it matches.
# 3. Passive capture: boot text at 115200, then what the camera sends to the
#    lens at 57600.
cd ~/cv610-fpv/work/camera2 || exit 1
CRC=8e0801bc
pkill -f "tools/tftpd_r[w].py"; sleep 1
(cd ~/cv610-fpv && nohup python3 tools/tftpd_rw.py work/camera2 6969 > work/camera2/tftpd4.log 2>&1 &)

echo "== defib: waiting for power-on $(date +%T)"
COLUMNS=140 timeout 900 ../defib-venv/bin/defib burn -c hi3516cv610:20s -p /dev/ttyUSB0 -b > defib-burn2.log 2>&1
echo "defib exit=$? $(date +%T)"; tail -3 defib-burn2.log | cut -c1-120
grep -q "U-Boot console ready\|Done!" defib-burn2.log || { echo "STOP: bootloader did not start"; exit 1; }

python3 - <<EOF
import serial, time, re
s = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.3)
line = ("setenv serverip 192.168.1.107;setenv tftpdstp 6969;"
        "tftpboot 0x42000000 camera2-stock.bin && sf probe 0 && sf erase 0 0x1000000 && "
        "sf write 0x42000000 0 0x1000000 && sf read 0x44000000 0 0x1000000 && "
        "crc32 0x44000000 0x1000000 && crc32 -v 0x44000000 0x1000000 $CRC && echo RESTORE-VERIFIED && reset\r")
s.reset_input_buffer(); s.write(b"\r"); time.sleep(0.3); s.write(line.encode())
buf = b""; t = time.time(); done = False
while time.time() - t < 420:
    d = s.read(4096); buf += d
    if b"RESTORE-VERIFIED" in buf.split(b"reset")[-1] or re.search(rb"RESTORE-VERIFIED\r?\n", buf):
        done = True; break
    if re.search(rb"crc32 for 44000000 \.\.\. 44ffffff ==> [0-9a-f]{8}", buf) and time.time() - t > 5 and b"-v" not in buf[-200:]:
        pass
open("restore2.log", "wb").write(buf)
txt = buf.decode("latin1").replace("\r", "")
for pat in ("Bytes transferred = \\d+", "Erased: \\w+", "Written: \\w+", "Read: \\w+", "==> [0-9a-f]{8}", "RESTORE-VERIFIED\\n", "Unknown command[^\\n]*", "ERROR[^\\n]*"):
    m = re.findall(pat, txt)
    if m: print("  ", m[-1].strip())
print("restore:", "verified, camera reset" if done else "NOT verified (see restore2.log)")
EOF
echo "== capture $(date +%T)"
python3 ../serial/sniff.py sniff2 120 50 420 2>&1
tr -d "\r" < sniff2.boot.txt 2>/dev/null | grep -aE "U-Boot 20|boardver|Starting kernel" | head -4
echo "frames logged: $(wc -l < sniff2.57600.log 2>/dev/null)"

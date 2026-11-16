#!/usr/bin/env python3
"""lenstest.py [cycles] - from a stopped U-Boot on /dev/ttyUSB0: dump the pad
mux registers, then switch the console UART to 57600 and send Pelco-D zoom
frames (address 1) by writing the bytes to the PL011 data register, which is
the same UART the lens module listens on. Nothing is saved to flash; the baud
rate goes back to 115200 at the end."""
import sys, time, serial

DR = 0x11040000          # UART0 data register
cycles = int(sys.argv[1]) if len(sys.argv) > 1 else 4
s = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.2)


def cmd(text, wait=1.5):
    s.reset_input_buffer()
    s.write(text.encode() + b"\r")
    end = time.time() + wait; buf = b""
    while time.time() < end:
        buf += s.read(4096)
    return buf


def show(tag, buf):
    print(f"--- {tag}")
    print(buf.decode("latin1").replace("\r", ""))


def frame(b2, b3):
    f = [0xFF, 0x01, b2, b3, 0x00, 0x00]
    f.append(sum(f[1:]) & 0xFF)
    return f


def send(name, f, hold):
    line = ";".join(f"mw.b {DR:#x} {b:#04x}" for b in f)
    out = cmd(line, 0.6)
    tail = out.split(b"\n")[-1] if out else b""
    extra = out.replace(line.encode(), b"")
    print(f"{time.strftime('%H:%M:%S')} {name:10s} {' '.join('%02X' % b for b in f)}  console after: {extra[-40:]!r}")
    time.sleep(hold)


cmd("")
show("iocfg3 (0x11130000) pads 0x00..0x5c", cmd("md.l 0x11130000 0x18", 2))
show("iocfg0 (0x10260000) pads 0x28..0x44", cmd("md.l 0x10260028 8", 2))
show("gpio1 dir / gpio7 dir", cmd("md.l 0x11091400 1; md.l 0x11097400 1", 2))

# console to 57600: U-Boot switches and waits for ENTER at the new speed
s.write(b"setenv baudrate 57600\r"); time.sleep(1.0); print(repr(s.read(4096)))
s.baudrate = 57600; time.sleep(0.2)
show("at 57600", cmd("", 1.5))

ZOOM_IN, ZOOM_OUT, STOP = frame(0x00, 0x20), frame(0x00, 0x40), frame(0x00, 0x00)
FOCUS_NEAR, FOCUS_FAR = frame(0x01, 0x00), frame(0x00, 0x80)
for i in range(cycles):
    send("zoom in", ZOOM_IN, 3); send("stop", STOP, 1.5)
    send("zoom out", ZOOM_OUT, 3); send("stop", STOP, 1.5)
send("focus near", FOCUS_NEAR, 2); send("stop", STOP, 1)
send("focus far", FOCUS_FAR, 2); send("stop", STOP, 1)

s.write(b"setenv baudrate 115200\r"); time.sleep(1.0); s.read(4096)
s.baudrate = 115200; time.sleep(0.2)
show("back at 115200", cmd("printenv baudrate", 1.5))

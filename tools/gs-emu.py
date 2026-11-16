#!/usr/bin/env python3
"""Ground-station emulator for the cv610 FPV images (stands in for a Radxa
Zero 3W running PixelPilot).

The camera streams H.265 RTP over Ethernet to this PC instead of wfb-ng.
A relay models the radio link (wfb-ng capacity for an MCS / channel width /
FEC, a TX queue that drops when full, random air loss), then GStreamer
decodes the stream the way the ground station would. Mode switches go out
the way a ground-station menu sends them: majestic over ssh (cli + SIGHUP),
waybeam over its HTTP API.

  gs-emu.py --cam 172.27.1.x --backend waybeam --mode 720p120-crop
  gs-emu.py --cam 172.27.1.x --backend majestic --sweep
  gs-emu.py --synthetic --sweep              # no camera: x265 test source

What it does not model: the RK3566 hardware decoder (decode here is libav on
the PC CPU), wfb-ng FEC recovery (air loss is applied after FEC), and the
display. Measured: decoded fps and size, video bitrate, link drops, link
queue delay and decoder delay.
"""
import argparse
import heapq
import json
import os
import random
import select
import socket
import statistics
import subprocess
import sys
import threading
import time
import urllib.request

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst  # noqa: E402

# wfb-ng PHY rates, Mbit/s, 1 spatial stream, long GI (MCS 0-7).
PHY = {
    20: [6.5, 13, 19.5, 26, 39, 52, 58.5, 65],
    40: [13.5, 27, 40.5, 54, 81, 108, 121.5, 135],
}
INJECT_EFF = 0.75  # airtime left after injection overhead (no aggregation)

S = "/etc/sensors/"
# name: (majestic profile, size, fps) -- encoded size is video0.size
MAJESTIC = {
    "1080p60": (S + "imx335_2l_1080p60.ini", "1920x1080", 60),
    "1080p90": (S + "imx335_2l_1080p90.ini", "1920x1080", 90),
    "720p90": (S + "imx335_2l_1080p90.ini", "1280x720", 90),
    "864p120": (S + "imx335_2l_864p120.ini", "1536x864", 120),
    "720p120": (S + "imx335_2l_864p120.ini", "1280x720", 120),
    "720p120-crop": (S + "imx335_2l_720p120.ini", "1280x720", 120),
    "bin960p60": (S + "imx335_2l_bin972p60.ini", "1280x960", 60),
    "5mp30": (S + "imx335_i2c_5M.ini", "1920x1440", 30),
}
# name: (waybeam sensor.mode, size, fps)
WAYBEAM = {
    "1080p60": (1, "1920x1080", 60),
    "1080p90": (2, "1920x1080", 90),
    "720p90": (2, "1280x720", 90),
    "864p120": (3, "1536x864", 120),
    "720p120": (3, "1280x720", 120),
    "720p120-crop": (6, "1280x720", 120),
    "wide1080p60": (4, "1920x1080", 60),
    "bin968p60": (5, "1296x968", 60),
    "5mp30": (0, "1920x1440", 30),
}
SYNTHETIC = {
    "1080p60": (None, "1920x1080", 60),
    "1080p90": (None, "1920x1080", 90),
    "720p120": (None, "1280x720", 120),
    "5mp30": (None, "1920x1440", 30),
}


def pc_address_towards(host):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((host, 9))
        return s.getsockname()[0]
    finally:
        s.close()


class Majestic:
    settle = 6.0

    def __init__(self, cam, key):
        self.cam = cam
        self.ssh = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20"]
        if key:
            self.ssh += ["-i", key]
        self.ssh.append("root@" + cam)
        self.saved = None

    def sh(self, cmd):
        r = subprocess.run(self.ssh + [cmd], capture_output=True, text=True,
                           timeout=60)
        if r.returncode == 255:  # ssh itself failed; the command never ran
            raise SystemExit("ssh to %s failed: %s" % (self.cam,
                                                       r.stderr.strip()))
        return r.stdout.strip()

    def stream_to(self, host, port):
        self.saved = (self.sh("cli -g .outgoing.enabled"),
                      self.sh("cli -g .outgoing.server"))
        self.sh("cli -s .outgoing.enabled true; "
                "cli -s .outgoing.server udp://%s:%d; killall -1 majestic"
                % (host, port))

    def restore(self):
        # cli -g prints nothing for a key majestic.yaml does not set; delete
        # those again rather than writing a value the image never had.
        if self.saved:
            cmds = []
            for key, val in zip(("enabled", "server"), self.saved):
                cmds.append("cli -s .outgoing.%s %s" % (key, val) if val
                            else "cli -d .outgoing.%s" % key)
            self.sh("; ".join(cmds) + "; killall -1 majestic")

    def set_mode(self, mode):
        ini, size, fps = mode
        self.sh("cli -s .isp.sensorConfig %s; cli -s .video0.size %s; "
                "cli -s .video0.fps %d; killall -1 majestic" % (ini, size, fps))

    def set_bitrate(self, kbps):
        self.sh("cli -s .video0.bitrate %d; killall -1 majestic" % kbps)


class Waybeam:
    settle = 3.0

    def __init__(self, cam, port=80):
        self.base = "http://%s:%d/api/v1/" % (cam, port)
        self.saved = None

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=10) as r:
            return json.loads(r.read() or b"{}")

    def set(self, field, value):
        try:
            return self.get("set?%s=%s" % (field, value))
        except urllib.error.HTTPError as e:
            raise SystemExit("waybeam refused %s=%s: %s"
                             % (field, value, e.read().decode(errors="replace")))

    def stream_to(self, host, port):
        self.saved = self.get("get?outgoing.server").get("data", {}).get("value")
        self.set("outgoing.server", "udp://%s:%d" % (host, port))

    def restore(self):
        if self.saved:
            self.set("outgoing.server", self.saved)

    def set_mode(self, mode):
        idx, size, _ = mode
        # Restart-required fields go one per request, and video0.size may not
        # exceed the selected capture: step down to 1280x720 (fits every mode),
        # switch the mode, then set the size.
        self.set("video0.size", "1280x720")
        time.sleep(1.0)
        self.set("sensor.mode", idx)
        time.sleep(1.0)
        if size != "1280x720":
            self.set("video0.size", size)

    def set_bitrate(self, kbps):
        self.set("video0.bitrate", kbps)


class Synthetic:
    """x265 test source on this PC, for checking the ground side alone.
    x265 cannot encode 1080p60+ in real time here, so each mode is encoded
    to a file first, then replayed at its frame rate."""
    settle = 2.0

    def __init__(self, kbps, seconds):
        self.kbps = kbps
        self.seconds = seconds
        self.proc = None
        self.dest = None

    def stream_to(self, host, port):
        self.dest = (host, port)

    def set_mode(self, mode):
        _, size, fps = mode
        w, h = size.split("x")
        self.restore()
        clip = "/tmp/gs-emu-%s-%d-%d.h265" % (size, fps, self.kbps)
        frames = int(fps * (self.seconds + self.settle + 3))
        if not os.path.exists(clip) or os.path.getsize(clip) == 0:
            subprocess.run([
                "gst-launch-1.0", "-q", "videotestsrc",
                "num-buffers=%d" % frames, "pattern=ball", "motion=sweep", "!",
                "video/x-raw,width=%s,height=%s,framerate=%d/1" % (w, h, fps),
                "!", "x265enc", "tune=zerolatency", "speed-preset=ultrafast",
                "bitrate=%d" % self.kbps, "key-int-max=%d" % fps, "!",
                "h265parse", "!", "filesink", "location=" + clip], check=True)
        self.proc = subprocess.Popen([
            "gst-launch-1.0", "-q", "filesrc", "location=" + clip, "!",
            "video/x-h265,stream-format=byte-stream,framerate=%d/1" % fps, "!",
            "h265parse", "!", "identity", "sync=true", "!",
            "rtph265pay", "config-interval=1", "mtu=1400", "!",
            "udpsink", "host=%s" % self.dest[0], "port=%d" % self.dest[1]],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def set_bitrate(self, kbps):
        self.kbps = kbps

    def restore(self):
        if self.proc:
            self.proc.terminate()
            self.proc.wait()
            self.proc = None


class Link(threading.Thread):
    """UDP relay standing in for the wfb-ng link: a TX queue drained at the
    link's video capacity (drops what would wait longer than max_queue) and
    random loss on air."""

    def __init__(self, listen, forward, capacity_bps, max_queue, loss):
        super().__init__(daemon=True)
        self.rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rx.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 << 20)
        self.rx.bind(("0.0.0.0", listen))
        self.tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.forward = ("127.0.0.1", forward)
        self.cap = capacity_bps
        self.max_queue = max_queue
        self.loss = loss
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        with self.lock:
            self.bytes = self.pkts = self.src_lost = 0
            self.q_drop = self.air_drop = 0
            self.delays = []
            self.last_seq = None

    def snapshot(self):
        with self.lock:
            return dict(bytes=self.bytes, pkts=self.pkts,
                        src_lost=self.src_lost, q_drop=self.q_drop,
                        air_drop=self.air_drop, delays=list(self.delays))

    def run(self):
        heap = []
        link_free = 0.0
        while True:
            now = time.monotonic()
            while heap and heap[0][0] <= now:
                _, _, data = heapq.heappop(heap)
                self.tx.sendto(data, self.forward)
            timeout = max(0.0, heap[0][0] - now) if heap else 0.5
            r, _, _ = select.select([self.rx], [], [], timeout)
            if not r:
                continue
            data = self.rx.recv(65536)
            now = time.monotonic()
            with self.lock:
                self.pkts += 1
                self.bytes += len(data)
                if len(data) >= 4:
                    seq = (data[2] << 8) | data[3]
                    if self.last_seq is not None:
                        gap = (seq - self.last_seq - 1) & 0xFFFF
                        if gap < 1000:
                            self.src_lost += gap
                    self.last_seq = seq
                if self.cap:
                    start = max(now, link_free)
                    dep = start + len(data) * 8 / self.cap
                    if dep - now > self.max_queue:
                        self.q_drop += 1
                        continue
                    link_free = dep
                else:
                    dep = now
                if self.loss and random.random() < self.loss:
                    self.air_drop += 1
                    continue
                self.delays.append(dep - now)
            heapq.heappush(heap, (dep, self.pkts, data))


class Decoder:
    def __init__(self, port, show):
        Gst.init(None)
        sink = ("autovideosink sync=false" if show
                else "fakesink sync=false")
        self.pipe = Gst.parse_launch(
            "udpsrc port=%d buffer-size=8388608 caps=\"application/x-rtp,"
            "media=video,clock-rate=90000,encoding-name=H265\" ! "
            "rtph265depay ! h265parse ! avdec_h265 name=dec ! "
            "videoconvert ! %s" % (port, sink))
        dec = self.pipe.get_by_name("dec")
        self.lock = threading.Lock()
        self.in_t = {}
        self.reset()
        dec.get_static_pad("sink").add_probe(Gst.PadProbeType.BUFFER, self._in)
        dec.get_static_pad("src").add_probe(Gst.PadProbeType.BUFFER, self._out)
        self.pipe.set_state(Gst.State.PLAYING)

    def reset(self):
        with self.lock:
            self.frames = 0
            self.dec_ms = []
            self.size = None
            self.errors = 0

    def _in(self, pad, info):
        self.in_t[info.get_buffer().pts] = time.monotonic()
        if len(self.in_t) > 512:
            self.in_t.clear()
        return Gst.PadProbeReturn.OK

    def _out(self, pad, info):
        now = time.monotonic()
        t = self.in_t.pop(info.get_buffer().pts, None)
        with self.lock:
            self.frames += 1
            if t is not None:
                self.dec_ms.append((now - t) * 1000)
            if self.size is None:
                st = pad.get_current_caps().get_structure(0)
                self.size = "%dx%d" % (st.get_value("width"),
                                       st.get_value("height"))
        return Gst.PadProbeReturn.OK

    def poll_bus(self):
        bus = self.pipe.get_bus()
        while True:
            m = bus.pop_filtered(Gst.MessageType.ERROR | Gst.MessageType.WARNING)
            if not m:
                return
            with self.lock:
                self.errors += 1

    def snapshot(self):
        with self.lock:
            return dict(frames=self.frames, size=self.size,
                        dec_ms=list(self.dec_ms), errors=self.errors)


def measure(link, dec, seconds):
    link.reset()
    dec.reset()
    t0 = time.monotonic()
    while time.monotonic() - t0 < seconds:
        time.sleep(0.2)
        dec.poll_bus()
    dt = time.monotonic() - t0
    l, d = link.snapshot(), dec.snapshot()
    sent = max(1, l["pkts"])
    delays = sorted(l["delays"]) or [0.0]
    return dict(
        fps=d["frames"] / dt, size=d["size"] or "-",
        mbps=l["bytes"] * 8 / dt / 1e6,
        drop=100.0 * (l["q_drop"] + l["air_drop"] + l["src_lost"]) / sent,
        q_ms=statistics.mean(delays) * 1000,
        q95=delays[int(len(delays) * 0.95) - 1 if len(delays) > 1 else 0] * 1000,
        dec_ms=statistics.mean(d["dec_ms"]) if d["dec_ms"] else 0.0,
        errors=d["errors"])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cam", help="camera IP (wired, instead of 10.5.0.10)")
    ap.add_argument("--backend", choices=["majestic", "waybeam"])
    ap.add_argument("--synthetic", action="store_true",
                    help="no camera: x265 test source on this PC")
    ap.add_argument("--key", help="ssh key for majestic (default: ssh's own)")
    ap.add_argument("--mode", help="switch to this mode and measure")
    ap.add_argument("--sweep", action="store_true", help="measure every mode")
    ap.add_argument("--list", action="store_true", help="list modes")
    ap.add_argument("--bitrate", type=int, help="video0.bitrate, kbit/s")
    ap.add_argument("--mcs", type=int, default=2)
    ap.add_argument("--width", type=int, choices=[20, 40], default=20)
    ap.add_argument("--fec", default="8/12", help="fec_k/fec_n")
    ap.add_argument("--no-link", action="store_true",
                    help="no capacity limit (wire speed)")
    ap.add_argument("--max-queue", type=float, default=50,
                    help="TX queue, ms of airtime before drops")
    ap.add_argument("--loss", type=float, default=0.0,
                    help="air packet loss after FEC, percent")
    ap.add_argument("--seconds", type=float, default=10)
    ap.add_argument("--port", type=int, default=5600)
    ap.add_argument("--show", action="store_true",
                    help="show the video in a window (needs the desktop)")
    a = ap.parse_args()

    if a.synthetic:
        cam, modes = Synthetic(a.bitrate or 8000, a.seconds), SYNTHETIC
        pc = "127.0.0.1"
    elif a.cam and a.backend:
        cam = Majestic(a.cam, a.key) if a.backend == "majestic" else Waybeam(a.cam)
        modes = MAJESTIC if a.backend == "majestic" else WAYBEAM
        pc = pc_address_towards(a.cam)
    else:
        ap.error("give --cam and --backend, or --synthetic")
    if a.list:
        for k, v in modes.items():
            print("%-14s %s @ %d fps" % (k, v[1], v[2]))
        return
    names = list(modes) if a.sweep else [a.mode] if a.mode else []
    for n in names:
        if n not in modes:
            ap.error("unknown mode %s (--list)" % n)

    k, n = (int(x) for x in a.fec.split("/"))
    cap = 0 if a.no_link else PHY[a.width][a.mcs] * 1e6 * INJECT_EFF * k / n
    print("link: %s" % ("unlimited" if not cap else
          "MCS%d %d MHz FEC %d/%d -> %.1f Mbit/s video capacity, "
          "queue %g ms, air loss %g%%" % (a.mcs, a.width, k, n, cap / 1e6,
                                          a.max_queue, a.loss)))
    link = Link(a.port, a.port + 1, cap, a.max_queue / 1000, a.loss / 100)
    link.start()
    dec = Decoder(a.port + 1, a.show)
    cam.stream_to(pc, a.port)
    if a.bitrate and not a.synthetic:
        cam.set_bitrate(a.bitrate)
    try:
        if not names:
            print("receiving; Ctrl-C to stop")
            while True:
                r = measure(link, dec, 2)
                print("%5.1f fps %-10s %5.2f Mbit/s drop %4.1f%% link %4.1f ms "
                      "decode %4.1f ms" % (r["fps"], r["size"], r["mbps"],
                                           r["drop"], r["q_ms"], r["dec_ms"]))
        print("%-14s %-10s %4s | %6s %-10s %6s %6s %13s %7s %4s" % (
            "mode", "expect", "fps", "dec", "size", "Mbit/s", "drop%",
            "link avg/p95", "decode", "err"))
        for name in names:
            mode = modes[name]
            cam.set_mode(mode)
            time.sleep(cam.settle)
            r = measure(link, dec, a.seconds)
            print("%-14s %-10s %4d | %6.1f %-10s %6.2f %6.1f %6.1f/%-6.1f %5.1fms %4d"
                  % (name, mode[1], mode[2], r["fps"], r["size"], r["mbps"],
                     r["drop"], r["q_ms"], r["q95"], r["dec_ms"], r["errors"]),
                  flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        cam.restore()
        dec.pipe.set_state(Gst.State.NULL)


if __name__ == "__main__":
    main()

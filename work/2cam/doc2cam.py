p = "README.md"; s = open(p).read()
marker = '### "lens" variant (camera with the UART zoom/focus lens board)'
assert s.count(marker) == 1
new = '''### Two-camera setup: "server" and "lenscam" variants

`./build.sh rubyfpv-server` and `./build.sh rubyfpv-lenscam` build two more
images, `firmware/hi3516cv6xx_rubyfpv_h5svx-imx335-server/` and
`…-lenscam/`. The plain rubyfpv and lens images are not affected. STATUS
(2026-11-13): both images build; the stream switch passed a loopback test on
the PC with two fake streams (`work/2cam/test_camswitch.py`). NOTHING OF THIS
HAS RUN ON TWO CAMERAS OR WITH A FLIGHT CONTROLLER YET.

```
 flight controller --MSP--> [server camera: radio, Ruby, camswitch] ---radio---> ground
                                   ^  Ethernet (video in, commands out)
                            [lens camera: majestic, camlink, lens, lensaf]
```

* **server** (camera with the Wi-Fi module and the flight controller, address
  192.168.1.10): Ruby as usual, plus
  * `/etc/ruby_video_out` (patch 0012): majestic sends its RTP to
    127.0.0.1:5602 instead of straight to Ruby on 5600.
  * `camswitch` (`scripts/camswitch.c`, `S72camswitch`): passes on to Ruby
    either the local stream or the one the lens camera sends to UDP 5604. A
    switch waits for a keyframe of the wanted camera (it asks for one; 1.5 s
    at most), RTP sequence numbers are rewritten to stay continuous, and if
    the lens camera's stream stops for 0.5 s the local one is used.
  * `/etc/ruby_msp_rc` (patch 0013): Ruby also polls MSP_RC ten times a
    second and hands the channel values to camswitch (UDP 127.0.0.1:5607).
  * `/etc/camswitch.conf`: `SELECT_CH`/`SELECT_ABOVE` (camera select
    channel; channel 1 is the first MSP_RC channel, AUX1 is 5) and
    `ZOOM_CH`/`ZOOM_MIN`/`ZOOM_MAX` (zoom dial). Defaults: channels 7 and 8.
    `FORCE=remote|local` for bench tests without a flight controller.
  * To the lens camera (UDP 5610): the zoom target, keyframe requests, the
    majestic settings both encoders must share (codec, size, fps, bitrate,
    GOP, QP delta, NAL size, sensor profile, exposure; read from
    `/etc/majestic.yaml` once a second) and the run-time API requests Ruby
    makes (adaptive bitrate; patch 0012 mirrors them to UDP 5606).
  * `/tmp/camswitch.status`: which camera is shown, channel values, counters.
* **lenscam** (lens camera, address 192.168.1.11; the "lens" variant plus
  `variants/…/lenscam/`, see its `base` file): no Ruby and no radio.
  `S73camlink` sets the address and points majestic's output at the server
  (`udp://192.168.1.10:5604`); the stock `S95majestic` starts the video.
  * `camlink` (`scripts/camlink.c`): takes the server's datagrams. Zoom: the
    lens board has no position command (Pelco-D "set zoom position" 0x4F was
    tried, no effect) and reports none, so the position is kept from motor
    run time. Full travel is `ZOOM_TRAVEL_MS` (about 8 s, measured in 250 ms
    steps from the picture statistics); at start and whenever the dial is at
    minimum the zoom is driven into the wide end stop to reset the count.
    Settings from the server are written with `cli` only when they differ,
    then majestic is reloaded.
  * `/etc/camlink.conf`: `OWN_IP`, `SERVER_IP`, `ZOOM`, `ZOOM_TRAVEL_MS`.
    `/tmp/camlink.status`: zoom state and position.
  * Lens tool, web sliders and autofocus as in the "lens" variant. A manual
    zoom from the web page is not seen by the position count until the dial
    next goes to minimum.

Known limits: the image settings Ruby applies (brightness, contrast, IR
filter) are not shared; one Ethernet cable between the cameras, no switch
needed; the lens camera's picture has no OSD of its own (Ruby draws it on the
ground). Wiring the flight controller to the server camera uses its normal
UART (`ttyAMA0`), as in the plain rubyfpv image.

'''
s = s.replace(marker, new + marker)
a = "* 0011"
import re
m = re.search(r"\n\* `?0011[^\n]*\n(?:  [^\n]*\n)*", s)
if m:
    s = s[:m.end()] + '''* `0012-openipc-video-out-from-file-and-api-mirror.patch`: majestic's output
  address from `/etc/ruby_video_out`; with the file present, run-time majestic
  API requests are also sent to UDP 127.0.0.1:5606. No file, no change.
* `0013-openipc-msp-rc-channels-to-udp.patch`: with `/etc/ruby_msp_rc`, MSP_RC
  is polled at 10 Hz and the channels go to UDP 127.0.0.1:5607. No file, no
  change.
''' + s[m.end():]
    print("patch list updated")
else:
    print("NOTE: patch list entry for 0011 not found; 0012/0013 described only in the two-camera section")
open(p, "w").write(s)
print("ok")

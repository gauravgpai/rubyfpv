# OpenIPC FPV firmware for Hi3516CV610-20S + IMX335 (2-lane)

Two wfb-ng air-unit images for the H5SVX-class camera module
(Hi3516CV610-20S, 128 MB, 16 MB NOR, IMX335 wired to **two** MIPI lanes):

| Image | Builder device | Streamer | Output |
| --- | --- | --- | --- |
| majestic | `hi3516cv6xx_wfbng_h5svx-imx335` | majestic lite | `openipc.hi3516cv6xx-nor-wfbng-split.tgz` |
| waybeam | `hi3516cv6xx_waybeam_h5svx-imx335` | waybeam (cv610 backend + IMX335 patch) | `openipc.hi3516cv6xx-nor-waybeam-split.tgz` |
| RubyFPV | `hi3516cv6xx_rubyfpv_h5svx-imx335` | majestic lite + RubyFPV vehicle | `openipc.hi3516cv6xx-nor-rubyfpv-split.tgz` |

Both are FPV builds in the OpenIPC sense (builder publishes `-fpv` and `-wfbng`
as the same image): wfb-ng with `wfb_tx` on the `rtp_local` socket,
adaptive-link, msposd, RTL8812AU / RTL8812EU drivers.

Built images live on the build PC in `~/cv610-fpv/firmware/<device>/`.

## What is in both

| | Why |
| --- | --- |
| `S69svbfix` | The vendor `open_pm` hangs the SoC (PLL power-down) unless sysctrl `0x1102034C` holds the SVB PWM value from CRG `0x11014580`. The OpenIPC U-Boot never writes it. The script copies it before `S70vendor` loads the media modules, so the image boots on a stock OpenIPC U-Boot. (A `mw.l 0x1102034c 0x2010` in `bootcmd` does the same from U-Boot.) |
| hisilicon-opensdk `0001` patch | The IMX335 driver's 5 MP mode never set LANEMODE, so the sensor ran 4-lane and this board got half-width lines. The mode now carries the 2-lane RAW10 table taken from the camera's stock firmware (`xrscam`). |
| hisilicon-opensdk `0002` patch | 2-lane crop and flex (`Isp_SnsMode=5`) modes: 1080p60/90, 1536x864@120, 2304x1296@60 (see "Frame rates"). |
| hisilicon-opensdk `0003` patch | 2-lane 2x2 binning (`Isp_SnsMode=1`), 1296x972 full field of view, up to 66 fps. |
| `S94imx335clk` | The 2-lane tables are timed for a 24 MHz INCK; sys_config gives imx335 37.125 MHz. Sets `0x11018440 = 0x4001` before the streamer starts. |
| Kernel `-fpv` config | Wireless stack for the Realtek drivers (as before), plus `TUN=m` (wfb-ng's `wfb_tun` tunnel and vtund need it; it was off) and `EXFAT_FS=m` (modules; `S97tun` loads `tun`). `HIGH_RES_TIMERS=y`: the stock 100 Hz tick without it makes every sleep at least 10 ms, and Ruby's per-packet pacing sleep then held the radio to about 200 packets/s (1.9 Mbit/s, 5 fps on the VRX); with it 1600+ packets/s. uImage 2029K of 2048K. Only the rubyfpv image is rebuilt with it so far. |
| wireless-tools, vtund, exfatprogs | What the published FPV images (ssc338q, hi3516ev300) carry and the cv6xx build lacked. |
| msposd cv6xx backend | Unchanged from the earlier wfbng draft. |
| Excludes | Other sensors' libraries and inis, HOSTAP leftovers, and the three 4-lane IMX335 mode inis. |

Not added: glibc-only bits of the ssc338q image, SigmaStar `zoom.sh`, the
legacy wfb (`datalink`/`telemetry`) files of the ev300 image, `wpa_supplicant`
(only some vendor boards ship it), zram.

IR-cut filter: GPIO 1 and GPIO 9 (stock `hw.cfg`, confirmed on the board).
The majestic image writes them to `nightMode.irCutPin1/2`; waybeam has no
day/night control.

## Frame rates

| Mode | Capture | Field of view (width) | majestic profile | waybeam |
| --- | --- | --- | --- | --- |
| 5MP30 | 2592x1944 | full | `imx335_i2c_5M.ini` | `sensor.mode` 0 / fps 30 |
| 1080p60 | 1920x1080 crop | 74% | `imx335_2l_1080p60.ini` (default) | 1 / fps 60 (default) |
| 1080p90 | 1920x1080 crop | 74% | `imx335_2l_1080p90.ini` | 2 / fps 90 |
| 864p120 | 1536x864 crop | 59% | `imx335_2l_864p120.ini` | 3 / fps 120 |
| wide 1296p60 | 2304x1296 crop | 89% | — (see below) | `sensor.mode` 4 |
| binned 972p60 | 1296x972, 2x2 binning | full | `imx335_2l_bin972p60.ini` | `sensor.mode` 5 |
| 720p120 crop | 1296x720 crop | 50% | `imx335_2l_720p120.ini` | `sensor.mode` 6 |

The encoded size is independent: VPSS scales the capture down to
`video0.size` (waybeam `auto` = capture size rounded to a multiple of 8, so
the binned mode encodes 1296x968). That is how to get

* **720p90**: 1080p90 with `video0.size 1280x720`;
* **720p120**: 864p120 with `video0.size 1280x720` (59% of the width), or
  the native 720p120 crop (50%; the driver's flex window must be a
  multiple of 24 wide, so it captures 1296x720 and VPSS trims it to
  1280x720);
* **wide 1080p60** (waybeam): 1296p60 with `video0.size 1920x1080`;
* binned on majestic: `video0.size 1280x960` (multiple of 8).

Scaling down from a crop keeps that crop's field of view; the native 720p
crop narrows it. On waybeam, `video0.fps` alone selects the first mode at
that rate (60 = 1080p60, 120 = 864p120); the wide, binned and native 720p
modes are chosen with `sensor.mode` 4, 5 or 6.

All verified on this camera: no MIPI CRC/ECC errors, clean image, full rate at
VPSS. Received H.265 RTP on waybeam: 1080p60 60.0, 864p120
120.2, wide→1080p60 59.9, binned 60.6, 720p90 90.1, 720p120 120.0 fps.
majestic (flashed image): 1080p60/90, 864p120, 720p120, binned 972p60 and
5MP30 encode with no VENC timeouts.

The wide 2304x1296 crop is **waybeam only**. majestic lite captures it (VI
and ISP run at 60) but its VPSS never receives a frame above 30 fps at that
width, native size or scaled, with nothing in its log; at 30 fps it works.
majestic is closed source, so its image ships no wide profile.

**2x2 binning stops at ~66 fps, so binned 90 is not possible.** Binning still
reads two sensor rows (4 H) per output row: it halves the data on the link
but not the readout time. Measured: VMAX 3900 truncates frames, and any line
shorter than the sensor minimum (HMAX 250, 230, 206 tried) streams at rate
with a broken image. At HMAX 275 that leaves VMAX ≥ ~4000, i.e. ~66 fps.

**Full sensor width at 60 is not possible either:** a 2592-wide row needs
HMAX ≥ ~430 on two lanes, so the whole 4:3 sensor reaches ~43 fps and a
full-width 16:9 strip ~56. 2304x1296 (89% width) is the widest crop that
holds 60.

**1080p120 is not possible on this board.** The sensor link runs 2 lanes at
1188 Mbit/s (`SYS_MODE 0x01`, the stock firmware's setting). A 1920-wide RAW10
row then needs HMAX >= ~319; at 1080p that is ~101 fps. Measured: HMAX 317
(102 fps) streams clean, 308 (105 fps) truncates every frame. The sensor's own
line minimum (HMAX 275) also caps smaller crops, which is why the 120 fps tier
is 1536x864 rather than something wider. Faster requests are refused by the
driver ("above the 2-lane limit") instead of streaming broken frames.

**4 lanes are not wired.** With the sensor switched to 4-lane
(`0x3A01=0x03`) and all four MIPI PHY lanes enabled, PHY lanes 0 and 2 carry
data while lanes 1 and 3 stay `IDLE` (not even LP-11): the sensor's third and
fourth lanes do not reach the SoC. The stock firmware also configures lanes
`{0,2}` only. 4-lane modes (1080p120 at full width) would need board/flex
rework connecting those lanes, not a firmware change.

## majestic image

* `/etc/sensors/imx335_i2c_5M.ini` is replaced by the 2-lane RAW10 profile
  (lanes `0|2`, `raw_bitness=10`, DevRect at 0,0), and five
  `imx335_2l_*.ini` profiles of the table are added (`Isp_SnsMode` 5 or 1,
  `Isp_W/H`, `Isp_FrameRate`); no wide profile (waybeam only).
* First boot (`customizer.sh`, and `S98wifibroadcast-cv6xx` after
  wifibroadcast's SigmaStar defaults): `imx335_2l_1080p60.ini`,
  **1920x1080@60**. To change, set `isp.sensorConfig`, `video0.size` and
  `video0.fps` to one row of the table together.
* Only majestic **lite** exists for hi3516cv6xx; there is no fpv build of
  majestic for this SoC. Lite has the keys wfb-ng and adaptive-link drive.

## waybeam image

* `general/package/waybeam` is shadowed with a version that also builds the
  cv610 backend, pinned to waybeam `0c880d8` plus
  `0001-cv610-IMX335-2-lane-sensor-profile.patch`:
  * a per-sensor descriptor (`CV610_SENSOR`), IMX335 on lanes 0/2, 24 MHz,
    with the modes of the table above (a per-mode `sns_mode` selects the
    plugin's flex crop or binning); IMX662 remains the default;
  * `video0.size` `auto` rounds the capture size down to a multiple of 8;
  * `CV610_MODULES=firmware` in `S95waybeam`, so it uses the modules
    `load_hisilicon` loaded instead of `load-cv610-online` (which refuses the
    vendor `open_pm`).
* `/etc/waybeam.json`: `unix://rtp_local` (wfb_tx), **`video0.fps` 60**
  (1080p60), `video0.size` `auto` (each mode encodes at its capture size),
  8 Mbit/s CBR, H.265 only. Change the rate with
  `curl 'http://<camera>/api/v1/set?video0.fps=120'`: the pipeline
  re-initialises into the matching mode and the value is saved.
  `/etc/waybeam-cv610.conf`: `CV610_SENSOR=imx335`, `CV610_MODULES=firmware`.
* `S94unixqlen` raises `net.unix.max_dgram_qlen` (from builder's
  `ssc338q_waybeam_generic`).
* Web panel/API on port 80: `/api/v1/set?video0.bitrate=…`, `/request/idr`,
  `/api/v1/snapshot.jpg`.
* The sensor clock control file `sns0_clk_hz` does not exist in this
  sys_config, so waybeam logs a warning and keeps the 24 MHz from `S94imx335clk`.

## RubyFPV image

`hi3516cv6xx_rubyfpv_h5svx-imx335`: majestic lite plus the RubyFPV vehicle
(`ruby_start`, `ruby_rt_vehicle`, `ruby_tx_telemetry`) instead of wfb-ng. It
needs a **Ruby controller** on the ground, not a wfb-ng ground station.

* `general/package/rubyfpv` is shadowed, pinned to RubyFPV `1c2365f` (11.8):
  * `0001-board-type-hi3516cv610.patch`: a new board type,
    `BOARD_TYPE_OPENIPC_HISI_CV610` (33). In shared code only the board name
    and `hardware_board_is_openipc()` change, so every existing board takes
    the same paths as before. It is not a Goke board, so the controller
    allows adaptive video and live camera changes. On the camera: 60 fps and
    7 Mbps defaults (as SigmaStar), OTA from the controller off, the 2-lane
    profile picked from the requested fps (≤60 `1080p60`, ≤90 `1080p90`,
    >90 `864p120` with 1280x720 scaled from it, 5MP at ≤30 fps above 1080p),
    `video0.size` clamped to the capture window, IR-cut on GPIO 1/9.
  * `0002-build-with-musl.patch`: RubyFPV 11.8 does not build against musl
    (`pthread_attr_setaffinity_np`, `PTHREAD_STACK_MIN`).
  * `tweaksys` gets a `hi3516cv608 | hi3516cv610 | hi3516cv613` first-boot
    case (this camera's SoC ID register reads 0x3516C613, so `ipcinfo -c`
    says `hi3516cv613`; Ruby's board detection matches any `hi3516cv6`): boot delay
    0, console UART freed for telemetry, majestic on `imx335_2l_1080p60.ini`
    1920x1080@60 H.265, then the reboot Ruby expects.
  * `0003-msp-armed-flag-file.patch` (camera-only code): the MSP parser now
    keeps `/tmp/ruby/tmp/armed` while the FC is armed, as the MAVLink parser
    already does, so Betaflight/INAV arming reaches `armrec`.
  * `0004-openipc-no-chmod-binaries.patch`: `ruby_start` ran
    `chmod 777 /usr/sbin/ruby*` on every start, which on the overlay root
    copies each binary into the settings partition; after a flash that kept
    settings the camera went on running the old Ruby. Skipped on OpenIPC.
    Cameras that ran an earlier image still hold those copies: after flashing,
    `rm /overlay/root/usr/sbin/ruby_*` and reboot.
  * `0005-cv610-exposure-in-ms.patch`: Ruby wrote the shutter setting to
    `majestic.yaml` in seconds (10 ms as `isp.exposure: 0.01`) except on
    SigmaStar; this majestic takes milliseconds, so auto-exposure was capped
    at 0.01 ms. In a lit room the sensor ran at ISO ~84000, the picture was
    grey noise, and the encoder sat at max QP 42 and still put out 14 Mbit/s
    for a 7 Mbit/s target. Now written in ms: ISO ~100, QP ~23, on target.
  * `0006-cv610-default-864p120.patch`: default video 1536x864 at 120 fps
    (the `imx335_2l_864p120.ini` crop, unscaled; 0010 adds that size to
    Ruby's resolution list). The high quality, high performance and user profiles
    default to 120 fps too; long range keeps 30. The high quality, user and
    custom profiles default to 10 Mbit/s (SigmaStar's 7 before): it fits
    MCS-2 with about 20% EC, and the encoder path tops out near 17 Mbit/s
    (above that majestic drops frames). Applies when Ruby's vehicle
    settings are reset; a camera with saved settings keeps its fps until it
    is changed on the controller. The image's first-boot `customizer.sh` sets
    the same mode. Measured live at 1456x816 (the default before 0010):
    120 fps, 6.8 Mbit/s at 7000, no drops, CPU about 75% busy.
  * `0007-cv610-majestic-udp-wait-1ms.patch`: the vehicle main loop reads
    majestic's video with `select()` and a 100 us timeout. That was 10 ms
    under the stock 100 Hz kernel; with high-res timers ruby_rt_vehicle woke
    ~5800 times a second polling an empty socket. 1 ms on the CV610 (select
    returns as soon as data arrives, so no added latency): timer interrupts
    5200 -> 2400/s, context switches 11400 -> 6100/s, CPU ~24% -> ~20% at
    60 fps / 7 Mbit/s. It does not bring the SoC temperature down by itself
    (89-90 C on the bench either way); most of that heat is the ISP/encoder
    and the radio, not the CPU. (A first try that skipped Ruby's per-packet
    pacing sleeps made no difference and was dropped; it is in
    `work/archive/`.)
  * `0008-cv610-ircut-pulse.patch`: 0001 switched the IR-cut filter the way
    Ruby does on other boards, one pin high and the other low, and left them
    there. This camera has a real bistable coil across GPIO 1 and 9 (stock
    `hw.cfg`: `ircut_gpio_p = 1`, `ircut_gpio_n = 9`, `ircut_hold_ms = 150`),
    so the coil was powered all the time: it overheated, and the SoC read
    91-92 C at 1080p60 where it reads 77-80 C with the coil released. Now a
    150 ms pulse, then both pins low. Every rubyfpv image before this one
    holds the coil whenever Ruby runs: do not leave those running.
    (The SoC temperature is otherwise set by the video pipeline: about 75 C
    with video off on the bench, +5 C for the 864p120 mode over 1080p60;
    Ruby and the radio add 1-2 C; encoder size, noise level and FPV mode
    make no measurable difference.)
  * `0009-cv610-shutter-like-sigmastar.patch` (camera and controller): this
    majestic takes exposure and QP delta live, but Ruby only knew that for
    SigmaStar. The exposure limit is now clamped to the frame time (it stayed
    14 ms at 120 fps, where a frame is 8.3 ms), a shutter change no longer
    restarts the video pipeline, QP delta changes are passed on, and the
    controller's camera menu shows shutter mode and value for this camera.
  * `0010-openipc-resolution-864p.patch` (camera and controller): adds
    1536x864 ("864p", up to 120 fps) to the OpenIPC resolution list, which
    both sides share. Update the controller before choosing it: an older
    controller has no entry for that size.
* `files/busybox-ruby.fragment`: `renice` and `taskset` in busybox. Ruby
  raises majestic with `renice` and pins processes with `taskset`; the stock
  OpenIPC busybox has neither (`sh: renice: not found` at every start), so
  those priorities were never applied.
* SD card recording on arm (`armrec`, `S72armrec`, `/etc/armrec.conf`): with
  a card in, the camera records while the FC is armed and for 30 s after it
  disarms (re-arming inside that keeps the same clip), whatever the controller
  records. See [SD card recording](#sd-card-recording-on-arm).
* Radio: RTL8812EU (`8812eu.ko`) and RTL8812AU drivers as in the other images.
* 64 MB for Linux (`S05osmem`): the kernel's default split of the 128 MB is
  32 MB for Linux and 96 MB for video. With the RTL8812EU and Ruby that runs
  out while the radio comes up: the OOM killer takes `ruby_rt_vehicle`, or the
  kernel panics ("System is deadlocked on memory") and the camera reboot-loops,
  until Ruby resets its vehicle settings after three fast reboots. Video
  (majestic, IMX335) uses about 35 MB, so on first boot `S05osmem` adds
  `osmem=64M` to the U-Boot variable `extras` and reboots once; after that
  Linux has 64 MB and video 64 MB (`dmesg | grep hisi_mem`). It leaves any
  `extras` that already has `osmem=` alone, so `fw_setenv extras osmem=32M`
  goes back. Measured with the adapter on: no OOM, about 30 MB of normal
  memory free (3 MB before), 64 MB video zone with about 30 MB spare.

### Two-camera setup: "server" and "lenscam" variants

`./build.sh rubyfpv-server` and `./build.sh rubyfpv-lenscam` build two more
images, `firmware/hi3516cv6xx_rubyfpv_h5svx-imx335-server/` and
`…-lenscam/`. The plain rubyfpv and lens images are not affected. STATUS
(2026-11-13): both images build (server CRC32 7f9b3f77, lenscam 16080c0c); camlink's zoom tracking was tried on camera 2 from /tmp (repeatable to about 0.2 % in the picture statistics); the stream switch passed a loopback test on
the PC with two fake streams (`work/2cam/test_camswitch.py`). The lenscam image runs on camera 2 and was
tested with the PC as stand-in server (`work/2cam/test_lenscam.py`: stream,
keyframe 12-21 ms after a request, settings follow, own mode). THE SERVER
IMAGE HAS NOT RUN ON A CAMERA; NOTHING HAS RUN ON TWO CAMERAS OR WITH A
FLIGHT CONTROLLER YET.

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
    GOP, QP delta, NAL size, sensor profile; read from `/etc/majestic.yaml`
    once a second) and the run-time API requests Ruby makes (adaptive
    bitrate; patch 0012 mirrors them to UDP 5606).
  * Picture controls from the ground station (`image.*`, `isp.exposure`) act
    on the camera being shown: camswitch keeps `/tmp/camswitch.remote` while
    the lens camera is shown, Ruby then skips its own majestic (patch 0012)
    and camswitch passes the request to the lens camera; while the server
    camera is shown they are not passed on. Ruby still stores one set of
    values and applies it to its own camera at start-up, so after a restart
    the server camera has the values set last, whichever camera they were
    set for. Flip/mirror, IR filter and noise level are not routed.
  * `S72camswitch` clears majestic's `outgoing.servers` list at boot: this
    majestic adds each new `outgoing.server` to that list instead of
    replacing it, and a left-over 127.0.0.1:5600 would give Ruby the picture
    twice. (The lens camera's `S73camlink` does the same.)
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
  * `/etc/camlink.conf`: `OWN_IP`, `SERVER_IP`, `ZOOM`, `ZOOM_TRAVEL_MS`,
    and `OWN_MODE`/`MODE`: with `OWN_MODE=1` the camera keeps its own
    resolution, frame rate and sensor profile (`MODE=1080p60|1080p90|
    864p120|720p120|972p60`, set by `S73camlink`) and ignores those three
    from the server; codec, bitrate and GOP still follow. The ground
    station's decoder then has to restart on each switch (not yet tried).
  * Address: `S73camlink` sets the U-Boot variable `ipaddr` to `OWN_IP`; the
    stock DHCP client falls back to that variable when no server answers.
    (Stopping the client instead left the camera without any address.)
  * `S96camvideo` is a second copy of `S95majestic`: a camera that ran a
    Ruby image has S95majestic deleted in its settings partition.
    `/tmp/camlink.status`: zoom state and position.
  * Lens tool, web sliders and autofocus as in the "lens" variant. A manual
    zoom from the web page is not seen by the position count until the dial
    next goes to minimum.

Known limits: the image settings Ruby applies (brightness, contrast, IR
filter) are not shared; one Ethernet cable between the cameras, no switch
needed; the lens camera's picture has no OSD of its own (Ruby draws it on the
ground). Wiring the flight controller to the server camera uses its normal
UART (`ttyAMA0`), as in the plain rubyfpv image.

### "lens" variant (camera with the UART zoom/focus lens board)

`./build.sh rubyfpv-lens` builds a second image,
`firmware/hi3516cv6xx_rubyfpv_h5svx-imx335-lens/`, from the rubyfpv device plus
`variants/hi3516cv6xx_rubyfpv_h5svx-imx335/lens/`. The plain rubyfpv image is
not affected. The image runs on camera 2 (2026-11-13, CRC32 eaf3d69b); its
lens page sliders and telemetry input have not been tried yet. The lens
method itself is verified: on 2026-11-13 the camera's bootloader sent the
stock firmware's opening query (`ff 01 9a 00 00 00 9b`, then `EXVER` + `8a`)
and plain Pelco-D zoom/focus frames at 57600, and the lens zoomed and focused
(`work/serial/mklensscr2.py`, `lensprobe2.sh`). Whether the opening query is
required is not known; an earlier try without it, seconds after the board got
power, did not move the lens. Standard VISCA was not confirmed.

Autofocus: the stock firmware sends the lens board a 16-byte image-sharpness
frame 30 times a second (`51 01 04 78 01 0d <value> <value> .. <sum>`), which
the board uses for its own autofocus. `lensaf` (`scripts/lensaf.c`, built by
`post-build-lens.sh`, started by `S71lens` unless `LENS_AF=0`) does the same:
it reads the ISP focus statistics next to majestic (read-only,
`ss_mpi_isp_get_focus_stats`) and sends (h1 + v1 over all zones) / 32 as the
value. Tried on camera 2 on 2026-11-13 from /tmp: the board pulled focus to a
sharper position than any reached by hand within about 2 s and again after
zoom moves, and the feeder carried on after a majestic restart. Byte 10 of the
frame (stock: 0x0b..0x1f, meaning unknown) is sent as 0x10. The lens board's
replies are not read.

Why a variant: on this camera the one wired UART (UART0, `ttyAMA0`) goes to the
lens board. The stock firmware talks to it at 57600 (`custommode.ini`:
`PTZProtocol=0,PelcoD`, `PTZBaudRate=0,57600`, `AFProtocolTypeV2=0,3`,
`LensReset` = preset 107, 16x zoom); pan/tilt is separate (HE2866 on GPIO
6/60/61). So Ruby must not use `ttyAMA0`:

* Ruby patch `0011-openipc-serial-port-from-file.patch` (in every rubyfpv
  image, inert without the file): Serial-0 is the device named in
  `/etc/ruby_serial_port`. The variant ships `/dev/ttyAMA2`.
* `S71lens`: switches the alarm-input pad (GPIO1_5, pad register 0x11130000,
  function 3) to UART2_RXD, so flight-controller telemetry comes in there.
  RX only by default: MAVLink streams work; Ruby's MSP parser also sends
  requests (status, battery), which need a TX line. `UART2_TX=reset` in
  `/etc/lens.conf` puts UART2_TXD on the reset-button pad (GPIO7_6, 0x1113004C,
  function 5). The alarm input's circuit (protection, level, polarity) has not
  been looked at.
* `/usr/sbin/lens zoom-in|zoom-out|focus-near|focus-far [ms]` and `lens stop`:
  Pelco-D frames (address 1) on `ttyAMA0` at 57600; settings in
  `/etc/lens.conf`. `lens init` sends the opening query; `S71lens` runs it at
  boot.
* Web interface: Camera > "Zoom and focus" (`lens.cgi`, `j/lens.cgi`): two
  spring-back sliders (zoom, focus) and hold-to-move buttons. The board
  reports no position, so the sliders give a direction only. majestic's own lens driver (`majestic-af`) cannot be used:
  the only majestic published for cv6xx (lite) does not export the symbols the
  plugin needs.
* No login prompt on the serial console (what the lens board sends would be
  typed into it). The bootloader prompt still works. Note that a serial
  adapter and the lens board both drive the camera's receive line; with the
  lens board attached, typing from the adapter stops getting through, and an
  adapter left on the pads can only reach the camera, never the lens input
  (the lens input is the camera's transmit line).

Other UART pads on this chip (from ipctool's pad table): UART1 RXD/TXD on the
SD slot's CMD/DAT3; UART2 RXD on GPIO1_5 (alarm in) or GPIO1_1 (IR-cut N), TXD
on GPIO1_4 (speaker enable) or GPIO7_6 (reset button), or both on two dedicated
pads (0x11130010/14).

### Ruby controller (Radxa Zero 3W)

A stock controller does not know board type 33. `ground/rubyfpv-radxa/` has
the patches the controller needs (0001, 0002, and the two shared ones, 0009
and 0010; 0003-0008 are camera-only) and `build-on-radxa.sh`, which builds Ruby 11.8 on the
Radxa itself (`make all RUBY_BUILD_ENV=radxa`, the stock compiler and flags)
and, with `--install`, backs up `/home/radxa/ruby/ruby_*` and replaces only
the binaries already there. The controller needs Ruby 11.8
(vehicle and controller versions must match); the script stops if another
version is installed. The script does not run from Ruby's USB update menu;
start it over ssh or a terminal on the Radxa (it needs internet for the source).

`--usb` also writes `ruby_update_11.8_cv610.zip`: the official
`ruby_update_11.8.zip` (sha256 checked) with only its `bin/radxaz3/ruby_*`
binaries replaced by the patched build (`make-update-zip.py`). Put it alone at
the root of a USB stick and use the controller's normal USB update; every other
Radxa then needs no build.

`cross-build.sh` makes the same zip on an x86 Linux PC: ARM GNU Toolchain
10.3-2021.07 (closest to the stock Debian GCC 10.2.1) against a sysroot from
the Ruby Radxa image (Debian 11, glibc 2.31, its own gcc-10 and libstdc++
headers) plus the image's versions of the cairo, libdrm, gpiod, i2c and
rockchip-mpp dev packages. Debian's defaults are set explicitly (PIE, gnu
hash, build-id, as-needed). Against the stock 11.8 Radxa binaries, all 18
programs have the same libraries, ELF type and sections, no newer
glibc/libstdc++ symbol versions, and sizes within 2%.

The controller does not need `0003` (it is vehicle-side MSP code) or `armrec`.

### SD card recording on arm

With a card in the camera's slot, `armrec` records video0 (the stream sent to
the controller, same resolution, fps and bitrate) to the card:

* Starts when the flight controller arms; stops 30 s after it disarms.
  Re-arming within those 30 s continues the same clip.
* Files: `fpv/sNNNN_HHMMSS.mp4` on the card. `NNNN` counts power-ups (the
  camera has no clock, so the time part restarts from a saved guess); each
  arm makes a new file (majestic may also split a long flight, `records.split`).
  Fragmented MP4, flushed every 5 s, so a power cut on landing loses at most
  the last few seconds.
* Card fuller than 90%: the oldest clips are deleted.
* Arming comes from Ruby's telemetry: MAVLink (ArduPilot, PX4, INAV in
  MAVLink mode) and MSP (Betaflight, INAV) with `0003`. Ruby's telemetry
  must be set up for the FC's UART. Ruby's "force armed" telemetry option
  makes it record all the time.
* The card is mounted by mdev at `/mnt/mmcblk0p1` (or `/mnt/mmcblk0` without
  a partition table): FAT32, exFAT or ext4.
* Settings: `/etc/armrec.conf` (`ENABLED`, `STOP_DELAY`, `FOLDER`,
  `MAX_USAGE`, `SYNC_SECONDS`); reboot to apply. `armrec status` shows what
  it is doing; `logread | grep armrec` shows each start and stop.

How: at boot (`S72armrec`, before Ruby starts majestic) it points majestic's
recorder at the card. The watcher then pauses and resumes the recorder with
majestic's `/api/v1/records/standdown` and `/resume` calls, which leave the
encoder alone. Switching `records.enabled` instead rebuilds majestic's
pipeline, a 0.7 s gap in the live video (measured), so that is only done at
boot, or when a card is inserted while disarmed. majestic records from its
first frame, so when Ruby restarts majestic while disarmed the watcher pauses
it within half a second and deletes that start-up stub. A card inserted after
boot is picked up while disarmed (one 0.7 s video gap on the ground).

Tested on the camera with a RAM disk standing in for the card: no gap in the
live stream at arm or disarm; 30 s tail and re-arm as above; stubs removed
after majestic restarts; clips decode (1280x720 H.264 60 fps). Not yet tested
with a real card or flight controller.

## Ground-station emulator

`tools/gs-emu.py` stands in for a Radxa Zero 3W ground station on the Linux
PC: the camera streams RTP over Ethernet to the PC, a relay models the wfb-ng
link (capacity from MCS, channel width and FEC, a 50 ms TX queue that drops
when full, optional air loss), GStreamer decodes it, and mode switches go out
the way a ground-station menu sends them (majestic: ssh `cli` + SIGHUP;
waybeam: HTTP API). It points the camera's `outgoing.server` at the PC and
puts it back on exit.

```sh
tools/gs-emu.py --cam <camera-ip> --backend waybeam --list
tools/gs-emu.py --cam <camera-ip> --backend waybeam --sweep
tools/gs-emu.py --cam <camera-ip> --backend majestic --mode 720p120-crop --show
tools/gs-emu.py --synthetic --sweep          # no camera: x265 test clips
```

`--mcs 3 --width 40 --fec 8/12 --loss 2 --bitrate 7000` change the link and
the encoder; `--no-link` removes the capacity limit. Per mode it reports
decoded fps and size, video bitrate, drops, link queue delay (average/p95)
and decoder delay. Not modelled: the RK3566 hardware decoder (the PC decodes
1080p H.265 at ~335 fps in software), FEC recovery and the display.

## Build (on the Linux PC)

```bash
cd ~/cv610-fpv
./build.sh            # all; or ./build.sh wfbng / waybeam / rubyfpv
```

Uses `~/openipc-builder` (firmware pinned to b7c61c4). The firmware tree is
reset and `make clean` is run for every device. Logs and images go to
`firmware/<device>/`.

## Flash

Full steps, U-Boot recovery and the Ruby controller update: [FLASHING.md](FLASHING.md).

From a camera already on OpenIPC hi3516cv6xx:

```bash
scp openipc.hi3516cv6xx-nor-<variant>-split.tgz root@192.168.1.10:/tmp/
ssh root@192.168.1.10 sysupgrade --archive=/tmp/openipc.hi3516cv6xx-nor-<variant>-split.tgz -n
```

`-n` clears the overlay so the first-boot scripts run. Add `--force_ver` if
the variant check refuses. Keep a UART attached for the first boot.

## First-boot checks

```bash
devmem 0x1102034C; devmem 0x11014580     # equal
devmem 0x11018440                        # 0x00004010 (24 MHz, enabled)
grep -E "lane_id|img_width|crc_err" /proc/umap/mipi_rx   # 0,2  2592  0
lsmod | grep -E "tun|cfg80211|88XXau|8812eu"
pidof majestic waybeam wfb_tx
logread | grep wifibroadcast
```

## Layout

```
build.sh                       assembles common/ + devices/<d>/ and builds
common/                        files both devices get
devices/<device>/              per-variant defconfig, overlay, packages, excludes
tools/make-fpv-kernel-config.py   derives and Kconfig-checks the -fpv kernel config
archive/                       superseded drafts (cv610-wfbng, notes)
```

On the PC, `~/cv610-fpv/work/` holds the serial helpers, boot logs, the
stock firmware dump and its extraction (`stock-firmware/`), the reference FPV
images, and the waybeam and msposd working trees.

## Status

* Native 720p120 crop: verified on the majestic image (119.8 fps at
  1280x720, no MIPI CRC errors).
* RubyFPV image: built, not yet run on the camera. Controller:
  `ruby_update_11.8_cv610.zip` cross-built and compared with stock (see
  above); not yet installed on a Radxa.
* Video path verified on this camera, with the same sensor library and
  waybeam the images build: every mode of the frame-rate table on waybeam
  (RTP counted on the PC), SVB fix and 24 MHz clock across reboots.
* The majestic image is flashed and verified (every majestic profile
  encodes); the waybeam image is built, not flashed. wfb-ng over the air
  needs the USB Wi-Fi adapter.
* 1080p is limited to ~101 fps by the two wired MIPI lanes (see "Frame
  rates"). A 1080p100 mode was verified (100.1 fps) and then dropped; 1080p90
  is the top 1080p mode.

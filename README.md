# OpenIPC FPV firmware for Hi3516CV610-20S + IMX335 (2-lane)

OpenIPC camera images for an H5SVX-class camera module, with wfb-ng or
RubyFPV 11.8 as the radio link. The repository holds the build script, the
patches and the per-image files. Built images are attached to the
[releases](https://github.com/gauravgpai/rubyfpv/releases).

## Hardware

### Camera module

| Part | Detail |
| --- | --- |
| SoC | Hi3516CV610-20S. Its ID register reads 0x3516C613, so `ipcinfo -c` prints `hi3516cv613`. |
| Memory | 128 MB RAM, 16 MB SPI NOR flash |
| Sensor | Sony IMX335, 5 MP. Two of its four MIPI lanes reach the SoC, on PHY lanes 0 and 2. |
| IR-cut filter | Bistable coil across GPIO 1 and GPIO 9, switched with a 150 ms pulse |
| Serial | One wired UART, UART0 (`ttyAMA0`), on solder pads. It carries the boot console. |
| Network | Ethernet. The images answer at 192.168.1.10 when no DHCP server replies. |
| Storage | SD card slot |
| USB | Host port for the Wi-Fi adapter |

### Radio

A USB Wi-Fi adapter with an RTL8812EU or RTL8812AU chip. All images carry
both drivers.

### Zoom lens, optional

A motorised zoom and focus lens with its own controller board. The board
connects to UART0 and takes Pelco-D frames at 57600 baud, address 1. It
reports no position. The stock firmware lists the lens as 16x zoom.

On a camera with this lens, UART0 is taken, so flight-controller telemetry
has to come in on another pad. See [Lens variant](#lens-variant).

### Flight controller

Any flight controller that speaks MSP or MAVLink on a UART. Betaflight and
INAV use MSP. ArduPilot, PX4 and INAV in MAVLink mode use MAVLink.

### Ground station

* For the RubyFPV images, a Ruby 11.8 controller. The patches and the update
  package here are for the Radxa Zero 3W.
* For the wfb-ng images, any wfb-ng ground station.

### Build and service tools

* An x86 Linux host to build the images.
* A USB serial adapter on the UART0 pads, for the first flash and for
  recovery.
* A computer on the camera's Ethernet network, for `ssh`, `scp` and TFTP.

## Setups

### One camera, wfb-ng

The camera encodes with majestic or waybeam and sends RTP to `wfb_tx`. The
`wfbng` and `waybeam` images are for this setup.

### One camera, RubyFPV

The camera runs majestic and the RubyFPV vehicle programs. The flight
controller connects to UART0. Use the `rubyfpv` image. On a camera with the
zoom lens, use `rubyfpv-lens` and wire telemetry to UART2.

### Two cameras, one radio

```
 flight controller --MSP--> [server camera: radio, Ruby, camswitch] ---radio---> ground
                                   ^  Ethernet: video in, commands out
                            [lens camera: majestic, camlink, lens, lensaf]
```

The server camera has the radio and the flight controller. The lens camera
has the zoom lens and no radio. One Ethernet cable joins them, with no
switch. A remote-control channel selects which camera's video goes to the
ground, and a second channel sets the zoom. Use `rubyfpv-server` on the
server camera and `rubyfpv-lenscam` on the lens camera.

## Images

| `build.sh` target | Image folder | Contents | `firmware.bin` CRC32 | Tested |
| --- | --- | --- | --- | --- |
| `wfbng` | `hi3516cv6xx_wfbng_h5svx-imx335` | majestic lite, wfb-ng | 4c8143b3 | Flashed. Every majestic profile encodes. Not tested over the air. |
| `waybeam` | `hi3516cv6xx_waybeam_h5svx-imx335` | waybeam with the cv610 backend, wfb-ng | 1077ddb0 | Built, not flashed. The same waybeam binary and sensor library ran every mode on the camera. |
| `rubyfpv` | `hi3516cv6xx_rubyfpv_h5svx-imx335` | majestic lite, RubyFPV vehicle | 4540fcd0 | Runs on the camera with a Ruby controller. |
| `rubyfpv-lens` | `…-imx335-lens` | `rubyfpv` plus lens control and autofocus | eaf3d69b | Runs on a camera with the lens. Zoom, focus and autofocus work. Telemetry on UART2 is untested. |
| `rubyfpv-server` | `…-imx335-server` | `rubyfpv` plus the stream switch | 7f9b3f77 | Never run on a camera. The stream switch passes its loopback tests. |
| `rubyfpv-lenscam` | `…-imx335-lenscam` | lens variant without Ruby, plus `camlink` | 16080c0c | Runs on a camera with the lens. Tested against a host that plays the server. |

The two-camera setup has not run with two cameras, a radio link or a flight
controller.

The wfb-ng images are FPV builds in the OpenIPC sense. They carry `wfb_tx` on
the `rtp_local` socket, adaptive-link, msposd and the Realtek drivers.

Each image folder holds `firmware.bin` for flash offset 0x50000 and
`openipc.hi3516cv6xx-nor-<variant>-split.tgz` for `sysupgrade`.

## Build

```bash
./build.sh            # wfbng, waybeam and rubyfpv
./build.sh rubyfpv-lens
./build.sh rubyfpv-server
./build.sh rubyfpv-lenscam
```

`build.sh` reads three environment variables.

| Variable | Default | Meaning |
| --- | --- | --- |
| `BUILDER` | `~/openipc-builder` | OpenIPC builder checkout. The script clones it if it is missing. |
| `OPENIPC_FW_REV` | `b7c61c4` | OpenIPC firmware commit the patches apply to |
| `OUT` | `./firmware` | Where the script collects images and build logs |

For each image the script resets the firmware tree to the pinned commit, runs
`make clean`, lays `common/` and `devices/<device>/` over the tree and builds.
A variant adds `variants/<device>/<variant>/general/` on top and appends its
`late-post-build-hooks.append` to OpenIPC's hook list. A variant can name
another variant in a `base` file and inherit it.

## Flash

[FLASHING.md](FLASHING.md) has the full steps, the U-Boot recovery and the
controller update.

On a camera that already runs OpenIPC for hi3516cv6xx:

```bash
scp openipc.hi3516cv6xx-nor-<variant>-split.tgz root@192.168.1.10:/tmp/
ssh root@192.168.1.10 sysupgrade --archive=/tmp/openipc.hi3516cv6xx-nor-<variant>-split.tgz -n
```

`-n` clears the settings partition so the first-boot scripts run. Add
`--force_ver` if the variant check refuses. This flash layout accepts only
`--archive`. `sysupgrade` refuses separate kernel and rootfs files. Keep the
serial adapter attached for the first boot.

## First-boot checks

```bash
devmem 0x1102034C; devmem 0x11014580     # equal
devmem 0x11018440                        # 0x00004010: 24 MHz, enabled
grep -E "lane_id|img_width|crc_err" /proc/umap/mipi_rx   # 0,2  2592  0
lsmod | grep -E "tun|cfg80211|88XXau|8812eu"
pidof majestic waybeam wfb_tx
logread | grep wifibroadcast
```

## What every image contains

| Item | Reason |
| --- | --- |
| `S69svbfix` | The vendor `open_pm` module powers down a PLL and hangs the SoC unless sysctrl register `0x1102034C` holds the SVB PWM value from CRG register `0x11014580`. The OpenIPC U-Boot never writes it. The script copies the value before `S70vendor` loads the media modules. `mw.l 0x1102034c 0x2010` in `bootcmd` does the same from U-Boot. |
| hisilicon-opensdk patch `0001` | The IMX335 driver's 5 MP mode never set LANEMODE. The sensor ran on four lanes and the board received half-width lines. The mode now uses the 2-lane RAW10 register table from the camera's stock firmware. |
| hisilicon-opensdk patch `0002` | 2-lane crop and flex modes, `Isp_SnsMode=5`. These are 1080p60, 1080p90, 1536x864 at 120 fps and 2304x1296 at 60 fps. |
| hisilicon-opensdk patch `0003` | 2-lane 2x2 binning, `Isp_SnsMode=1`. 1296x972 with the full field of view, up to 66 fps. |
| `S94imx335clk` | The 2-lane tables assume a 24 MHz sensor clock. `sys_config` gives the IMX335 37.125 MHz. The script writes `0x4001` to `0x11018440` before the streamer starts. |
| Kernel `-fpv` config | The wireless stack for the Realtek drivers, `TUN=m` for `wfb_tun` and vtund, `EXFAT_FS=m`, and `HIGH_RES_TIMERS=y`. `S97tun` loads `tun`. Without high-resolution timers every sleep lasts at least 10 ms on the 100 Hz tick. Ruby's per-packet pacing sleep then held the radio to about 200 packets/s, which is 1.9 Mbit/s and 5 fps on the ground. With them the radio sends more than 1600 packets/s. The uImage is 2029K of the 2048K partition. Only the rubyfpv images are built with this config so far. |
| wireless-tools, vtund, exfatprogs | The published OpenIPC FPV images for ssc338q and hi3516ev300 carry them. The cv6xx build did not. |
| msposd cv6xx backend | An OSD backend for Hi3516CV610 and CV608, `common/general/package/msposd`. |
| Excludes | The libraries and profiles of other sensors, HOSTAP leftovers and the three 4-lane IMX335 profiles are left out of the image. |

Left out on purpose are the glibc-only parts of the ssc338q image, SigmaStar's
`zoom.sh`, the legacy wfb files of the ev300 image, `wpa_supplicant` and zram.

The majestic images write the IR-cut pins to `nightMode.irCutPin1` and
`irCutPin2`. waybeam has no day and night control.

## Sensor modes and frame rates

| Mode | Capture | Field of view, width | majestic profile | waybeam |
| --- | --- | --- | --- | --- |
| 5MP30 | 2592x1944 | full | `imx335_i2c_5M.ini` | `sensor.mode` 0, fps 30 |
| 1080p60 | 1920x1080 crop | 74% | `imx335_2l_1080p60.ini` | `sensor.mode` 1, fps 60, default |
| 1080p90 | 1920x1080 crop | 74% | `imx335_2l_1080p90.ini` | `sensor.mode` 2, fps 90 |
| 864p120 | 1536x864 crop | 59% | `imx335_2l_864p120.ini` | `sensor.mode` 3, fps 120 |
| wide 1296p60 | 2304x1296 crop | 89% | none | `sensor.mode` 4 |
| binned 972p60 | 1296x972, 2x2 binning | full | `imx335_2l_bin972p60.ini` | `sensor.mode` 5 |
| 720p120 crop | 1296x720 crop | 50% | `imx335_2l_720p120.ini` | `sensor.mode` 6 |

The `wfbng` image starts in 1080p60. The RubyFPV images start in 864p120.

The encoded size is separate from the capture size. VPSS scales the capture
down to `video0.size`. On waybeam, `auto` means the capture size rounded down
to a multiple of 8, so the binned mode encodes 1296x968. Scaling gives these
extra modes.

* 720p90 is 1080p90 with `video0.size 1280x720`.
* 720p120 is 864p120 with `video0.size 1280x720`, at 59% of the width. The
  native 720p120 crop covers 50%. The driver's flex window must be a multiple
  of 24 pixels wide, so it captures 1296x720 and VPSS trims that to 1280x720.
* Wide 1080p60, on waybeam only, is 1296p60 with `video0.size 1920x1080`.
* The binned mode on majestic needs `video0.size 1280x960`, a multiple of 8.

A scaled mode keeps the field of view of its crop. On waybeam, `video0.fps`
alone selects the first mode at that rate, so 60 gives 1080p60 and 120 gives
864p120. Select the wide, binned and native 720p modes with `sensor.mode` 4,
5 or 6.

### Measured

Every mode ran on the camera with no MIPI CRC or ECC errors and at full rate
at VPSS. Received H.265 RTP on waybeam, in fps:

| 1080p60 | 864p120 | wide scaled to 1080p60 | binned | 720p90 | 720p120 |
| --- | --- | --- | --- | --- | --- |
| 60.0 | 120.2 | 59.9 | 60.6 | 90.1 | 120.0 |

On the flashed majestic image, 1080p60, 1080p90, 864p120, 720p120, binned
972p60 and 5MP30 encode with no VENC timeouts. The native 720p120 crop
measured 119.8 fps.

### Limits

The wide 2304x1296 crop works on waybeam only. majestic lite captures it, and
VI and ISP run at 60 fps, but its VPSS receives no frames above 30 fps at
that width, at native size or scaled. Its log shows nothing. majestic is
closed source, so the majestic images ship no wide profile.

2x2 binning stops near 66 fps, so binned 90 fps is not possible. Binning
still reads two sensor rows per output row. It halves the data on the link
but not the readout time. A VMAX of 3900 truncates frames. Lines shorter than
the sensor minimum, tried at HMAX 250, 230 and 206, stream at rate with a
broken picture. At HMAX 275 the smallest VMAX is about 4000, which is 66 fps.

Full sensor width at 60 fps is not possible. A 2592-pixel row needs an HMAX
of about 430 on two lanes. The whole 4:3 sensor then reaches about 43 fps and
a full-width 16:9 strip about 56 fps. 2304x1296 is the widest crop that holds
60 fps.

1080p120 is not possible on this board. The sensor link runs two lanes at
1188 Mbit/s, `SYS_MODE 0x01`, the stock firmware's setting. A 1920-pixel
RAW10 row then needs an HMAX of about 319, which is 101 fps at 1080p. HMAX
317 streams clean at 102 fps. HMAX 308 truncates every frame at 105 fps. The
sensor's own line minimum of HMAX 275 also caps smaller crops, which is why
the 120 fps mode is 1536x864. The driver refuses faster requests with "above
the 2-lane limit". A 1080p100 mode measured 100.1 fps and was dropped, so
1080p90 is the fastest 1080p mode.

Four lanes are not wired. With the sensor set to 4-lane mode, `0x3A01=0x03`,
and all four PHY lanes enabled, PHY lanes 0 and 2 carry data and lanes 1 and
3 stay idle without reaching LP-11. The stock firmware also configures lanes
0 and 2 only. A 4-lane mode needs the board or the flex cable reworked.

## wfb-ng image with majestic

* The 2-lane RAW10 profile replaces `/etc/sensors/imx335_i2c_5M.ini`. It uses
  lanes `0|2`, `raw_bitness=10` and a DevRect at 0,0. The image adds the five
  `imx335_2l_*.ini` profiles of the table.
* First boot sets `imx335_2l_1080p60.ini` and 1920x1080 at 60 fps.
  `customizer.sh` does this, and `S98wifibroadcast-cv6xx` repeats it after
  wifibroadcast writes its SigmaStar defaults. To change the mode, set
  `isp.sensorConfig`, `video0.size` and `video0.fps` together to one row of
  the table.
* Only majestic lite exists for hi3516cv6xx. Lite has the settings that
  wfb-ng and adaptive-link change.

## waybeam image

* `general/package/waybeam` replaces the stock package with one that also
  builds the cv610 backend. It pins waybeam `0c880d8` and applies
  `0001-cv610-IMX335-2-lane-sensor-profile.patch`.
  * The patch adds a per-sensor descriptor, `CV610_SENSOR`. The IMX335 entry
    uses lanes 0 and 2, a 24 MHz clock and the modes of the table. A per-mode
    `sns_mode` selects the flex crop or binning. IMX662 stays the default.
  * `video0.size` `auto` rounds the capture size down to a multiple of 8.
  * `S95waybeam` sets `CV610_MODULES=firmware`. waybeam then uses the modules
    that `load_hisilicon` loaded. Its own `load-cv610-online` refuses the
    vendor `open_pm`.
* `/etc/waybeam.json` sends to `unix://rtp_local`, which is `wfb_tx`. The
  defaults are `video0.fps` 60, `video0.size` `auto`, 8 Mbit/s CBR and H.265.
  Change the rate with `curl 'http://<camera>/api/v1/set?video0.fps=120'`.
  The pipeline restarts in the matching mode and waybeam saves the value.
* `/etc/waybeam-cv610.conf` holds `CV610_SENSOR=imx335` and
  `CV610_MODULES=firmware`.
* `S94unixqlen` raises `net.unix.max_dgram_qlen`. It comes from the builder's
  `ssc338q_waybeam_generic` device.
* The web panel and API are on port 80. Examples are
  `/api/v1/set?video0.bitrate=…`, `/request/idr` and `/api/v1/snapshot.jpg`.
* This `sys_config` has no `sns0_clk_hz` control file. waybeam logs a warning
  and keeps the 24 MHz that `S94imx335clk` set.

## RubyFPV image

`hi3516cv6xx_rubyfpv_h5svx-imx335` runs majestic lite and the RubyFPV vehicle
programs `ruby_start`, `ruby_rt_vehicle` and `ruby_tx_telemetry` in place of
wfb-ng. It needs a Ruby controller on the ground. A wfb-ng ground station
does not work with it.

`general/package/rubyfpv` replaces the stock package and pins RubyFPV
`1c2365f`, version 11.8.

### Patches

`0001-board-type-hi3516cv610.patch` adds board type 33,
`BOARD_TYPE_OPENIPC_HISI_CV610`. In shared code only the board name and
`hardware_board_is_openipc()` change, so existing boards behave as before.
The board is not treated as a Goke board, so the controller allows adaptive
video and live camera changes. On the camera the patch sets these.

* OTA update from the controller is off.
* The requested frame rate selects the profile. Up to 60 fps gives `1080p60`,
  up to 90 gives `1080p90`, above 90 gives `864p120`. Sizes above 1080p use
  the 5 MP profile at up to 30 fps.
* `video0.size` is clamped to the capture window.
* The IR-cut filter is on GPIO 1 and 9.

`0002-build-with-musl.patch` makes RubyFPV 11.8 build against musl, which
lacks `pthread_attr_setaffinity_np` and `PTHREAD_STACK_MIN`.

`0003-msp-armed-flag-file.patch` changes camera code only. The MSP parser
keeps `/tmp/ruby/tmp/armed` while the flight controller is armed, as the
MAVLink parser already does. Betaflight and INAV arming then reaches `armrec`.

`0004-openipc-no-chmod-binaries.patch` stops `ruby_start` from running
`chmod 777 /usr/sbin/ruby*` at every start on OpenIPC. On the overlay root
that command copies each binary into the settings partition, and after a
flash that kept settings the camera went on running the old Ruby. A camera
that ran an earlier image still holds those copies. After flashing it, run
`rm /overlay/root/usr/sbin/ruby_*` and reboot.

`0005-cv610-exposure-in-ms.patch` writes the shutter limit to
`majestic.yaml` in milliseconds. Ruby wrote seconds on every board except
SigmaStar, so 10 ms became `isp.exposure: 0.01` and this majestic capped
auto-exposure at 0.01 ms. In a lit room the sensor then ran at about ISO
84000, the picture was grey noise, and the encoder sat at its maximum QP of
42 and still produced 14 Mbit/s for a 7 Mbit/s target. With the patch the
same scene gives about ISO 100, QP 23 and the target bitrate.

`0006-cv610-default-864p120.patch` sets the default video to 1536x864 at 120
fps, the unscaled `imx335_2l_864p120.ini` crop.

* The high quality, high performance and user profiles default to 120 fps.
  Long range keeps 30.
* The high quality, user and custom profiles default to 10 Mbit/s. That fits
  MCS-2 with about 20% error correction. The encoder path tops out near 17
  Mbit/s, and above that majestic drops frames.
* The defaults apply when Ruby's vehicle settings are reset. A camera with
  saved settings keeps its values until the controller changes them.
* An unpaired vehicle limits video to what MCS-0 carries, about 2.8 Mbit/s.
  The 10 Mbit/s default takes effect after pairing.
* Measured at 1456x816, the default before patch 0010: 120 fps, 6.8 Mbit/s
  at a 7000 kbit/s target, no drops, CPU about 75% busy.

`0007-cv610-majestic-udp-wait-1ms.patch` raises a `select()` timeout in the
vehicle's main loop from 100 µs to 1 ms on the CV610. With high-resolution
timers `ruby_rt_vehicle` woke about 5800 times a second to poll an empty
socket. `select()` returns as soon as data arrives, so the longer timeout
adds no latency. At 60 fps and 7 Mbit/s, timer interrupts fell from 5200 to
2400 per second, context switches from 11400 to 6100 per second, and CPU
load from about 24% to about 20%. The SoC temperature did not change. An
earlier attempt that skipped Ruby's per-packet pacing sleeps made no
difference. It is in `work/archive/`.

`0008-cv610-ircut-pulse.patch` switches the IR-cut filter with a 150 ms
pulse and then sets both pins low. Patch 0001 held one pin high and one low,
as Ruby does on other boards. This camera's filter is a bistable coil, and
the stock `hw.cfg` says `ircut_gpio_p = 1`, `ircut_gpio_n = 9` and
`ircut_hold_ms = 150`. Held on, the coil overheated and the SoC read 91 to
92 °C at 1080p60. With the coil released it reads 77 to 80 °C. Do not leave
a rubyfpv image built before this patch running.

The video pipeline sets the rest of the SoC temperature. On the bench it is
about 75 °C with video off, and 864p120 runs 5 °C hotter than 1080p60. Ruby
and the radio add 1 to 2 °C. Encoder size, noise reduction level and FPV
mode make no measurable difference.

`0009-cv610-shutter-like-sigmastar.patch` changes camera and controller.
This majestic applies exposure and QP delta without a restart, and Ruby
assumed that only for SigmaStar. With the patch:

* the exposure limit is clamped to the frame time. It stayed at 14 ms at 120
  fps, where a frame lasts 8.3 ms;
* a shutter change no longer restarts the video pipeline;
* QP delta changes reach majestic;
* the controller's camera menu shows shutter mode and value for this board.

`0010-openipc-resolution-864p.patch` changes camera and controller. It adds
1536x864, shown as "864p" with up to 120 fps, to the OpenIPC resolution list
that both sides share. Update the controller before selecting it.

`0011-openipc-serial-port-from-file.patch` makes Ruby's Serial-0 the device
named in `/etc/ruby_serial_port`. Without the file nothing changes.

`0012-openipc-video-out-from-file-and-api-mirror.patch` and
`0013-openipc-msp-rc-channels-to-udp.patch` serve the two-camera setup. Each
does nothing unless its file exists, `/etc/ruby_video_out` or
`/etc/ruby_msp_rc`. See
[Two-camera variants](#two-camera-variants-server-and-lenscam).

### Other additions

* `tweaksys` has a first-boot case for `hi3516cv608`, `hi3516cv610` and
  `hi3516cv613`. It sets the boot delay to 0, frees the console UART for
  telemetry, sets majestic to H.265 and reboots, as Ruby expects. Ruby's
  board detection matches any name that starts with `hi3516cv6`.
* `files/busybox-ruby.fragment` adds `renice` and `taskset` to busybox. Ruby
  uses them to raise majestic's priority and pin processes. The stock
  OpenIPC busybox has neither, so Ruby never applied those priorities.
* `S05osmem` gives Linux 64 MB. The default split of the 128 MB is 32 MB for
  Linux and 96 MB for video. With the RTL8812EU driver and Ruby, Linux ran
  out while the radio came up. The OOM killer took `ruby_rt_vehicle`, or the
  kernel panicked with "System is deadlocked on memory" and the camera
  rebooted in a loop. Video uses about 35 MB. On first boot the script adds
  `osmem=64M` to the U-Boot variable `extras` and reboots once. It leaves an
  `extras` that already has `osmem=` alone, so `fw_setenv extras osmem=32M`
  restores the old split. Measured with the adapter running: no OOM, about
  30 MB of normal memory free where 3 MB were free before, and about 30 MB
  spare in the 64 MB video zone. Check with `dmesg | grep hisi_mem`.

### SD card recording on arm

With a card in the slot, `armrec` records video0 to the card. That is the
stream sent to the controller, at the same resolution, frame rate and
bitrate. It does not depend on what the controller records.

* Recording starts when the flight controller arms and stops 30 s after it
  disarms. Re-arming within those 30 s continues the same clip.
* Files are `fpv/sNNNN_HHMMSS.mp4`. `NNNN` counts power-ups. The camera has
  no clock, so the time part restarts from a saved guess. Each arm makes a
  new file. majestic may also split a long flight, see `records.split`.
* The files are fragmented MP4, flushed every 5 s. A power cut loses at most
  the last few seconds.
* When the card is more than 90% full, `armrec` deletes the oldest clips.
* Arming comes from Ruby's telemetry, MAVLink or MSP. Set up Ruby's
  telemetry for the flight controller's UART. Ruby's "force armed" option
  makes it record all the time.
* mdev mounts the card at `/mnt/mmcblk0p1`, or `/mnt/mmcblk0` without a
  partition table. FAT32, exFAT and ext4 work.
* Settings are in `/etc/armrec.conf`: `ENABLED`, `STOP_DELAY`, `FOLDER`,
  `MAX_USAGE` and `SYNC_SECONDS`. Reboot to apply them. `armrec status`
  shows the current state, and `logread | grep armrec` shows each start and
  stop.

At boot, `S72armrec` points majestic's recorder at the card before Ruby
starts majestic. The watcher then pauses and resumes the recorder with
majestic's `/api/v1/records/standdown` and `/resume` calls, which leave the
encoder alone. Switching `records.enabled` rebuilds majestic's pipeline and
interrupts the live video for 0.7 s, so `armrec` does that only at boot or
when a card is inserted while disarmed. majestic records from its first
frame. When Ruby restarts majestic while disarmed, the watcher pauses the
recorder within half a second and deletes the short start-up file.

Tested on the camera with a RAM disk in place of the card. The live stream
had no gap at arm or disarm, the 30 s tail and re-arm worked, the start-up
files were removed, and the clips decode. Not tested with a real card or a
flight controller.

### Lens variant

`./build.sh rubyfpv-lens` builds
`firmware/hi3516cv6xx_rubyfpv_h5svx-imx335-lens/` from the rubyfpv device
plus `variants/hi3516cv6xx_rubyfpv_h5svx-imx335/lens/`.

The lens board is on UART0, the only wired UART. The stock firmware's
`custommode.ini` has `PTZProtocol=0,PelcoD`, `PTZBaudRate=0,57600` and
`AFProtocolTypeV2=0,3`. Pan and tilt are separate, on an HE2866 driver at
GPIO 6, 60 and 61, and this image does not use them. Ruby must stay off
`ttyAMA0`, so the variant does the following.

* `/etc/ruby_serial_port` names `/dev/ttyAMA2`, which patch 0011 reads.
* `S71lens` switches the alarm-input pad GPIO1_5 to UART2_RXD. The pad
  register is 0x11130000, function 3. Flight-controller telemetry comes in
  there. Only RX is connected by default, which is enough for MAVLink
  streams. Ruby's MSP parser also sends requests, and those need a TX line.
  `UART2_TX=reset` in `/etc/lens.conf` puts UART2_TXD on the reset-button
  pad GPIO7_6, register 0x1113004C, function 5. The alarm input's circuit
  has not been checked for protection, level or polarity.
* `/usr/sbin/lens zoom-in|zoom-out|focus-near|focus-far [ms]` and
  `lens stop` send Pelco-D frames on `ttyAMA0` at 57600. `lens init` sends
  the stock firmware's opening query, and `S71lens` runs it at boot.
  Settings are in `/etc/lens.conf`.
* The web interface has a "Zoom and focus" page under Camera, `lens.cgi`. It
  has one spring-back slider for zoom and one for focus. The sliders set a
  direction and not a position, because the board reports none.
* The serial console has no login prompt, because the lens board's replies
  would be typed into it. The bootloader prompt still works.

What the lens board accepts:

* Pelco-D zoom and focus frames move the lens. Zoom in is
  `ff 01 00 20 00 00 21`, stop is `ff 01 00 00 00 00 01`.
* The stock firmware first sends `ff 01 9a 00 00 00 9b` and then `EXVER`
  followed by byte `8a`. Whether the board needs this is not known. One
  attempt without it, seconds after power-on, did not move the lens.
* Pelco-D "set zoom position", command 0x4F, has no effect.
* Standard VISCA was not confirmed.

Autofocus is done by the lens board. The stock firmware sends it a 16-byte
sharpness frame about 30 times a second,
`51 01 04 78 01 0d <value> <value> .. <sum>`. `lensaf` does the same. It
reads the ISP focus statistics with `ss_mpi_isp_get_focus_stats` from a
second process, without touching majestic, and sends the sum of h1 and v1
over all zones divided by 32. `post-build-lens.sh` compiles it from
`scripts/lensaf.c`. `S71lens` starts it unless `/etc/lens.conf` has
`LENS_AF=0`.

On the camera the board pulled focus within about 2 s to a sharper position
than manual stepping reached, and refocused after zoom moves. `lensaf` kept
running through a majestic restart. Byte 10 of the frame varies from 0x0b to
0x1f in the stock firmware. Its meaning is unknown and `lensaf` sends 0x10.
`lensaf` does not read the board's replies.

majestic's own lens plugin, `majestic-af`, cannot be used. majestic lite
does not export the symbols the plugin needs.

A serial adapter on the UART0 pads and the lens board both drive the
camera's receive line. With the lens board attached, typing from the adapter
stops getting through. The adapter cannot reach the lens board either,
because the lens input is the camera's transmit line.

Other UART pads on this SoC, from ipctool's pad table:

| UART | RXD | TXD |
| --- | --- | --- |
| UART1 | SD slot CMD | SD slot DAT3 |
| UART2 | GPIO1_5, alarm input, or GPIO1_1, IR-cut N | GPIO1_4, speaker enable, or GPIO7_6, reset button |
| UART2 | dedicated pad 0x11130010 | dedicated pad 0x11130014 |

### Two-camera variants: server and lenscam

`./build.sh rubyfpv-server` and `./build.sh rubyfpv-lenscam` build
`firmware/hi3516cv6xx_rubyfpv_h5svx-imx335-server/` and `…-lenscam/`.

Ports, all UDP:

| Port | Where | Carries |
| --- | --- | --- |
| 5600 | server, loopback | video into Ruby |
| 5602 | server, loopback | the server camera's own majestic video into `camswitch` |
| 5604 | server, Ethernet | the lens camera's video |
| 5606 | server, loopback | copies of the majestic API requests Ruby makes |
| 5607 | server, loopback | remote-control channel values from MSP_RC |
| 5610 | lens camera, Ethernet | commands from `camswitch` to `camlink` |

#### Server camera

Address 192.168.1.10. It runs Ruby as in the plain image, plus the stream
switch.

* `/etc/ruby_video_out` holds `udp://127.0.0.1:5602`. Patch 0012 makes Ruby
  set majestic's output to that address in place of 127.0.0.1:5600.
* `camswitch` passes one of the two streams on to Ruby. Its source is
  `scripts/camswitch.c` and `S72camswitch` starts it.
  * Before it switches, it asks the wanted camera for a keyframe and waits
    up to 1.5 s for one.
  * It rewrites RTP sequence numbers so they stay continuous.
  * If the lens camera's stream stops for 0.5 s, it falls back to the local
    stream.
* `/etc/ruby_msp_rc` enables patch 0013. Ruby then requests MSP_RC ten times
  a second and passes the channel values to `camswitch`.
* `/etc/camswitch.conf` sets the channels. Channel 1 is the first MSP_RC
  channel, and AUX1 is channel 5.

  | Key | Default | Meaning |
  | --- | --- | --- |
  | `CLIENT_IP` | 192.168.1.11 | the lens camera |
  | `SELECT_CH` | 7 | camera select channel |
  | `SELECT_ABOVE` | 1500 | the lens camera is shown above this value |
  | `ZOOM_CH` | 8 | zoom dial channel |
  | `ZOOM_MIN`, `ZOOM_MAX` | 1000, 2000 | dial range, wide end to tele end |
  | `FORCE` | unset | `remote` or `local`, for bench tests without a flight controller |

* `camswitch` sends the lens camera the zoom target, keyframe requests and
  the settings both encoders share. It reads those from
  `/etc/majestic.yaml` once a second. They are codec, size, frame rate,
  bitrate, GOP, QP delta, rate control mode, slice units, NAL size and
  sensor profile. It also repeats the encoder requests Ruby makes while
  running, such as adaptive bitrate.
* Picture controls from the ground station, `image.*` and `isp.exposure`,
  act on the camera being shown. While the lens camera is shown,
  `camswitch` keeps the file `/tmp/camswitch.remote`. Ruby then skips its
  own majestic and `camswitch` passes the request to the lens camera.
* `S72camswitch` clears majestic's `outgoing.servers` list at boot. This
  majestic adds each new `outgoing.server` to the list and never removes
  one. A leftover 127.0.0.1:5600 would give Ruby the picture twice.
* `/tmp/camswitch.status` shows the camera on screen, the channel values
  and counters.

The flight controller connects to UART0 as in the plain rubyfpv image.

#### Lens camera

Address 192.168.1.11. It is the lens variant without Ruby and without a
radio. `variants/…/lenscam/base` names `lens` as its base.

* `S73camlink` sets the address and points majestic's output at
  `udp://192.168.1.10:5604`. It clears the `outgoing.servers` list first.
* The address comes from the U-Boot variable `ipaddr`, which `S73camlink`
  sets to `OWN_IP`. The stock DHCP client falls back to that variable when
  no server answers. Stopping the DHCP client leaves the camera with no
  address.
* `S96camvideo` is a copy of `S95majestic`. A camera that once ran a Ruby
  image has `S95majestic` deleted in its settings partition, and that
  deletion survives an upgrade.
* `camlink` takes the server's commands on port 5610 and accepts them only
  from `SERVER_IP`. Its source is `scripts/camlink.c`.
* `camlink` writes changed settings with `cli` and reloads majestic.
* `/tmp/camlink.status` shows the zoom state and position.
* `/etc/camlink.conf`:

  | Key | Default | Meaning |
  | --- | --- | --- |
  | `OWN_IP` | 192.168.1.11 | this camera |
  | `SERVER_IP` | 192.168.1.10 | the server camera |
  | `ZOOM` | 1 | 0 turns zoom tracking off |
  | `ZOOM_TRAVEL_MS` | 8000 | motor time from the wide end to the tele end |
  | `OWN_MODE` | 0 | 1 keeps this camera's own video mode |
  | `MODE` | `1080p60` | `1080p60`, `1080p90`, `864p120`, `720p120` or `972p60`, used with `OWN_MODE=1` |

Zoom position. The lens board accepts no position command and reports no
position, so `camlink` counts motor run time. Full travel takes about 8 s,
measured in 250 ms steps from the picture statistics. At start, and each
time the dial is at minimum, `camlink` drives the zoom into the wide end
stop and resets the count. Positions repeated to about 0.2% in the picture
statistics. A zoom move from the web page is not counted until the dial next
reaches minimum.

Own video mode. With `OWN_MODE=1`, `S73camlink` sets resolution, frame rate
and sensor profile from `MODE`, and `camlink` ignores those three from the
server. Codec, bitrate and GOP still follow the server. The ground station's
decoder then sees a new resolution at each switch. That has not been tried.

#### Limits

* Ruby stores one set of picture values and applies it to its own camera at
  start. After a restart the server camera has the values set last,
  whichever camera they were set for.
* Flip, mirror, the IR filter and the noise reduction level are not passed
  to the lens camera.
* Ruby draws the OSD on the ground, so it is the same for both cameras.

#### Tests

* `work/2cam/test_camswitch.py` and `test_routing.py` run `camswitch` on the
  build host against two generated streams. They check switching, fallback,
  sequence numbers and the routing of picture controls.
* `work/2cam/test_lenscam.py` plays the server towards a real lens camera.
  The camera sent a keyframe 12 to 21 ms after a request, followed bitrate
  changes, and in own mode kept 1536x864 at 120 fps while the bitrate
  followed.

### Ruby controller on the Radxa Zero 3W

A stock controller does not know board type 33. `ground/rubyfpv-radxa/` has
the four patches the controller needs. They are 0001, 0002, 0009 and 0010.
Camera and controller must both run Ruby 11.8.

There are three ways to get the patched controller.

* Use `ruby_update_11.8_cv610.zip` from the release. Put it alone at the
  root of a USB stick and run the controller's normal USB update.
* `build-on-radxa.sh` builds Ruby 11.8 on the Radxa with
  `make all RUBY_BUILD_ENV=radxa`. With `--install` it backs up
  `/home/radxa/ruby/ruby_*` and replaces only the binaries already there.
  With `--usb` it also writes the update zip. The script stops if the
  installed version is not 11.8. Run it over ssh or in a terminal on the
  Radxa. It needs internet access for the source.
* `cross-build.sh` makes the same zip on an x86 Linux host.

The update zip is the official `ruby_update_11.8.zip`, checked by sha256,
with only its `bin/radxaz3/ruby_*` binaries replaced. `make-update-zip.py`
builds it.

`cross-build.sh` uses ARM GNU Toolchain 10.3-2021.07, the closest release
to the Radxa image's Debian GCC 10.2.1. The sysroot comes from the Ruby
Radxa image, which is Debian 11 with glibc 2.31, plus that image's versions
of the cairo, libdrm, gpiod, i2c and rockchip-mpp development packages. The
script sets Debian's defaults explicitly: PIE, GNU hash, build-id and
as-needed. Compared with the stock 11.8 Radxa binaries, all 18 programs
link the same libraries, have the same ELF type and sections, need no newer
glibc or libstdc++ symbol versions, and differ in size by less than 2%.

## Ground-station emulator

`tools/gs-emu.py` plays a Radxa Zero 3W ground station on a Linux host with
GStreamer. The camera streams RTP to the host over Ethernet. A relay models
the wfb-ng link: capacity from MCS, channel width and FEC, a 50 ms transmit
queue that drops packets when full, and optional loss. GStreamer decodes
the result. The tool switches modes as a ground-station menu does, with ssh
`cli` and SIGHUP for majestic and the HTTP API for waybeam. It points the
camera's `outgoing.server` at the host and restores it on exit.

```sh
tools/gs-emu.py --cam <camera-ip> --backend waybeam --list
tools/gs-emu.py --cam <camera-ip> --backend waybeam --sweep
tools/gs-emu.py --cam <camera-ip> --backend majestic --mode 720p120-crop --show
tools/gs-emu.py --synthetic --sweep          # no camera: x265 test clips
```

`--mcs 3 --width 40 --fec 8/12 --loss 2 --bitrate 7000` set the link and
the encoder. `--no-link` removes the capacity limit. For each mode the tool
reports decoded fps and size, video bitrate, drops, link queue delay as
average and 95th percentile, and decoder delay. It does not model the
RK3566 hardware decoder, FEC recovery or the display.

## Repository layout

```
build.sh                assembles common/ + devices/<device>/ (+ variant) and builds
common/                 files every image gets
devices/<device>/       defconfig, overlay, packages and excludes per image
variants/<device>/<v>/  files a variant lays over its device
ground/rubyfpv-radxa/   controller patches and build scripts
tools/                  kernel config generator, TFTP servers, ground-station emulator, helpers
work/                   test scripts, lens probes, serial and recovery helpers
archive/                superseded drafts
stock-firmware/         flash dumps of two cameras on stock firmware
FLASHING.md             flashing and recovery steps
```

`tools/make-fpv-kernel-config.py` derives the `-fpv` kernel config and
checks it against Kconfig.

## Open points

* The server image has never run on a camera. The two-camera setup is
  untested with two cameras, over the radio and with a flight controller.
* A switch between cameras with different resolutions is untested on the
  ground station's decoder.
* Telemetry input on UART2 in the lens variant is untested.
* SD recording is untested with a real card and a real flight controller.
* The `waybeam` image is built and not flashed. The `wfbng` image is not
  tested over the air.
* The cross-built controller update matches the stock binaries in the
  checks above. No installation on a Radxa is recorded.

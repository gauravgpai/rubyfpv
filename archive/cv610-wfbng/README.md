# OpenIPC wfb-ng air unit for Hi3516CV610 + IMX335

An OpenIPC/builder device target that turns a Hi3516CV610 + IMX335 camera into a
wfb-ng FPV air unit, with majestic as the streamer. It supersedes the drafts in
`../cv610-fpv-notes/patches/` (see "What changed from the drafts" below).

**Status: built, not booted.** The image builds (firmware b7c61c4, builder
71bc3d3, openipc/linux hisilicon-hi3516cv6xx 5.10.221,
majestic.hi3516cv6xx.lite of 2026-10-28) and passes both size checks, but has
not been run on a camera yet. A built copy is in `out/`.

## Files

```
build.sh                                     clone builder, drop the target in, build
tools/make-fpv-kernel-config.py              derives + Kconfig-checks the kernel config
devices/hi3516cv6xx_wfbng_generic-imx335/
  br-ext-chip-hisilicon/configs/hi3516cv6xx_wfbng_generic-imx335_defconfig
  br-ext-chip-hisilicon/board/hi3516cv6xx/hi3516cv6xx.generic-fpv.config
  general/overlay/usr/share/openipc/customizer.sh      first boot: latch sensor, 1080p30 flex mode
  general/overlay/etc/init.d/S98wifibroadcast-cv6xx    undoes wifibroadcast's SigmaStar defaults
  general/scripts/excludes/hi3516cv6xx_wfbng.list      drops other sensors + unused wireless modules
  general/package/msposd/msposd.mk                     shadows firmware's: cv6xx target, pinned source
  general/package/msposd/0001-Add-a-Hi3516CV610-CV608-cv6xx-backend.patch   the cv6xx OSD backend
  general/overlay/etc/wfb.yaml                         wfb-ng defaults with telemetry on ttyAMA1
```

## Why majestic, not Waybeam

Only the `lite` majestic is published for hi3516cv6xx (`fpv` and `ultimate` are
403 on S3). It is the same flavour the SigmaStar wfbng targets ship, and the
cv6xx binary carries every key wfb-ng drives: `.fpv`, `.outgoing` with `wfb`,
`video0.sliceUnits`, `rtsp.naluSize`, `/api/v1/set`, `/request/idr`. The one key
it lacks is `noiseLevel` (3DNR off), which wifibroadcast writes and majestic
will ignore.

Waybeam stays the fallback if majestic fails on hardware (step 4 below). Its
cv610 backend exists upstream but names only the IMX662, has no sensor FPS
unlock on cv610, and the OpenIPC package builds it for Infinity6E only. Using
it would mean adding IMX335 to that backend and a cv6xx variant of
`general/package/waybeam`.

## What the target changes, and why

| Change | Reason |
| --- | --- |
| Kernel: `WIRELESS`, `CFG80211=m`, `WIRELESS_EXT`, `WEXT_PRIV`, `FW_LOADER`, `WLAN` | The stock cv6xx kernel has all of them off; the Realtek USB drivers need cfg80211 and wireless extensions. Mirrors the ssc378qe_wfbng 5.10 kernel. |
| Kernel: `HOSTAP=m` | `WIRELESS_EXT`/`WEXT_PRIV` are hidden symbols; on this kernel HOSTAP is the only selector that needs no PCI/PCMCIA. The module itself is dropped by the excludes list. |
| Kernel: `CFG80211_CERTIFICATION_ONUS=y`, signed regdb off | Otherwise X.509/RSA/keyring get built in, eating into the 2 MiB the cv610 U-Boot reads. |
| `BR2_PACKAGE_RTL8812AU_OPENIPC`, `RTL88X2EU_OPENIPC`, `WIFIBROADCAST_NG`, `ADAPTIVE_LINK` | The air-unit stack, as on ssc338q_wfbng. |
| 16 MB NOR, split layout | IMX335 is filtered out of the 8 MB lite image, and the wfb stack does not fit there anyway. |
| libcurl: proxy, cookies, extra protocols off | As on every upstream defconfig. Left at their defaults, curl 8's configure fails looking for libldap. |
| msposd: cv6xx backend patch | wifibroadcast-ng selects msposd, whose `.mk` falls back to the SigmaStar build and cannot link on cv6xx. The patch adds a `cv6xx` target: msposd's Goke render path with the region calls moved to the SDK V5 `ss_mpi_rgn_*` API (one ARGB1555 overlay, handle 6, layer 7, on VENC channel 0). Source pinned to msposd 642faae, which the patch applies to. To go upstream as a PR to OpenIPC/msposd. |
| `wfb.yaml`: `serial: ttyAMA1` | The stock default `ttyS2` is a SigmaStar name; the cv610's PL011 UARTs are `ttyAMA0` (console) to `ttyAMA2`. Set this to whichever port your flight controller is wired to. |
| `S98wifibroadcast-cv6xx` | wifibroadcast's first-boot `video_settings` sets `isp.sensorConfig` to a SigmaStar `.bin`, 60 fps and 1920x1440 for IMX335. On cv6xx this hook puts back `/etc/sensors/modes/imx335_flex.ini`, 1920x1080, 30 fps. |

`tools/make-fpv-kernel-config.py` changes only those lines of the stock config and,
given a kernel source tree, resolves the result with kconfiglib and fails unless
every symbol above comes out as intended. Rerun it if you build against a newer
firmware whose stock `hi3516cv6xx.generic.config` has changed.

## Hardware assumptions

* Hi3516CV610 with 16 MB SPI NOR.
* IMX335 on MIPI, detected by `ipcinfo -s` as `imx335`.
* An RTL8812AU or RTL8812EU USB adapter on the USB host port.
* Frame rate: **30 fps**. That is the ceiling of the current cv6xx IMX335 driver.
  60/90/120 fps needs new sensor modes in openhisilicon (see the earlier notes).
* Memory: `load_hisilicon` assumes 64 MB DRAM / 32 MB OS when U-Boot has no
  `totalmem`/`osmem`, leaving 32 MB for video. 1080p30 should fit in that. On a
  128 MB die (CV610-20S/-20B) set `fw_setenv totalmem 128M` for more headroom.
  Don't set it on a 64 MB die.

## 1. Build (Linux or WSL2)

```bash
sudo apt-get install -y git make gcc g++ unzip bc bison flex rsync wget cpio file python3 libncurses-dev
./build.sh ~/openipc-builder
```

`build.sh` clones OpenIPC/builder, copies the target in (setting the exec bits that
a Windows checkout loses) and runs `builder.sh` with the firmware pinned to
b7c61c4. The first build downloads Buildroot, the toolchain and the kernel. The
image lands in `~/openipc-builder/archive/hi3516cv6xx_wfbng_generic-imx335/<timestamp>/`
as `openipc.hi3516cv6xx-nor-wfbng-split.tgz`.

Read the size lines the build prints. `firmware.bin` must fit, and
`uImage: [...KB/2048KB read by the bootloader]` must pass. If the kernel read check
fails, the uImage has outgrown what the vendor U-Boot reads. Don't just raise
`BR2_OPENIPC_NOR_KERNEL_READ_SIZE`: the camera's `bootcmd` has to read the larger
size too.

## 2. Flash

Have a UART console attached before the first flash (see the OpenIPC wiki pages on
flashing and serial pins).

* **Camera already on OpenIPC hi3516cv6xx:** copy the `.tgz` to `/tmp` and run
  `sysupgrade --archive=/tmp/openipc.hi3516cv6xx-nor-wfbng-split.tgz -n`. `-n` wipes
  the overlay so the first-boot scripts run. If the variant check refuses, add `--force_ver`.
* **Camera on vendor firmware:** install OpenIPC hi3516cv6xx ultimate first by the
  standard procedure, then do the above.

## 3. First boot checks (on the camera)

```
dmesg | grep -iE "cfg80211|8812|88x2"
lsmod | grep -E "cfg80211|88XXau|8812eu"
iw dev
ipcinfo -s
cli -g .isp.sensorConfig       # expect /etc/sensors/modes/imx335_flex.ini
logread | grep wifibroadcast
```

## 4. majestic acceptance test

This decides majestic vs Waybeam:

```
curl -s localhost/api/v1/config.json | jsonfilter -e '@.outgoing' -e '@.fpv' -e '@.video0'
curl -s 'localhost/api/v1/set?video0.bitrate=4000'
curl -s localhost/request/idr
```

On the ground station, the wfb-ng video should arrive at 1080p30 H.265. Bitrate
changes should take effect without the stream restarting (adaptive-link relies on
this). If `.outgoing` with `wfb` or the live `set` doesn't work on this lite build,
switch to the Waybeam route.

## 5. OSD test (msposd)

```
pidof msposd                      # started by wifibroadcast with router: msposd
killall msposd; msposd -b 115200 -c 8 -r 20 -m /dev/ttyAMA1 -o 127.0.0.1:14551 \
    -z $(cli -g .video0.size) -v   # verbose run in the foreground
cat /proc/umap/rgn                # the overlay should be listed on VENC chn 0
```

With no flight controller attached, msposd still draws its font preview and the
`/tmp/MSPOSD.msg` status line into the stream. If `RGN_Create` or
`RGN_AttachToChn` prints an error code, that code and `/proc/umap/rgn` are what
the backend needs to be adjusted against. If the UART is not muxed out on your
board, the port opens but stays silent; check the pin-mux before blaming msposd.

## What changed from the drafts in cv610-fpv-notes

* Kernel: the draft left `WIRELESS_EXT` and `FW_LOADER` off. Both Realtek packages
  require them, and `WIRELESS_EXT` can't be turned on with a config line alone.
  The draft also left signed regdb pulling in X.509/RSA.
* Kept as a builder device dir: the wifibroadcast fix-up is an init hook in the
  overlay, not a patch to firmware's shared script, so no firmware fork is needed.
* Excludes list added (other sensors' libraries, the HOSTAP-only modules).
* Waybeam: upstream does have a cv610 backend (IMX662 only), contrary to the
  earlier "SigmaStar only" reading of the firmware package.

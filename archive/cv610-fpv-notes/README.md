# OpenIPC FPV on Hi3516CV610 + IMX335: what has to change

Written 2026-10-28 against these checkouts (all included as zips in this folder):

| repo | commit | what it is |
|---|---|---|
| OpenIPC/firmware | b7c61c4 (2026-10-28) | Buildroot tree, SoC configs, packages (majestic, wifibroadcast-ng, rubyfpv, osdrv) |
| OpenIPC/builder | 71bc3d3 (2026-10-18) | Per-device FPV and Ruby build targets that overlay the firmware tree |
| RubyFPV/RubyFPV | HEAD as of 2026-10-19 | Ruby FPV source (the `backup/userland-master.zip` Raspberry Pi blob was left out of the zip) |

Everything in `patches/` is a draft I wrote by reading the code. None of it has been
compiled or flashed. Treat it as a starting point, not a release.

## Unpacking

Extract every `openipc-firmware-b7c61c4.partN.zip` into the same place; they all
contain a top-level `firmware/` folder and the parts just split the file list so
each zip stays under the transfer limit. Same for `rubyfpv-src.partN.zip`
(`RubyFPV/`). The builder is one zip (`builder/`).

If you have git on the machine, `git clone` of the three repos is the better way to
get an updatable tree; the zips are snapshots without history.

## Where things stand today

The cv6xx port exists in OpenIPC/firmware and is moving fast (IMX335 was added on
2026-10-18 in PR #2628, IMX662 in #2695, the split NOR image in #2638). What it does
not have is anything FPV:

* No `hi3516cv6xx_*` target in OpenIPC/builder, neither wfbng nor rubyfpv. The
  HiSilicon FPV targets there are hi3516ev200, hi3516ev300 and hi3536dv100 only.
* The cv6xx kernel (openipc/linux branch `hisilicon-hi3516cv6xx`, Linux 5.10.221)
  has `# CONFIG_WIRELESS is not set` and `# CONFIG_WLAN is not set`
  (`br-ext-chip-hisilicon/board/hi3516cv6xx/hi3516cv6xx.generic.config`). The
  defconfig comments say so outright and ask for it to be re-enabled. Without
  cfg80211 the RTL8812AU / RTL8812EU / RTL8733BU out-of-tree drivers that
  wfb-ng and Ruby both depend on cannot even be built.
* majestic for cv6xx is published in the "lite" flavor only
  (`BR2_OPENIPC_MAJESTIC` comment in `hi3516cv6xx_ultimate_defconfig`). Every other
  wfbng target uses `BR2_OPENIPC_MAJESTIC="fpv"`. majestic is closed source, so
  whether the lite cv6xx binary honours `.fpv.enabled`, `.outgoing.wfb`,
  `.video0.noiseLevel`, `.video0.sliceUnits`, `.rtsp.naluSize` and live
  bitrate/gop changes via `localhost/api/v1/set` is unknown until someone runs it.
  This is the one item you cannot fix from the repos; it needs the OpenIPC
  majestic maintainers to publish an fpv (or ultimate) cv6xx build.
* IMX335 on cv6xx is "ultimate only" and 30 fps. `hisilicon-opensdk.mk` filters
  `sony_imx335` out of the lite build because the 8 MB squashfs slot is already at
  "0KB left", and the mode presets that ship
  (`general/package/hisilicon-osdrv-hi3516cv6xx/files/sensor/config/modes/`) are
  `imx335_1520p.ini` (2592x1520 @30), `imx335_flex.ini` (1920x1080 @30) and
  `imx335_full10.ini` (2592x1944 @40). The install comment says these are "the
  ones the T6 crop timing actually reaches, not high fps". The 1080p55 / 720p120
  presets that FPV builds use on hi3516ev300 live in the V4 sensor driver
  (`hisilicon-osdrv-hi3516ev200/files/sensor/config/high-fps/`) and have not been
  ported to the V5 driver in openhisilicon (`libraries/sensor/hi3516cv6xx/sony_imx335`).
* 5 MP IMX335 needs `osmem=64M`. On a 64 MB DDR die (Hi3516CV610-10B) that leaves
  nothing for the MMZ video pool, so you need a 128 MB variant (20S / 20B with
  in-package DDR3, or 00S / 00B with external DDR). 1080p "flex" mode may be fine
  on 32 M osmem; untested.
* Flash: the cv610 vendor U-Boot reads a fixed 2048K kernel slot and the firmware
  Makefile notes the 16 MiB kernel already overruns it on master. OpenIPC's answer
  is the "split" NOR layout (`general/scripts/post-image-split.sh`): one
  `firmware.bin` = uImage padded to 64 KiB + squashfs, written at the firmware
  partition start, with the kernel splitting it at boot via mtdsplit. Your U-Boot
  `bootcmd` must `sf read` enough bytes to cover the whole kernel, not 0x200000.
  Use a 16 MB NOR module; 8 MB is out for FPV + IMX335.

Hardware side, the good news: Hi3516CV610 is a dual Cortex-A7 at 950 MHz (community
spec sheets; I could not pull the official datasheet), the kernel config enables
`CONFIG_USB_XHCI_PLATFORM`, so a USB Realtek dongle has a host port, and the
encoder does 4K@20 / 5MP@30 H.265 with an 80 Mbit cap. That is comfortably ahead of
the Goke v200 that Ruby dropped as "single core".

## The change list

### Shared by wfb-ng and Ruby (OpenIPC/firmware and builder)

1. Kernel: turn on the wireless stack. `patches/firmware/0001-hi3516cv6xx-kernel-enable-cfg80211.patch`
   sets `CONFIG_WIRELESS=y`, `CONFIG_CFG80211=m`, `CONFIG_WLAN=y` with all in-tree
   vendors off (the Realtek drivers are out-of-tree). The full resulting file is
   also included as `hi3516cv6xx.generic-fpv.config` inside both builder device
   dirs, which is how the hi3516ev300 wfbng target does it (its own
   `*.generic-fpv.config` under `devices/common/.../board/`). Buildroot runs
   `olddefconfig`, so the fragment approach is fine, but check `make linux-menuconfig`
   once to confirm nothing else gets pulled in. Watch the uImage size against the
   kernel slot afterwards.

2. Realtek drivers: `BR2_PACKAGE_RTL8812AU_OPENIPC=y` (openipc/realtek-wlan,
   branch `rtl8812au_fpv`) and `BR2_PACKAGE_RTL88X2EU_OPENIPC=y`
   (libc0607/rtl88x2eu-20230815). Both are plain `kernel-module` packages built
   against `$(LINUX_DIR)`. They compile on 5.10 for other SoCs; expect nothing
   worse than a few API warnings on 5.10.221.

3. Builder device target. `patches/builder/devices/hi3516cv6xx_wfbng_generic/`
   is a complete draft: defconfig (ultimate cv6xx config minus the IP-camera
   extras like divinus, mosquitto, wireguard, zerotier, uacme, motors; plus
   adaptive-link, wifibroadcast-ng, both Realtek drivers), the kernel config, and a
   first-boot `customizer.sh`. Copy the directory into your builder checkout and
   run `./builder.sh hi3516cv6xx_wfbng_generic`. builder.sh clones
   OpenIPC/firmware HEAD, copies the device dir over it, then `make BOARD=...`.
   Set `OPENIPC_FW_REPO` to your fork if you carry the firmware patches below.

4. wifibroadcast script. `patches/firmware/0002-wifibroadcast-hisilicon-sensor-profile.patch`
   fixes two SigmaStar assumptions in `general/package/wifibroadcast-ng/files/wifibroadcast`:
   `video_settings()` does `cli -s .isp.sensorConfig /etc/sensors/<sensor>_<family>.bin`
   (the `.bin` presets only exist for infinity6c/6e) and forces `video0.fps 60` and
   `1920x1440` for IMX335. On HiSilicon cv6xx it now points at
   `/etc/sensors/modes/imx335_flex.ini`, 1920x1080, 30 fps. Everything else in that
   script (driver detection by USB id, `iw ... set monitor none`, wfb_tx/rx,
   msposd/mavfwd, alink) is SoC-agnostic. `start_telemetry` has one `ssc33x` devmem
   poke that is correctly skipped on other chips.

5. majestic. Either get a cv6xx "fpv" flavor published to
   `https://openipc.s3-eu-west-1.amazonaws.com/majestic.hi3516cv6xx.fpv.master.tar.bz2`
   and set `BR2_OPENIPC_MAJESTIC="fpv"`, or validate the lite binary key by key.
   First test on hardware: `cli -s .outgoing.server udp://127.0.0.1:5600`,
   `cli -s .fpv.enabled true`, then check `wfb_tx` receives RTP and that
   `curl 'localhost/api/v1/set?video0.bitrate=4000'` changes the stream without a
   restart. If `.outgoing.wfb` is ignored, adaptive-link will not work.

6. IMX335 frame rate. If 30 fps is not acceptable, the work is in openhisilicon
   `libraries/sensor/hi3516cv6xx/sony_imx335/` (new register tables for a 1080p
   crop at 55-60 fps and 720p at 90-120, like the V4 driver's
   `imx335_1920x1080_55fps.ini` and `imx335_1280x720_120fps.ini`) plus matching
   `modes/*.ini` profiles. That is real sensor bring-up, with a scope on the MIPI
   lines or at least `cat /proc/umap/isp` / `vi` stats to confirm the timing.

7. Memory and bootargs. `fw_setenv osmem 64M` (and `set_allocator cma`) on a 128 MB
   part; `load_hisilicon` reads `osmem`/`totalmem` from U-Boot env or the hisi_mem
   sysfs node and sizes MMZ from the remainder. The `customizer.sh` draft leaves this
   commented because it depends on which cv610 die you have.

### Ruby only

8. Builder target `patches/builder/devices/hi3516cv6xx_rubyfpv_generic/`: same as the
   wfbng one but `BR2_OPENIPC_VARIANT="rubyfpv"`, `BR2_PACKAGE_RUBYFPV=y`,
   `BR2_PACKAGE_LIBPCAP=y`, no wifibroadcast-ng/adaptive-link. The rubyfpv.mk in
   firmware builds `make vehicle RUBY_BUILD_ENV=openipc` from RubyFPV HEAD with the
   target toolchain. Ruby's ssc338q image is built with a glibc toolchain
   (`arm-openipc-linux-gnueabihf`, 4.9 headers); cv6xx is musl + 5.10 headers +
   GCC 13. I grepped Ruby for the usual musl breakers (execinfo/backtrace,
   `__GLIBC__`, `malloc_trim`, `mallinfo`, `error.h`) and found none in the vehicle
   code paths, only `_GNU_SOURCE` defines, so it should compile. Expect `-Werror`-ish
   noise from GCC 13 that the Makefile's `-Wno-stringop-truncation` may not cover.

9. Ruby source `patches/rubyfpv/0001-rubyfpv-add-hi3516cv610-board-type.patch`:
   adds `BOARD_TYPE_OPENIPC_HISILICON_CV610 = 50`, matches `hi3516cv6` from
   `ipcinfo -c` in `_hardware_detect_board_openipc()`, counts it as OpenIPC in
   `hardware_board_is_openipc()`, adds `hardware_board_is_hisilicon_cv6()` and
   display strings. Without this a cv610 falls through to the default
   `BOARD_TYPE_OPENIPC_GOKE200`, and Ruby then disables adaptive bitrate / keyframe
   control and force-restarts majestic on every bitrate change (`models.cpp` ~2892,
   `video_sources.cpp` ~619).

   Deliberately NOT done in the patch: the cv610 is neither "goke" nor "sigmastar"
   in Ruby's gating functions. That means adaptive video stays enabled (good), but
   the SigmaStar-only paths are skipped: CPU/VENC clock boosts
   (`/sys/venc/ven_clock`, cpufreq min 800 MHz in `hardware.cpp` ~2087 and ~2293),
   no-restart shutter changes (`video_sources.cpp` ~610), the Thinker/RTL8733BU
   subtype detection in `r_start_vehicle.cpp` ~659, and the per-board TX power
   tables in `tx_powers.cpp` ~138. Each of those needs a cv610 decision once you
   can measure on the board. Ruby's OTA also only ships `bin/ssc338q/`
   (`config_file_names.h` line 89), so cv610 units cannot take Ruby OTA updates
   until a second folder and a musl build are added to the release process.

10. `tweaksys` (first-boot script in the firmware's rubyfpv package)
    `patches/firmware/0003-rubyfpv-tweaksys-hi3516cv6xx.patch`: adds a
    `hi3516cv610 | hi3516cv608` case (basic + streamer + finish) and a
    `majestic_hisilicon_cv6()` that selects the IMX335 flex profile, h265,
    1080p30, cbr, and `udp://127.0.0.1:5600` out. The console is PL011
    (`ttyAMA0`), so Ruby's default telemetry port name matches without the
    SigmaStar `ttyS0` rewrite.

11. Petru Soroaga reviews board support personally (README: "contact us"), so plan
    on a PR to RubyFPV with 9 plus a builder PR with 8 and 10 if you want this in an
    official release rather than a private fork.

## Suggested order of work

Kernel + Realtek driver first (items 1-2), on the stock ultimate image: if
`modprobe 8812eu` loads and `iw dev wlan0 set monitor none` works, half the risk is
gone. Then the wfbng builder target (3-4) with the lite majestic and the key-by-key
check (5). Only then decide on Ruby (8-10), since it inherits every one of the
shared items and adds the toolchain and OTA questions. IMX335 high-fps (6) is a
separate track that can run in parallel if 30 fps is a blocker for you.

## File map

```
cv610-fpv-notes/
  README.md                                   this file
  patches/
    firmware/
      0001-hi3516cv6xx-kernel-enable-cfg80211.patch
      0002-wifibroadcast-hisilicon-sensor-profile.patch
      0003-rubyfpv-tweaksys-hi3516cv6xx.patch
    builder/devices/
      hi3516cv6xx_wfbng_generic/
        br-ext-chip-hisilicon/configs/hi3516cv6xx_wfbng_generic_defconfig
        br-ext-chip-hisilicon/board/hi3516cv6xx/hi3516cv6xx.generic-fpv.config
        general/overlay/usr/share/openipc/customizer.sh
      hi3516cv6xx_rubyfpv_generic/
        br-ext-chip-hisilicon/configs/hi3516cv6xx_rubyfpv_generic_defconfig
        br-ext-chip-hisilicon/board/hi3516cv6xx/hi3516cv6xx.generic-fpv.config
    rubyfpv/
      0001-rubyfpv-add-hi3516cv610-board-type.patch
openipc-firmware-b7c61c4.part1..4.zip        OpenIPC/firmware @ b7c61c4, no .git
openipc-builder-71bc3d3.zip                  OpenIPC/builder @ 71bc3d3, no .git
rubyfpv-src.part1..2.zip                     RubyFPV @ 2026-10-19, no .git, no backup/
```

Apply the firmware patches from inside `firmware/` with `git apply ../cv610-fpv-notes/patches/firmware/*.patch`
(or `patch -p1 <` if the tree is from the zip). The Ruby patch applies the same way inside `RubyFPV/`.

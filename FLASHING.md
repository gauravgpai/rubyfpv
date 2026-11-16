# Flashing: Hi3516CV610 + IMX335 camera and Ruby controller

Files on the USB stick (`cv610-fpv-firmware/`):

| What | Where |
|---|---|
| Camera images | `hi3516cv6xx_<variant>_h5svx-imx335/` (`rubyfpv`, `wfbng`, `waybeam`) |
| Camera image for the zoom-lens camera | `hi3516cv6xx_rubyfpv_h5svx-imx335-lens/` (CRC32 eaf3d69b; see README, "lens" variant; runs on camera 2 since 2026-11-13 with autofocus; upgrade a running camera with `sysupgrade --archive=` and the .tgz, separate kernel/rootfs files are refused) |
| Two-camera setup, camera with radio and flight controller | `hi3516cv6xx_rubyfpv_h5svx-imx335-server/` (CRC32 7f9b3f77; see README, two-camera setup; not yet run on a camera) |
| Two-camera setup, lens camera (192.168.1.11, no Ruby) | `hi3516cv6xx_rubyfpv_h5svx-imx335-lenscam/` (CRC32 16080c0c, 10560 KB; boots unattended on camera 2 since 2026-11-13: address, video, camlink)  |
| Ruby controller update | `ruby_update_11.8_cv610.zip` |
| Controller build scripts | `rubyfpv-radxa-controller/` |
| Stock camera flash dumps (16 MB each) | `../backup-hi3516cv610-stock firmware.bin` (camera 1), `../backup-hi3516cv610-stock-camera2 firmware.bin` (camera 2, CRC32 8e0801bc) |

Each camera folder has `openipc.hi3516cv6xx-nor-<variant>-split.tgz` (for
sysupgrade), `firmware.bin` (for U-Boot), `uImage`, `rootfs.squashfs` and
`md5sums.txt`.

For RubyFPV, flash **both** sides: the camera with the `rubyfpv` image and the
Radxa with `ruby_update_11.8_cv610.zip`. Both are Ruby 11.8 with the same
CV610 patch. A stock controller doesn't know the CV610 board type.

## 1. Camera via sysupgrade (camera already runs OpenIPC)

**Prefer section 2 (U-Boot) for this camera.** On 2026-11-05 a sysupgrade
from the wfbng image to rubyfpv left the flash scrambled from 0x820000 on
(our own image data at growing offsets), and the camera panicked at boot with
"Unable to mount root fs". The cause is not known. The U-Boot method below
checks every write by reading it back.

From a PC on the camera's network (camera at 192.168.1.10):

```bash
cd hi3516cv6xx_rubyfpv_h5svx-imx335
md5sum -c md5sums.txt
scp openipc.hi3516cv6xx-nor-rubyfpv-split.tgz root@192.168.1.10:/tmp/
ssh root@192.168.1.10 sysupgrade --archive=/tmp/openipc.hi3516cv6xx-nor-rubyfpv-split.tgz -n
```

* `-n` clears the settings overlay so the first-boot scripts run (needed
  when changing variant, e.g. wfbng to rubyfpv).
* If sysupgrade refuses because the variant differs from the running one, add
  `--force_ver`.
* Don't power off while it writes; it reboots by itself (about 2 to 3 min).
* On Windows, use the same commands in PowerShell (OpenSSH is built in).

## 2. Camera via U-Boot (recommended; also recovery)

Needs a 3.3 V UART adapter on the camera's debug pads (115200 8N1), the camera
on Ethernet, and a TFTP server on the PC serving the image folder. No root is
needed on the PC: run the bundled server on port 6969 and point U-Boot at it.

```bash
python3 tools/tftpd.py hi3516cv6xx_rubyfpv_h5svx-imx335 6969
```

1. Power on (or `reboot` over ssh) and press Ctrl+C in the serial console to
   stop at `OpenIPC #`.
2. Note the image's size and CRC32 (the current rubyfpv image: 0xa40000 bytes,
   CRC32 4540fcd0, with SD card recording on arm, 64 MB for Linux, high-res timers, the exposure fix, 864p120 / 10 Mbit/s defaults, the 1 ms video wait, the IR-cut pulse fix, CV610 shutter handling, 864p and renice/taskset; `python3 -c "import zlib;d=open('firmware.bin','rb').read();print(hex(len(d)),'%08x'%zlib.crc32(d))"`).
3. Flash (replace `<pc-ip>` and `<size>`; 0x42000000 and 0x43000000 are RAM,
   which starts at 0x40000000 on this board):

```
setenv serverip <pc-ip>
setenv tftpdstp 6969
tftpboot 0x42000000 firmware.bin
crc32 0x42000000 <size>
sf probe 0
sf erase 0x50000 <size>
sf write 0x42000000 0x50000 <size>
sf read 0x43000000 0x50000 <size>
crc32 0x43000000 <size>
reset
```

* Both `crc32` lines must print the image's CRC. If the second one differs,
  run the erase and write again before `reset`.
* `firmware.bin` is the kernel (uImage) followed by the squashfs, a multiple
  of 64 KiB. Written at 0x50000, it ends exactly where the settings partition
  starts, so the settings (root password, ssh keys, majestic changes) are
  kept. U-Boot (0x0) and its env (0x40000) are not touched. `setenv` without
  `saveenv` changes nothing permanently.
* Once only, when the camera ran a rubyfpv image built before 0004 (before
  2026-11-06 afternoon): Ruby had copied its binaries into the settings
  partition, and those copies hide the new ones. After the first boot run
  `rm /overlay/root/usr/sbin/ruby_*; reboot` over ssh.
* The rubyfpv image reboots once by itself on its first boot: it sets
  `extras=osmem=64M` in the U-Boot env so Linux gets 64 MB (needed with the
  Wi-Fi adapter). The env survives later flashes, so this happens only once.
* To also clear the settings (first boot from scratch), erase the rest of the
  flash after the write: `sf erase <0x50000 + size> <0xfb0000 - size>` (for
  the current image: `sf erase 0xa90000 0x570000`). Never write past
  `<size>`: anything beyond the image lands in the settings partition, and
  jffs2 then refuses to mount it.
* Without Ethernet: `loady 0x42000000` and send `firmware.bin` with YMODEM
  from the serial terminal (about 16 minutes at 115200), then continue from
  the first `crc32`.

**Back to stock firmware (last resort):** the 16 MB dump replaces everything,
U-Boot included, so only use it if the stock U-Boot is wanted back:
copy it into the TFTP folder as `stock.bin`, then `tftpboot 0x42000000
stock.bin`, `sf probe 0`, `sf erase 0 0x1000000`, `sf write 0x42000000 0
0x1000000`, and check it with `sf read` + `crc32` as above before `reset`.
A failed write here needs an SPI flash programmer to recover.

## 2a. A camera still on stock firmware (backup, then convert)

Done on the second camera on 2026-11-11. Needs the UART adapter, Ethernet to
the PC, and [defib](https://github.com/OpenIPC/defib) (not on PyPI:
`pip install git+https://github.com/OpenIPC/defib` in a venv; on the build PC
it is in `work/defib-venv`).

1. Start defib, then power-cycle the camera. It loads the OpenIPC bootloader
   into RAM over the chip's boot ROM; the flash is not touched. The chip needs
   its variant (`hi3516cv610` alone has no image):

   ```bash
   defib burn -c hi3516cv610:20s -p /dev/ttyUSB0 -b
   ```

2. Back up the whole flash from the `OpenIPC #` prompt. `tools/tftpd_rw.py`
   takes uploads (the plain `tftpd.py` is read-only) and prints the CRC32 of
   what it received, which must match the camera's:

   ```bash
   python3 tools/tftpd_rw.py <folder> 6969
   ```
   ```
   sf probe 0
   sf read 0x42000000 0 0x1000000
   crc32 0x42000000 0x1000000
   setenv serverip <pc-ip>; setenv tftpdstp 6969
   tftpput 0x42000000 0x1000000 stock.bin
   ```

   Note the factory `ethaddr` (`printenv ethaddr`) while the stock env is
   still loaded.

3. Write the bootloader (`~/.cache/defib/firmware/boot-hi3516cv610-20s-nor.bin`,
   0x32000 bytes, as `boot.bin`) and the image, checking each `crc32` against
   the file's:

   ```
   tftpboot 0x42000000 boot.bin;      crc32 0x42000000 0x32000
   tftpboot 0x43000000 firmware.bin;  crc32 0x43000000 <size>
   sf erase 0 0x1000000
   sf write 0x42000000 0 0x32000
   sf write 0x43000000 0x50000 <size>
   sf read 0x45000000 0 0x32000;       crc32 0x45000000 0x32000
   sf read 0x45000000 0x50000 <size>;  crc32 0x45000000 <size>
   reset
   ```

4. Stop at the prompt once more and put the factory MAC back, then `reset`:
   `setenv ethaddr <factory mac>; saveenv`. Do NOT `saveenv` from the
   RAM-loaded bootloader before the first reset without `env default -a`
   first: it still holds the stock environment (stock `bootcmd`), and the
   camera then stops at the prompt instead of booting.

The first boot sets `extras=osmem=64M`, runs Ruby's setup and reboots once by
itself. The camera then answers at 192.168.1.10 with the default OpenIPC
login; set a root password and add your ssh key.

## 3. Ruby controller (Radxa Zero 3W)

The controller must already run Ruby 11.8. If it shows an older version, update
it to 11.8 first with the official `ruby_update_11.8.zip` from the RubyFPV
GitHub releases, the same way as below.

1. FAT32 USB stick with `ruby_update_11.8_cv610.zip` in the **root folder**,
   and no other `ruby_update*.zip` on the stick.
2. Plug it into the Radxa, then Menu > Controller > Update > Update from USB.
3. Wait until it says it's done and reboots.
4. Check: Menu > Controller shows version 11.8. After pairing with the CV610
   camera, the vehicle's board shows as "OpenIPC HiSilicon CV610".

To undo, run the same update with the official `ruby_update_11.8.zip`.

Alternative without the zip: copy `rubyfpv-radxa-controller/` to the Radxa
and run `./build-on-radxa.sh --install` over ssh (needs internet; builds on
the Radxa, backs up the old binaries, prints the undo command).

## 4. First boot checks (camera, over ssh)

```bash
devmem 0x1102034C; devmem 0x11014580                    # equal
grep -E "lane_id|img_width|crc_err" /proc/umap/mipi_rx   # 0,2  2592  0
lsmod | grep -E "8812eu|88XXau"
pidof majestic ruby_start ruby_rt_vehicle               # rubyfpv image
```

The first boot of the rubyfpv image runs Ruby's setup (`Preparing system
tweaks for hi3516cv613...`; this SoC reports itself as CV613) and reboots once
by itself. Ruby needs an RTL8812EU/AU USB Wi-Fi adapter on the camera; without
one, `/tmp/logs/log_errors.txt` says "No 2.4/5.8 radio modules found".

Ruby takes over the radio, so pair from the controller: it finds the camera
on its own when both run 11.8 on the same band.

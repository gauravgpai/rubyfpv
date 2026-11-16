# Flashing the Hi3516CV610 + IMX335 camera and the Ruby controller

## Files

The built images are attached to the
[releases](https://github.com/gauravgpai/rubyfpv/releases). `./build.sh`
writes the same folders to `firmware/`.

| File | For | `firmware.bin` size | CRC32 |
| --- | --- | --- | --- |
| `hi3516cv6xx_rubyfpv_h5svx-imx335.zip` | RubyFPV camera | 0xa40000 | 4540fcd0 |
| `hi3516cv6xx_rubyfpv_h5svx-imx335-lens.zip` | RubyFPV camera with the zoom lens | 0xa40000 | eaf3d69b |
| `hi3516cv6xx_rubyfpv_h5svx-imx335-server.zip` | two-camera setup, camera with the radio | 0xa40000 | 7f9b3f77 |
| `hi3516cv6xx_rubyfpv_h5svx-imx335-lenscam.zip` | two-camera setup, lens camera | 0xa50000 | 16080c0c |
| `hi3516cv6xx_wfbng_h5svx-imx335.zip` | wfb-ng with majestic | 0xa4a000 | 4c8143b3 |
| `hi3516cv6xx_waybeam_h5svx-imx335.zip` | wfb-ng with waybeam | 0x8dc000 | 1077ddb0 |
| `ruby_update_11.8_cv610.zip` | Ruby controller on the Radxa Zero 3W | | |

Each camera zip holds three files.

* `openipc.hi3516cv6xx-nor-<variant>-split.tgz` is for `sysupgrade`.
* `firmware.bin` is for U-Boot. It is the kernel followed by the root
  filesystem.
* `md5sums.txt` lists the checksums of the kernel and root filesystem.

Print the size and CRC32 of a `firmware.bin` with:

```bash
python3 -c "import zlib;d=open('firmware.bin','rb').read();print(hex(len(d)),'%08x'%zlib.crc32(d))"
```

For RubyFPV, flash both sides. The camera gets a `rubyfpv` image and the
Radxa gets `ruby_update_11.8_cv610.zip`. A stock controller does not know
the CV610 board type.

## Flash layout

16 MB SPI NOR. RAM starts at 0x40000000.

| Offset | Content |
| --- | --- |
| 0x0 | U-Boot |
| 0x40000 | U-Boot environment |
| 0x50000 | `firmware.bin`: kernel, then root filesystem |
| 0x50000 + image size | settings partition, to the end of the flash |

The settings partition starts where the image ends. It holds the root
password, ssh keys and every changed file under `/etc`.

## What you need

* A computer on the camera's Ethernet network. The camera answers at
  192.168.1.10 when no DHCP server replies. The lens camera of the
  two-camera setup uses 192.168.1.11.
* For sections 2 and 3, a USB serial adapter on the camera's UART0 pads at
  115200 8N1, and Python 3 for the bundled TFTP servers.
* For section 3, [defib](https://github.com/OpenIPC/defib). It is not on
  PyPI. Install it in a virtual environment with
  `pip install git+https://github.com/OpenIPC/defib`.

The TFTP servers in `tools/` run on port 6969 and need no root rights.
`tftpd.py` serves files only. `tftpd_rw.py` also takes uploads and prints
the CRC32 of each file it receives.

## 1. Camera that already runs OpenIPC: sysupgrade

```bash
md5sum -c md5sums.txt
scp openipc.hi3516cv6xx-nor-rubyfpv-split.tgz root@192.168.1.10:/tmp/
ssh root@192.168.1.10 sysupgrade --archive=/tmp/openipc.hi3516cv6xx-nor-rubyfpv-split.tgz -n
```

* `-n` clears the settings partition so the first-boot scripts run. Use it
  when you change variant, for example from wfbng to rubyfpv. Leave it out
  to keep the settings.
* Add `--force_ver` if `sysupgrade` refuses because the variant differs.
* This layout accepts only `--archive`. `sysupgrade` refuses separate
  kernel and rootfs files.
* Do not cut power while it writes. The camera reboots by itself after 2 to
  3 minutes.
* The same commands work in PowerShell on Windows.

One `sysupgrade` from the wfbng image to rubyfpv left the flash scrambled
from 0x820000 on, and the camera stopped at boot with "Unable to mount root
fs". The cause is unknown. Later upgrades between the rubyfpv variants
worked. `sysupgrade` does not read back what it wrote. The U-Boot method in
section 2 does, so keep the serial adapter within reach.

## 2. Camera with OpenIPC U-Boot: TFTP and `sf write`

Use this when `sysupgrade` failed, when the camera does not boot, or when
you want every write verified.

Serve the image folder:

```bash
python3 tools/tftpd.py hi3516cv6xx_rubyfpv_h5svx-imx335 6969
```

1. Power the camera on, or run `reboot` over ssh. Press Ctrl+C in the serial
   console to stop at the `OpenIPC #` prompt.
2. Look up the size and CRC32 of the image in the table above.
3. Flash. Replace `<host-ip>` with the TFTP server's address and `<size>`
   with the image size.

```
setenv serverip <host-ip>
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

Both `crc32` lines must print the image's CRC32. If the second one differs,
repeat the erase and the write before `reset`.

Notes:

* These commands leave U-Boot, its environment and the settings partition
  alone. `setenv` without `saveenv` changes nothing permanently.
* Never write more than `<size>` bytes. Anything past the image lands in the
  settings partition, and jffs2 then refuses to mount it.
* To clear the settings as well, erase the rest of the flash after the
  write with `sf erase <0x50000 + size> <0xfb0000 - size>`. For a 0xa40000
  image that is `sf erase 0xa90000 0x570000`.
* `sf erase` takes whole 64 KiB blocks. The rubyfpv images are a multiple
  of 64 KiB. For the wfbng and waybeam images, round the erase length up to
  the next multiple of 0x10000 and keep `<size>` for the write and the
  `crc32` lines.
* An image of a different size moves the start of the settings partition.
  Clear the settings when the size changes.
* Without Ethernet, run `loady 0x42000000` and send `firmware.bin` with
  YMODEM from the serial terminal. That takes about 16 minutes at 115200.
  Continue from the first `crc32`.
* A camera with the zoom lens board attached does not receive what the
  adapter sends. Unplug the lens board first.

After the first boot:

* A rubyfpv image reboots once by itself. It sets `extras=osmem=64M` in the
  U-Boot environment so Linux gets 64 MB. The environment survives later
  flashes, so this happens once per camera.
* If the camera ran a rubyfpv image built without patch 0004, Ruby copied
  its binaries into the settings partition and those copies hide the new
  ones. Run `rm /overlay/root/usr/sbin/ruby_*; reboot` over ssh once.

## 3. Camera on stock firmware: back up, then convert

1. Start defib, then power-cycle the camera. defib loads the OpenIPC
   bootloader into RAM through the SoC's boot ROM and does not touch the
   flash. Name the chip variant, because `hi3516cv610` alone has no image.

   ```bash
   defib burn -c hi3516cv610:20s -p /dev/ttyUSB0 -b
   ```

2. Back up the whole flash from the `OpenIPC #` prompt. Start the upload
   server on the computer:

   ```bash
   python3 tools/tftpd_rw.py <folder> 6969
   ```

   Then on the camera:

   ```
   sf probe 0
   sf read 0x42000000 0 0x1000000
   crc32 0x42000000 0x1000000
   setenv serverip <host-ip>; setenv tftpdstp 6969
   tftpput 0x42000000 0x1000000 stock.bin
   ```

   The CRC32 the server prints must match the camera's. Run
   `printenv ethaddr` and note the factory MAC address while the stock
   environment is still loaded.

3. Write the bootloader and the image. defib keeps the bootloader at
   `~/.cache/defib/firmware/boot-hi3516cv610-20s-nor.bin`, 0x32000 bytes.
   Copy it into the TFTP folder as `boot.bin`. Check each `crc32` against
   the file's.

   ```
   tftpboot 0x42000000 boot.bin;      crc32 0x42000000 0x32000
   tftpboot 0x43000000 firmware.bin;  crc32 0x43000000 <size>
   sf erase 0 0x1000000
   sf write 0x42000000 0 0x32000
   sf write 0x43000000 0x50000 <size>
   sf read 0x45000000 0 0x32000;       crc32 0x45000000 0x32000
   sf read 0x45000000 0x50000 <size>;  crc32 0x45000000 <size>
   ```

4. Reset the environment and restore the MAC address, then restart.

   ```
   env default -a
   setenv ethaddr <factory mac>
   saveenv
   reset
   ```

   The bootloader loaded into RAM still holds the stock environment.
   `saveenv` without `env default -a` stores the stock `bootcmd`, and the
   camera then stops at the prompt and does not boot.

The first boot sets `extras=osmem=64M`, runs Ruby's setup and reboots once
by itself. The camera then answers at 192.168.1.10 with the default OpenIPC
login. Set a root password and add your ssh key.

## 4. Back to stock firmware

A full 16 MB dump replaces everything, U-Boot included. Use the backup you
made of that same camera in section 3, because the last partitions hold
that camera's identity. `stock-firmware/` has the dumps of two cameras and
their partition layout.

Copy the dump into the TFTP folder as `stock.bin`, stop at the prompt and
run:

```
tftpboot 0x42000000 stock.bin
crc32 0x42000000 0x1000000
sf probe 0
sf erase 0 0x1000000
sf write 0x42000000 0 0x1000000
sf read 0x43000000 0 0x1000000
crc32 0x43000000 0x1000000
reset
```

Both `crc32` lines must match the dump's CRC32 before `reset`. If the write
fails and the camera loses power, defib can still load a bootloader into
RAM as in section 3.

## 5. Ruby controller on the Radxa Zero 3W

The controller must already run Ruby 11.8. If it shows an older version,
update it first with the official `ruby_update_11.8.zip` from the RubyFPV
releases, in the same way.

1. Put `ruby_update_11.8_cv610.zip` in the root folder of a FAT32 USB
   stick. Keep no other `ruby_update*.zip` on the stick.
2. Plug the stick into the Radxa and select Menu > Controller > Update >
   Update from USB.
3. Wait until the controller reports that it is done and reboots.
4. Check that Menu > Controller shows version 11.8. After pairing, the
   vehicle's board shows as "OpenIPC HiSilicon CV610".

To undo, run the same update with the official `ruby_update_11.8.zip`.

Without the zip, copy `ground/rubyfpv-radxa/` to the Radxa and run
`./build-on-radxa.sh --install` over ssh. It needs internet access, builds
on the Radxa, backs up the old binaries and prints the undo command.

## 6. First-boot checks on the camera

```bash
devmem 0x1102034C; devmem 0x11014580                    # equal
grep -E "lane_id|img_width|crc_err" /proc/umap/mipi_rx   # 0,2  2592  0
lsmod | grep -E "8812eu|88XXau"
pidof majestic ruby_start ruby_rt_vehicle               # rubyfpv images
```

* The first boot of a rubyfpv image prints
  `Preparing system tweaks for hi3516cv613...` and reboots once. The SoC
  reports itself as CV613.
* Ruby needs an RTL8812EU or RTL8812AU adapter on the camera. Without one,
  `/tmp/logs/log_errors.txt` says "No 2.4/5.8 radio modules found", Ruby
  does not start majestic, and the web interface on port 80 does not load.
* Ruby controls the radio. Pair from the controller. It finds the camera
  when both run 11.8 on the same band.

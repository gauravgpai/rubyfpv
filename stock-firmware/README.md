# Stock firmware dumps

Full 16 MB SPI NOR dumps of two H5SVX-class cameras, read with `sf read`
before the cameras were converted to OpenIPC. FLASHING.md section 3 shows
how to make such a dump and section 4 how to write one back.

| File | CRC32 |
| --- | --- |
| `stock-camera1.bin` | 7346163e |
| `stock-camera2.bin` | 8e0801bc |

Layout, from the stock `bootargs`:

| Offset | Size | Partition |
| --- | --- | --- |
| 0x0 | 256K | uboot |
| 0x40000 | 64K | env |
| 0x50000 | 13952K | rootfs, squashfs |
| 0xDF0000 | 2M | data, jffs2 |
| 0xFF0000 | 64K | devinfo |

`uboot` and `rootfs` are byte-identical in both dumps. `env`, `data` and
`devinfo` differ. They hold each camera's own MAC address, cloud ID and
configuration, so write a dump back only to the camera it came from.

The firmware is the camera vendor's. It is kept here for reference and for
restoring these two cameras.

#!/bin/sh

# This image is built for one sensor. Latching it skips load_hisilicon's
# probe (a module load/unload cycle on every cold boot until it succeeds).
[ -z "$(fw_printenv -n sensor 2>/dev/null)" ] && fw_setenv sensor imx335

# The stream settings (unix://rtp_local for wfb_tx, 1920x1080@30 cropped from
# the 2592x1944 capture, 8 Mbit/s) ship in /etc/waybeam.json; change them with
# json_cli or http://<camera>/api/v1/set?<key>=<value>.

# No upgrade URL: no release of this target is published. Point it at your
# own build before using sysupgrade.

exit 0

#!/bin/sh

# This image is built for one sensor. Latching it skips load_hisilicon's
# probe (a module load/unload cycle on every cold boot until it succeeds).
[ -z "$(fw_printenv -n sensor 2>/dev/null)" ] && fw_setenv sensor imx335

# The cv6xx IMX335 driver reaches 30 fps at most; flex is its 1920x1080 mode.
# S98wifibroadcast-cv6xx puts these back after wifibroadcast's first-boot
# defaults, which are written for SigmaStar.
cli -s .isp.sensorConfig /etc/sensors/modes/imx335_flex.ini
cli -s .video0.size 1920x1080
cli -s .video0.fps 30

# No upgrade URL: no release of this target is published. Point it at your
# own build before using sysupgrade, e.g.
# fw_setenv upgrade 'https://github.com/<you>/builder/releases/download/latest/hi3516cv6xx_wfbng_generic-imx335-nor.tgz'

exit 0

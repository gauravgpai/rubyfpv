#!/bin/sh

# This image is built for one sensor. Latching it skips load_hisilicon's
# probe (a module load/unload cycle on every cold boot until it succeeds).
[ -z "$(fw_printenv -n sensor 2>/dev/null)" ] && fw_setenv sensor imx335

# The board wires IMX335 to two MIPI lanes. Profiles in /etc/sensors:
#   imx335_2l_1080p60.ini / _1080p90                1920x1080 crop
#   imx335_2l_864p120.ini                           1536x864 crop
#   imx335_2l_720p120.ini                           1296x720 crop (size 1280x720)
#   imx335_2l_bin972p60.ini                         1296x972 2x2 binning
#   imx335_i2c_5M.ini                               2592x1944@30
# Set video0.size and video0.fps to match the profile. S98wifibroadcast-cv6xx
# puts these back after wifibroadcast's first-boot defaults (SigmaStar).
cli -s .isp.sensorConfig /etc/sensors/imx335_2l_1080p60.ini
cli -s .video0.size 1920x1080
cli -s .video0.fps 60

# IR-cut filter: GPIO 1 and GPIO 9 (stock hw.cfg, confirmed on the board).
cli -s .nightMode.irCutPin1 1
cli -s .nightMode.irCutPin2 9

# No upgrade URL: no release of this target is published. Point it at your
# own build before using sysupgrade.

exit 0

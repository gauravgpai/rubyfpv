#!/bin/sh
# First-boot customizer for the hi3516cv6xx wfbng build (DRAFT, untested).
# Runs once from the OpenIPC init; see other builder devices for the convention.

# IMX335 on cv6xx: majestic auto-picks /etc/sensors/imx335_i2c_5M.ini (5 MP, RAW12,
# 30 fps). For FPV the 1080p "flex" preset is the lighter mode. Both are 30 fps on
# the current openhisilicon V5 driver; there is no 60 fps IMX335 timing for cv6xx yet.
if [ "$(ipcinfo -s 2>/dev/null)" = "imx335" ]; then
	cli -s .isp.sensorConfig /etc/sensors/modes/imx335_flex.ini
	cli -s .video0.size 1920x1080
	cli -s .video0.fps 30
fi

# 5 MP / 1080p60 later needs osmem=64M, which only the 128 MB DDR die variants
# (cv610-20S / 20B, or 00S/00B with external DDR) can spare. Leave 32M on 64 MB parts.
# fw_setenv osmem 64M

# Point sysupgrade at your own builder release once you publish one
# fw_setenv upgrade 'https://github.com/<you>/builder/releases/download/latest/hi3516cv6xx_wfbng_generic-nor.tgz'

exit 0

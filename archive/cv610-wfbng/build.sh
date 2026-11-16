#!/bin/bash
# Build the hi3516cv6xx wfb-ng (IMX335) image with OpenIPC/builder.
# Runs on Linux (Ubuntu 22.04/24.04 or WSL2), not on Windows directly.
#
# usage: ./build.sh [path to a builder checkout]   (cloned there if missing)
#
# The firmware tree is pinned to the commit the kernel config was derived from
# and checked against. Override with OPENIPC_FW_REV=<ref> to build newer HEAD;
# if the stock hi3516cv6xx.generic.config changed there, regenerate the -fpv
# config first with tools/make-fpv-kernel-config.py.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
builder=${1:-$here/builder}
device=hi3516cv6xx_wfbng_generic-imx335

[ -d "$builder/.git" ] || git clone https://github.com/OpenIPC/builder.git "$builder"
rm -rf "$builder/devices/$device"
cp -a "$here/devices/$device" "$builder/devices/"
# Files written on Windows carry no exec bit; rcS runs init scripts as `$i start`.
chmod 755 "$builder/devices/$device/general/overlay/etc/init.d/S98wifibroadcast-cv6xx" \
	"$builder/devices/$device/general/overlay/usr/share/openipc/customizer.sh"

cd "$builder"
OPENIPC_FW_REV=${OPENIPC_FW_REV:-b7c61c4aecf405a2dd76ea11262c32788470636e} ./builder.sh "$device"

#!/bin/bash
# Build the Hi3516CV610 + IMX335 (2-lane) FPV images on Linux.
#
# usage: ./build.sh [wfbng|waybeam|rubyfpv|rubyfpv-lens|rubyfpv-server|rubyfpv-lenscam|all]  (default: all)
#
#   wfbng    hi3516cv6xx_wfbng_h5svx-imx335    majestic + wfb-ng
#   waybeam  hi3516cv6xx_waybeam_h5svx-imx335  waybeam  + wfb-ng
#   rubyfpv  hi3516cv6xx_rubyfpv_h5svx-imx335  majestic + RubyFPV vehicle
#   rubyfpv-lens  the rubyfpv device plus variants/<device>/lens/: the camera
#            with the UART zoom/focus lens module (telemetry in on UART2,
#            lens control from the web interface). Not part of `all`.
#   rubyfpv-server   two-camera setup, the camera with the radio and the
#            flight controller: stream switch, camera select and zoom
#            dial from MSP remote-control channels. Not part of `all`.
#   rubyfpv-lenscam  two-camera setup, the lens camera (variant "lens" plus
#            "lenscam"): no Ruby, video over Ethernet to the server,
#            zoom position tracking. Not part of `all`.
#
# A variant is the device with variants/<device>/<variant>/general/ laid over
# it, and its late-post-build-hooks.append added to OpenIPC's hook list; the
# image goes to <device>-<variant>/. The base device's own image is not touched.
#
# Each device is common/ with devices/<device>/ laid over it. The steps are
# builder.sh's (extra packages, device files over the firmware tree, make),
# except that the firmware checkout is reset to the pinned commit rather than
# re-cloned, so Buildroot's download cache survives, and `make clean` runs
# first, so nothing one variant installed leaks into the other.
#
# Environment:
#   BUILDER         OpenIPC/builder checkout   (default ~/openipc-builder, cloned if missing)
#   OPENIPC_FW_REV  firmware commit            (default b7c61c4, what the patches are made against)
#   OUT             where images are collected (default ./firmware)
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
builder=${BUILDER:-$HOME/openipc-builder}
fw=$builder/openipc
rev=${OPENIPC_FW_REV:-b7c61c4aecf405a2dd76ea11262c32788470636e}
out=${OUT:-$here/firmware}

case "${1:-all}" in
	wfbng) devices="hi3516cv6xx_wfbng_h5svx-imx335" ;;
	waybeam) devices="hi3516cv6xx_waybeam_h5svx-imx335" ;;
	rubyfpv) devices="hi3516cv6xx_rubyfpv_h5svx-imx335" ;;
	rubyfpv-lens) devices="hi3516cv6xx_rubyfpv_h5svx-imx335+lens" ;;
	rubyfpv-server) devices="hi3516cv6xx_rubyfpv_h5svx-imx335+server" ;;
	rubyfpv-lenscam) devices="hi3516cv6xx_rubyfpv_h5svx-imx335+lenscam" ;;
	all) devices="hi3516cv6xx_wfbng_h5svx-imx335 hi3516cv6xx_waybeam_h5svx-imx335 hi3516cv6xx_rubyfpv_h5svx-imx335" ;;
	*) echo "usage: $0 [wfbng|waybeam|rubyfpv|rubyfpv-lens|rubyfpv-server|rubyfpv-lenscam|all]" >&2; exit 1 ;;
esac

[ -d "$builder/.git" ] || git clone https://github.com/OpenIPC/builder.git "$builder"
[ -d "$fw/.git" ] || git clone https://github.com/OpenIPC/firmware.git "$fw"
git -C "$fw" cat-file -e "$rev^{commit}" 2>/dev/null || git -C "$fw" fetch -q origin

for item in $devices; do
	device=${item%%+*}
	variant=""; image=$device
	case "$item" in *+*) variant=${item#*+}; image=$device-$variant ;; esac
	echo "=== $image"
	stage=$builder/devices/$device
	rm -rf "$stage"
	mkdir -p "$stage"
	cp -a "$here/common/." "$here/devices/$device/." "$stage/"
	# A variant may name a parent in its `base` file; the parent is laid first.
	vlist=""
	if [ -n "$variant" ]; then
		v=$here/variants/$device/$variant
		[ -d "$v/general" ] || { echo "no variant $v" >&2; exit 1; }
		[ -f "$v/base" ] && vlist=$(tr -d ' \r\n' < "$v/base")
		vlist="$vlist $variant"
		for one in $vlist; do
			[ -d "$here/variants/$device/$one/general" ] || { echo "no variant $one" >&2; exit 1; }
			cp -a "$here/variants/$device/$one/general/." "$stage/general/"
		done
		chmod 755 "$stage"/general/scripts/*.sh
		find "$stage/general/overlay/usr/sbin" "$stage/general/overlay/var/www/cgi-bin" \
			-type f -exec chmod 755 {} + 2>/dev/null || true
	fi
	# A checkout made on Windows carries no exec bits; rcS runs `$i start`.
	chmod 755 "$stage"/general/overlay/etc/init.d/* \
		"$stage/general/overlay/usr/share/openipc/customizer.sh"

	# Pristine firmware tree at the pinned commit; output/ (Buildroot, the
	# download cache, the host tools) is kept.
	git -C "$fw" reset -q --hard "$rev"
	git -C "$fw" clean -qfd -e /output

	# builder.sh copy_extra_packages
	cp -af "$builder"/package/* "$fw/general/package/"
	for p in "$builder"/package/*; do
		name=$(basename "$p")
		grep -Fq "$name" "$fw/general/package/Config.in" ||
			printf 'source "$BR2_EXTERNAL_GENERAL_PATH/package/%s/Config.in"\n' "$name" \
				>> "$fw/general/package/Config.in"
	done

	cp -af "$stage"/* "$fw/"
	# A variant's post-build step: OpenIPC sets its own post-build script and
	# runs the hooks this list names, after the overlay is in place.
	for one in $vlist; do
		[ -f "$here/variants/$device/$one/late-post-build-hooks.append" ] || continue
		grep -v '^#' "$here/variants/$device/$one/late-post-build-hooks.append" \
			>> "$fw/general/scripts/late-post-build-hooks.list"
	done

	# The firmware Makefile derives its paths from $(PWD), which `make -C`
	# does not update, so run it from the tree.
	log=$out/$image/build.log
	mkdir -p "$out/$image"
	(cd "$fw" && make clean)
	if ! (cd "$fw" && make BOARD="$device") > "$log" 2>&1; then
		tail -40 "$log"
		echo "=== $image FAILED, full log: $log" >&2
		exit 1
	fi
	(cd "$fw" && make BOARD="$device" size-report) >> "$log" 2>&1 || true

	# Split layout: the -split.tgz is what sysupgrade takes; firmware.bin is
	# uImage + squashfs back to back, for flashing at the firmware offset.
	rm -f "$out/$image"/openipc.* "$out/$image"/uImage "$out/$image"/rootfs.squashfs \
		"$out/$image"/firmware.bin "$out/$image"/sizes.*
	cp -a "$fw"/output/images/openipc.*.tgz "$fw"/output/images/uImage \
		"$fw"/output/images/rootfs.squashfs "$fw"/output/images/firmware.bin "$out/$image/"
	cp -a "$fw"/output/images/sizes.*.json "$out/$image/" 2>/dev/null || true
	(cd "$out/$image" && md5sum openipc.*.tgz firmware.bin uImage rootfs.squashfs > md5sums.txt)
	grep -E "^firmware.bin:|^- firmware.bin|^- uImage" "$log" | tail -3 || true
	echo "=== $image done: $out/$image"
done

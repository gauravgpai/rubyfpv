#!/bin/sh
# Buildroot post-build step of the "lens" variant ($1 is the target tree).
# Done at build time so nothing has to be changed on the camera, where an
# edited file in the settings partition would hide a later image's version.
set -e
T=$1

# 1. No login prompt on the serial console: ttyAMA0 is the lens module's
#    port, and what the module sends would be typed into the prompt.
grep -q '^console::respawn:/sbin/getty' "$T/etc/inittab"
sed -i 's|^console::respawn:/sbin/getty.*|# lens variant: the serial console is the lens port, no getty on it|' "$T/etc/inittab"

# 2. "Zoom and focus" in the web interface's Camera menu.
H=$T/var/www/cgi-bin/p/header.cgi
P=$T/var/www/cgi-bin/p/pages.cgi
grep -q 'href="camera.cgi"' "$H"
sed -i '/<li><a class="dropdown-item" href="camera.cgi">/a\
							<li><a class="dropdown-item" href="lens.cgi"><% page_label lens %></a></li>' "$H"
grep -q 'href="lens.cgi"' "$H"

grep -q '	camera)         printf' "$P"
sed -i '/	camera)         printf/a\
	lens)           printf '"'"'%s'"'"' "Zoom and focus" ;;' "$P"
sed -i 's/	camera|counting|usb|stream-urls|raw|config)/	camera|lens|counting|usb|stream-urls|raw|config)/' "$P"
grep -q 'camera|lens|counting' "$P"



# 3. lensaf, the autofocus feeder (scripts/lensaf.c): built here against the
#    vendor ISP library already in the target tree. It needs the libraries
#    majestic uses, since libot_mpi_isp.so has undefined symbols of its own.
O=$(dirname "$T")
CC=$(ls "$O"/host/bin/arm-*-gcc | head -1)
SDK=$(ls -d "$O"/build/hisilicon-opensdk-*/ | head -1)
[ -x "$CC" ] && [ -d "$SDK" ]
"$CC" -O2 -Wall \
	-I"$SDK/libraries/isp/include/hi3516cv6xx" -I"$SDK/kernel/include/hi3516cv6xx" \
	-I"$SDK/libraries/isp/include/hi3516cv6xx/ext_inc" \
	"$(dirname "$0")/lensaf.c" -o "$T/usr/sbin/lensaf" \
	-L"$T/usr/lib" -Wl,--no-as-needed -lss_mpi_isp -lot_mpi_isp -lss_mpi -lss_mpi_sysmem \
	-lss_mpi_sysbind -lsecurec -ldrc -lacs -lldci -ldehaze -lextend_stats -lbnr -lcalcflicker \
	-lir_auto -lss_mpi_ae -lss_mpi_awb -Wl,--allow-shlib-undefined -Wl,-rpath-link,"$T/usr/lib"
chmod 755 "$T/usr/sbin/lensaf"

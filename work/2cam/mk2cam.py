#!/usr/bin/env python3
"""mk2cam.py - run from ~/cv610-fpv: Ruby patches 0012/0013, the "server" and
"lenscam" variants, and variant inheritance in build.sh."""
import os, re, shutil, subprocess, sys, tempfile

SRC = "/home/hwt/openipc-builder/openipc/output/build/rubyfpv-1c2365f212135d408eca55e3a6084a255afeb8e8"
DEV = "hi3516cv6xx_rubyfpv_h5svx-imx335"
PKG = f"devices/{DEV}/general/package/rubyfpv"
VAR = f"variants/{DEV}"
WORK = "work/2cam"


def mkpatch(rel, edit, name, header):
    old = open(f"{SRC}/{rel}", encoding="utf-8", errors="surrogateescape").read()
    new = edit(old)
    assert new != old, rel
    d = tempfile.mkdtemp()
    for side, text in (("a", old), ("b", new)):
        os.makedirs(os.path.dirname(f"{d}/{side}/{rel}"), exist_ok=True)
        open(f"{d}/{side}/{rel}", "w", encoding="utf-8", errors="surrogateescape").write(text)
    diff = subprocess.run(["diff", "-u", f"a/{rel}", f"b/{rel}"], cwd=d, capture_output=True).stdout.decode("utf-8", "surrogateescape")
    diff = re.sub(r"^(--- a/\S+)\t.*$", r"\1", diff, flags=re.M)
    diff = re.sub(r"^(\+\+\+ b/\S+)\t.*$", r"\1", diff, flags=re.M)
    open(f"{PKG}/{name}", "w", encoding="utf-8", errors="surrogateescape").write(header + "---\n" + diff)
    shutil.rmtree(d)
    print(name, diff.count("\n"), "lines")


def rep(s, a, b):
    assert s.count(a) == 1, (s.count(a), a[:60])
    return s.replace(a, b)


# ---- 0012: majestic output address from a file, API requests mirrored ----
def edit_maj(s):
    s = rep(s, '   _execute_maj_command_wait("cli -s .outgoing.server udp://127.0.0.1:5600");\n', '''   {
      // An image may put a stream switch between majestic and Ruby: it names
      // the address majestic sends to in /etc/ruby_video_out.
      char szOut[128];
      char szOutComm[200];
      strcpy(szOut, "udp://127.0.0.1:5600");
      FILE* fdOut = fopen("/etc/ruby_video_out", "r");
      if ( NULL != fdOut )
      {
         char szLine[128];
         szLine[0] = 0;
         if ( NULL != fgets(szLine, sizeof(szLine), fdOut) )
         {
            int n = strlen(szLine);
            while ( (n > 0) && ((szLine[n-1] == '\\n') || (szLine[n-1] == '\\r') || (szLine[n-1] == ' ')) )
               szLine[--n] = 0;
            if ( 0 == strncmp(szLine, "udp://", 6) )
               strcpy(szOut, szLine);
         }
         fclose(fdOut);
      }
      snprintf(szOutComm, sizeof(szOutComm), "cli -s .outgoing.server %s", szOut);
      _execute_maj_command_wait(szOutComm);
   }
''')
    s = rep(s, '''   snprintf(szRequest, sizeof(szRequest)/sizeof(szRequest[0]), "GET %s HTTP/1.0\\r\\n\\r\\n", szTmp);
''', '''   snprintf(szRequest, sizeof(szRequest)/sizeof(szRequest[0]), "GET %s HTTP/1.0\\r\\n\\r\\n", szTmp);

   // With a stream switch in place, tell it about run-time encoder changes
   // (UDP 127.0.0.1:5606) so a second camera can follow them.
   if ( access("/etc/ruby_video_out", R_OK) == 0 )
   {
      int iMirror = socket(AF_INET, SOCK_DGRAM, 0);
      if ( iMirror >= 0 )
      {
         struct sockaddr_in addrMirror;
         memset(&addrMirror, 0, sizeof(addrMirror));
         addrMirror.sin_family = AF_INET;
         addrMirror.sin_port = htons(5606);
         addrMirror.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
         sendto(iMirror, szTmp, strlen(szTmp), 0, (struct sockaddr*)&addrMirror, sizeof(addrMirror));
         close(iMirror);
      }
   }
''')
    return s


mkpatch("code/base/hardware_cam_maj.cpp", edit_maj, "0012-openipc-video-out-from-file-and-api-mirror.patch", """From: cv610-fpv
Subject: [PATCH] OpenIPC: majestic output address from /etc/ruby_video_out

For a two-camera setup a stream switch sits between majestic and Ruby. The
image names the address majestic sends to in /etc/ruby_video_out (one line,
udp://host:port); Ruby still reads 127.0.0.1:5600. With the file present,
the majestic API requests Ruby makes at run time (bitrate, GOP, QP) are also
sent as datagrams to 127.0.0.1:5606, so the switch can repeat them to the
second camera. Without the file nothing changes.
""")


# ---- 0013: MSP_RC polling, channels to UDP 127.0.0.1:5607 ----
def edit_msp(s):
    s = rep(s, '#include "../base/msp.h"\n', '''#include "../base/msp.h"
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>

// Remote-control channels for an image that wants them (/etc/ruby_msp_rc):
// MSP_RC (105) is requested 10 times a second and the answer, 16-bit
// little-endian channel values, goes to UDP 127.0.0.1:5607.
#define MSP_CMD_RC_CHANNELS 105
static int s_iMSPRCEnabled = -1;
static u32 s_uMSPLastRequestRCTime = 0;
static int s_iMSPRCSocket = -1;
''')
    s = rep(s, '''   if ( g_TimeNow >= s_uMSPLastRequestBatteryInfoTime + 500 )
   {
''', '''   if ( s_iMSPRCEnabled < 0 )
      s_iMSPRCEnabled = (access("/etc/ruby_msp_rc", R_OK) == 0) ? 1 : 0;
   if ( s_iMSPRCEnabled && (g_TimeNow >= s_uMSPLastRequestRCTime + 100) )
   {
      s_uMSPLastRequestRCTime = g_TimeNow;
      _send_msp_to_fc(MSP_CMD_RC_CHANNELS, NULL, 0);
   }

   if ( g_TimeNow >= s_uMSPLastRequestBatteryInfoTime + 500 )
   {
''')
    s = rep(s, '''   switch ( s_uMSPCommand )
   {
      case MSP_CMD_STATUS:
''', '''   switch ( s_uMSPCommand )
   {
      case MSP_CMD_RC_CHANNELS:
         if ( s_iMSPCommandPayloadSize >= 2 )
         {
            if ( s_iMSPRCSocket < 0 )
               s_iMSPRCSocket = socket(AF_INET, SOCK_DGRAM, 0);
            if ( s_iMSPRCSocket >= 0 )
            {
               struct sockaddr_in addrRC;
               memset(&addrRC, 0, sizeof(addrRC));
               addrRC.sin_family = AF_INET;
               addrRC.sin_port = htons(5607);
               addrRC.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
               sendto(s_iMSPRCSocket, s_uMSPCommandPayload, s_iMSPCommandPayloadSize, MSG_DONTWAIT, (struct sockaddr*)&addrRC, sizeof(addrRC));
            }
         }
         break;

      case MSP_CMD_STATUS:
''')
    return s


mkpatch("code/r_vehicle/telemetry_msp.cpp", edit_msp, "0013-openipc-msp-rc-channels-to-udp.patch", """From: cv610-fpv
Subject: [PATCH] OpenIPC: MSP remote-control channels to a local UDP port

With /etc/ruby_msp_rc present, Ruby also asks the flight controller for
MSP_RC ten times a second and passes the channel values to UDP
127.0.0.1:5607, where an image's own program (camera select, zoom) reads
them. Without the file nothing changes.
""")

# ---- variants ----
def put(path, text, mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", newline="\n").write(text)
    os.chmod(path, mode)


S = f"{VAR}/server"
put(f"{S}/late-post-build-hooks.append", "BR2_PACKAGE_RUBYFPV:scripts/post-build-server.sh\n")
shutil.copy(f"{WORK}/camswitch.c", f"{S}/general/scripts/camswitch.c") if os.path.isdir(f"{S}/general/scripts") else (os.makedirs(f"{S}/general/scripts"), shutil.copy(f"{WORK}/camswitch.c", f"{S}/general/scripts/camswitch.c"))
put(f"{S}/general/scripts/post-build-server.sh", '''#!/bin/sh
# Buildroot post-build step of the "server" variant ($1 is the target tree):
# builds camswitch, the two-camera stream switch (scripts/camswitch.c).
set -e
T=$1
O=$(dirname "$T")
CC=$(ls "$O"/host/bin/arm-*-gcc | head -1)
[ -x "$CC" ]
"$CC" -O2 -Wall "$(dirname "$0")/camswitch.c" -o "$T/usr/sbin/camswitch"
chmod 755 "$T/usr/sbin/camswitch"
''', 0o755)
put(f"{S}/general/overlay/etc/ruby_video_out", "udp://127.0.0.1:5602\n")
put(f"{S}/general/overlay/etc/ruby_msp_rc", "1\n")
put(f"{S}/general/overlay/etc/camswitch.conf", '''# Two-camera server: this camera has the radio and the flight controller.
# Restart to apply (/etc/init.d/S72camswitch restart).

# The second camera (lens camera), reached over Ethernet.
CLIENT_IP=192.168.1.11

# Camera select: remote-control channel number (1 = first channel of MSP_RC,
# so AUX1 is 5). Above SELECT_ABOVE the second camera is shown.
SELECT_CH=7
SELECT_ABOVE=1500

# Zoom dial: channel number, and the channel values for fully out and fully in.
ZOOM_CH=8
ZOOM_MIN=1000
ZOOM_MAX=2000

# Bench test without a flight controller: FORCE=remote or FORCE=local.
#FORCE=local
''')
put(f"{S}/general/overlay/etc/init.d/S72camswitch", '''#!/bin/sh
#
# Two-camera stream switch (see /etc/camswitch.conf). Must run before Ruby
# starts majestic, which sends its video to the switch in this image.
#

case "$1" in
	start)
		start-stop-daemon -S -b -q -x /usr/sbin/camswitch
		;;
	stop)
		start-stop-daemon -K -q -x /usr/sbin/camswitch
		;;
	restart)
		"$0" stop; sleep 1; "$0" start
		;;
	*)
		echo "Usage: $0 {start|stop|restart}"
		exit 1
		;;
esac
''', 0o755)

L = f"{VAR}/lenscam"
put(f"{L}/base", "lens\n")
put(f"{L}/late-post-build-hooks.append", "BR2_PACKAGE_RUBYFPV:scripts/post-build-lenscam.sh\n")
os.makedirs(f"{L}/general/scripts", exist_ok=True)
shutil.copy(f"{WORK}/camlink.c", f"{L}/general/scripts/camlink.c")
put(f"{L}/general/scripts/post-build-lenscam.sh", '''#!/bin/sh
# Buildroot post-build step of the "lenscam" variant ($1 is the target tree),
# after the "lens" variant's own step.
set -e
T=$1
O=$(dirname "$T")
CC=$(ls "$O"/host/bin/arm-*-gcc | head -1)
[ -x "$CC" ]

# 1. camlink: zoom position tracking and settings from the server camera.
"$CC" -O2 -Wall "$(dirname "$0")/camlink.c" -o "$T/usr/sbin/camlink"
chmod 755 "$T/usr/sbin/camlink"

# 2. This camera has no radio and does not run Ruby: S73camlink sets it up
#    and the stock S95majestic starts the video.
rm -f "$T/etc/init.d/S73ruby" "$T/etc/ruby_serial_port"
[ -f "$T/etc/init.d/S95majestic" ]
''', 0o755)
put(f"{L}/general/overlay/etc/camlink.conf", '''# Second camera of the two-camera setup (lens camera, no radio).
# Reboot to apply.

# This camera's address on the Ethernet link, and the server camera's.
OWN_IP=192.168.1.11
SERVER_IP=192.168.1.10

# Zoom from the server's dial: 1 on, 0 off. ZOOM_TRAVEL_MS is the motor run
# time from fully out to fully in (measured at about 8 s on the H5SVX lens).
ZOOM=1
ZOOM_TRAVEL_MS=8000
''')
put(f"{L}/general/overlay/etc/lens.conf", '''# Zoom/focus lens module of the "lenscam" image variant. Reboot to apply.

# Lens module: Pelco-D on the camera's wired UART, as the stock firmware
# drives it (PTZProtocol=PelcoD, PTZBaudRate=57600, Address=1).
LENS_PORT=/dev/ttyAMA0
LENS_BAUD=57600
LENS_ADDR=1

# Autofocus: 1 = send the lens board the picture's sharpness (lensaf), so it
# focuses by itself, also after a zoom. 0 = manual focus only.
LENS_AF=1

# No flight controller on this camera: the alarm-input pad is left alone.
UART2_RX=none
UART2_TX=none
''')
put(f"{L}/general/overlay/etc/init.d/S73camlink", '''#!/bin/sh
#
# "lenscam" variant: second camera of a two-camera setup. No radio and no
# Ruby here; the video goes over Ethernet to the server camera, which also
# sends the zoom target and the encoder settings (camlink).
#

[ -f /etc/camlink.conf ] && . /etc/camlink.conf
OWN_IP=${OWN_IP:-192.168.1.11}
SERVER_IP=${SERVER_IP:-192.168.1.10}

want() {	# want <key> <value>: write a majestic setting only if it differs
	[ "$(cli -g "$1" 2>/dev/null)" = "$2" ] || cli -s "$1" "$2"
}

case "$1" in
	start)
		ifconfig eth0 "$OWN_IP" netmask 255.255.255.0 up

		want .outgoing.enabled true
		want .outgoing.server "udp://$SERVER_IP:5604"
		want .video0.enabled true
		want .video0.codec h265
		want .video0.rcMode cbr
		want .video1.enabled false
		want .isp.slowShutter disabled
		want .rtsp.enabled false
		want .hls.enabled false
		want .netip.enabled false
		want .jpeg.enabled false
		want .watchdog.enabled false

		start-stop-daemon -S -b -q -x /usr/sbin/camlink
		;;
	stop)
		start-stop-daemon -K -q -x /usr/sbin/camlink
		;;
	*)
		echo "Usage: $0 {start|stop}"
		exit 1
		;;
esac
''', 0o755)

# ---- build.sh: variant inheritance + names ----
b = open("build.sh").read()
m = re.search(r'\tif \[ -n "\$variant" \]; then\n\t\tv=\$here/variants/\$device/\$variant\n.*?\n\tfi\n', b, flags=re.S)
assert m
b = b.replace(m.group(0), '''	# A variant may name a parent in its `base` file; the parent is laid first.
	vlist=""
	if [ -n "$variant" ]; then
		v=$here/variants/$device/$variant
		[ -d "$v/general" ] || { echo "no variant $v" >&2; exit 1; }
		[ -f "$v/base" ] && vlist=$(tr -d ' \\r\\n' < "$v/base")
		vlist="$vlist $variant"
		for one in $vlist; do
			[ -d "$here/variants/$device/$one/general" ] || { echo "no variant $one" >&2; exit 1; }
			cp -a "$here/variants/$device/$one/general/." "$stage/general/"
		done
		chmod 755 "$stage"/general/scripts/*.sh
		find "$stage/general/overlay/usr/sbin" "$stage/general/overlay/var/www/cgi-bin" \\
			-type f -exec chmod 755 {} + 2>/dev/null || true
	fi
''')
m = re.search(r'\tif \[ -n "\$variant" \] && \[ -f "\$here/variants/\$device/\$variant/late-post-build-hooks.append" \]; then\n.*?\n\tfi\n', b, flags=re.S)
assert m
b = b.replace(m.group(0), '''	for one in $vlist; do
		[ -f "$here/variants/$device/$one/late-post-build-hooks.append" ] || continue
		grep -v '^#' "$here/variants/$device/$one/late-post-build-hooks.append" \\
			>> "$fw/general/scripts/late-post-build-hooks.list"
	done
''')
b = rep(b, '\trubyfpv-lens) devices="hi3516cv6xx_rubyfpv_h5svx-imx335+lens" ;;\n',
        '\trubyfpv-lens) devices="hi3516cv6xx_rubyfpv_h5svx-imx335+lens" ;;\n'
        '\trubyfpv-server) devices="hi3516cv6xx_rubyfpv_h5svx-imx335+server" ;;\n'
        '\trubyfpv-lenscam) devices="hi3516cv6xx_rubyfpv_h5svx-imx335+lenscam" ;;\n')
b = b.replace('[wfbng|waybeam|rubyfpv|rubyfpv-lens|all]', '[wfbng|waybeam|rubyfpv|rubyfpv-lens|rubyfpv-server|rubyfpv-lenscam|all]')
b = rep(b, '#            lens control from the web interface). Not part of `all`.\n',
        '#            lens control from the web interface). Not part of `all`.\n'
        '#   rubyfpv-server   two-camera setup, the camera with the radio and the\n'
        '#            flight controller: stream switch, camera select and zoom\n'
        '#            dial from MSP remote-control channels. Not part of `all`.\n'
        '#   rubyfpv-lenscam  two-camera setup, the lens camera (variant "lens" plus\n'
        '#            "lenscam"): no Ruby, video over Ethernet to the server,\n'
        '#            zoom position tracking. Not part of `all`.\n')
open("build.sh", "w").write(b)
print("build.sh ok")

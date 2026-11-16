#!/usr/bin/env python3
"""mk2cam2.py - run from ~/cv610-fpv. Second round of the two-camera work:
picture controls act on the camera being shown, and the lens camera may keep
its own video mode. Regenerates patch 0012 and edits the variant sources."""
import os, re, shutil, subprocess, tempfile

SRC = "/home/hwt/openipc-builder/openipc/output/build/rubyfpv-1c2365f212135d408eca55e3a6084a255afeb8e8"
DEV = "hi3516cv6xx_rubyfpv_h5svx-imx335"
PKG = f"devices/{DEV}/general/package/rubyfpv"
VAR = f"variants/{DEV}"
REL = "code/base/hardware_cam_maj.cpp"
NAME = "0012-openipc-video-out-from-file-and-api-mirror.patch"


def rep(s, a, b):
    assert s.count(a) == 1, (s.count(a), a[:70])
    return s.replace(a, b)


# ---- patch 0012: the build tree already has the old 0012 applied; undo it first ----
d = tempfile.mkdtemp()
for side in ("a", "b"):
    os.makedirs(os.path.dirname(f"{d}/{side}/{REL}"))
    shutil.copy(f"{SRC}/{REL}", f"{d}/{side}/{REL}")
    r = subprocess.run(["patch", "-R", "-p1", "-s", "-i", os.path.abspath(f"{PKG}/{NAME}")], cwd=f"{d}/{side}")
    assert r.returncode == 0, "could not undo the old 0012"
s = open(f"{d}/b/{REL}", encoding="utf-8", errors="surrogateescape").read()
assert "ruby_video_out" not in s
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

   // With a stream switch in place, tell it about run-time majestic changes
   // (UDP 127.0.0.1:5606) so a second camera can follow them. Picture
   // controls (image.*, isp.exposure) act on the camera being shown: while
   // the switch shows the second camera (/tmp/camswitch.remote exists) they
   // are not applied to the local majestic.
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
      if ( ((NULL != strstr(szTmp, "?image.")) || (NULL != strstr(szTmp, "?isp.exposure"))) &&
           (access("/tmp/camswitch.remote", F_OK) == 0) )
      {
         close(iSock);
         return 0;
      }
   }
''')
open(f"{d}/b/{REL}", "w", encoding="utf-8", errors="surrogateescape").write(s)
diff = subprocess.run(["diff", "-u", f"a/{REL}", f"b/{REL}"], cwd=d, capture_output=True).stdout.decode("utf-8", "surrogateescape")
diff = re.sub(r"^(--- a/\S+)\t.*$", r"\1", diff, flags=re.M)
diff = re.sub(r"^(\+\+\+ b/\S+)\t.*$", r"\1", diff, flags=re.M)
open(f"{PKG}/{NAME}", "w", encoding="utf-8", errors="surrogateescape").write("""From: cv610-fpv
Subject: [PATCH] OpenIPC: majestic output address from /etc/ruby_video_out

For a two-camera setup a stream switch sits between majestic and Ruby. The
image names the address majestic sends to in /etc/ruby_video_out (one line,
udp://host:port); Ruby still reads 127.0.0.1:5600. With the file present,
the majestic API requests Ruby makes at run time (bitrate, GOP, QP, picture
controls) are also sent as datagrams to 127.0.0.1:5606, so the switch can
repeat them to the second camera, and picture controls (image.*,
isp.exposure) are not applied locally while the switch shows the second
camera (/tmp/camswitch.remote). Without the file nothing changes.
---
""" + diff)
shutil.rmtree(d)
print("0012 regenerated,", diff.count("\n"), "lines")

# ---- camswitch: flag file, picture routing, exposure no longer a shared setting ----
p = f"{VAR}/server/general/scripts/camswitch.c"; s = open(p).read()
s = rep(s, ''' *   127.0.0.1:5606  majestic API requests Ruby makes at run time (mirrored
 *                   to the second camera so its encoder follows)
''', ''' *   127.0.0.1:5606  majestic API requests Ruby makes at run time. Encoder
 *                   ones (video0.*) are repeated to the second camera so it
 *                   follows. Picture controls (image.*, isp.exposure) go to
 *                   the camera being shown only: Ruby skips the local
 *                   majestic while /tmp/camswitch.remote exists, and they
 *                   are passed to the second camera only while it is shown.
''')
s = rep(s, '"video0.rcMode", "video0.sliceUnits", "outgoing.naluSize", "isp.sensorConfig", "isp.exposure", NULL };',
        '"video0.rcMode", "video0.sliceUnits", "outgoing.naluSize", "isp.sensorConfig", NULL };')
s = rep(s, '''/* first RTP packet of a keyframe''', '''/* /tmp/camswitch.remote exists while the second camera is the one shown */
static void set_shown(int remote)
{
    if (remote) { int f = open("/tmp/camswitch.remote", O_WRONLY | O_CREAT, 0644); if (f >= 0) close(f); }
    else unlink("/tmp/camswitch.remote");
}

static int is_picture(const char *path)
{
    return strstr(path, "?image.") || strstr(path, "?isp.exposure");
}

/* first RTP packet of a keyframe''')
s = rep(s, '''    unsigned short ch[32]; int nch = 0;
''', '''    unsigned short ch[32]; int nch = 0;
    int shown = -1;
''')
s = rep(s, '''                if (!strncmp(msg + 4, "/api/v1/set?", 12)) { memcpy(msg, "api ", 4); to_client(msg); }
''', '''                if (strncmp(msg + 4, "/api/v1/set?", 12)) continue;
                if (is_picture(msg + 4) && !active) continue;      /* Ruby applied it to the local camera */
                memcpy(msg, "api ", 4); to_client(msg);
''')
s = rep(s, '''        /* zoom target: on change''', '''        if (active != shown) { shown = active; set_shown(active); }

        /* zoom target: on change''')
s = rep(s, '''    return 0;
}
''' if False else '''        }
    }
    return 0;
}
''', '''        }
    }
    set_shown(0);
    return 0;
}
''')
open(p, "w").write(s)
shutil.copy(p, "work/2cam/camswitch.c")

# ---- camlink: own video mode ----
p = f"{VAR}/lenscam/general/scripts/camlink.c"; s = open(p).read()
s = rep(s, ''' *   cfg k=v;k=v;...  majestic.yaml settings to share with the server; changed
 *                    ones are written with cli and majestic is reloaded
''', ''' *   cfg k=v;k=v;...  majestic.yaml settings to share with the server; changed
 *                    ones are written with cli and majestic is reloaded.
 *                    With OWN_MODE=1 this camera keeps its own resolution,
 *                    frame rate and sensor profile (S73camlink sets them from
 *                    MODE) and those three are ignored here.
''')
s = rep(s, "static int travel_ms = 8000, lens_addr = 1, zoom_enabled = 1;", "static int travel_ms = 8000, lens_addr = 1, zoom_enabled = 1, own_mode = 0;")
s = rep(s, '''        else if (!strcmp(k, "ZOOM")) zoom_enabled = atoi(v);
''', '''        else if (!strcmp(k, "ZOOM")) zoom_enabled = atoi(v);
        else if (!strcmp(k, "OWN_MODE")) own_mode = atoi(v);
''')
s = rep(s, '''        if (!strncmp(k, "outgoing.server", 15)) continue;       /* ours points at the server */
''', '''        if (!strncmp(k, "outgoing.server", 15)) continue;       /* ours points at the server */
        if (own_mode && (!strcmp(k, "video0.size") || !strcmp(k, "video0.fps") || !strcmp(k, "isp.sensorConfig"))) continue;
''')
open(p, "w").write(s)
shutil.copy(p, "work/2cam/camlink.c")

p = f"{VAR}/lenscam/general/overlay/etc/camlink.conf"; s = open(p).read()
s += '''
# Video mode. OWN_MODE=0: resolution, frame rate and sensor profile follow the
# server camera. OWN_MODE=1: this camera uses MODE instead; codec, bitrate and
# keyframe interval still follow the server. The ground station's decoder
# restarts when the shown camera changes to one with another resolution.
#   MODE=1080p60 | 1080p90 | 864p120 | 720p120 | 972p60
OWN_MODE=0
MODE=1080p60
'''
open(p, "w").write(s)

p = f"{VAR}/lenscam/general/overlay/etc/init.d/S73camlink"; s = open(p).read()
s = rep(s, '''		want .watchdog.enabled false
''', '''		want .watchdog.enabled false

		# Own video mode (see /etc/camlink.conf); otherwise camlink takes
		# resolution, frame rate and sensor profile from the server.
		if [ "${OWN_MODE:-0}" = 1 ]; then
			case "${MODE:-1080p60}" in
				1080p60) m="imx335_2l_1080p60 1920x1080 60" ;;
				1080p90) m="imx335_2l_1080p90 1920x1080 90" ;;
				864p120) m="imx335_2l_864p120 1536x864 120" ;;
				720p120) m="imx335_2l_720p120 1280x720 120" ;;
				972p60)  m="imx335_2l_bin972p60 1296x972 60" ;;
				*) m="" ; logger -t camlink "unknown MODE $MODE, video mode left as it is" ;;
			esac
			if [ -n "$m" ]; then
				set -- $m
				want .isp.sensorConfig "/etc/sensors/$1.ini"
				want .video0.size "$2"
				want .video0.fps "$3"
			fi
		fi
''')
open(p, "w").write(s)
print("sources updated")

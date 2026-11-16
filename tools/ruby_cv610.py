#!/usr/bin/env python3
# RubyFPV: add BOARD_TYPE_OPENIPC_HISI_CV610 (Hi3516CV608/CV610/CV613 + IMX335 2-lane).
# Run from a clean RubyFPV checkout (1c2365f). Controller-side effect is limited
# to the board name and hardware_board_is_openipc(); every existing board takes
# the same code paths as before.
import sys

def sub(path, old, new, count=1):
    s = open(path).read()
    n = s.count(old)
    if n != count:
        sys.exit(f"{path}: expected {count} match(es), found {n}:\n{old}")
    open(path, "w").write(s.replace(old, new))

CV = "hardware_board_is_hisi_cv610"

# ---------------------------------------------------------------- shared
sub("code/base/hardware.h",
    "#define BOARD_TYPE_OPENIPC_GOKE300 32\n",
    "#define BOARD_TYPE_OPENIPC_GOKE300 32\n"
    "// HiSilicon Hi3516CV608 / CV610 / CV613 (majestic, like the Goke boards, but with a\n"
    "// live encoder API: adaptive video and live camera changes work).\n"
    "#define BOARD_TYPE_OPENIPC_HISI_CV610 33\n")
sub("code/base/hardware.h",
    "int hardware_board_is_sigmastar(u32 uBoardType);\n",
    "int hardware_board_is_sigmastar(u32 uBoardType);\n"
    f"int {CV}(u32 uBoardType);\n")

sub("code/base/hardware.cpp",
    """   if ( (uBoardType & BOARD_TYPE_MASK) == BOARD_TYPE_OPENIPC_SIGMASTAR_338Q )
      return 1;
   return 0;
}

int hardware_board_is_goke(u32 uBoardType)""",
    """   if ( (uBoardType & BOARD_TYPE_MASK) == BOARD_TYPE_OPENIPC_SIGMASTAR_338Q )
      return 1;
   if ( (uBoardType & BOARD_TYPE_MASK) == BOARD_TYPE_OPENIPC_HISI_CV610 )
      return 1;
   return 0;
}

int """ + CV + """(u32 uBoardType)
{
   if ( (uBoardType & BOARD_TYPE_MASK) == BOARD_TYPE_OPENIPC_HISI_CV610 )
      return 1;
   return 0;
}

int hardware_board_is_goke(u32 uBoardType)""")

sub("code/common/string_utils.c",
    '   static const char* s_szBoardTypeOpenIPCGoke300 = "OpenIPC Goke300";\n',
    '   static const char* s_szBoardTypeOpenIPCGoke300 = "OpenIPC Goke300";\n'
    '   static const char* s_szBoardTypeOpenIPCHisiCV610 = "OpenIPC HiSilicon CV610";\n')
sub("code/common/string_utils.c",
    """   if ( (board_type & BOARD_TYPE_MASK) == BOARD_TYPE_OPENIPC_GOKE300 )
      return s_szBoardTypeOpenIPCGoke300;
""",
    """   if ( (board_type & BOARD_TYPE_MASK) == BOARD_TYPE_OPENIPC_GOKE300 )
      return s_szBoardTypeOpenIPCGoke300;
   if ( (board_type & BOARD_TYPE_MASK) == BOARD_TYPE_OPENIPC_HISI_CV610 )
      return s_szBoardTypeOpenIPCHisiCV610;
""")
sub("code/common/string_utils.c",
    '   static const char* s_szBoardSTypeOpenIPCGoke300 = "Goke300";\n',
    '   static const char* s_szBoardSTypeOpenIPCGoke300 = "Goke300";\n'
    '   static const char* s_szBoardSTypeOpenIPCHisiCV610 = "CV610";\n')
sub("code/common/string_utils.c",
    """   if ( (board_type & BOARD_TYPE_MASK) == BOARD_TYPE_OPENIPC_GOKE300 )
      return s_szBoardSTypeOpenIPCGoke300;
""",
    """   if ( (board_type & BOARD_TYPE_MASK) == BOARD_TYPE_OPENIPC_GOKE300 )
      return s_szBoardSTypeOpenIPCGoke300;
   if ( (board_type & BOARD_TYPE_MASK) == BOARD_TYPE_OPENIPC_HISI_CV610 )
      return s_szBoardSTypeOpenIPCHisiCV610;
""")

# ---------------------------------------------------------------- vehicle
# Detection (only built into the camera binaries).
sub("code/base/hardware.cpp",
    """   if ( NULL != strstr(szBoardId, "ssc33x") )
      s_uHardwareBoardType = BOARD_TYPE_OPENIPC_SIGMASTAR_338Q;
   #endif
}""",
    """   if ( NULL != strstr(szBoardId, "ssc33x") )
      s_uHardwareBoardType = BOARD_TYPE_OPENIPC_SIGMASTAR_338Q;
   if ( NULL != strstr(szBoardId, "hi3516cv6") )
      s_uHardwareBoardType = BOARD_TYPE_OPENIPC_HISI_CV610;
   #endif
}""")

# Defaults: 60 fps and the 7 Mbps start bitrate, as on SigmaStar.
s = open("code/base/models.cpp").read()
old = """   if ( hardware_board_is_sigmastar(hardware_getBoardType()) )
      video_params.iVideoFPS = DEFAULT_VIDEO_FPS_OIPC_SIGMASTAR;"""
assert s.count(old) == 1, "fps1"
s = s.replace(old, f"""   if ( hardware_board_is_sigmastar(hardware_getBoardType()) || {CV}(hardware_getBoardType()) )
      video_params.iVideoFPS = DEFAULT_VIDEO_FPS_OIPC_SIGMASTAR;""")
old = """      if ( hardware_board_is_sigmastar(hardware_getBoardType()) )
         video_params.iVideoFPS = DEFAULT_VIDEO_FPS_OIPC_SIGMASTAR;"""
assert s.count(old) == 1, "fps2"
s = s.replace(old, f"""      if ( hardware_board_is_sigmastar(hardware_getBoardType()) || {CV}(hardware_getBoardType()) )
         video_params.iVideoFPS = DEFAULT_VIDEO_FPS_OIPC_SIGMASTAR;""")
old = """   if ( hardware_board_is_sigmastar(hardware_getBoardType()) )
      video_link_profiles[iProfile].uTargetVideoBitrateBPS = DEFAULT_VIDEO_BITRATE_OPIC_SIGMASTAR;"""
assert s.count(old) == 1, "br1"
s = s.replace(old, f"""   if ( hardware_board_is_sigmastar(hardware_getBoardType()) || {CV}(hardware_getBoardType()) )
      video_link_profiles[iProfile].uTargetVideoBitrateBPS = DEFAULT_VIDEO_BITRATE_OPIC_SIGMASTAR;""")
# OTA from the controller would push binaries built for another SoC.
old = """   if ( hardware_board_is_goke( hardware_getBoardType() ) )
      hwCapabilities.uHWFlags &= ~MODEL_HW_CAP_FLAG_OTA;"""
assert s.count(old) == 1, "ota"
s = s.replace(old, f"""   if ( hardware_board_is_goke( hardware_getBoardType() ) || {CV}( hardware_getBoardType() ) )
      hwCapabilities.uHWFlags &= ~MODEL_HW_CAP_FLAG_OTA;""")
open("code/base/models.cpp", "w").write(s)
# the bitrate reset at line ~6469 (all profiles)
s = open("code/base/models.cpp").read()
i = s.find("   if ( hardware_board_is_sigmastar(hardware_getBoardType()) )\n", s.find("video_link_profiles[VIDEO_PROFILE_CUST].uTargetVideoBitrateBPS = DEFAULT_VIDEO_BITRATE_PI_ZERO;"))
assert i > 0, "br2"
s = s[:i] + f"   if ( hardware_board_is_sigmastar(hardware_getBoardType()) || {CV}(hardware_getBoardType()) )\n" + s[i+len("   if ( hardware_board_is_sigmastar(hardware_getBoardType()) )\n"):]
open("code/base/models.cpp", "w").write(s)

for old in ("""   if ( hardware_board_is_sigmastar(hardware_getBoardType()) )
      pModel->video_params.iVideoFPS = DEFAULT_VIDEO_FPS_OIPC_SIGMASTAR;""",):
    s = open("code/r_utils/ruby_update.cpp").read()
    assert s.count(old) == 2, "upd fps"
    s = s.replace(old, f"""   if ( hardware_board_is_sigmastar(hardware_getBoardType()) || {CV}(hardware_getBoardType()) )
      pModel->video_params.iVideoFPS = DEFAULT_VIDEO_FPS_OIPC_SIGMASTAR;""")
    open("code/r_utils/ruby_update.cpp", "w").write(s)

# IMX335 default profile on cv610: the 2-lane 1080p60 ini.
sub("code/base/hardware_camera.cpp",
    """   if ( iCameraType == CAMERA_TYPE_OPENIPC_IMX335 )
   {
      if ( access("/etc/sensors/imx335_fpv.bin", R_OK) != -1 )""",
    f"""   if ( (iCameraType == CAMERA_TYPE_OPENIPC_IMX335) && {CV}(hardware_getBoardType()) )
      sprintf(szMajComm, "cli -s .isp.sensorConfig /etc/sensors/imx335_2l_1080p60.ini");
   else if ( iCameraType == CAMERA_TYPE_OPENIPC_IMX335 )
   {{
      if ( access("/etc/sensors/imx335_fpv.bin", R_OK) != -1 )""")

# Sensor profile from fps, size clamped to the capture window.
sub("code/base/hardware_cam_maj.cpp",
    "void _hardware_camera_maj_set_all_params()\n{",
    """// Hi3516CV610 + IMX335 on two MIPI lanes: the sensor profile sets the
// capture window and frame rate, and video0.size may not exceed the window.
// Picks the profile for the requested fps (5MP for <=30 fps above 1080p) and
// returns the size to give majestic, clamped to the window.
static void _hardware_camera_maj_cv610_select_sensor(int iFPS, int iWidth, int iHeight, int* piOutWidth, int* piOutHeight)
{
   const char* szIni = "imx335_2l_1080p60.ini";
   int iMaxW = 1920, iMaxH = 1080;
   if ( (iFPS <= 30) && ((iWidth > 1920) || (iHeight > 1080)) )
   {
      szIni = "imx335_i2c_5M.ini";
      iMaxW = 2592; iMaxH = 1944;
   }
   else if ( iFPS <= 60 )
      szIni = "imx335_2l_1080p60.ini";
   else if ( iFPS <= 90 )
      szIni = "imx335_2l_1080p90.ini";
   else
   {
      // 1536x864 crop at 120 fps; 1280x720 is scaled from it (59% of the width).
      szIni = "imx335_2l_864p120.ini";
      iMaxW = 1536; iMaxH = 864;
   }

   *piOutWidth = iWidth;
   *piOutHeight = iHeight;
   if ( (iWidth > iMaxW) || (iHeight > iMaxH) )
   {
      *piOutWidth = iMaxW;
      *piOutHeight = iMaxH;
   }

   char szComm[256];
   snprintf(szComm, sizeof(szComm)/sizeof(szComm[0]), "cli -s .isp.sensorConfig /etc/sensors/%s", szIni);
   log_line("[HwCamMajestic] CV610 IMX335: %d fps %dx%d -> %s, size %dx%d", iFPS, iWidth, iHeight, szIni, *piOutWidth, *piOutHeight);
   _execute_maj_command_wait(szComm);
}

void _hardware_camera_maj_set_all_params()
{""")
sub("code/base/hardware_cam_maj.cpp",
    """   sprintf(szComm, "cli -s .video0.size %dx%d", s_pCurrentMajesticModel->video_params.iVideoWidth, s_pCurrentMajesticModel->video_params.iVideoHeight);
   _execute_maj_command_wait(szComm);""",
    f"""   int iMajWidth = s_pCurrentMajesticModel->video_params.iVideoWidth;
   int iMajHeight = s_pCurrentMajesticModel->video_params.iVideoHeight;
   if ( {CV}(hardware_getBoardType()) && (s_pCurrentMajesticModel->getActiveCameraType() == CAMERA_TYPE_OPENIPC_IMX335) )
      _hardware_camera_maj_cv610_select_sensor(s_pCurrentMajesticModel->video_params.iVideoFPS,
         s_pCurrentMajesticModel->video_params.iVideoWidth, s_pCurrentMajesticModel->video_params.iVideoHeight,
         &iMajWidth, &iMajHeight);
   sprintf(szComm, "cli -s .video0.size %dx%d", iMajWidth, iMajHeight);
   _execute_maj_command_wait(szComm);""")

# IR-cut filter: GPIO 1 / 9 (majestic nightMode.irCutPin1/2 on this board).
s = open("code/base/hardware_cam_maj.cpp").read()
for set_, clr in (("10", "11"), ("11", "10")):
    old = f"""      if ( (hardware_getBoardType() & BOARD_TYPE_MASK) == BOARD_TYPE_OPENIPC_GOKE300 )
      {{
         _add_maj_command_to_queue_or_exec("gpio set {set_}", false);
         _add_maj_command_to_queue_or_exec("gpio clear {clr}", false);
      }}"""
    assert s.count(old) == 1, "ircut"
    a, b = ("1", "9") if set_ == "10" else ("9", "1")
    s = s.replace(old, old + f"""
      if ( {CV}(hardware_getBoardType()) )
      {{
         _add_maj_command_to_queue_or_exec("gpio set {a}", false);
         _add_maj_command_to_queue_or_exec("gpio clear {b}", false);
      }}""")
open("code/base/hardware_cam_maj.cpp", "w").write(s)
print("ok")

#!/usr/bin/env python3
"""Derive hi3516cv6xx.generic-fpv.config from the stock hi3516cv6xx.generic.config.

The stock cv6xx kernel ships with the wireless stack off, so the out-of-tree
Realtek drivers (rtl8812au-openipc, rtl88x2eu-openipc) have nothing to link
against. The block below reproduces the wireless symbols of the ssc378qe_wfbng
kernel (infinity6c-ssc027d.config), the one 5.10 kernel these drivers already
run on in OpenIPC: CFG80211=m, WIRELESS_EXT=y, WEXT_PRIV=y, CFG80211_WEXT off.

WIRELESS_EXT and WEXT_PRIV are hidden symbols that only a driver's `select`
sets. SigmaStar's kernel gets them from its GKI_LEGACY_WEXT_ALLCONFIG option,
which openipc/linux hisilicon-hi3516cv6xx does not have; there, every selector
but HOSTAP needs PCI or PCMCIA. HOSTAP=m is therefore built only for its
selects -- hostap.ko and the lib80211 modules it pulls in are dropped from the
rootfs by the board's excludes list.

CFG80211_REQUIRE_SIGNED_REGDB has no prompt unless CFG80211_CERTIFICATION_ONUS
is set, and left to its default it builds X.509, RSA and the system keyring
into the uImage to verify a regulatory.db this image never loads (wfb-ng runs
`iw reg set 00`). The uImage has to stay inside the 2 MiB the cv610 U-Boot
reads (CHECK_KERNEL_READ), so ONUS is set only to make that symbol settable;
the options ONUS exposes besides default to n.

Everything outside the replaced lines is left byte-for-byte as the stock file
has it; Buildroot's olddefconfig fills in whatever the new symbols select.

usage: make-fpv-kernel-config.py <stock .config> <out .config> [<linux src> for a Kconfig check]
"""
import os, sys

REPLACE = {
    "# CONFIG_WIRELESS is not set": """CONFIG_WIRELESS=y
CONFIG_CFG80211=m
# CONFIG_NL80211_TESTMODE is not set
# CONFIG_CFG80211_DEVELOPER_WARNINGS is not set
CONFIG_CFG80211_CERTIFICATION_ONUS=y
# CONFIG_CFG80211_REQUIRE_SIGNED_REGDB is not set
# CONFIG_CFG80211_REG_CELLULAR_HINTS is not set
# CONFIG_CFG80211_REG_RELAX_NO_IR is not set
# CONFIG_CFG80211_DEFAULT_PS is not set
# CONFIG_CFG80211_DEBUGFS is not set
CONFIG_CFG80211_CRDA_SUPPORT=y
# CONFIG_CFG80211_WEXT is not set
# CONFIG_MAC80211 is not set""",
    "# CONFIG_WLAN is not set": "CONFIG_WLAN=y\n" + "\n".join(
        f"# CONFIG_WLAN_VENDOR_{v} is not set" for v in (
            "ADMTEK ATH ATMEL BROADCOM CISCO INTEL MARVELL MEDIATEK "
            "MICROCHIP RALINK REALTEK RSI ST TI ZYDAS QUANTENNA").split())
        + "\nCONFIG_WLAN_VENDOR_INTERSIL=y\nCONFIG_HOSTAP=m\n# CONFIG_HOSTAP_FIRMWARE is not set",
    # Both Realtek packages say they need a firmware loading mechanism, and
    # cfg80211 loads regulatory.db through it.
    "# CONFIG_FW_LOADER is not set": """CONFIG_FW_LOADER=y
CONFIG_EXTRA_FIRMWARE=""
# CONFIG_FW_LOADER_USER_HELPER is not set
# CONFIG_FW_LOADER_COMPRESS is not set""",
    # wfb_tun (the IP/MAVLink tunnel wifibroadcast starts) and vtund both open
    # /dev/net/tun. Modules, so the uImage does not grow; S97tun loads it.
    "# CONFIG_TUN is not set": "CONFIG_TUN=m",
    # exFAT for SD-card recording, as the other FPV images carry (exfatprogs).
    "# CONFIG_EXFAT_FS is not set": 'CONFIG_EXFAT_FS=m\nCONFIG_EXFAT_DEFAULT_IOCHARSET="utf8"',
    # The stock kernel has a 100 Hz periodic tick and no high-resolution
    # timers, so every nanosleep lasts at least 10 ms. Ruby paces video
    # packets with sub-millisecond sleeps (video_tx_buffers.cpp: 3/4 of the
    # last packet's airtime) and wfb-ng/majestic time things in microseconds
    # too; with 10 ms sleeps Ruby sent about 200 packets/s (1.8 Mbit/s) and
    # dropped the rest of a 7 Mbit/s stream. The ARM arch timer does one-shot
    # mode, so hrtimers work. The tick stays periodic (no NO_HZ) to keep the
    # uImage inside the 2 MiB the cv610 U-Boot reads.
    "# CONFIG_HIGH_RES_TIMERS is not set": "CONFIG_HIGH_RES_TIMERS=y",
}

# What has to hold after olddefconfig for the drivers to build and wfb-ng to run.
EXPECT = {
    "WIRELESS": "y", "CFG80211": "m", "CFG80211_WEXT": "n", "WIRELESS_EXT": "y",
    "WEXT_CORE": "y", "WEXT_PROC": "y", "WEXT_PRIV": "y", "WLAN": "y",
    "HOSTAP": "m", "FW_LOADER": "y", "MODULES": "y", "USB_XHCI_PLATFORM": "y",
    "MAC80211": "n", "CFG80211_REQUIRE_SIGNED_REGDB": "n", "SYSTEM_DATA_VERIFICATION": "n",
    "TUN": "m", "EXFAT_FS": "m", "HIGH_RES_TIMERS": "y",
}


def build(stock, out):
    text = open(stock, newline="\n").read()
    for old, new in REPLACE.items():
        if text.count(old + "\n") != 1:
            sys.exit(f"expected exactly one '{old}' in {stock}")
        text = text.replace(old + "\n", new + "\n")
    with open(out, "w", newline="\n") as f:
        f.write(text)


def check(out, src):
    import kconfiglib
    # No cross compiler here: the $(shell)/$(success) probes in the kernel's
    # Kconfig only decide CC_HAS_* style capability symbols, none of which the
    # wireless block depends on, so answer them with a fixed "gcc 13, no".
    kconfiglib._success_fn = lambda kconf, _, *a: "n"
    kconfiglib._failure_fn = lambda kconf, _, *a: "y"
    kconfiglib._shell_fn = lambda kconf, _, cmd: "130000" if "version" in cmd else "0"
    os.environ.update(ARCH="arm", SRCARCH="arm", KERNELVERSION="5.10.221",
                      CC="gcc", LD="ld", HOSTCC="gcc", CC_VERSION_TEXT="gcc (GCC) 13.2.0")
    cwd = os.getcwd()
    os.chdir(src)
    try:
        kc = kconfiglib.Kconfig("Kconfig", warn=False)
        stock = kconfiglib.Kconfig("Kconfig", warn=False)
    finally:
        os.chdir(cwd)
    kc.load_config(out)
    bad = []
    for name, want in EXPECT.items():
        got = kc.syms[name].str_value
        print(f"  {name:20s} {got:2s} (want {want})")
        if got != want:
            bad.append(name)
    # Which symbols the new block drags in beyond the lines written above.
    stock.load_config(sys.argv[1])
    pulled = sorted(n for n, s in kc.syms.items()
                    if s.str_value != stock.syms[n].str_value and s.type in (kconfiglib.BOOL, kconfiglib.TRISTATE))
    print("  changed vs stock:", " ".join(f"{n}={kc.syms[n].str_value}" for n in pulled))
    if bad:
        sys.exit("unresolved: " + " ".join(bad))


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
    if len(sys.argv) > 3:
        check(sys.argv[2], sys.argv[3])

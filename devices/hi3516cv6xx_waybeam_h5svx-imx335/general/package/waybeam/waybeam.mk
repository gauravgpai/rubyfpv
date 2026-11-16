################################################################################
#
# waybeam
#
################################################################################

# Device-local copy of firmware's general/package/waybeam (b7c61c4), shadowing
# it when builder copies this device over the firmware tree. The stock package
# builds the Infinity6E (star6e) backend only; this one adds the Hi3516CV6xx
# (cv610) backend. The source is pinned because
# 0001-cv610-IMX335-2-lane-sensor-profile.patch is made
# against that commit.

WAYBEAM_VERSION = 0c880d8bc874f803b569aa1bf028de82bb6e6045
WAYBEAM_SITE = https://github.com/OpenIPC/waybeam.git
WAYBEAM_SITE_METHOD = git
WAYBEAM_LICENSE = MIT
WAYBEAM_LICENSE_FILES = LICENSE

ifeq ($(OPENIPC_SOC_FAMILY),hi3516cv6xx)

# The backend compiles against the openhisilicon headers in the opensdk build
# tree and links the vendor MPP libraries hisilicon-osdrv-hi3516cv6xx installs
# (libss_mpi_audio_adp needs the HiSi opus shim from opus-openipc).
WAYBEAM_SOC = cv610
WAYBEAM_DEPENDENCIES += hisilicon-opensdk hisilicon-osdrv-hi3516cv6xx opus-openipc
WAYBEAM_MAKE_OPTS = SOC_BUILD=cv610 CV610_CC="$(TARGET_CC)" \
	CV610_SDK_INC="$(HISILICON_OPENSDK_DIR)" CV610_SDK_LIB="$(TARGET_DIR)/usr/lib"

define WAYBEAM_BUILD_CMDS
	$(MAKE) -C $(@D) build json_cli $(WAYBEAM_MAKE_OPTS)
endef

define WAYBEAM_INSTALL_TARGET_CMDS
	$(INSTALL) -m 0755 -D $(@D)/out/$(WAYBEAM_SOC)/waybeam \
		$(TARGET_DIR)/usr/bin/waybeam
	$(INSTALL) -m 0755 -D $(@D)/out/$(WAYBEAM_SOC)/json_cli \
		$(TARGET_DIR)/usr/bin/json_cli
	$(INSTALL) -m 0644 -D $(WAYBEAM_PKGDIR)/files/waybeam.cv610.json \
		$(TARGET_DIR)/etc/waybeam.json
	$(INSTALL) -m 0644 -D $(WAYBEAM_PKGDIR)/files/waybeam-cv610.conf \
		$(TARGET_DIR)/etc/waybeam-cv610.conf
endef

define WAYBEAM_INSTALL_INIT_SYSV
	$(INSTALL) -m 0755 -D $(@D)/init.d/S95waybeam.cv610 \
		$(TARGET_DIR)/etc/init.d/S95waybeam
endef

else

# Infinity6E, unchanged from the firmware package.
WAYBEAM_GIT_SUBMODULES = YES
WAYBEAM_SOC = star6e
WAYBEAM_MAKE_OPTS = SOC_BUILD=star6e STAR6E_CC="$(TARGET_CC)" CC_BIN="$(TARGET_CC)"
WAYBEAM_DEPENDENCIES += sigmastar-osdrv-sensors sigmastar-osdrv-infinity6e linux

define WAYBEAM_BUILD_CMDS
	$(MAKE) -C $(@D) build json_cli $(WAYBEAM_MAKE_OPTS)
	$(MAKE) -C $(@D)/drivers sensor SOC=$(WAYBEAM_SOC) \
		KSRC="$(LINUX_DIR)" CROSS="$(TARGET_CROSS)"
endef

define WAYBEAM_INSTALL_TARGET_CMDS
	$(INSTALL) -m 0755 -D $(@D)/out/$(WAYBEAM_SOC)/waybeam \
		$(TARGET_DIR)/usr/bin/waybeam
	$(INSTALL) -m 0755 -D $(@D)/out/$(WAYBEAM_SOC)/json_cli \
		$(TARGET_DIR)/usr/bin/json_cli
	$(INSTALL) -m 0644 -D $(WAYBEAM_PKGDIR)/files/waybeam.json \
		$(TARGET_DIR)/etc/waybeam.json
endef

define WAYBEAM_INSTALL_SENSOR_MODULES
	$(INSTALL) -m 0644 -D $(@D)/drivers/sensor_imx335_$(WAYBEAM_SOC).ko \
		$(TARGET_DIR)/lib/modules/$(LINUX_VERSION_PROBED)/sigmastar/sensor_imx335_mipi.ko
	$(INSTALL) -m 0644 -D $(@D)/drivers/sensor_imx415_$(WAYBEAM_SOC).ko \
		$(TARGET_DIR)/lib/modules/$(LINUX_VERSION_PROBED)/sigmastar/sensor_imx415_mipi.ko
endef
WAYBEAM_POST_INSTALL_TARGET_HOOKS += WAYBEAM_INSTALL_SENSOR_MODULES

define WAYBEAM_INSTALL_INIT_SYSV
	$(INSTALL) -m 0755 -D $(WAYBEAM_PKGDIR)/files/S95waybeam \
		$(TARGET_DIR)/etc/init.d/S95waybeam
endef

endif

$(eval $(generic-package))

#!/bin/bash
# Cross-build the patched Ruby 11.8 Radxa controller on an x86 Linux PC, then
# package it as a Ruby USB update (ruby_update_11.8_cv610.zip).
#
#   cross-build.sh TOOLCHAIN SYSROOT RUBYFPV_DIR OFFICIAL_ZIP OUT_ZIP
#
# TOOLCHAIN  ARM GNU Toolchain 10.3-2021.07 aarch64-none-linux-gnu (closest
#            release to the stock build's Debian GCC 10.2.1)
# SYSROOT    headers + libraries from the Ruby Radxa image (Debian 11,
#            glibc 2.31, libstdc++ 10.2.1) plus the -dev packages at the
#            image's versions (cairo, libdrm, gpiod, i2c, rockchip-mpp)
# RUBYFPV_DIR RubyFPV at 1c2365f with every 00*.patch of this folder applied
#
# Same Makefile, targets and flags as `make all RUBY_BUILD_ENV=radxa` on the
# Radxa; only the host include/lib paths the Makefile hard-codes are pointed
# into the sysroot, and the image's own GCC 10.2.1 C++ headers are used.
set -euo pipefail

tc=$(realpath "$1"); sr=$(realpath "$2"); src=$(realpath "$3")
official=$(realpath "$4"); out=$5
here=$(cd "$(dirname "$0")" && pwd)
t=$tc/bin/aarch64-none-linux-gnu-
ml=aarch64-linux-gnu

[ -e "$sr/usr/lib/ld-linux-aarch64.so.1" ] || ln -sf "$ml/ld-linux-aarch64.so.1" "$sr/usr/lib/ld-linux-aarch64.so.1"

# Header search order of the Radxa's own gcc-10 (its internal headers too: the
# toolchain's include-fixed is generated from glibc 2.33, the image has 2.31).
common="--sysroot=$sr -nostdinc -isystem $sr/usr/lib/gcc/$ml/10/include -isystem $sr/usr/local/include -isystem $sr/usr/include/$ml -isystem $sr/usr/include"
cxxinc="-nostdinc++ -isystem $sr/usr/include/c++/10 -isystem $sr/usr/include/$ml/c++/10 -isystem $sr/usr/include/c++/10/backward"
# Debian gcc-10 defaults the ARM toolchain lacks: PIE, gnu hash; and the stock
# binaries carry no unused DT_NEEDED entries (--as-needed).
common="$common -fPIE"
link="-pie -Wl,--hash-style=gnu -Wl,--build-id -Wl,--as-needed -B$sr/usr/lib/$ml -L$sr/usr/lib/gcc/$ml/10 -L$sr/usr/lib/$ml -Wl,-rpath-link,$sr/usr/lib/$ml"

# Wrappers: the Makefile calls $(CC), $(CXX) and a literal `cc`.
w=$src/.cross-bin
mkdir -p "$w"
printf '#!/bin/sh\nexec %sgcc %s %s "$@"\n' "$t" "$common" "$link" > "$w/cc"
printf '#!/bin/sh\nexec %sg++ %s %s %s "$@"\n' "$t" "$cxxinc" "$common" "$link" > "$w/c++"
chmod +x "$w/cc" "$w/c++"
ln -sf cc "$w/gcc"; ln -sf c++ "$w/g++"

cd "$src"
PATH=$w:$PATH make -j"$(nproc)" vehicle station ruby_i2c ruby_central \
	RUBY_BUILD_ENV=radxa CC="$w/cc" CXX="$w/c++" \
	CFLAGS_RENDERER="-I$sr/usr/include/drm -I$sr/usr/include/libdrm -I$sr/usr/include/cairo" \
	INCLUDE_CENTRAL="-Imenu -Iosd -I../menu -I../osd -Icode/r_central/menu -Icode/r_central/osd -I$sr/usr/include/freetype2" \
	LDFLAGS_CENTRAL="-lpthread -lrt -lm"

python3 "$here/make-update-zip.py" "$official" "$src" "$out"

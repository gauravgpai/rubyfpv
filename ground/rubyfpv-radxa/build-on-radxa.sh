#!/bin/bash
# Build the RubyFPV controller for Radxa Zero 3W with the Hi3516CV610 board
# type, on the Radxa itself (same compiler, flags and libraries as the stock
# Ruby build: make all RUBY_BUILD_ENV=radxa).
#
#   ./build-on-radxa.sh            build only, into ./RubyFPV
#   ./build-on-radxa.sh --install  build, back up /home/radxa/ruby's binaries,
#                                  replace only the binaries already there
#
# The patch adds a board type and its name; no controller setting, menu
# default, radio or video path of an existing board changes. Vehicle and
# controller must run the same Ruby version: both are 11.8 (1c2365f).
set -euo pipefail

rev=1c2365f212135d408eca55e3a6084a255afeb8e8
here=$(cd "$(dirname "$0")" && pwd)
ruby=/home/radxa/ruby

if [ -f "$ruby/version_ruby_base.txt" ]; then
	have=$(head -1 "$ruby/version_ruby_base.txt" | tr -d '\r\n ')
	if [ "$have" != "11.8" ]; then
		echo "Installed controller is Ruby $have; the camera image is 11.8."
		echo "Flash the Ruby 11.8 Radxa image first (vehicle and controller must match)."
		[ "${1:-}" = "--install" ] && exit 1
	fi
fi

[ -d RubyFPV/.git ] || git clone https://github.com/RubyFPV/RubyFPV RubyFPV
cd RubyFPV
git fetch -q origin "$rev" 2>/dev/null || git fetch -q origin
git checkout -q -f "$rev"
git clean -qfdx
for p in "$here"/00*.patch; do
	echo "applying $(basename "$p")"
	patch -p1 -s < "$p"
done

make -j"$(nproc)" all RUBY_BUILD_ENV=radxa

[ "${1:-}" = "--install" ] || { echo "Built in $(pwd). Run again with --install to install."; exit 0; }

backup=$HOME/ruby-backup-$(date +%Y%m%d-%H%M%S)
mkdir -p "$backup"
n=0
for f in ruby_*; do
	[ -f "$f" ] && [ -x "$f" ] || continue
	[ -f "$ruby/$f" ] || continue    # only replace what the stock install has
	sudo cp -a "$ruby/$f" "$backup/"
	sudo install -m 755 "$f" "$ruby/$f"
	n=$((n + 1))
done
echo "Replaced $n binaries in $ruby; originals in $backup. Reboot to start them."
echo "To undo: sudo cp -a $backup/* $ruby/ && sudo reboot"

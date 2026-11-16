#!/bin/sh
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

# 3. A camera that ran a Ruby image before has S95majestic deleted in its
#    settings partition (Ruby removes it on first boot), and that deletion
#    survives an upgrade. A second copy under a new name starts the video
#    there; on a clean camera it finds majestic already running.
cp "$T/etc/init.d/S95majestic" "$T/etc/init.d/S96camvideo"

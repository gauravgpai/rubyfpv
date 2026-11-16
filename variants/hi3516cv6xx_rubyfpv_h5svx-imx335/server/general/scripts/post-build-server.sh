#!/bin/sh
# Buildroot post-build step of the "server" variant ($1 is the target tree):
# builds camswitch, the two-camera stream switch (scripts/camswitch.c).
set -e
T=$1
O=$(dirname "$T")
CC=$(ls "$O"/host/bin/arm-*-gcc | head -1)
[ -x "$CC" ]
"$CC" -O2 -Wall "$(dirname "$0")/camswitch.c" -o "$T/usr/sbin/camswitch"
chmod 755 "$T/usr/sbin/camswitch"

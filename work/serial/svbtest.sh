#!/bin/sh
# Catch U-Boot, store the PWM copy the SVB check wants, boot once with open_pm allowed (nothing saved).
python3 ~/serstop.py 180 | tail -1
python3 ~/sercmd.py 2 "help setexpr\r"
python3 ~/sercmd.py 2 "md.l 0x11014580 1; mw.l 0x1102034c 0x2010; md.l 0x1102034c 1\r"
python3 ~/sercmd.py 1 "setenv extras ignore_loglevel\r" >/dev/null
python3 ~/sercmd.py 120 "run bootflash\r" > ~/cv610-svb.log
echo DONE

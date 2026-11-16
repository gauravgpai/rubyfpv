#!/bin/sh
# Catch U-Boot, save extras=module_blacklist=open_pm, then boot normally and log it.
python3 ~/serstop.py 180 | tail -1
python3 ~/sercmd.py 2 "setenv extras module_blacklist=open_pm\r"
python3 ~/sercmd.py 4 "saveenv\r"
python3 ~/sercmd.py 2 "printenv extras\r"
python3 ~/sercmd.py 120 "run bootcmd\r" > ~/cv610-fixed.log
python3 ~/sercmd.py 3 "\r" >> ~/cv610-fixed.log
echo DONE

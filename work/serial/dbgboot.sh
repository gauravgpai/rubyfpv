#!/bin/sh
# dbgboot.sh "<extras>" <logname> - catch U-Boot, boot once with extras (setenv only, not saved), log 150 s.
python3 ~/serstop.py 180 | tail -1
python3 ~/sercmd.py 1 "setenv extras $1\r" >/dev/null
python3 ~/sercmd.py 150 "run bootflash\r" > ~/$2
python3 ~/sercmd.py 3 "\r" >> ~/$2
echo DONE $(wc -c < ~/$2)

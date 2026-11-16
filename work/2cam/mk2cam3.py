#!/usr/bin/env python3
"""mk2cam3.py - run from ~/cv610-fpv: both two-camera images clear majestic's
list of output addresses at boot. This majestic turns outgoing.server into an
entry of outgoing.servers and ADDS every new address to that list, so an
address from an earlier image or test would keep receiving the video (on the
server camera: Ruby would get the picture twice)."""
VAR = "variants/hi3516cv6xx_rubyfpv_h5svx-imx335"

FUNC = r'''
# majestic keeps a list of output addresses (outgoing.servers) and adds every
# new outgoing.server to it instead of replacing. Drop the list at boot so
# only the address set afterwards is used.
clear_outputs() {
	y=/etc/majestic.yaml
	[ -f "$y" ] || return 0
	awk '/^  servers:[ \t]*$/ { skip = 1; next }
	     skip && (/^  - / || /^    /) { next }
	     { skip = 0; print }' "$y" > /tmp/majestic.yaml.new || return 0
	if ! cmp -s "$y" /tmp/majestic.yaml.new; then
		cat /tmp/majestic.yaml.new > "$y"
		logger -t camvideo "cleared majestic's list of output addresses"
	fi
	rm -f /tmp/majestic.yaml.new
}
'''


def rep(s, a, b):
    assert s.count(a) == 1, (s.count(a), a[:60])
    return s.replace(a, b)


p = f"{VAR}/lenscam/general/overlay/etc/init.d/S73camlink"; s = open(p).read()
s = rep(s, '\ncase "$1" in\n', FUNC + '\ncase "$1" in\n')
s = rep(s, '\t\twant .outgoing.enabled true\n', '\t\tclear_outputs\n\t\twant .outgoing.enabled true\n')
open(p, "w").write(s)

p = f"{VAR}/server/general/overlay/etc/init.d/S72camswitch"; s = open(p).read()
s = rep(s, '\ncase "$1" in\n', FUNC + '\ncase "$1" in\n')
s = rep(s, '\tstart)\n\t\tstart-stop-daemon -S', '''	start)
		# Ruby sets outgoing.server to the switch (127.0.0.1:5602) when it
		# starts majestic; an older entry for 127.0.0.1:5600 must not stay.
		clear_outputs
		cli -s .outgoing.server udp://127.0.0.1:5602 2>/dev/null
		start-stop-daemon -S''')
open(p, "w").write(s)
print("ok")

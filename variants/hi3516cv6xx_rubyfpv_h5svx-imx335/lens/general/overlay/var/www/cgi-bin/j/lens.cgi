#!/bin/sh
# /cgi-bin/j/lens.cgi?cmd=<zoom-in|zoom-out|focus-near|focus-far|stop>[&ms=N]
# Runs /usr/sbin/lens. Only these five words and a number reach the shell.

reply() {	# reply <status line> <json>
	printf 'HTTP/1.1 %s\nContent-type: application/json\nCache-Control: no-store\n\n%s\n' "$1" "$2"
	exit 0
}

cmd=$(printf '%s' "$QUERY_STRING" | tr '&' '\n' | sed -n 's/^cmd=//p' | head -1)
ms=$(printf '%s' "$QUERY_STRING" | tr '&' '\n' | sed -n 's/^ms=//p' | head -1 | tr -cd '0-9' | cut -c1-4)

case "$cmd" in
	zoom-in|zoom-out|focus-near|focus-far|stop) ;;
	*) reply "400 Bad Request" '{"error":"cmd must be zoom-in, zoom-out, focus-near, focus-far or stop"}' ;;
esac

[ -x /usr/sbin/lens ] || reply "503 Service Unavailable" '{"error":"no lens driver in this image"}'

if err=$(/usr/sbin/lens "$cmd" $ms 2>&1); then
	reply "200 OK" "{\"ok\":true,\"cmd\":\"$cmd\"}"
else
	reply "500 Internal Server Error" "{\"error\":\"$(printf '%s' "$err" | tr -d '"\\\n' | cut -c1-120)\"}"
fi

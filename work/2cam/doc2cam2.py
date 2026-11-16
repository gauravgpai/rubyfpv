import re
p = "README.md"; s = open(p).read()


def rep(s, a, b):
    assert s.count(a) == 1, (s.count(a), a[:60])
    return s.replace(a, b)


s = re.sub(r"server CRC32 [0-9a-f]{8}, lenscam [0-9a-f]{8}\)", "server CRC32 7f9b3f77, lenscam 16080c0c)", s)
s = rep(s, '''    majestic settings both encoders must share (codec, size, fps, bitrate,
    GOP, QP delta, NAL size, sensor profile, exposure; read from
    `/etc/majestic.yaml` once a second) and the run-time API requests Ruby
    makes (adaptive bitrate; patch 0012 mirrors them to UDP 5606).
''', '''    majestic settings both encoders must share (codec, size, fps, bitrate,
    GOP, QP delta, NAL size, sensor profile; read from `/etc/majestic.yaml`
    once a second) and the run-time API requests Ruby makes (adaptive
    bitrate; patch 0012 mirrors them to UDP 5606).
  * Picture controls from the ground station (`image.*`, `isp.exposure`) act
    on the camera being shown: camswitch keeps `/tmp/camswitch.remote` while
    the lens camera is shown, Ruby then skips its own majestic (patch 0012)
    and camswitch passes the request to the lens camera; while the server
    camera is shown they are not passed on. Ruby still stores one set of
    values and applies it to its own camera at start-up, so after a restart
    the server camera has the values set last, whichever camera they were
    set for. Flip/mirror, IR filter and noise level are not routed.
  * `S72camswitch` clears majestic's `outgoing.servers` list at boot: this
    majestic adds each new `outgoing.server` to that list instead of
    replacing it, and a left-over 127.0.0.1:5600 would give Ruby the picture
    twice. (The lens camera's `S73camlink` does the same.)
''')
s = rep(s, '''  * `/etc/camlink.conf`: `OWN_IP`, `SERVER_IP`, `ZOOM`, `ZOOM_TRAVEL_MS`.
''', '''  * `/etc/camlink.conf`: `OWN_IP`, `SERVER_IP`, `ZOOM`, `ZOOM_TRAVEL_MS`,
    and `OWN_MODE`/`MODE`: with `OWN_MODE=1` the camera keeps its own
    resolution, frame rate and sensor profile (`MODE=1080p60|1080p90|
    864p120|720p120|972p60`, set by `S73camlink`) and ignores those three
    from the server; codec, bitrate and GOP still follow. The ground
    station's decoder then has to restart on each switch (not yet tried).
  * Address: `S73camlink` sets the U-Boot variable `ipaddr` to `OWN_IP`; the
    stock DHCP client falls back to that variable when no server answers.
    (Stopping the client instead left the camera without any address.)
  * `S96camvideo` is a second copy of `S95majestic`: a camera that ran a
    Ruby image has S95majestic deleted in its settings partition.
''')
s = rep(s, "NOTHING OF THIS\nHAS RUN ON TWO CAMERAS OR WITH A FLIGHT CONTROLLER YET.",
        "The lenscam image runs on camera 2 and was\ntested with the PC as stand-in server (`work/2cam/test_lenscam.py`: stream,\nkeyframe 12-21 ms after a request, settings follow, own mode). THE SERVER\nIMAGE HAS NOT RUN ON A CAMERA; NOTHING HAS RUN ON TWO CAMERAS OR WITH A\nFLIGHT CONTROLLER YET.")
open(p, "w").write(s)
p = "FLASHING.md"; s = open(p).read()
s = re.sub(r"server/` \(CRC32 [0-9a-f]{8};", "server/` (CRC32 7f9b3f77;", s)
s = re.sub(r"lenscam/` \(CRC32 [0-9a-f]{8}, 10560 KB;", "lenscam/` (CRC32 16080c0c, 10560 KB;", s)
assert "7f9b3f77" in s and "16080c0c" in s
open(p, "w").write(s)
print("ok")

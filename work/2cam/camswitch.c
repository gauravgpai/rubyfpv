/* camswitch - two-camera stream switch for the Ruby "server" camera.
 *
 * Ruby reads its video as RTP on 127.0.0.1:5600. In the server image majestic
 * sends to 5602 instead (/etc/ruby_video_out) and this program passes on
 * either that stream or the one a second camera sends over Ethernet to 5604.
 *
 *   127.0.0.1:5602  RTP from the local majestic
 *   0.0.0.0:5604    RTP from the second camera
 *   127.0.0.1:5606  majestic API requests Ruby makes at run time. Encoder
 *                   ones (video0.*) are repeated to the second camera so it
 *                   follows. Picture controls (image.*, isp.exposure) go to
 *                   the camera being shown only: Ruby skips the local
 *                   majestic while /tmp/camswitch.remote exists, and they
 *                   are passed to the second camera only while it is shown.
 *   127.0.0.1:5607  remote-control channels from Ruby's MSP_RC polling
 *                   (16-bit little-endian values, channel 1 first)
 *   -> CLIENT:5610  text datagrams to camlink on the second camera:
 *                   "zoom <0..1000>", "idr", "api <path>", "cfg k=v;k=v;..."
 *
 * A switch is made on a keyframe: the wanted camera is asked for one and the
 * old stream is passed on until its parameter sets arrive (1.5 s at most).
 * RTP sequence numbers are rewritten so Ruby sees one continuous stream.
 * If the second camera's stream stops for 0.5 s the local one is used.
 *
 * Settings: /etc/camswitch.conf. State: /tmp/camswitch.status.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <time.h>
#include <sys/time.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

static char client_ip[64] = "192.168.1.11";
static int select_ch = 7, select_above = 1500, zoom_ch = 8, zoom_min = 1000, zoom_max = 2000;
static int force_cam = -1;              /* FORCE=local|remote, for bench tests without a remote */

static const char *MIRROR_KEYS[] = {    /* majestic.yaml keys the second camera must share */
    "video0.codec", "video0.size", "video0.fps", "video0.bitrate", "video0.gopSize", "video0.qpDelta",
    "video0.rcMode", "video0.sliceUnits", "outgoing.naluSize", "isp.sensorConfig", NULL };

static volatile int run = 1;
static void on_term(int s) { (void)s; run = 0; }

static long long now_ms(void)
{
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
    return (long long)t.tv_sec * 1000 + t.tv_nsec / 1000000;
}

static void load_conf(void)
{
    const char *path = getenv("CAMSWITCH_CONF");     /* for tests on a PC */
    FILE *f = fopen(path ? path : "/etc/camswitch.conf", "r");
    char line[200], k[64], v[128];
    if (!f) return;
    while (fgets(line, sizeof(line), f)) {
        if (line[0] == '#' || sscanf(line, " %63[A-Z_0-9]=%127s", k, v) != 2) continue;
        if (!strcmp(k, "CLIENT_IP")) snprintf(client_ip, sizeof(client_ip), "%.60s", v);
        else if (!strcmp(k, "SELECT_CH")) select_ch = atoi(v);
        else if (!strcmp(k, "SELECT_ABOVE")) select_above = atoi(v);
        else if (!strcmp(k, "ZOOM_CH")) zoom_ch = atoi(v);
        else if (!strcmp(k, "ZOOM_MIN")) zoom_min = atoi(v);
        else if (!strcmp(k, "ZOOM_MAX")) zoom_max = atoi(v);
        else if (!strcmp(k, "FORCE")) force_cam = !strcmp(v, "remote") ? 1 : !strcmp(v, "local") ? 0 : -1;
    }
    fclose(f);
    if (zoom_max == zoom_min) zoom_max = zoom_min + 1;
}

static int udp_bind(unsigned long addr, int port)
{
    int s = socket(AF_INET, SOCK_DGRAM, 0), one = 1, buf = 1024 * 1024;
    struct sockaddr_in a = { .sin_family = AF_INET, .sin_port = htons(port), .sin_addr.s_addr = htonl(addr) };
    if (s < 0) return -1;
    setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
    setsockopt(s, SOL_SOCKET, SO_RCVBUF, &buf, sizeof(buf));
    if (bind(s, (struct sockaddr *)&a, sizeof(a)) < 0) { perror("bind"); close(s); return -1; }
    fcntl(s, F_SETFL, fcntl(s, F_GETFL) | O_NONBLOCK);
    return s;
}

static int out_sock;
static struct sockaddr_in ruby_addr, client_addr;

static void to_client(const char *msg)
{
    sendto(out_sock, msg, strlen(msg), 0, (struct sockaddr *)&client_addr, sizeof(client_addr));
}

/* GET <path> on the local majestic; does not wait for the answer */
static void local_get(const char *path)
{
    struct sockaddr_in a = { .sin_family = AF_INET, .sin_port = htons(80), .sin_addr.s_addr = htonl(INADDR_LOOPBACK) };
    struct timeval tv = { 0, 200000 };
    char req[300];
    int s = socket(AF_INET, SOCK_STREAM, 0);
    if (s < 0) return;
    setsockopt(s, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));
    if (connect(s, (struct sockaddr *)&a, sizeof(a)) == 0) {
        snprintf(req, sizeof(req), "GET %s HTTP/1.0\r\n\r\n", path);
        send(s, req, strlen(req), 0);
    }
    close(s);
}

/* /tmp/camswitch.remote exists while the second camera is the one shown */
static void set_shown(int remote)
{
    if (remote) { int f = open("/tmp/camswitch.remote", O_WRONLY | O_CREAT, 0644); if (f >= 0) close(f); }
    else unlink("/tmp/camswitch.remote");
}

static int is_picture(const char *path)
{
    return strstr(path, "?image.") || strstr(path, "?isp.exposure");
}

/* first RTP packet of a keyframe: H.265 VPS/SPS/PPS or H.264 SPS */
static int is_param_set(const unsigned char *p, int n)
{
    if (n < 14 || (p[0] & 0xC0) != 0x80) return 0;
    int h265 = (p[12] >> 1) & 0x3F;
    return (h265 >= 32 && h265 <= 34) || (p[12] & 0x1F) == 7;
}

/* "section.key" values from /etc/majestic.yaml as one "cfg k=v;..." line */
static void build_cfg(char *out, size_t size)
{
    FILE *f = fopen("/etc/majestic.yaml", "r");
    char line[256], section[64] = "", key[64], val[160], full[130];
    size_t used = snprintf(out, size, "cfg ");
    if (!f) { out[0] = 0; return; }
    while (fgets(line, sizeof(line), f)) {
        if (line[0] != ' ' && line[0] != '\t') {
            if (sscanf(line, "%63[A-Za-z0-9_]:", section) != 1) section[0] = 0;
            continue;
        }
        val[0] = 0;
        if (sscanf(line, " %63[A-Za-z0-9_]: %159[^\r\n]", key, val) < 2) continue;
        char *v = val; size_t l = strlen(v);
        if (l >= 2 && (v[0] == '"' || v[0] == '\'') && v[l - 1] == v[0]) { v[l - 1] = 0; v++; }
        snprintf(full, sizeof(full), "%s.%s", section, key);
        for (int i = 0; MIRROR_KEYS[i]; i++)
            if (!strcmp(full, MIRROR_KEYS[i]) && used + strlen(full) + strlen(v) + 3 < size)
                used += snprintf(out + used, size - used, "%s=%s;", full, v);
    }
    fclose(f);
}

int main(void)
{
    load_conf();
    signal(SIGTERM, on_term); signal(SIGINT, on_term);

    int s_local = udp_bind(INADDR_LOOPBACK, 5602), s_remote = udp_bind(INADDR_ANY, 5604);
    int s_api = udp_bind(INADDR_LOOPBACK, 5606), s_rc = udp_bind(INADDR_LOOPBACK, 5607);
    out_sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (s_local < 0 || s_remote < 0 || s_api < 0 || s_rc < 0 || out_sock < 0) return 1;
    ruby_addr = (struct sockaddr_in){ .sin_family = AF_INET, .sin_port = htons(5600), .sin_addr.s_addr = htonl(INADDR_LOOPBACK) };
    client_addr = (struct sockaddr_in){ .sin_family = AF_INET, .sin_port = htons(5610) };
    if (!inet_aton(client_ip, &client_addr.sin_addr)) { fprintf(stderr, "camswitch: bad CLIENT_IP\n"); return 1; }

    static unsigned char pkt[65536];
    char msg[1500];
    int active = 0, want = 0, rc_want = 0, zoom = -1, last_zoom_sent = -1, have_seq = 0;
    unsigned short seq = 0;
    long long t_remote = 0, t_rc = 0, t_pending = 0, t_idr = 0, t_zoom = 0, t_sec = 0;
    unsigned long n_local = 0, n_remote = 0, n_switch = 0;
    unsigned short ch[32]; int nch = 0;
    int shown = -1;

    while (run) {
        struct pollfd fds[4] = { { s_local, POLLIN, 0 }, { s_remote, POLLIN, 0 }, { s_api, POLLIN, 0 }, { s_rc, POLLIN, 0 } };
        poll(fds, 4, 20);
        long long now = now_ms();

        for (int src = 0; src < 2; src++) {
            if (!(fds[src].revents & POLLIN)) continue;
            int n;
            while ((n = recv(src ? s_remote : s_local, pkt, sizeof(pkt), 0)) > 0) {
                if (src) { t_remote = now; n_remote++; } else n_local++;
                if (want != active && src == want && is_param_set(pkt, n)) { active = want; n_switch++; }
                if (src != active) continue;
                if (n >= 12 && (pkt[0] & 0xC0) == 0x80) {
                    if (!have_seq) { seq = (pkt[2] << 8) | pkt[3]; have_seq = 1; }
                    pkt[2] = seq >> 8; pkt[3] = seq & 0xFF; seq++;
                }
                sendto(out_sock, pkt, n, 0, (struct sockaddr *)&ruby_addr, sizeof(ruby_addr));
            }
        }
        if (fds[2].revents & POLLIN) {
            int n;
            while ((n = recv(s_api, msg + 4, sizeof(msg) - 5, 0)) > 0) {
                msg[4 + n] = 0;
                if (strncmp(msg + 4, "/api/v1/set?", 12)) continue;
                if (is_picture(msg + 4) && !active) continue;      /* Ruby applied it to the local camera */
                memcpy(msg, "api ", 4); to_client(msg);
            }
        }
        if (fds[3].revents & POLLIN) {
            int n;
            while ((n = recv(s_rc, ch, sizeof(ch), 0)) > 0) { nch = n / 2; t_rc = now; }
            if (select_ch >= 1 && select_ch <= nch) rc_want = ch[select_ch - 1] > select_above;
            if (zoom_ch >= 1 && zoom_ch <= nch) {
                long z = ((long)ch[zoom_ch - 1] - zoom_min) * 1000 / (zoom_max - zoom_min);
                zoom = z < 0 ? 0 : z > 1000 ? 1000 : (int)z;
            }
        }

        /* which camera: the switch channel, unless the second camera is silent */
        int remote_alive = t_remote && now - t_remote < 500;
        int w = force_cam >= 0 ? force_cam : rc_want;
        if (w == 1 && !remote_alive) w = 0;
        if (w != want) { want = w; t_pending = now; t_idr = 0; }
        if (want != active) {
            if (now - t_idr >= 300) { t_idr = now; if (want) to_client("idr"); else local_get("/request/idr"); }
            if (now - t_pending > 1500) { active = want; n_switch++; }
        }

        if (active != shown) { shown = active; set_shown(active); }

        /* zoom target: on change (10 per second at most) and once a second */
        if (zoom >= 0 && now - t_rc < 1000 &&
            ((zoom != last_zoom_sent && now - t_zoom >= 100) || now - t_zoom >= 1000)) {
            snprintf(msg, sizeof(msg), "zoom %d", zoom);
            to_client(msg); last_zoom_sent = zoom; t_zoom = now;
        }

        if (now - t_sec >= 1000) {
            t_sec = now;
            build_cfg(msg, sizeof(msg));
            if (msg[0]) to_client(msg);
            FILE *f = fopen("/tmp/camswitch.status.tmp", "w");
            if (f) {
                fprintf(f, "active=%s want=%s remote_alive=%d rc_age_ms=%lld channels=%d select_ch=%d(%d) zoom_ch=%d(%d) zoom=%d "
                        "packets_local=%lu packets_remote=%lu switches=%lu\n",
                        active ? "remote" : "local", want ? "remote" : "local", remote_alive, t_rc ? now - t_rc : -1, nch,
                        select_ch, select_ch >= 1 && select_ch <= nch ? ch[select_ch - 1] : 0,
                        zoom_ch, zoom_ch >= 1 && zoom_ch <= nch ? ch[zoom_ch - 1] : 0, zoom, n_local, n_remote, n_switch);
                fclose(f); rename("/tmp/camswitch.status.tmp", "/tmp/camswitch.status");
            }
        }
    }
    set_shown(0);
    return 0;
}

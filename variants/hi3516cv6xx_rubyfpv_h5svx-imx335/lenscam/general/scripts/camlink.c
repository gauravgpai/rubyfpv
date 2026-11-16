/* camlink - second-camera side of the two-camera setup (lens camera).
 *
 * Listens on UDP 5610 for text datagrams from camswitch on the server camera:
 *
 *   zoom <0..1000>   zoom target from the remote's dial. The lens board takes
 *                    no position command and reports none, so the position
 *                    is kept here from motor run time: full travel is
 *                    ZOOM_TRAVEL_MS, zero is the wide end. At start, and each
 *                    time the target is 0, the zoom is driven into the wide
 *                    end stop to reset the count.
 *   idr              ask majestic for a keyframe
 *   api <path>       repeat a majestic API request Ruby made on the server
 *   cfg k=v;k=v;...  majestic.yaml settings to share with the server; changed
 *                    ones are written with cli and majestic is reloaded.
 *                    With OWN_MODE=1 this camera keeps its own resolution,
 *                    frame rate and sensor profile (S73camlink sets them from
 *                    MODE) and those three are ignored here.
 *
 * Datagrams from any address but SERVER_IP are ignored.
 * Settings: /etc/camlink.conf. State: /tmp/camlink.status.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <termios.h>
#include <time.h>
#include <sys/time.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <netinet/in.h>
#include <arpa/inet.h>

static char server_ip[64] = "192.168.1.10", lens_port[64] = "/dev/ttyAMA0";
static int travel_ms = 8000, lens_addr = 1, zoom_enabled = 1, own_mode = 0;
#define DEADBAND_MS 120     /* smaller corrections are not worth a motor start */
#define OVERRUN_MS  700     /* extra run into the wide end stop */

static volatile int run = 1;
static void on_term(int s) { (void)s; run = 0; }

static long long now_ms(void)
{
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
    return (long long)t.tv_sec * 1000 + t.tv_nsec / 1000000;
}

static void load_conf(void)
{
    FILE *f = fopen("/etc/camlink.conf", "r");
    char line[200], k[64], v[128];
    if (!f) return;
    while (fgets(line, sizeof(line), f)) {
        if (line[0] == '#' || sscanf(line, " %63[A-Z_0-9]=%127s", k, v) != 2) continue;
        if (!strcmp(k, "SERVER_IP")) snprintf(server_ip, sizeof(server_ip), "%.60s", v);
        else if (!strcmp(k, "ZOOM_TRAVEL_MS")) travel_ms = atoi(v);
        else if (!strcmp(k, "ZOOM")) zoom_enabled = atoi(v);
        else if (!strcmp(k, "OWN_MODE")) own_mode = atoi(v);
        else if (!strcmp(k, "LENS_PORT")) snprintf(lens_port, sizeof(lens_port), "%.60s", v);
        else if (!strcmp(k, "LENS_ADDR")) lens_addr = atoi(v);
    }
    fclose(f);
    if (travel_ms < 500) travel_ms = 500;
}

/* ---- lens: Pelco-D zoom tele (0x20) / wide (0x40) / stop ---- */
static int lens_fd = -1;
static void lens_cmd(int cmd2)
{
    unsigned char f[7] = { 0xFF, lens_addr, 0, cmd2, 0, 0, 0 };
    f[6] = (f[1] + f[2] + f[3] + f[4] + f[5]) & 0xFF;
    if (lens_fd >= 0 && write(lens_fd, f, 7) != 7) perror("lens write");
}

/* ---- majestic ---- */
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

static int safe(const char *s, const char *extra)
{
    if (!*s) return 0;
    for (; *s; s++)
        if (!((*s >= 'a' && *s <= 'z') || (*s >= 'A' && *s <= 'Z') || (*s >= '0' && *s <= '9') || strchr(extra, *s))) return 0;
    return 1;
}

static int run_wait(char *const argv[])
{
    int st = -1; pid_t p = fork();
    if (p == 0) { int n = open("/dev/null", O_RDWR); dup2(n, 1); dup2(n, 2); execvp(argv[0], argv); _exit(127); }
    if (p > 0) waitpid(p, &st, 0);
    return st;
}

static void cli_get(const char *key, char *out, size_t size)
{
    char cmd[160]; out[0] = 0;
    snprintf(cmd, sizeof(cmd), "cli -g .%s 2>/dev/null", key);      /* key passed safe() */
    FILE *p = popen(cmd, "r");
    if (!p) return;
    if (fgets(out, size, p)) out[strcspn(out, "\r\n")] = 0;
    pclose(p);
}

#define MAXCFG 16
static char cfg_k[MAXCFG][64], cfg_v[MAXCFG][160];
static int cfg_n;

static void apply_cfg(char *list)
{
    int changed = 0;
    for (char *tok = strtok(list, ";"); tok; tok = strtok(NULL, ";")) {
        char *eq = strchr(tok, '=');
        if (!eq) continue;
        *eq = 0;
        const char *k = tok, *v = eq + 1;
        if (!safe(k, "._") || !safe(v, "._/-:") || strlen(k) > 60 || strlen(v) > 150) continue;
        if (!strncmp(k, "outgoing.server", 15)) continue;       /* ours points at the server */
        if (own_mode && (!strcmp(k, "video0.size") || !strcmp(k, "video0.fps") || !strcmp(k, "isp.sensorConfig"))) continue;
        int i;
        for (i = 0; i < cfg_n && strcmp(cfg_k[i], k); i++) ;
        if (i == cfg_n) {
            if (cfg_n == MAXCFG) continue;
            strcpy(cfg_k[i], k); cli_get(k, cfg_v[i], sizeof(cfg_v[i])); cfg_n++;
        }
        if (!strcmp(cfg_v[i], v)) continue;
        char dotted[66]; snprintf(dotted, sizeof(dotted), ".%s", k);
        char *argv[] = { "cli", "-s", dotted, (char *)v, NULL };
        run_wait(argv);
        strcpy(cfg_v[i], v); changed++;
    }
    if (changed) { char *argv[] = { "killall", "-1", "majestic", NULL }; run_wait(argv); }
}

int main(void)
{
    load_conf();
    signal(SIGTERM, on_term); signal(SIGINT, on_term);

    int s = socket(AF_INET, SOCK_DGRAM, 0), one = 1;
    struct sockaddr_in a = { .sin_family = AF_INET, .sin_port = htons(5610), .sin_addr.s_addr = htonl(INADDR_ANY) };
    struct in_addr server; int have_server = inet_aton(server_ip, &server);
    setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
    if (s < 0 || bind(s, (struct sockaddr *)&a, sizeof(a)) < 0) { perror("camlink: bind"); return 1; }

    if (zoom_enabled) {
        struct termios t;
        lens_fd = open(lens_port, O_WRONLY | O_NOCTTY);
        if (lens_fd < 0) perror(lens_port);
        else if (tcgetattr(lens_fd, &t) == 0) { cfmakeraw(&t); cfsetspeed(&t, B57600); t.c_cflag |= CLOCAL; tcsetattr(lens_fd, TCSANOW, &t); }
    }

    /* zoom state, all in motor milliseconds from the wide end */
    enum { IDLE, IN, OUT, HOMING } st = IDLE;
    long pos = 0, pos_start = 0, target = -1;
    long long t_start = 0, t_home_end = 0, t_sec = 0, t_msg = 0;
    int dirty = 1;                      /* moved since the last end-stop reset */
    unsigned long n_msg = 0;
    char msg[1500];

    if (lens_fd >= 0) { lens_cmd(0x40); st = HOMING; t_home_end = now_ms() + travel_ms + OVERRUN_MS; }

    while (run) {
        struct pollfd fd = { s, POLLIN, 0 };
        poll(&fd, 1, 20);
        long long now = now_ms();

        if (fd.revents & POLLIN) {
            struct sockaddr_in from; socklen_t fl = sizeof(from);
            int n = recvfrom(s, msg, sizeof(msg) - 1, 0, (struct sockaddr *)&from, &fl);
            if (n > 0 && (!have_server || from.sin_addr.s_addr == server.s_addr)) {
                msg[n] = 0; n_msg++; t_msg = now;
                if (!strncmp(msg, "zoom ", 5)) {
                    long z = atol(msg + 5);
                    z = z < 0 ? 0 : z > 1000 ? 1000 : z;
                    target = z * travel_ms / 1000;
                } else if (!strcmp(msg, "idr")) local_get("/request/idr");
                else if (!strncmp(msg, "api ", 4)) { if (!strncmp(msg + 4, "/api/v1/set?", 12) && safe(msg + 4, "._/?=&-")) local_get(msg + 4); }
                else if (!strncmp(msg, "cfg ", 4)) apply_cfg(msg + 4);
            }
        }

        if (lens_fd >= 0) {
            if (st == IN) pos = pos_start + (now - t_start);
            if (st == OUT) pos = pos_start - (now - t_start);
            if (pos > travel_ms) pos = travel_ms;
            if (pos < 0) pos = 0;

            if (st == HOMING) {
                if (now >= t_home_end) { lens_cmd(0); lens_cmd(0); st = IDLE; pos = 0; dirty = 0; }
            } else if (target >= 0) {
                long diff = target - pos;
                if (st == IN && diff <= 0) { lens_cmd(0); lens_cmd(0); st = IDLE; }
                else if (st == OUT && diff >= 0) {
                    if (target == 0 && dirty) { st = HOMING; t_home_end = now + OVERRUN_MS; }   /* keep running into the stop */
                    else { lens_cmd(0); lens_cmd(0); st = IDLE; }
                }
                if (st == IDLE) {
                    if (diff > DEADBAND_MS) { lens_cmd(0x20); st = IN; pos_start = pos; t_start = now; dirty = 1; }
                    else if (diff < -DEADBAND_MS) { lens_cmd(0x40); st = OUT; pos_start = pos; t_start = now; dirty = 1; }
                    else if (target == 0 && dirty && pos <= DEADBAND_MS) { lens_cmd(0x40); st = HOMING; t_home_end = now + pos + OVERRUN_MS; }
                }
            }
        }

        if (now - t_sec >= 1000) {
            t_sec = now;
            FILE *f = fopen("/tmp/camlink.status.tmp", "w");
            if (f) {
                fprintf(f, "zoom_state=%s position_ms=%ld target_ms=%ld travel_ms=%d messages=%lu last_message_age_ms=%lld\n",
                        st == IDLE ? "idle" : st == IN ? "in" : st == OUT ? "out" : "homing", pos, target, travel_ms,
                        n_msg, t_msg ? now - t_msg : -1);
                fclose(f); rename("/tmp/camlink.status.tmp", "/tmp/camlink.status");
            }
        }
    }
    if (lens_fd >= 0 && st != IDLE) { lens_cmd(0); lens_cmd(0); }
    return 0;
}

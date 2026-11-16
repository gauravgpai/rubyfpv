/* lensaf - autofocus feeder for the UART zoom/focus lens board.
 *
 * The lens board focuses by itself, but needs the camera to tell it how sharp
 * the picture is. The stock firmware sends it a 16-byte frame about 30 times
 * a second:
 *
 *   51 01 04 78 01 0d  FVhi FVlo  FVhi FVlo  b10 b11 b12 b13 b14  sum
 *
 * FV is a 16-bit sharpness figure (sent twice), sum is the low byte of the
 * sum of the 15 bytes before it. The meaning of b10..b14 is not known; the
 * stock firmware was seen sending b10 = 0x0b..0x1f and zeros for the rest.
 *
 * This program reads the image processor's focus statistics (read-only, next
 * to majestic) and sends that frame.
 *
 *   lensaf [-p port] [-d divisor] [-b b10] [-r rate] [-v] [-n]
 *     -d  FV = (h1 + v1 summed over all zones) / divisor, default 32
 *     -v  print FV once a second     -n  do not send, only print
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <signal.h>
#include <termios.h>
#include <time.h>
#include "ot_mpi_isp.h"

td_s32 ss_mpi_isp_get_focus_stats(ot_vi_pipe vi_pipe, ot_isp_af_stats *af_stat);

static volatile int run = 1;
static void stop(int s) { (void)s; run = 0; }

int main(int argc, char **argv)
{
    const char *port = "/dev/ttyAMA0";
    unsigned div = 32, b10 = 0x10, rate = 30;
    int verbose = 0, send = 1, o, fd = -1;

    while ((o = getopt(argc, argv, "p:d:b:r:vn")) != -1)
        switch (o) {
        case 'p': port = optarg; break;
        case 'd': div = strtoul(optarg, NULL, 0); break;
        case 'b': b10 = strtoul(optarg, NULL, 0); break;
        case 'r': rate = strtoul(optarg, NULL, 0); break;
        case 'v': verbose = 1; break;
        case 'n': send = 0; break;
        default: fprintf(stderr, "usage: lensaf [-p port] [-d divisor] [-b b10] [-r rate] [-v] [-n]\n"); return 2;
        }
    if (!div) div = 1;
    if (rate < 1 || rate > 60) rate = 30;

    if (send) {
        struct termios t;
        fd = open(port, O_WRONLY | O_NOCTTY);
        if (fd < 0) { perror(port); return 1; }
        if (tcgetattr(fd, &t) == 0) {
            cfmakeraw(&t); cfsetspeed(&t, B57600); t.c_cflag |= CLOCAL;
            tcsetattr(fd, TCSANOW, &t);
        }
    }
    signal(SIGTERM, stop); signal(SIGINT, stop);

    /* padded: the vendor library may have been built from newer headers */
    ot_isp_af_stats *st = calloc(1, sizeof(*st) + 65536);
    if (!st) return 1;
    unsigned n = 0, fails = 0;
    while (run) {
        td_s32 r = ss_mpi_isp_get_focus_stats(0, st);
        if (r != 0) {
            /* no video pipeline (yet): wait, send nothing */
            if (verbose && (fails++ % 5) == 0) printf("no focus statistics (0x%x)\n", (unsigned)r);
            sleep(1);
            continue;
        }
        unsigned long sum = 0;
        for (int row = 0; row < OT_ISP_AF_ZONE_ROW; row++)
            for (int col = 0; col < OT_ISP_AF_ZONE_COLUMN; col++) {
                ot_isp_focus_zone *z = &st->be_af_stat.zone_metrics[row][col];
                sum += z->h1 + z->v1;
            }
        unsigned long fv = sum / div;
        if (fv > 0xFFFF) fv = 0xFFFF;
        unsigned char f[16] = {0x51, 0x01, 0x04, 0x78, 0x01, 0x0d, fv >> 8, fv & 0xFF, fv >> 8, fv & 0xFF,
                               b10 > 255 ? 255 : b10, 0, 0, 0, 0, 0};
        unsigned s = 0;
        for (int i = 0; i < 15; i++) s += f[i];
        f[15] = s & 0xFF;
        if (send && write(fd, f, sizeof(f)) != (ssize_t)sizeof(f) && verbose) perror("write");
        if (verbose && (n % rate) == 0) { printf("fv=%lu\n", fv); fflush(stdout); }
        n++;
        usleep(1000000 / rate);
    }
    return 0;
}

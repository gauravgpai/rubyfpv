/* afprobe - read the image processor's focus statistics from a second
 * process while majestic owns the video pipeline, and print one sharpness
 * figure per reading. Read-only: it changes no ISP setting. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "ot_mpi_isp.h"

td_s32 ss_mpi_isp_get_focus_stats(ot_vi_pipe vi_pipe, ot_isp_af_stats *af_stat);
td_s32 ss_mpi_isp_get_stats_cfg(ot_vi_pipe vi_pipe, ot_isp_stats_cfg *stat_cfg);

int main(int argc, char **argv)
{
    int n = argc > 1 ? atoi(argv[1]) : 20;
    /* padded: the vendor library may have been built from newer headers */
    ot_isp_stats_cfg *cfg = calloc(1, sizeof(*cfg) + 65536);
    ot_isp_af_stats *st = calloc(1, sizeof(*st) + 65536);
    td_s32 r = ss_mpi_isp_get_stats_cfg(0, cfg);
    printf("get_stats_cfg: 0x%x  sizeof cfg=%u stats=%u\n", (unsigned)r, (unsigned)sizeof(*cfg), (unsigned)sizeof(*st));
    if (r == 0) {
        ot_isp_af_cfg *a = &cfg->focus_cfg.config;
        printf("af_en=%d zones=%ux%u peak=%d square=%d pos=%d crop=%d,%d %ux%u en=%d\n", a->af_en, a->zone_col, a->zone_row,
               a->peak_mode, a->square_mode, a->stats_pos, a->crop.x, a->crop.y, a->crop.width, a->crop.height, a->crop.enable);
    }
    for (int i = 0; i < n; i++) {
        memset(st, 0, sizeof(*st));
        r = ss_mpi_isp_get_focus_stats(0, st);
        if (r != 0) { printf("get_focus_stats: 0x%x\n", (unsigned)r); usleep(200000); continue; }
        unsigned long v1 = 0, h1 = 0, v2 = 0, h2 = 0, y = 0; int nz = 0;
        for (int row = 0; row < OT_ISP_AF_ZONE_ROW; row++)
            for (int col = 0; col < OT_ISP_AF_ZONE_COLUMN; col++) {
                ot_isp_focus_zone *z = &st->be_af_stat.zone_metrics[row][col];
                v1 += z->v1; h1 += z->h1; v2 += z->v2; h2 += z->h2; y += z->y; if (z->y) nz++;
            }
        printf("pts=%llu zones=%d v1=%lu h1=%lu v2=%lu h2=%lu y=%lu status=%d\n", (unsigned long long)st->pts, nz,
               v1, h1, v2, h2, y, st->be_af_grid_info.status);
        usleep(200000);
    }
    return 0;
}

/* afstat - can a second process read the ISP focus statistics while majestic
 * runs? The structure layout is not taken from a header (none for this chip
 * in the toolchain), so the call gets a large zeroed buffer with a guard
 * pattern behind it and the result is dumped for inspection. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int ss_mpi_isp_get_focus_stats(int vi_pipe, void *af_stat);

#define BUF (256 * 1024)

int main(int argc, char **argv)
{
	int n = argc > 1 ? atoi(argv[1]) : 3;
	unsigned char *b = malloc(BUF);
	for (int k = 0; k < n; k++) {
		memset(b, 0xA5, BUF);
		int rc = ss_mpi_isp_get_focus_stats(0, b);
		int last = -1, nz = 0;
		for (int i = 0; i < BUF; i++)
			if (b[i] != 0xA5) { last = i; if (b[i]) nz++; }
		printf("rc=0x%x written_up_to=%d nonzero=%d\n", rc, last + 1, nz);
		if (rc == 0 && last > 0) {
			unsigned short *w = (unsigned short *)b;
			int words = (last + 1) / 2;
			printf("first 24 words:");
			for (int i = 0; i < 24 && i < words; i++) printf(" %u", w[i]);
			printf("\nlast 24 words:");
			for (int i = words - 24; i < words; i++) if (i >= 0) printf(" %u", w[i]);
			printf("\n");
			if (argc > 2) { FILE *f = fopen(argv[2], "wb"); fwrite(b, 1, last + 1, f); fclose(f); }
		}
		usleep(300000);
	}
	return 0;
}

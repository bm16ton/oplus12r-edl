/*
* Copyright (c) 1998 Todd C. Miller <Todd.Miller@courtesan.com>
*
* Permission to use, copy, modify, and distribute this software for any
* purpose with or without fee is hereby granted, provided that the above
* copyright notice and this permission notice appear in all copies.
*
* THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
* WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
* MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
* ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
* WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
* ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
* OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
*/


#include "windows_utils.h"

char *optarg;
int optind = 1, opterr, optopt;

int getopt_long(int argc, char * const argv[], const char *optstring, const struct option *longopts, int *longindex) {
    char *pch;

    if (longopts == NULL || longindex != NULL || optind >= argc || strlen(argv[optind]) < 2 || argv[optind][0] != '-')
        return -1;

    if (strlen(argv[optind]) == 2 && isalnum(argv[optind][1])) {
        pch=strchr(optstring, argv[optind][1]);
        if (NULL != pch) {
            optind++;
            if (*(pch+1) == ':')
                optarg = argv[optind++];
            return (int)(*pch);
        }
    }
    else if (strlen(argv[optind]) >= 3 && argv[optind][1] == '-') {
        return -1;
    }
    return -1;
}

/*
int mkdir(const char *path, enum mode_t mode) {
    return _mkdir(path);
}
*/

int access(const char *path, int amode) {
	return 0;
}

void gettimeofday(struct timeval *t, void* tzp) {
	unsigned long system_uptime = GetTickCount();
	t->tv_sec = system_uptime/1000;
	t->tv_usec = (system_uptime%1000)*1000;
	return;
}

int getpagesize(void) {
	static DWORD page_size = 0;
	if (0 == page_size) {
		SYSTEM_INFO system_info;
		GetSystemInfo (&system_info);
		page_size = system_info.dwPageSize;
	}
    return page_size;
}


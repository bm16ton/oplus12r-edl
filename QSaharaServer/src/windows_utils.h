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


#ifndef WINDOWS_UTILS_H
#define WINDOWS_UTILS_H

#include <ctype.h>
#include <string.h>
#include <Windows.h>
#include <direct.h>
//#include <io.h>	// for _access

struct option {
    const char *name;
    int         has_arg;
    int        *flag;
    int         val;
};
extern char *optarg;
extern int optind, opterr, optopt;
int getopt_long(int argc, char * const argv[], const char *optstring, const struct option *longopts, int *longindex);

enum mode_t {
	S_IRWXU,
	S_IRWXG,
	S_IROTH,
	S_IXOTH
};
//int mkdir(const char *path, enum mode_t mode);

void gettimeofday(struct timeval *t, void* tzp);
int getpagesize(void);

#endif

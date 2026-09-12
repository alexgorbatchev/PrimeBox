/*
 * compat_shim.c - glibc 2.13 compatibility shim for DirectFB 1.4 fbdev
 *
 * When cross-compiling with modern toolchains (GCC 13+, glibc 2.38+ headers),
 * several standard POSIX functions (fstat, fcntl, __fdelt_chk) are redirected
 * to newer GLIBC versioned symbols (GLIBC_2.15 - GLIBC_2.38). This shim provides
 * explicit implementations linking against glibc 2.13 primitives / direct syscalls
 * so the resulting module only requires GLIBC_2.4.
 */

#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <sys/syscall.h>
#include <fcntl.h>
#include <stdarg.h>

#ifdef __arm__
/* In ARM glibc 2.13, fstat() was __fxstat(_STAT_VER, fd, buf) */
#ifndef _STAT_VER
#define _STAT_VER 3
#endif

extern int __fxstat(int ver, int fd, struct stat *buf);

int fstat(int fd, struct stat *buf) {
    return __fxstat(_STAT_VER, fd, buf);
}

/* __fdelt_chk is called by FD_SET when FORTIFY_SOURCE is active */
long int __fdelt_chk(long int d) {
    return d / (8 * sizeof(long int));
}

/* Direct syscall forward for fcntl to avoid 64-bit time redirects in modern headers */
int fcntl(int fd, int cmd, ...) {
    va_list ap;
    va_start(ap, cmd);
    void *arg = va_arg(ap, void *);
    va_end(ap);
    return syscall(__NR_fcntl64, fd, cmd, arg);
}
#endif

/*
 * LD_PRELOAD shim: deterministic RNG injection (spec §7.3 point 4).
 *
 * Seeds /dev/urandom reads, getrandom(), random(), srand() from
 * POLYEVAL_SEED env var (16-char hex = 8 bytes).  Same seed → same byte
 * stream across all trials with the same index.
 *
 * Build:
 *   gcc -shared -fPIC -O2 -o libpolyeval_seed.so libpolyeval_seed.c -ldl
 */

#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <unistd.h>

/* ---------- xorshift64 PRNG seeded from env ----------------------------- */
static uint64_t _seed = 0xCAFEF00DDEADC0DEULL;
static int _initialized = 0;

static void _init_seed(void) {
    if (_initialized) return;
    const char *env = getenv("POLYEVAL_SEED");
    if (env && strlen(env) >= 16) {
        uint64_t v = 0;
        for (int i = 0; i < 16; i++) {
            char c = env[i];
            uint64_t nibble = (c >= '0' && c <= '9') ? (c - '0') :
                              (c >= 'a' && c <= 'f') ? (c - 'a' + 10) :
                              (c >= 'A' && c <= 'F') ? (c - 'A' + 10) : 0;
            v = (v << 4) | nibble;
        }
        _seed = v;
    }
    _initialized = 1;
}

static uint64_t _xorshift64(void) {
    _seed ^= _seed << 13;
    _seed ^= _seed >> 7;
    _seed ^= _seed << 17;
    return _seed;
}

static void _fill_random(void *buf, size_t n) {
    _init_seed();
    uint8_t *p = (uint8_t *)buf;
    for (size_t i = 0; i < n; i++) {
        if ((i & 7) == 0) _xorshift64();
        p[i] = (uint8_t)((_seed >> ((i & 7) * 8)) & 0xff);
    }
}

/* ---------- intercept getrandom ----------------------------------------- */
ssize_t getrandom(void *buf, size_t buflen, unsigned int flags) {
    _fill_random(buf, buflen);
    return (ssize_t)buflen;
}

/* ---------- intercept read on /dev/urandom ------------------------------- */
static int (*_real_open)(const char *, int, ...) = NULL;
static ssize_t (*_real_read)(int, void *, size_t) = NULL;

/* Track which fds are /dev/urandom so we can intercept only those reads. */
#define MAX_URANDOM_FDS 32
static int _urandom_fds[MAX_URANDOM_FDS];
static int _urandom_count = 0;

static int _is_urandom_fd(int fd) {
    for (int i = 0; i < _urandom_count; i++)
        if (_urandom_fds[i] == fd) return 1;
    return 0;
}

int open(const char *path, int flags, ...) {
    if (!_real_open)
        _real_open = dlsym(RTLD_NEXT, "open");
    int is_rand = (strcmp(path, "/dev/urandom") == 0 ||
                   strcmp(path, "/dev/random") == 0);
    int fd = _real_open(path, flags);
    if (is_rand && fd >= 0 && _urandom_count < MAX_URANDOM_FDS)
        _urandom_fds[_urandom_count++] = fd;
    return fd;
}

ssize_t read(int fd, void *buf, size_t count) {
    if (!_real_read)
        _real_read = dlsym(RTLD_NEXT, "read");
    if (_is_urandom_fd(fd)) {
        _fill_random(buf, count);
        return (ssize_t)count;
    }
    return _real_read(fd, buf, count);
}

/* ---------- intercept random() / srand() --------------------------------- */
static unsigned int _libc_rand_state = 0;

void srand(unsigned int seed) {
    (void)seed;
    _init_seed();
    _libc_rand_state = (unsigned int)(_seed & 0xffffffff);
}

int rand(void) {
    _libc_rand_state ^= _libc_rand_state << 13;
    _libc_rand_state ^= _libc_rand_state >> 17;
    _libc_rand_state ^= _libc_rand_state << 5;
    return (int)(_libc_rand_state & 0x7fffffff);
}

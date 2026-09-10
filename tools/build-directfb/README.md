# tools/build-directfb

Patched **DirectFB 1.4** `systems/fbdev` module for the Prime GO's
`rockchipdrmfb`.

`rbp` renders through DirectFB. The stock RX3 fbdev driver assumes a 16 bpp,
1280×800, pannable i.MX6 framebuffer. The Prime GO has a fixed 32 bpp,
triple-buffered DRM framebuffer with no panning and no rotation. Without
changes, the modeset is rejected (`EINVAL`), DirectFB corrupts its layer
bookkeeping, and `rbp` crashes (sometimes rebooting the device).

## Files

| File | What |
|---|---|
| `directfb-full.diff` | all PrimeBox modifications against DirectFB 1.4.16 |

There are **no upstream DirectFB source files in this repository**. The diff is
the only third-party-derived artefact; DirectFB is LGPL-2.1 and the diff (and
any build you make from it) remains under the LGPL. You fetch the pristine
DirectFB tree yourself and apply the diff:

```bash
git clone https://github.com/deniskropp/DirectFB.git directfb
cd directfb && git checkout v1.4.16
patch -p1 < /path/to/PrimeBox/tools/build-directfb/directfb-full.diff
```

The diff contains the usual patch context lines from DirectFB plus the
PrimeBox changes, including debug instrumentation (`/tmp/dfbdig*.log` writes)
that you may strip for production.

## What the patch changes

1. **Serialise all fb ioctls** with a mutex. The DRM fb is unsafe under
   concurrent `FBIOPUT_VSCREENINFO`/`FBIOPAN_DISPLAY`.
2. **Force the real fb format** in `dfb_fbdev_set_mode()` and
   `dfb_fbdev_test_mode()`: before `FBIOPUT_VSCREENINFO`, overwrite
   `bits_per_pixel` and the colour bitfields from a live
   `FBIOGET_VSCREENINFO`. The kernel then accepts the modeset and the region
   test passes, so window creation succeeds.
3. **Use the read-back state** after a rejected/clamped modeset for
   `shared->current_var` — never the rejected request (which corrupted the
   internal geometry).
4. **Fall back to `FRONTONLY`** when the fb cannot pan, keeping the real
   `yres_virtual`.
5. **Software rotation + RGB565→RGB32 conversion** in
   `fbdev_rotate_primary()`: copy the logical surface to a system-memory
   scratch buffer, rotate (90/270/180 via `DFB_ROTATE`), convert to 32 bpp and
   present into the physical fb. The system-memory source buffer eliminates
   tearing.
6. **Force `DLBM_TRIPLE`** at layer init so flips occur.

## Build

Requires a DirectFB 1.4.x tree (tested with 1.4.16) and the soft-float EABI5
cross compiler.

```bash
# 0. toolchain
sudo apt-get install gcc-arm-linux-gnueabi libc6-dev-armel-cross

# 1. source
git clone https://github.com/deniskropp/DirectFB.git directfb
cd directfb
git checkout v1.4.16

# 2. apply the patches
patch -p1 < /path/to/PrimeBox/tools/build-directfb/directfb-full.diff

# 3. configure against the RX3 sysroot so the module references only
#    GLIBC_2.4/2.7 symbols (glibc 2.13 target).
#    Point CC at the soft-float compiler and pass the RX3 rootfs as sysroot:
export CC=arm-linux-gnueabi-gcc
export CFLAGS="-march=armv5t -mfloat-abi=soft --sysroot=$RX3"
export LDFLAGS="--sysroot=$RX3 -Wl,-rpath-link,$RX3/lib:$RX3/usr/lib"

./autogen.sh \
    --host=arm-linux-gnueabi \
    --prefix=/usr \
    --disable-x11 --disable-sdl --disable-vnc --disable-avifile \
    --with-gfxdrivers=none \
    --disable-osx --disable-devmem

make -C systems/fbdev libdirectfb_fbdev.la
```

Some builds leave `fstat`/`__fdelt_chk` unversioned; if so, add a tiny
`compat_shim.c` in `systems/fbdev` that forwards them via `syscall()`.

## Soname fix-up

The RX3 tree names its libraries `libdirectfb-1.4.so.0` (not `.so.6`), so
rewrite the NEEDED entries:

```bash
for s in libdirect-1.4.so.6 libfusion-1.4.so.6 libdirectfb-1.4.so.6; do
  patchelf --replace-needed $s ${s%.6}.0 \
      systems/fbdev/.libs/libdirectfb_fbdev.so
done
```

## Deploy

```
/data/rbx3-run/usr/lib/directfb-1.4-6/systems/libdirectfb_fbdev.so
```

and run with `DFB_ROTATE=left`.

## Gotchas

* DirectFB 1.4's dependency tracking is broken. After editing `fbdev.c`,
  always delete the object before rebuilding:

  ```bash
  rm -f systems/fbdev/fbdev.lo systems/fbdev/.libs/fbdev.o
  make -C systems/fbdev libdirectfb_fbdev.la
  ```

* The module must be soft-float and reference only `GLIBC_2.4`/`GLIBC_2.7`.
  Check with `arm-linux-gnueabi-objdump -T`.
* Do not set `layer-size` in `directfbrc` (historically caused a 2×/half-width
  bug); do not rely on `layer-rotate` (unimplemented).
* The diff/sources include **debug instrumentation** (many
  `fopen("/tmp/dfbdig*.log", …)` blocks). It is harmless but noisy; delete
  those blocks for a production build. They are not required for the fix.
* The rotation direction is read from `DFB_ROTATE` (`left`/`right`/`180`) in
  `system_initialize`. PrimeBox uses `DFB_ROTATE=left`.

# PrimeBox

Pioneer DJ XDJ-RX3 rekordbox standalone player (`rbp`) interoperability and hardware translation layer for Denon DJ Prime GO.

## Commands
- Build firmware decryptor: `cd tools/rx3dec && cargo build --release`
- Decrypt firmware: `./tools/rx3dec/target/release/rx3dec <path/to/XDJRX3.UPD> keys/aes256.key extracted/XDJRX3.iso`
- Apply interoperability patches: `python3 tools/patch-rbp/rbp_patch.py extracted/stock-rbp -o extracted/rbp-audio`
- Build ARM32 soft-float translation shims: `make -C scripts/shims RX3="$PWD/extracted/XDJRX3-rootfs"`
- Verify shim GLIBC symbols & soft-float ABI: `make -C scripts/shims RX3="$PWD/extracted/XDJRX3-rootfs" check`
- Build patched DirectFB fbdev module: See instructions in `tools/build-directfb/README.md`

## Setup & Prerequisites
- Cross compiler: `gcc-arm-linux-gnueabi` and `libc6-dev-armel-cross` (Target: ARMv5t / ARM32 soft-float EABI5).
- Build tools: `autoconf`, `automake`, `libtool`, `patchelf`, `p7zip-full`, `docker` (for `fusecram`).
- Firmware update image: Official XDJ-RX3 v1.20 `.UPD` (SHA256: `e81f34ef300c5faa7faf4b4c436eaaf1476d407447b2dbb845c7fbddb4f51389`).

## Conventions
- **GLIBC Target Baseline:** All shims and compiled shared libraries MUST reference only `GLIBC_2.4` / `GLIBC_2.7` symbols to run under the soft-float glibc-2.13 target userland.
- **Modern Host Toolchain Flag Guard:** When compiling with GCC 13+ / glibc 2.38+ headers, always supply `-U_TIME_BITS -U_FILE_OFFSET_BITS -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0 -D__GLIBC_USE_ISOC2X=0 -std=gnu89 -fno-stack-protector` to avoid pulling unversioned or newer versioned symbols.
- **Single-Library IOCTL Ownership:** `fbshim-tsc.so` must be first in `LD_PRELOAD` so it claims `/dev/fb0` ioctls and synthesizes the TSC2007 touch protocol before other shims.
- **Clean Device Stubs:** Device nodes polled by threads (`/dev/subucom_spi*`, `hidg0`) must be FIFOs to prevent CPU busy-spin, while `/dev/gpiodrv` and `/dev/printkdrv0` must be regular files.

## Gotchas
- `symbol open64 is already defined` -> Modern toolchains default to `_FILE_OFFSET_BITS=64`, aliasing `open` to `open64`. Pass `-U_FILE_OFFSET_BITS -U_TIME_BITS` in `CFLAGS`.
- `version GLIBC_2.15/2.28/2.33/2.38 not found` at runtime -> Modern cross headers redirected standard calls (`fstat`, `fcntl`, `__fdelt_chk`, `sscanf`). Include `tools/build-directfb/compat_shim.c` and compile with `-std=gnu89 -D_FORTIFY_SOURCE=0`.
- Touch / Buttons unresponsive on device -> Ensure `/data/fix-dev.sh` was executed before launching `rbp` and verify `engine.service` is stopped.

## Boundaries
- Always: automatically record all new user instructions in the most appropriate `AGENTS.md` file immediately upon receipt (check with user if existing instructions conflict).
- Always (code-based projects only): any time code is changed such that results from running that code are changed, a test file must be changed as well; 90% code coverage is required (`scripts/` folder is excluded from this rule).
- Always: run `make -C scripts/shims check` after modifying any shim C code to verify zero hard-float tags and strict `GLIBC_2.4` linkage.
- Ask first: structural changes to memory patch offsets in `tools/patch-rbp/rbp_patch.py` or DirectFB rotation logic in `tools/build-directfb/directfb-full.diff`.
- Never: publish releases, tags, packages, or production deployments automatically without explicit user authorization.

### Strict Legal & Clean-Room Git History Boundaries
- **NEVER commit or stage proprietary Pioneer / AlphaTheta / Denon binary assets**:
  - No `.UPD`, `.iso`, `.cramfs`, `.img`, or squashfs firmware images.
  - No `rbp`, `rbp-audio`, `stock-rbp`, `edb_streamd`, or any extracted binary executables.
  - No proprietary font files (`NS_FONT_ID_*.bin`, `imagedata.dat`).
- **NEVER commit or stage firmware decryption keys**:
  - `keys/aes256.key` must remain strictly local and gitignored at all times.
- **NEVER commit or stage deployment directories**:
  - The `/deploy/` folder contains generated chroot bundles and patched executables; it is strictly gitignored and must never be tracked in git history.
- **Maintain Clean-Room Interoperability Separation**:
  - Only commit original translation source code (C), build automation scripts, documentation, and byte-offset patch definitions (`rbp_patch.py`).

## References
- Repository Overview: `README.md`
- Step-by-Step Setup: `TUTORIAL.md`
- Subsystem Documentation: `docs/00-overview.md` to `docs/11-troubleshooting.md`
- Legal and Copyright Notice: `NOTICE.md`

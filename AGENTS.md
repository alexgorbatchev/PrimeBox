# PrimeBox

Pioneer DJ XDJ-RX3 rekordbox standalone player (`rbp`) interoperability and hardware translation layer for Denon DJ Prime GO.

## Commands
- Pure Python staging pipeline: `python3 tools/bundle/prepare-rx3.py --firmware <XDJRX3.zip> --gpl <part00.zip> <part01.zip> --output <staging_dir>`
- Configure device launcher & auto-start: `python3 tools/launcher/setup_launcher.py [--root <dir>] [--remote root@<ip>] [--mode retrogo|udev|all] [--install-retrogo]`
- Apply interoperability patches: `python3 tools/patch-rbp/rbp_patch.py extracted/stock-rbp -o extracted/rbp-audio`
- Build ARM32 soft-float translation shims: `make -C scripts/shims RX3="$PWD/extracted/XDJRX3-rootfs"`
- Verify shim GLIBC symbols & soft-float ABI: `make -C scripts/shims RX3="$PWD/extracted/XDJRX3-rootfs" check`
- Verify ELF link dependencies: `python3 tools/build-directfb/verify-rx3-links.py extracted/XDJRX3-rootfs scripts/shims/*.so`
- Verify DirectFB module: `python3 tools/build-directfb/verify-module.py <module.so> extracted/XDJRX3-rootfs`
- Run test suite: `uv run python -m unittest discover -s tests -v`
- Build patched DirectFB fbdev module: See instructions in `tools/build-directfb/README.md`

## Setup & Prerequisites
- Cross compiler: `gcc-arm-linux-gnueabi` and `libc6-dev-armel-cross` (Target: ARMv5t / ARM32 soft-float EABI5).
- Build & Python tools: `autoconf`, `automake`, `libtool`, `patchelf`, `unzip` (Deflate64), `pycryptodome`, `pycdlib`.
- Firmware update image: Official XDJ-RX3 v1.20 `.UPD` (SHA256: `e81f34ef300c5faa7faf4b4c436eaaf1476d407447b2dbb845c7fbddb4f51389`).

## Denon DJ Prime GO Target Platform Architecture

### 1. Hardware Specifications & SoC
- **SoC:** Rockchip RK3288 (Quad-Core ARM Cortex-A17 @ 1.4–1.8 GHz, ARMv7-A with NEON).
- **Float ABI:** Hard-float kernel (`armhf`), but kernel transparently executes ARM32 soft-float (`armel` EABI5) binaries.
- **Memory & Storage:** 2 GB LPDDR3 RAM. Root filesystem is a ~466 MB read-only SquashFS partition; `/data` (ext4) is persistent (~2 GB free); `/tmp` is a tmpfs (wiped on reboot).
- **Display Panel:** 7.0-inch 800×1280 portrait MIPI-DSI LCD, 32-bit ARGB/XRGB DRM framebuffer (`/dev/fb0`, `rockchipdrmfb`), triple-buffered.
- **Touch Controller:** ILI2117 capacitive touch controller providing evdev multi-touch events on `/dev/input/event0`.
- **Audio Subsystem:** Integrated `JP11` 4-channel audio codec on ALSA `hw:1,0` (channels 0/1 = Master output, channels 2/3 = Headphones/Cue).
- **Control Surface:** Dedicated USB MIDI surface (`15e4:800c`, "PRIME GO Control Surface") attached to ALSA sequencer client `16:0` (requires active ALSA sequencer subscription to stream events).
- **Storage Ports:** Exactly 1 rear USB-A 2.0 host port (sysfs `usb3`/`usb4` EHCI/OHCI pair, `/dev/sda`), 1 internal USB-B OTG computer port, 1 SD card slot.

### 2. Software Environment & Runtime Capabilities
- **Operating System:** Engine OS (Buildroot 2023.02.11 base) with Linux 6.1.111-inmusic PREEMPT_RT kernel and `systemd`.
- **Target Userland:** BusyBox `/bin/sh` and POSIX utilities only. **No Python runtime**, no compiler, no package manager on the device.
- **Networking:** Wi-Fi (802.11abgn/ac) and 100/1000M Ethernet. Local root SSH access on port 22 (no outbound internet access on device).
- **Core Engine Daemons:**
  - `engine.service`: Stock Denon DJ UI application (holds exclusive locks on `/dev/fb0` and ALSA `hw:1,0`).
  - `edisksd.service`: Denon disk daemon (resets and unmounts storage devices not registered with Engine OS).
  - `soundswitch.service`: SoundSwitch lighting daemon (used as boot execution vector for `/data/launcher`).
  - `enginestream.service`: Background network streaming audio daemon.

### 3. Hardware Mismatches & Translation Layer
- **Display Orientation & Depth:** XDJ-RX3 renders 1280×800 landscape RGB565; Prime GO has an 800×1280 portrait RGB32 panel. Rebuilt DirectFB `libdirectfb_fbdev.so` rotates output 90° CCW and converts RGB565 to RGB32.
- **Touchscreen Interface:** XDJ-RX3 expects TSC2007 resistive touch on `/dev/tsc2007_2-0048`; Prime GO provides ILI2117 capacitive evdev. `fbshim-tsc.so` translates evdev events into the synthesized TSC2007 protocol.
- **Audio Output:** XDJ-RX3 expects 3 discrete CS4344 DACs; Prime GO uses a single 4-channel `hw:1,0` ALSA PCM. `audioshim.so` multiplexes Master and Headphone streams onto `hw:1,0`.
- **Controls & MIDI:** XDJ-RX3 reads keycodes from Pioneer microcontrollers over SPI; Prime GO sends raw MIDI over ALSA sequencer `16:0`. `knobshim2.so` subscribes to sequencer `16:0` and injects virtual key events into `rbp`'s `KeyManager`.
- **Single USB Port:** Prime GO has only 1 host port. Phantom USB 2 is suppressed in memory (`uiConnectedMedia = 0x2`).

## Conventions
- **GLIBC Target Baseline:** All shims and compiled shared libraries MUST reference only `GLIBC_2.4` / `GLIBC_2.7` symbols to run under the soft-float glibc-2.13 target userland.
- **Modern Host Toolchain Flag Guard:** When compiling with GCC 13+ / glibc 2.38+ headers, always supply `-U_FILE_OFFSET_BITS -D_FILE_OFFSET_BITS=32 -U_TIME_BITS -D_TIME_BITS=32 -fno-stack-protector` and link `legacy-scan.c` to avoid pulling unversioned `__isoc23_*` or 64-bit time symbols.
- **Single-Library IOCTL Ownership:** `fbshim-tsc.so` must be first in `LD_PRELOAD` so it claims `/dev/fb0` ioctls and synthesizes the TSC2007 touch protocol before other shims.
- **Clean Device Stubs:** Device nodes polled by threads (`/dev/subucom_spi*`, `hidg0`) must be FIFOs to prevent CPU busy-spin, while `/dev/gpiodrv` and `/dev/printkdrv0` must be regular files.
- **Embedded Target Runtime Guarantee:** Stock Engine OS contains only `/bin/sh` and busybox utilities (no Python runtime). All device-side scripts must be pure POSIX `/bin/sh`. Host Python tools must run strictly on the workstation and populate the staging directory.

## Gotchas
- `symbol open64 is already defined` -> Modern toolchains default to `_FILE_OFFSET_BITS=64`, aliasing `open` to `open64`. Pass `-U_FILE_OFFSET_BITS -D_FILE_OFFSET_BITS=32 -U_TIME_BITS -D_TIME_BITS=32` in `CFLAGS`.
- `version GLIBC_2.15/2.28/2.33/2.38 not found` or `__isoc23_*` symbols -> Modern cross headers redirect POSIX calls (`sscanf`, `strtol`). Include `scripts/shims/legacy-scan.c` and link `librt-2.13.so`.
- Touch / Buttons unresponsive on device -> Ensure `/data/fix-dev.sh` was executed before launching `rbp` and verify `engine.service` is stopped.

## Boundaries
- Always: automatically record all new user instructions in the most appropriate `AGENTS.md` file immediately upon receipt (check with user if existing instructions conflict).
- Always: clearly document launcher prerequisites (e.g. RetroGo / soundswitch menu mods vs stock units) and outline headless launch options (USB auto-detection, hardware button chords), explicitly noting when designs have not yet been validated on physical hardware.
- Always (code-based projects only): any time code is changed such that results from running that code are changed, a test file must be changed as well; 90% code coverage is required (`scripts/` folder is excluded from this rule).
- Always: STRICT PROHIBITION against string sampling in unit tests. All generated configuration files, scripts, udev rules, templates, and command payloads MUST be asserted with complete, 100% exact full-string or structural equality (never loose `assertIn`, substring, or partial sampling checks for generated files or text).
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

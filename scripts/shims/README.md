# scripts/shims

`LD_PRELOAD` libraries (and two static test helpers) that adapt the Prime GO's
hardware to what the XDJ-RX3 `rbp` binary expects. All are original PrimeBox
code (MIT). None of them contain Pioneer code; they only call into `rbp`'s
exported/singleton entry points and translate hardware.

## Build requirements

* `arm-linux-gnueabi-gcc` (soft-float EABI5)
* the extracted RX3 rootfs as sysroot (`RX3=… make`)

```sh
make RX3=../../extracted/XDJRX3-rootfs
```

The resulting libraries must reference **only** `GLIBC_2.4`/`GLIBC_2.7`. If you
see `GLIBC_2.17` (typically `clock_gettime`) or `GLIBC_2.34` (`dlopen`), you
linked against the host glibc. `make check` catches this.

## `knobshim2.c` → `knobshim.so`

The largest shim. On `rbp` startup it waits for `ui::KeyManager` to exist,
subscribes to ALSA sequencer client `16:0` ("PRIME GO Control Surface"),
decodes notes/CCs/14-bit pairs, and calls `KeyManager::sendKey()`.

Responsibilities:

* full button/knob/fader/jog/pitch map (see [docs/05](../../docs/05-controls.md)),
* encoder two's-complement deltas,
* jog speed/position model, pitch-fader normalisation,
* analogue mixer values as normalised floats,
* startup defaults (mixer routes, Sound Color FX Filter, Beat FX MASTER),
* `usb_auto_thread` (phantom USB2 suppression, caution-id clear),
* USB1 source selection when there is no physical USB1 button.

Env (`KNOB_SCALE`, `JOG_*`, `TEMPO_VERBOSE`, `KNOB_VERBOSE`) is documented in
the controls doc.

## `audioshim.c` → `audioshim.so`

Intercepts the ALSA PCM **and control** APIs and the scheduler-affinity calls.
Presents the RX3's several stereo devices over the single 4-channel `hw:1,0`,
forcing `S24_LE / 44100 / 4ch / 64-frame period`, and interleaves
master→ch0/1, headphones→ch2/3. Uses `.symver` to pin `libdl` to `GLIBC_2.4`
and redirects a broken `mmap(MAP_SHARED, fd=-1)` from the RTC init path to an
anonymous mapping so it cannot crash the watchdog.

## `fbshim-tsc.c` → `fbshim.so`

**One library, three jobs** (it must own `ioctl`, so the fb part cannot be
split from the touch part):

1. **fb ioctl shim** — report a 1280×800 **16 bpp RGB565** logical fb
   (`line_length=2560`) and accept `FBIOPUT_VSCREENINFO`. This makes DirectFB
   create RGB16 surfaces, matching `rbp`'s own rendering.
2. **tsc2007 emulation** — intercept `open("/dev/tsc2007_2-0048")`, serve a pipe
   that a reader thread fills from `/dev/input/event0` with the 6-byte RX3
   protocol, including the rotation transform and debounce burst.
3. **CPU/pacing fixes** — 60 fps `FBIOPAN_DISPLAY` cap + mutex; `poll()` on
   `/dev/gpiodrv` parks instead of spinning; `read()` on `/dev/gpiodrv` returns
   one zero byte.

## `gpioshim.c`, `tscshim.c`

Earlier standalone implementations kept for reference. `gpioshim` emulates the
i.MX6 GPIO; `tscshim` is the pre-`fbshim-tsc` touch shim. New deployments use
`fbshim-tsc`.

## `crashcatch.c`

Logs SIGSEGV `pc`/`lr`/registers to `/tmp/crash.log`. Useful when adding a new
patch. Note: individual register values can be unreliable (ucontext layout);
trust `pc`, `lr` and the fault address.

## `seqinject2.c`

Static ARM tool to inject MIDI events into the shim's sequencer port, so the
mapping can be tested with no physical interaction:

```
seqinject2 note <ch> <note> <on|off>
seqinject2 cc   <ch> <cc> <val>
seqinject2 jog  <deck> <pos14>
seqinject2 pitch <deck> <pos14>
seqinject2 knob <val>
seqinject2 --dest C:P note ...
```

Channels are 0-based (`15` = global).

## `udplog.c`

Static UDP listener for `rbp`'s DebugLog (port 20001) → `/data/rbp-debug.log`.

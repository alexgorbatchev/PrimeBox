# scripts/

Two kinds of code live here:

* **[`device/`](device/)** — shell scripts that run **on the Prime GO**.
* **[`shims/`](shims/)** — our C `LD_PRELOAD` libraries and test tools, cross-
  compiled on the workstation.

## `device/`

| Script | Purpose |
|---|---|
| `fix-dev.sh` | Rebuild the chroot `/dev` binds and device stubs after every reboot; create the USB FIFOs; symlink `/etc/mtab`. **Run this first.** |
| `start-rb.sh` | Clean launcher: stop Engine + edisksd, deploy binaries, start `edb_streamd`, launch `rbp`, start the USB watcher, keep foreground. |
| `restart-knob2.sh` | Deploy + relaunch with verbose logging (development). |
| `usb-watch.sh` | USB hotplug daemon (`start`/`stop`/`status`). |
| `launcher.conf` | Boot-menu entry for the Denon launcher. |
| `debug/` | `setup-env.sh`, `run-test.sh`, `relaunch2.sh`, `usbstate.sh` for strace/gdb sessions. |

Copy them to `/data` on the device (see [TUTORIAL](../TUTORIAL.md)).

## `shims/`

| Source | Output | Role |
|---|---|---|
| `knobshim2.c` | `knobshim.so` | Prime GO MIDI → `rbp` keycodes, USB/library glue, FX defaults |
| `audioshim.c` | `audioshim.so` | JUCE/ALSA → `hw:1,0` 4-channel JP11 codec |
| `fbshim-tsc.c` | `fbshim.so` | fb ioctl shim (16 bpp) + ILI2117 → tsc2007 touch + poll/read/pacing |
| `gpioshim.c` | `gpioshim.so` | GPIO stubs (older, kept for reference) |
| `tscshim.c` | `tscshim.so` | standalone touch shim (older; `fbshim-tsc` supersedes it) |
| `crashcatch.c` | `crashcatch.so` | SIGSEGV logger (debug) |
| `seqinject2.c` | `seqinject2` | inject MIDI events to test the mapping |
| `udplog.c` | `udplog` | capture `rbp` DebugLog UDP to a file (debug) |

Build:

```sh
make RX3=/path/to/extracted/XDJRX3-rootfs
make check          # verify GLIBC_2.4-only + soft-float
```

See [`shims/README.md`](shims/README.md) for details and gotchas.

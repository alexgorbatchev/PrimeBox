# 09 — Runtime & launcher

This document ties the pieces together: what runs on the Prime GO, in what
order, and how to launch it from the device's boot menu.

## 1. The launch sequence

```
systemctl stop engine.service edisksd.service   # release audio, USB, controls
        │
        ▼
sh /data/fix-dev.sh          # bind /dev /proc /sys /tmp; device stubs; FIFOs; mtab
        │
        ▼
deploy binaries into /data/rbx3-run
   rbp-audio  knobshim2.so  audioshim.so  fbshim-tsc.so  libdirectfb_fbdev.so
        │
        ▼
start edb_streamd            # DeviceSQL daemon (EDB_BIN=/usr/bin)
        │
        ▼
start rbp inside the chroot
   LD_PRELOAD = fbshim.so : audioshim.so : knobshim.so
   DFB_ROTATE = left
   /lib/ld-linux.so.3 /root/pdj/rbp -a
        │
        ▼
wait until rbp has /tmp/udev_usb1 open, then start usb-watch.sh
        │
        ▼
keep running while rbp lives; on exit stop the watcher and daemons
```

The `LD_PRELOAD` order matters only in that the **first** library's `ioctl`
wins; `fbshim-tsc.so` deliberately contains both the fb ioctl shim **and** the
touch emulation so one library owns `ioctl`. `audioshim` and `knobshim` follow.

## 2. Device scripts

| Script | Role |
|---|---|
| `scripts/device/start-rb.sh` | full clean launcher (recommended) |
| `scripts/device/restart-knob2.sh` | deploy + relaunch with verbose logs |
| `scripts/device/fix-dev.sh` | bind mounts + device stubs + FIFOs + mtab |
| `scripts/device/usb-watch.sh` | USB hotplug daemon |
| `scripts/device/launcher.conf` | boot-menu entry for the Denon launcher |
| `scripts/device/debug/` | `setup-env.sh`, `run-test.sh`, `relaunch2.sh` for gdb/strace sessions |

All live in `/data` on the device. They must be copied there; `/tmp` is wiped
on reboot.

## 3. Launching without SSH

There are several ways to launch PrimeBox on the Prime GO without relying on an interactive SSH terminal.

### 3.1 Third-Party Touch Boot Launcher (RetroGo / SoundSwitch mod)

Units running the third-party **RetroGo / Denon Homebrew** mod utilize a framebuffer menu launcher binary (`/data/launcher`) driven by `soundswitch.service` on boot. It reads `/data/launcher.conf`.

PrimeBox ships `scripts/device/launcher.conf` with a pre-configured entry, and provides an automated setup tool (`tools/launcher/setup_launcher.py`) that idempotently updates `/data/launcher.conf` without overwriting other homebrew apps:

```bash
# On device or staging root:
python3 tools/launcher/setup_launcher.py --mode retrogo
```

```
# DJ Apps
ENGINE |
REKORDBOX (XDJ-RX3) | /data/start-rb.sh

# RetroGo Launcher
...
```

`start-rb.sh` runs in the foreground for as long as `rbp` lives, so the launcher does not fight `rbp` for `/dev/fb0`. When `rbp` exits, cleanup runs and the menu returns.

> **Note on availability:** `/data/launcher` is not a stock Denon feature and is not built by PrimeBox; it is installed separately as part of the RetroGo package. If your unit is running stock Engine OS without RetroGo, see the alternative options below.

---

### 3.2 Alternative Standalone Launch Approaches (Untested on Hardware)

> ⚠️ **Hardware Validation Notice:** The three approaches below represent viable architectural designs for stock or headless units, but **have not yet been tested or validated on physical Prime GO hardware**.

#### Option A: USB Library Auto-Launch (`export.pdb` detection)
Automatically launch `rbp` whenever a USB stick formatted for Rekordbox is inserted into the rear USB-A port.

* **Mechanism:**
  1. A host udev rule triggers on block partition addition (`ACTION=="add", SUBSYSTEM=="block"`).
  2. A helper script mounts the partition to a temporary path read-only and checks for the existence of `PIONEER/rekordbox/export.pdb`.
  3. If found and `rbp` is not already active, the helper unmounts the temp path and executes `/data/start-rb.sh &`.

* **Example udev rule (`/etc/udev/rules.d/99-rb-autostart.rules`):**
  ```udev
  ACTION=="add", SUBSYSTEM=="block", KERNEL=="sd[a-z][0-9]", RUN+="/data/check-and-launch-rb.sh %k"
  ```

* **Example helper (`/data/check-and-launch-rb.sh`):**
  ```sh
  #!/bin/sh
  DEV="/dev/$1"
  TMPMNT="/tmp/check_usb"
  mkdir -p "$TMPMNT"
  mount -o ro "$DEV" "$TMPMNT" 2>/dev/null || exit 0

  if [ -f "$TMPMNT/PIONEER/rekordbox/export.pdb" ]; then
    umount "$TMPMNT"
    /data/start-rb.sh &
  else
    umount "$TMPMNT"
  fi
  ```

> ⚠️ **Mount Concurrency Caution with `edisksd`:** If running stock Engine OS when the drive is inserted, Denon's `edisksd.service` will detect the block device concurrently with udev and attempt to manage or reset it. Any automated USB launcher script must immediately stop `edisksd.service` and `engine.service` (as done in step 1 of `start-rb.sh`) before attempting to bind-mount the partition into `/data/rbx3-run/media/usb1/sda1`.

#### Option B: Boot-Time Button Hold (ALSA MIDI Sequencer)
Hold a button combo during device power-on to divert boot flow from Engine OS to Rekordbox.

* **Mechanism:**
  1. A systemd unit configured `Before=engine.service` runs early in the boot sequence.
  2. A small helper listens to ALSA sequencer client `16:0` ("PRIME GO Control Surface") for 2–3 seconds.
  3. If a combo like `SHIFT` (Note 8) + `VIEW` (Note 7) is held, the service starts `/data/start-rb.sh` and prevents `engine.service` from starting.
  4. If no buttons are pressed before the timeout expires, the unit continues booting stock Engine OS normally.

#### Option C: Runtime Hardware Button Chord Daemon
Switch from Engine OS to Rekordbox on the fly via a hardware button combo.

* **Mechanism:**
  1. A lightweight daemon runs in the background, maintaining an ALSA sequencer subscription to `16:0` (ALSA sequencer supports multiple concurrent subscribers, allowing it to passively monitor events while Engine OS runs).
  2. When a defined chord (e.g. holding `MEDIA/EJECT` + `BACK` for 3 seconds) is detected, it executes `systemctl stop engine.service && /data/start-rb.sh`.

## 4. Daemons

### `edb_streamd` (DeviceSQL)

Pioneer's embedded database server. Needed for USB library import/analysis and
playlist access.

```sh
export EDB_BIN=/usr/bin
chroot /data/rbx3-run /lib/ld-linux.so.3 /usr/bin/edb_streamd
```

It uses `/tmp/req_LocalDBServer` and `/tmp/guard_LocalDBServer`. Before starting
a fresh `rbp`:

```sh
rm -f /tmp/guard_LocalDBServer /tmp/req_LocalDBServer
# kill any stale rbp still holding the guard lock
```

### `usb-watch.sh`

Started **after** `rbp` has opened `/tmp/udev_usb1`, so the initial mount
notification is not lost. See [06 — USB](06-usb.md).

## 5. Running without systemd (manual)

```sh
ssh root@YOUR_PRIMEGO
sh /data/start-rb.sh
```

To go back to stock Engine:

```sh
systemctl start engine.service
```

`engine.service` is stopped at runtime but **not disabled**, so a normal reboot
returns to Engine OS.

## 6. Files at runtime

| Path (device) | Purpose |
|---|---|
| `/data/rbx3-run/` | soft-float chroot |
| `/data/rbx3-run/root/pdj/rbp` | player binary |
| `/data/rbx3-run/usr/lib/{knobshim,audioshim,fbshim}.so` | shims |
| `/data/rbx3-run/usr/lib/directfb-1.4-6/systems/libdirectfb_fbdev.so` | patched display driver |
| `/data/rbp-p.log` | rbp stdout/stderr |
| `/tmp/knobshim.log`, `/tmp/audioshim.log` | shim logs (chroot `/tmp` = host `/tmp`) |
| `/data/usbwatch.log` | USB watcher log |
| `/data/edb_d.log` | DeviceSQL log |

## 7. Startup troubleshooting

| Symptom | Fix |
|---|---|
| rbp starts then dies immediately | run `fix-dev.sh` (missing `/dev/fb0` in chroot) |
| no buttons after UI appears | `/dev/gpiodrv` is a FIFO (must be a regular file); read/poll shims must be active |
| black screen | `engine.service` still running and owns `fb0`; stop it |
| rbp hangs before UI | stale `guard_LocalDBServer` lock or stale frozen `rbp`; kill and clean |
| USB not seen | watcher started before `rbp` opened the FIFO; restart `usb-watch.sh` |
| device reboots under load | an old display stack panicking the fb path; use the shipped patched DirectFB module and frame pacing |

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

## 3. Denon boot launcher

The Prime GO has a custom launcher (`/data/launcher`, driven by
`soundswitch.service`) that reads `/data/launcher.conf`. Add PrimeBox at the
top:

```
# DJ Apps
REKORDBOX (XDJ-RX3) | /data/start-rb.sh

# RetroGo Launcher
...
BACK TO ENGINE |
```

`start-rb.sh` runs in the foreground for as long as `rbp` lives, so the
launcher does not fight `rbp` for `/dev/fb0`. When `rbp` exits, cleanup runs
and the menu returns.

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

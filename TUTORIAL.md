# PrimeBox tutorial — from zero to rekordbox on a Prime GO

This is the complete, working procedure. Read it once before starting.

**What you need**

* A Denon DJ Prime GO with root SSH access.
* A Linux workstation (x86-64) with ~2 GB free.
* The XDJ-RX3 v1.20 firmware (downloaded by the script below).
* ~15 minutes for the first build, ~2 minutes for each deploy.

**Conventions**

* `WORKSTATION$` — commands on your PC.
* `PRIMEGO#` — commands on the device (over SSH).
* `$REPO` — the path to this repository.

> ⚠️ `rbp` on the wrong display stack has historically locked up the device
> hard enough to panic the kernel. Follow the sequence; it uses the stable
> stack. You can always restore stock Engine OS with
> `systemctl start engine.service`.

---

## Part A — Build the payload on the workstation

### A0. Install build dependencies

```bash
WORKSTATION$ sudo apt-get update
WORKSTATION$ sudo apt-get install -y \
    build-essential git curl unzip p7zip-full \
    gcc-arm-linux-gnueabi libc6-dev-armel-cross \
    patchelf docker.io
# plus Rust (for the decryptor):
WORKSTATION$ curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

### A1. Get the firmware

```bash
WORKSTATION$ cd "$REPO"
WORKSTATION$ ./tools/get-firmware.sh ~/xdjrx3-fw
# -> ~/xdjrx3-fw/XDJ-RX3_v120/XDJ-RX3.UPD  (69,171,216 bytes)
```

### A1b. Supply the firmware key

PrimeBox does **not** ship the decryption key. Obtain `aes256.key` from
AlphaTheta's own GPL source distribution
(<https://www.pioneerdj.com/en/support/open-source-code-distribution/gnu-open-source-license/>)
and place it at `keys/aes256.key`. The path is gitignored. Full instructions:
[`keys/README.md`](keys/README.md).

```bash
WORKSTATION$ ls -l keys/aes256.key     # must exist before the next step
```

### A2. Decrypt the `.UPD` → ISO

The decryption approach used here comes from
[`nsaintot/cdj3k-emu`](https://github.com/nsaintot/cdj3k-emu/tree/main) — many
thanks to that project for showing how Pioneer `.UPD` images are unwrapped.

```bash
WORKSTATION$ cd "$REPO/tools/rx3dec"
WORKSTATION$ cargo build --release
WORKSTATION$ ./target/release/rx3dec \
    ~/xdjrx3-fw/XDJ-RX3_v120/XDJ-RX3.UPD \
    "$REPO/keys/aes256.key" \
    "$REPO/extracted/XDJRX3.iso"
```

Expect `[+] OK: ISO 9660 signature CD001 found at sector 64`.

### A3. Extract the ISO

```bash
WORKSTATION$ cd "$REPO"
WORKSTATION$ mkdir -p extracted/XDJRX3
WORKSTATION$ 7z x extracted/XDJRX3.iso -oextracted/XDJRX3 >/dev/null
WORKSTATION$ cat extracted/XDJRX3/images/release.txt    # 1.20
```

### A4. Extract the `gui` partition (fonts are mandatory)

```bash
WORKSTATION$ mkdir -p extracted/XDJRX3-gui
WORKSTATION$ tar xzf extracted/XDJRX3/images/gui.tar.gz -C extracted/XDJRX3-gui
WORKSTATION$ ls extracted/XDJRX3-gui/pset/fontdata/ | head
```

### A5. Extract the rootfs (runtime + DeviceSQL)

```bash
WORKSTATION$ mkdir -p extracted/XDJRX3-rootfs
WORKSTATION$ docker run --rm --privileged \
  -v "$PWD/extracted/XDJRX3/images/rootfs.cramfs:/in/r.cramfs:ro" \
  -v "$PWD/extracted/XDJRX3-rootfs:/out" \
  --entrypoint bash ubuntu:18.04 -c '
    apt-get update -qq && apt-get install -y -qq fusecram
    mkdir -p /mnt/r && fusecram /in/r.cramfs /mnt/r & sleep 4
    cp -a /mnt/r/. /out/'
```

### A6. Patch `rbp`

```bash
WORKSTATION$ cp extracted/XDJRX3/pdj/rbp extracted/stock-rbp
WORKSTATION$ md5sum extracted/stock-rbp
# 4f2efcfc0c9e3f539289f863acfddcc6  extracted/stock-rbp

WORKSTATION$ python3 tools/patch-rbp/rbp_patch.py \
    extracted/stock-rbp -o extracted/rbp-audio
WORKSTATION$ md5sum extracted/rbp-audio
# 3706c68f7242779d46afa09f35a39acf  extracted/rbp-audio
```

### A7. Build the shims

```bash
WORKSTATION$ make -C scripts/shims RX3="$PWD/extracted/XDJRX3-rootfs"
WORKSTATION$ make -C scripts/shims RX3="$PWD/extracted/XDJRX3-rootfs" check
```

`check` must show only `GLIBC_2.4`/`GLIBC_2.7` and no hard-float tag.
You can also run automated link and module validation:

```bash
WORKSTATION$ python3 tools/build-directfb/verify-rx3-links.py \
    extracted/XDJRX3-rootfs scripts/shims/*.so
```

### A8. Build the patched DirectFB fbdev module

Follow [`tools/build-directfb/README.md`](tools/build-directfb/README.md). You can
verify the resulting module using:

```bash
WORKSTATION$ python3 tools/build-directfb/verify-module.py \
    deploy/libdirectfb_fbdev-rot16.so extracted/XDJRX3-rootfs
```

```
libdirectfb_fbdev.so
```

### A9. Assemble the deployment directory

```bash
WORKSTATION$ mkdir -p deploy

# player
WORKSTATION$ cp extracted/rbp-audio deploy/rbp-audio

# shims
WORKSTATION$ cp scripts/shims/knobshim2.so      deploy/knobshim2.so
WORKSTATION$ cp scripts/shims/audioshim.so      deploy/audioshim.so
WORKSTATION$ cp scripts/shims/fbshim-tsc.so     deploy/fbshim-tsc.so
WORKSTATION$ cp scripts/shims/seqinject2        deploy/seqinject2

# display driver
WORKSTATION$ cp /path/to/DirectFB/systems/fbdev/.libs/libdirectfb_fbdev.so \
                deploy/libdirectfb_fbdev-rot16.so

# device scripts
WORKSTATION$ cp scripts/device/*.sh scripts/device/launcher.conf deploy/
```

---

## Part B — Prepare the Prime GO

### B0. Connect

```bash
WORKSTATION$ ssh root@YOUR_PRIMEGO          # or your device's address
PRIMEGO# uname -a
PRIMEGO# df -h /data                          # ensure >100 MB free
```

If root login is disabled, enable Developer/SSH mode from the Prime GO's
settings first (Denon's "Update & Reset" / engineering menu, depending on
firmware). The reference unit already allows `root` SSH.

### B1. Create the soft-float chroot

Build a tarball on the workstation from the RX3 rootfs and ship it:

```bash
WORKSTATION$ cd extracted
WORKSTATION$ tar czf /tmp/rbx3-run.tar.gz \
    -C XDJRX3-rootfs lib usr/bin usr/lib usr/share usr/local \
    etc/mtab bin 2>/dev/null || true
# add the rest of the RX3 userland the player needs
WORKSTATION$ tar czf /tmp/rbx3-extra.tar.gz \
    -C XDJRX3 lib usr gui
```

```bash
WORKSTATION$ scp /tmp/rbx3-run.tar.gz root@YOUR_PRIMEGO:/data/
WORKSTATION$ scp /tmp/rbx3-extra.tar.gz root@YOUR_PRIMEGO:/data/
PRIMEGO# mkdir -p /data/rbx3-run
PRIMEGO# tar xzf /data/rbx3-run.tar.gz -C /data/rbx3-run
PRIMEGO# tar xzf /data/rbx3-extra.tar.gz -C /data/rbx3-run
PRIMEGO# ln -sf /proc/mounts /data/rbx3-run/etc/mtab
```

The chroot must contain at least:

```
lib/ld-linux.so.3          soft-float loader
lib/libc.so.6 libpthread.so.0 libdl.so.2 librt.so.1 libm.so.6
usr/lib/                   libstdc++, DirectFB 1.4, freetype, libg2d, …
usr/bin/edb_streamd usr/bin/kill_daemon
bin/sh -> busybox
usr/share/alsa/
root/gui/                  fonts (pset/fontdata, system/fontdata, imagedata)
root/pdj/rbp               (replaced in B2)
```

### B2. Ship the payload

```bash
WORKSTATION$ cd "$REPO"
WORKSTATION$ for f in deploy/*; do scp "$f" root@YOUR_PRIMEGO:/data/; done
```

On the device:

```bash
PRIMEGO# cp /data/rbp-audio   /data/rbx3-run/root/pdj/rbp
PRIMEGO# chmod 755 /data/rbx3-run/root/pdj/rbp

PRIMEGO# cp /data/knobshim2.so  /data/rbx3-run/usr/lib/knobshim.so
PRIMEGO# cp /data/audioshim.so  /data/rbx3-run/usr/lib/audioshim.so
PRIMEGO# cp /data/fbshim-tsc.so /data/rbx3-run/usr/lib/fbshim.so
PRIMEGO# chmod 755 /data/rbx3-run/usr/lib/*.so

PRIMEGO# cp /data/libdirectfb_fbdev-rot16.so \
            /data/rbx3-run/usr/lib/directfb-1.4-6/systems/libdirectfb_fbdev.so
```

The launcher copies from `/data` on every start, so this is a one-time setup;
later updates just replace the file in `/data`.

---

## Part C — First run

### C1. Stop Engine OS and set up devices

```bash
PRIMEGO# systemctl stop engine.service edisksd.service
PRIMEGO# sh /data/fix-dev.sh
```

### C2. Launch

```bash
PRIMEGO# sh /data/start-rb.sh
```

The script prints progress and then keeps running while `rbp` lives. The
screen should show the rekordbox UI, correct orientation, full width.

### C3. Verify each subsystem

| Check | Expected |
|---|---|
| **Display** | 1280×800 UI, upright, full-screen, ~60 fps |
| **Touch** | tap the left category sidebar → category switches; drag the track list → it scrolls |
| **Buttons** | VIEW opens the library; FWD opens Source; BACK goes up |
| **USB** | plug a rekordbox stick into the rear USB-A → it appears as `USB1 <label>` |
| **Library** | select it → TRACK / PLAYLIST / ARTIST … populate with real counts |
| **Load** | highlight a track, press LOAD 1 → waveform appears |
| **Play** | press PLAY → audio out of master + headphones, scrolling waveform |
| **Mixer** | faders, trim, EQ, crossfader all affect audio |
| **FX** | Sound Color knob filters; Beat FX ON/OFF + ASSIGN 1/2 change beat |

If the screen is black, Engine is probably still running or `fix-dev.sh` was
not run. See [docs/11-troubleshooting.md](docs/11-troubleshooting.md).

### C4. Logs

```bash
PRIMEGO# tail -f /data/rbp-p.log
PRIMEGO# cat /tmp/knobshim.log          # KNOB_VERBOSE=1 for detail
PRIMEGO# cat /tmp/audioshim.log
PRIMEGO# cat /data/usbwatch.log
```

---

## Part D — Boot menu & Headless Launch

### Option 1: Touchscreen Boot Menu (Units with RetroGo mod)

If your unit has the third-party RetroGo / homebrew touch launcher installed (`/data/launcher`), add `start-rb.sh` to the config (`/data/launcher.conf`):

```
# DJ Apps
REKORDBOX (XDJ-RX3) | /data/start-rb.sh

# RetroGo Launcher
...
BACK TO ENGINE |
```

`start-rb.sh` runs in the foreground for the lifetime of `rbp`, so the launcher
does not redraw over it, and it cleans up the daemons when `rbp` exits.

### Option 2: Headless / Stock Launch (Untested on hardware)

For units without the RetroGo boot menu, several headless launch approaches (such as USB auto-launch on `export.pdb` detection or MIDI button chords) are outlined in [docs/09-runtime-launcher.md](docs/09-runtime-launcher.md#32-alternative-standalone-launch-approaches-untested-on-hardware). *Note: these alternative methods have not yet been validated on physical hardware.*

---

## Part E — Updating & restoring

### Update the player or a shim

```bash
WORKSTATION$ scp deploy/rbp-audio root@YOUR_PRIMEGO:/data/
PRIMEGO# sh /data/start-rb.sh
```

### Restore stock Engine OS

```bash
PRIMEGO# systemctl start engine.service
```

PrimeBox touches nothing in the host rootfs; the chroot and scripts live
entirely under `/data`. A normal reboot returns to Engine OS.

### Uninstall

```bash
PRIMEGO# rm -rf /data/rbx3-run /data/rbp-audio /data/*shim2.so /data/*.so \
              /data/seqinject2 /data/fix-dev.sh /data/start-rb.sh \
              /data/restart-knob2.sh /data/usb-watch.sh
PRIMEGO# systemctl enable engine.service   # if it was ever disabled
```

---

## Known limitations

* `/data` is small; keep the chroot trimmed.
* The device has no internet; fetch anything you need on the workstation.
* Only the rear USB-A port is supported (that is the only host port).
* Beat FX is locked to MASTER by design.
* Firmware versions other than v1.20 will need the patch addresses re-derived.

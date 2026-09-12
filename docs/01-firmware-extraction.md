# 01 — Firmware extraction

Everything starts with the XDJ-RX3 firmware update file. This document explains
the container format, the decryption key, and how to get from the official
`.zip` to the files PrimeBox needs (`rbp`, libs, fonts, `edb_streamd`).

## 1. Get the firmware

Official download (AlphaTheta):

```
https://downloads.support.alphatheta.com/firmwares/all-in-one-dj-systems/XDJ-RX3/XDJ-RX3_v120.zip
```

Use [`tools/get-firmware.sh`](../tools/get-firmware.sh) or download manually.
Unzip to get `XDJ-RX3_v120/XDJ-RX3.UPD` (**69,171,216 bytes**, v1.20).

> PrimeBox is developed against **v1.20**. Other versions may work but the
> patch addresses in `tools/patch-rbp/` are specific to the v1.20 binary
> (md5 `4f2efcfc0c9e3f539289f863acfddcc6`).

## 2. The key

PrimeBox does **not** ship the key. Obtain it from AlphaTheta's own GPL
source distribution and place it at `keys/aes256.key` (gitignored). See
[`keys/README.md`](../keys/README.md) for how to find it.

The RX3 updater uses:

```sh
cat $aeskey | losetup -e aes $NOHASH -p 0 $dev $filename
```

which means the effective AES-256 key is the **first 31 bytes of the first
line** of the key file plus a NUL (32 bytes total). `tools/rx3dec` performs
that derivation itself.

## 3. Container formats

Pioneer `.UPD` files come in (at least) two container flavours:

### 3a. XDJ-RX3 — AES-256-CBC "cryptoloop" (this device)

The XDJ-RX3 v1.20 `.UPD` is **not** LUKS. It is a raw, sector-wise
AES-256-CBC image in the classic Linux `cryptoloop` / `losetup -e aes -p 0`
format:

```
[ AES-256-CBC-encrypted ISO 9660 image, 512-byte aligned ]
[ 16-byte plaintext trailer: "MODELVER\0" + CRC32       ]

Cipher : AES-256-CBC, applied independently to each 512-byte sector
IV     : little-endian u32 sector index + 12 zero bytes
Key    : first 31 bytes of key file line 1 + NUL (32 bytes)
```

The 16-byte trailer identifies the model/version and a CRC32. `cryptsetup
luksDump` rejects the file — that is expected.

The decryption approach here was inspired by
[`nsaintot/cdj3k-emu`](https://github.com/nsaintot/cdj3k-emu/tree/main).

### 3b. CDJ-3000 / other players — LUKS1

Other models (e.g. `CDJ3Kv322.UPD`) are genuine **LUKS1** containers at offset
0 (`LUKS\xba\xbe`, `aes-xts-plain64`, sha256, 512-bit master key). Those need
`cryptsetup` + `losetup` (see the [`cdj3k-emu` `tools/upd-decrypt`
helper](https://github.com/nsaintot/cdj3k-emu/tree/main/tools/upd-decrypt)) or a
pure-Rust LUKS decryptor. The `aes256.key` supplied for the RX3 is **not** the
CDJ-3000 key.

> **Credit:** the [`cdj3k-emu`](https://github.com/nsaintot/cdj3k-emu) project
> (nsaintot) is what showed us how Pioneer `.UPD` images are decrypted in the
> first place — its `tools/upd-decrypt` helper (LUKS keyfile + `losetup`)
> was the reference that led to the XDJ-RX3 cryptoloop analysis above. Many
> thanks to them.

## 4. Decrypt with `rx3dec`

`tools/rx3dec/` is a small Rust program (based on `RustCrypto`) that implements
the XDJ-RX3 cryptoloop scheme.

```bash
cd tools/rx3dec
cargo build --release

# usage: rx3dec <input.UPD> <keyfile> <output.iso>
#        <keyfile> is the user-supplied key from ../keys/
./target/release/rx3dec \
    XDJRX3.UPD ../../keys/aes256.key ../XDJRX3.iso
```

Expected output (the key prefix is truncated here):

```
[+] key = <your key> (31 bytes -> 32)
[+] body: 69171200 bytes (135100 sectors), trailer: [...]
[+] OK: ISO 9660 signature CD001 found at sector 64
[+] wrote ../XDJRX3.iso (69171200 bytes)
```

Sanity check the result:

```bash
file XDJRX3.iso            # ISO 9660 CD-ROM filesystem data 'UsbAuto'
7z l XDJRX3.iso | head     # or: sudo mount -o loop,ro XDJRX3.iso /mnt
```

## 5. Extract the ISO

The ISO is a normal ISO 9660 image with this layout:

```
images/
  uImage              Linux 3.0.101 kernel (i.MX6)
  rootfs.cramfs       base Linux (busybox, ALSA, DirectFB, ...)
  u-boot.bin.nand     bootloader
  gui.tar.gz          display resources (fonts, pset, imagedata)
  pdj.tar.gz          the rekordbox application partition
  settings.tar.gz     settings
  LCD.bin, LCD_RT.bin display bitmaps
  EUP.mot, SUB.mot    front-panel / sub-board MCU firmware
  release.txt         "1.20"
pdj/                  launch scripts (apl_start, decrypt_autoexec.sh)
update, usb_update.sh
```

Mount or extract:

```bash
mkdir -p extracted/XDJRX3
sudo mount -o loop,ro XDJRX3.iso /mnt/rx3
sudo cp -a /mnt/rx3/. extracted/XDJRX3/
sudo umount /mnt/rx3
# or, without root:
7z x XDJRX3.iso -oextracted/XDJRX3
```

### The player binary

The rekordbox application is **`pdj/rbp`** (7,620,543 bytes, ARM32 EABI5
soft-float, not stripped). It is *not* in the rootfs; it lives in the `pdj`
partition (`images/pdj.tar.gz`):

```bash
cd extracted/XDJRX3
tar xzf images/pdj.tar.gz      # -> pdj/rbp, pdj/apl_start, ...
cp pdj/rbp ../stock-rbp
```

### The `gui` partition (fonts are essential)

`rbp` cannot start without its NS bitmap fonts and `imagedata.dat`. They are in
`images/gui.tar.gz`:

```bash
mkdir -p extracted/XDJRX3-gui
tar xzf extracted/XDJRX3/images/gui.tar.gz -C extracted/XDJRX3-gui
ls extracted/XDJRX3-gui/pset/fontdata/   # NS_FONT_ID_*.bin
ls extracted/XDJRX3-gui/system/fontdata/ # *.ttf
```

### The rootfs (runtime + `edb_streamd`)

`rootfs.cramfs` is a cramfs image. Many modern host kernels cannot mount cramfs; you can use
`fusecram` in a container:

```bash
mkdir -p extracted/XDJRX3-rootfs
docker run --rm --privileged \
  -v "$PWD/extracted/XDJRX3/images/rootfs.cramfs:/in/r.cramfs:ro" \
  -v "$PWD/extracted/XDJRX3-rootfs:/out" \
  --entrypoint bash ubuntu:18.04 -c '
    apt-get update -qq && apt-get install -y -qq fusecram
    mkdir -p /mnt/r && fusecram /in/r.cramfs /mnt/r & sleep 4
    cp -a /mnt/r/. /out/'
```

---

## 6. Alternative: Pure Python All-in-One Staging Pipeline

If you prefer not to use Rust, Docker, or root mounts, you can use the pure-Python staging script at [`tools/bundle/prepare-rx3.py`](../tools/bundle/README.md).

### Prerequisites:
```bash
uv pip install pycryptodome pycdlib
```

### Run staging:
```bash
python3 tools/bundle/prepare-rx3.py \
    --firmware /path/to/XDJ-RX3_v120.zip \
    --gpl /path/to/pioneerdj_xdj_rx3.tar.bz2.00.zip /path/to/pioneerdj_xdj_rx3.tar.bz2.01.zip \
    --output extracted/staging
```

This single command extracts the decryption key, decrypts the `.UPD` image, parses the ISO, and decompresses the `cramfs` rootfs directly in userland.

From the rootfs you need, at minimum:

* `lib/` — soft-float **glibc 2.13** runtime (`ld-linux.so.3`, `libc.so.6`,
  `libpthread.so.0`, `libdl.so.2`, `librt.so.1`, `libm.so.6`, …),
* `usr/lib/` — `libstdc++`, DirectFB 1.4, freetype, `libg2d`, GAL stubs, etc.,
* `usr/bin/edb_streamd`, `usr/bin/kill_daemon` — DeviceSQL database daemon,
* `bin/busybox` — used as `/bin/sh` inside the chroot,
* `usr/share/alsa/` — ALSA configuration,
* `usr/local/pdj/aes256.key` — confirmation of the key (optional),
* `lib/libGAL.so` — 59 `gco*` Vivante GPU symbols. The RX3 rootfs may ship a
  stub; otherwise create one (the Prime GO has no Vivante GPU).

## 6. What you should end up with

```
extracted/
├── XDJRX3.iso
├── XDJRX3/            # ISO contents
├── XDJRX3-gui/        # gui.tar.gz contents (fonts!)
├── XDJRX3-rootfs/     # rootfs.cramfs contents
└── stock-rbp          # pdj/rbp, md5 4f2efcfc0c9e3f539289f863acfddcc6
```

Verify the stock binary hash before patching:

```bash
md5sum stock-rbp
# 4f2efcfc0c9e3f539289f863acfddcc6  stock-rbp
```

## 7. Next step

Patch the binary:

```bash
python3 tools/patch-rbp/rbp_patch.py stock-rbp -o rbp-audio
md5sum rbp-audio
# 3706c68f7242779d46afa09f35a39acf  rbp-audio
```

See [10 — Memory map](10-memory-map.md) and
[`tools/patch-rbp/PATCHES.md`](../tools/patch-rbp/PATCHES.md) for what each
patch does.
